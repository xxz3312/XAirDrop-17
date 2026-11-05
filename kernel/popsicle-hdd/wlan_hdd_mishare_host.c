// SPDX-License-Identifier: GPL-2.0-only
/* Owned host lifetime and explicit NDI session progression. No auto caller. */
#include <linux/errno.h>
#include <linux/device.h>
#include <linux/etherdevice.h>
#include <linux/rtnetlink.h>
#include <linux/slab.h>
#include <linux/module.h>
#include <linux/spinlock.h>
#include <cds_api.h>
#include "wlan_hdd_main.h"
#include "osif_psoc_sync.h"
#include "osif_vdev_sync.h"
#include "wlan_objmgr_psoc_obj.h"
#include "wlan_objmgr_pdev_obj.h"
#include "wlan_hdd_mishare_host.h"
#include "wlan_hdd_mishare_runtime.h"
#include "wlan_hdd_mishare_session.h"

struct mishare_wonder_host {
    struct mishare_wonder_host *next;
    struct wlan_objmgr_psoc *psoc;
    struct wlan_objmgr_pdev *pdev;
    struct device *parent_dev;
    struct hdd_context *hdd;
    struct hdd_adapter *adapter;
    struct osif_vdev_sync *sync;
    struct mishare_runtime_owner *runtime;
    struct mishare_session session;
    bool idle_owned;
};

/* The psoc transition serializes allocation/retirement against idle shutdown.
 * This small registry covers host allocations even before a runtime exists.
 * Never hold its lock across native allocation, adapter close or a callback.
 */
static DEFINE_SPINLOCK(mishare_host_lock);
static struct mishare_wonder_host *mishare_hosts;

/* Object references retain allocations, NOT HDD/component/firmware readiness.
 * The caller must still retain HDD and serialize native teardown throughout
 * every asynchronous poll. Never use these pins to authorize SSR or remove.
 */
static int mishare_host_pin_parents(struct mishare_wonder_host *host,
                                   struct hdd_context *hdd)
{
    struct device *parent = get_device(hdd->parent_dev);

    if (!parent)
        return -ENODEV;
    if (wlan_objmgr_psoc_try_get_ref(hdd->psoc, WLAN_HDD_ID_OBJ_MGR) !=
        QDF_STATUS_SUCCESS)
        goto put_parent;
    if (wlan_objmgr_pdev_try_get_ref(hdd->pdev, WLAN_HDD_ID_OBJ_MGR) !=
        QDF_STATUS_SUCCESS)
        goto put_psoc;
    if (wlan_pdev_get_psoc(hdd->pdev) != hdd->psoc) {
        wlan_objmgr_pdev_release_ref(hdd->pdev, WLAN_HDD_ID_OBJ_MGR);
        wlan_objmgr_psoc_release_ref(hdd->psoc, WLAN_HDD_ID_OBJ_MGR);
        put_device(parent);
        return -EUCLEAN;
    }
    host->parent_dev = parent;
    host->psoc = hdd->psoc;
    host->pdev = hdd->pdev;
    return 0;

put_psoc:
    wlan_objmgr_psoc_release_ref(hdd->psoc, WLAN_HDD_ID_OBJ_MGR);
put_parent:
    put_device(parent);
    return -ESHUTDOWN;
}

static void mishare_host_unpin_parents(struct mishare_wonder_host *host)
{
    wlan_objmgr_pdev_release_ref(host->pdev, WLAN_HDD_ID_OBJ_MGR);
    wlan_objmgr_psoc_release_ref(host->psoc, WLAN_HDD_ID_OBJ_MGR);
    put_device(host->parent_dev);
}

static int mishare_host_parent_identity(struct mishare_wonder_host *host)
{
    /* Assert against the pinned device, never a replacement read from HDD. */
    osif_psoc_sync_assert_trans_protected(host->parent_dev);
    if (host->hdd->parent_dev != host->parent_dev ||
        host->hdd->psoc != host->psoc || host->hdd->pdev != host->pdev)
        return -EUCLEAN;
    return 0;
}

bool mishare_wonder_host_psoc_busy(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_wonder_host *host;
    unsigned long flags;
    bool busy = false;

    if (!psoc)
        return false;
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (host = mishare_hosts; host; host = host->next) {
        if (host->psoc == psoc) {
            busy = true;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return busy;
}

bool mishare_wonder_host_adapter_owned(struct hdd_adapter *adapter)
{
    struct mishare_wonder_host *host;
    unsigned long flags;
    bool owned = false;

    if (!adapter)
        return false;
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (host = mishare_hosts; host; host = host->next) {
        if (host->adapter == adapter) {
            owned = true;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return owned;
}

static bool mishare_host_hdd_mismatch(struct hdd_context *hdd)
{
    struct mishare_wonder_host *host;
    unsigned long flags;
    bool mismatch = false;

    spin_lock_irqsave(&mishare_host_lock, flags);
    for (host = mishare_hosts; host; host = host->next) {
        if (host->hdd == hdd &&
            (host->psoc != hdd->psoc || host->parent_dev != hdd->parent_dev ||
             host->pdev != hdd->pdev)) {
            mismatch = true;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return mismatch;
}

int mishare_wonder_host_stop_ready_locked(struct hdd_context *hdd)
{
    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    if (mishare_host_hdd_mismatch(hdd))
        return -EUCLEAN;
    /* The caller's exclusive parent/driver transition spans BOTH snapshots
     * and the native stop decision. Never nest the two registry locks.
     * Any owner counts, even before VDEV allocation or after a failed delete.
     */
    if (mishare_wonder_host_psoc_busy(hdd->psoc) ||
        mishare_runtime_psoc_busy(hdd->psoc))
        return -EBUSY;
    return 0;
}

int mishare_wonder_host_handoff_idle_locked(struct mishare_wonder_host **owner)
{
    struct mishare_wonder_host *host;
    unsigned long flags;
    int ret;

    if (!owner)
        return -EINVAL;
    host = *owner;
    if (!host)
        return 0;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    if (cds_is_driver_recovering())
        return -ESHUTDOWN;
    ret = wlan_hdd_validate_context(host->hdd);
    if (ret)
        return ret;
    if (netif_running(host->adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &host->adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, host->adapter->deflink->link_flags))
        return -EBUSY;
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (host->idle_owned) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return -EBUSY;
    }
    /* Transfer the sole owner, not the address of the caller's possibly
     * temporary slot. The host registry now retains this closing session.
     */
    host->session.closing = true;
    host->idle_owned = true;
    *owner = NULL;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return 0;
}

/* Exclusive PSOC transition serializes host publication/retirement. Preflight
 * ALL matching hosts before doing anything: never steal a caller's owner or
 * use another HDD/device/PDEV. No native function runs under this list lock.
 */
static int mishare_host_idle_candidate(struct hdd_context *hdd,
                                      struct mishare_wonder_host **candidate)
{
    struct mishare_wonder_host *host;
    unsigned long flags;
    int ret = 0;

    *candidate = NULL;
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (host = mishare_hosts; host; host = host->next) {
        /* A retained HDD cannot silently migrate its old hosts to a new
         * PSOC. Still exclude genuinely foreign HDD/PSOC pairs below.
         */
        if (host->hdd == hdd && hdd->psoc != host->psoc) {
            ret = -EUCLEAN;
            break;
        }
        if (host->psoc != hdd->psoc)
            continue;
        if (host->hdd != hdd || host->parent_dev != hdd->parent_dev ||
            host->pdev != hdd->pdev) {
            ret = -EUCLEAN;
            break;
        }
        if (!host->idle_owned) {
            ret = -EBUSY;
            break;
        }
        if (!*candidate)
            *candidate = host;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return ret;
}

int mishare_wonder_host_idle_prepare_locked(struct hdd_context *hdd)
{
    struct mishare_wonder_host *host;
    int ret;

    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    ret = mishare_host_idle_candidate(hdd, &host);
    if (ret)
        return ret;
    if (!host)
        return mishare_wonder_host_stop_ready_locked(hdd);
    if (cds_is_driver_recovering())
        return -ESHUTDOWN;
    /* Native idle already holds the exclusive PSOC transition. Creation may
     * acquire RTNL first: NEVER wait for RTNL in the reverse order here.
     * Contention defers idle; it cannot justify freeing or stopping anything.
     */
    if (!rtnl_trylock())
        return -EAGAIN;
    do {
        ret = mishare_wonder_host_destroy_locked(&host);
        if (ret)
            break;
        ret = mishare_host_idle_candidate(hdd, &host);
    } while (!ret && host);
    rtnl_unlock();
    if (ret)
        return ret;
    /* Standalone runtime owners may still exist. They are never adopted by
     * this host-only coordinator and continue to block native module stop.
     */
    return mishare_wonder_host_stop_ready_locked(hdd);
}

int mishare_wonder_host_ssr_prepare_locked(struct hdd_context *hdd)
{
    struct mishare_wonder_host *host;
    int ret;

    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    ret = mishare_wonder_host_stop_ready_locked(hdd);
    if (ret != -EBUSY)
        return ret;
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    if (!cds_is_driver_recovering())
        return -ESHUTDOWN;
    ret = mishare_host_idle_candidate(hdd, &host);
    if (ret)
        return ret;
    if (!host)
        return -EBUSY; /* Do not adopt a standalone runtime owner. */
    /* The native post-disable caller already owns the PSOC transition. Never
     * wait for RTNL in the reverse of the host-create lock order.
     */
    if (!rtnl_trylock())
        return -EAGAIN;
    ret = mishare_wonder_host_reclaim_handoff_ssr_locked(hdd);
    rtnl_unlock();
    /* The qualified bridge preserves registry ownership and updated tokens
     * on pending/error results; success includes both registries empty.
     */
    return ret;
}

static bool mishare_ssr_checkpoint_matches(struct mishare_ssr_stop_checkpoint *c,
                                           struct hdd_context *hdd,
                                           bool parents_may_be_closed)
{
    return c->hdd == hdd && c->parent_dev == hdd->parent_dev &&
           c->psoc == hdd->psoc &&
           (c->pdev == hdd->pdev || (parents_may_be_closed && !hdd->pdev));
}

int mishare_ssr_stop_unload_ready_locked(struct mishare_ssr_stop_checkpoint *c,
                                        bool upper_blocked)
{
    unsigned long flags;
    bool busy;

    if (!c)
        return -EINVAL;
    /* Caller retains the exclusive DRIVER transition and drains operations.
     * Do not scope this check to a current HDD/PSOC lookup: it can be missing
     * or replaced while a foreign owner or failed journal is still retained.
     * Never nest host and runtime registry locks.
     */
    spin_lock_irqsave(&mishare_host_lock, flags);
    busy = upper_blocked || c->phase != MISHARE_SSR_STOP_EMPTY ||
           c->first_error || c->paused || c->hdd || c->parent_dev ||
           c->psoc || c->pdev || c->driver_status || mishare_hosts;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    if (busy || mishare_runtime_any_busy())
        return -EBUSY;
    return 0;
}

int mishare_ssr_stop_begin_locked(struct mishare_ssr_stop_checkpoint *c,
                                 struct hdd_context *hdd, bool *tracked)
{
    unsigned long flags;
    int ret;

    if (!c || !tracked)
        return -EINVAL;
    *tracked = false;
    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    /* Check retained state even outside recovery, before any prefix side
     * effect. Host retirement cannot erase this independent journal. */
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (c->phase != MISHARE_SSR_STOP_EMPTY) {
        ret = mishare_ssr_checkpoint_matches(c, hdd, false) ? -EBUSY : -EUCLEAN;
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return ret;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    if (!cds_is_driver_recovering())
        return 0;
    /* Native PLD remove unregisters the PSOC lookup before HDD module stop.
     * Its preflight has already drained operations under the retained native
     * transition. A genuinely empty private lifetime needs no lookup/assert;
     * any host/runtime or migrated HDD still takes the protected path below.
     * This snapshot alone never authorizes parent teardown or owner adoption.
     */
    if (!mishare_host_hdd_mismatch(hdd) &&
        !mishare_wonder_host_psoc_busy(hdd->psoc) &&
        !mishare_runtime_psoc_busy(hdd->psoc))
        return 0;
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    ret = mishare_wonder_host_stop_ready_locked(hdd);
    if (ret != -EBUSY)
        return ret;
    if (!hdd->pdev)
        return -EINVAL;
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (c->phase != MISHARE_SSR_STOP_EMPTY) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return -EBUSY;
    }
    c->hdd = hdd;
    c->parent_dev = hdd->parent_dev;
    c->psoc = hdd->psoc;
    c->pdev = hdd->pdev;
    c->first_error = 0;
    c->driver_status = hdd->driver_status;
    c->paused = false;
    c->phase = MISHARE_SSR_STOP_PREFIX;
    *tracked = true;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return 0;
}

int mishare_ssr_stop_step_locked(struct mishare_ssr_stop_checkpoint *c,
                                struct hdd_context *hdd,
                                enum mishare_ssr_stop_phase phase,
                                int result, bool tracked)
{
    unsigned long flags;
    int ret = 0;

    if (!tracked)
        return result;
    if (!c || !hdd || !c->parent_dev)
        return -EINVAL;
    osif_psoc_sync_assert_trans_protected(c->parent_dev);
    spin_lock_irqsave(&mishare_host_lock, flags);
    /* PDEV may disappear only after entering the native parent-close suffix.
     * Repeating that phase records errors; it never authorizes replay. */
    if (!mishare_ssr_checkpoint_matches(c, hdd,
                                       c->phase == MISHARE_SSR_STOP_PARENTS))
        ret = -EUCLEAN;
    else if (!((c->phase == MISHARE_SSR_STOP_PREFIX &&
                phase == MISHARE_SSR_STOP_POST_DISABLED) ||
               (c->phase == MISHARE_SSR_STOP_POST_DISABLED &&
                phase == MISHARE_SSR_STOP_PARENTS) ||
               (c->phase == MISHARE_SSR_STOP_PARENTS &&
                phase == MISHARE_SSR_STOP_PARENTS)))
        ret = -EPROTO;
    if (!c->first_error)
        c->first_error = ret ? ret : result;
    if (!ret)
        c->phase = phase;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return ret ? ret : result;
}

int mishare_ssr_stop_finish_locked(struct mishare_ssr_stop_checkpoint *c,
                                  struct hdd_context *hdd, int result,
                                  bool modules_closed, bool tracked)
{
    unsigned long flags;
    int ret;

    if (!tracked)
        return result;
    if (!c || !hdd || !c->parent_dev)
        return -EINVAL;
    osif_psoc_sync_assert_trans_protected(c->parent_dev);
    spin_lock_irqsave(&mishare_host_lock, flags);
    ret = mishare_ssr_checkpoint_matches(c, hdd,
                           c->phase == MISHARE_SSR_STOP_PARENTS) ? result : -EUCLEAN;
    if (!ret && (c->phase != MISHARE_SSR_STOP_PARENTS || !modules_closed))
        ret = -EIO;
    if (!c->first_error)
        c->first_error = ret;
    ret = c->first_error;
    c->paused = false;
    if (!ret) {
        /* Only native completion of this invocation may release the slot.
         * In particular, empty ownership registries are not an ACK. */
        c->phase = MISHARE_SSR_STOP_EMPTY;
        c->hdd = NULL;
        c->parent_dev = NULL;
        c->psoc = NULL;
        c->pdev = NULL;
        c->driver_status = 0;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return ret;
}

int mishare_ssr_stop_pause_locked(struct mishare_ssr_stop_checkpoint *c,
                                 struct hdd_context *hdd, int result, bool tracked)
{
    unsigned long flags;

    if (!tracked)
        return result;
    if (!c || !hdd || !c->parent_dev)
        return -EINVAL;
    osif_psoc_sync_assert_trans_protected(c->parent_dev);
    spin_lock_irqsave(&mishare_host_lock, flags);
    if ((result == -EINPROGRESS || result == -EAGAIN) &&
        c->phase == MISHARE_SSR_STOP_POST_DISABLED && !c->first_error &&
        !c->paused && mishare_ssr_checkpoint_matches(c, hdd, false) &&
        c->driver_status == hdd->driver_status && cds_is_driver_recovering()) {
        c->paused = true;
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return result;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    /* A wait elsewhere is not proof that the native prefix can be skipped. */
    return mishare_ssr_stop_finish_locked(c, hdd, result ? result : -EIO,
                                         false, tracked);
}

int mishare_ssr_stop_resume_locked(struct mishare_ssr_stop_checkpoint *c,
                                  struct hdd_context *hdd, bool *tracked)
{
    unsigned long flags;
    int ret = 0;

    if (!c || !tracked)
        return -EINVAL;
    *tracked = false;
    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    /* Assert the retained transition, never one selected by a replacement HDD. */
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (c->phase == MISHARE_SSR_STOP_EMPTY) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return -ENOENT;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    osif_psoc_sync_assert_trans_protected(c->parent_dev);
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (!mishare_ssr_checkpoint_matches(c, hdd, false) ||
        c->driver_status != hdd->driver_status)
        ret = -EUCLEAN;
    else if (!cds_is_driver_recovering())
        ret = -ESHUTDOWN;
    else if (c->phase != MISHARE_SSR_STOP_POST_DISABLED ||
             c->first_error || !c->paused)
        ret = -EBUSY;
    if (!ret) {
        c->paused = false;
        *tracked = true;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return ret;
}

int mishare_ssr_stop_remove_ready_locked(struct mishare_ssr_stop_checkpoint *c,
                                        struct hdd_context *hdd)
{
    unsigned long flags;
    int ret;

    if (!c || !hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (c->phase == MISHARE_SSR_STOP_EMPTY && !c->first_error && !c->paused)
        ret = 0;
    else
        ret = mishare_ssr_checkpoint_matches(c, hdd, false) ? -EBUSY : -EUCLEAN;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return ret;
}

static void mishare_host_track(struct mishare_wonder_host *host,
                                struct hdd_context *hdd)
{
    unsigned long flags;

    host->hdd = hdd;
    spin_lock_irqsave(&mishare_host_lock, flags);
    host->next = mishare_hosts;
    mishare_hosts = host;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
}

static void mishare_host_untrack(struct mishare_wonder_host *host)
{
    struct mishare_wonder_host **link;
    unsigned long flags;

    spin_lock_irqsave(&mishare_host_lock, flags);
    for (link = &mishare_hosts; *link; link = &(*link)->next) {
        if (*link == host) {
            *link = host->next;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
}

int mishare_wonder_host_create_locked(struct hdd_context *hdd, const u8 *mac,
                                    struct mishare_wonder_host **owner)
{
    struct mishare_wonder_host *host;
    struct hdd_adapter *adapter;
    unsigned long flags;
    u8 address[ETH_ALEN];
    int ret;

    if (!owner || !hdd || !hdd->parent_dev || !hdd->psoc || !hdd->pdev ||
        !mac || !is_valid_ether_addr(mac))
        return -EINVAL;
    if (*owner)
        return -EBUSY;
    ASSERT_RTNL();
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    ret = wlan_hdd_validate_context(hdd);
    if (ret)
        return ret;
    if (hdd_get_adapter(hdd, QDF_PASSTHRU_MODE))
        return -EBUSY;
    /* Acquire before publishing any host/native callback. Normal module
     * removal must refuse while this independently retained owner exists.
     * Parent transitions still serialize final put/return against teardown.
     */
    if (!try_module_get(THIS_MODULE))
        return -ESHUTDOWN;
    host = kzalloc(sizeof(*host), GFP_KERNEL);
    if (!host) {
        module_put(THIS_MODULE);
        return -ENOMEM;
    }
    ret = mishare_host_pin_parents(host, hdd);
    if (ret) {
        kfree(host);
        module_put(THIS_MODULE);
        return ret;
    }
    mishare_host_track(host, hdd);
    ret = osif_vdev_sync_create(hdd->parent_dev, &host->sync);
    if (ret)
        goto free_host;
    ether_addr_copy(address, mac);
    adapter = hdd_mishare_host_adapter_open(hdd, address);
    if (!adapter) {
        ret = -ENODEV;
        goto destroy_sync;
    }
    /* Global reset lookups can observe other PSOCs. Publish the adapter under
     * the same registry lock they use, not just this PSOC's transition.
     */
    spin_lock_irqsave(&mishare_host_lock, flags);
    host->adapter = adapter;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    osif_vdev_sync_register(host->adapter->dev, host->sync);
    *owner = host;
    return 0;

destroy_sync:
    osif_vdev_sync_destroy(host->sync);
free_host:
    mishare_host_unpin_parents(host);
    mishare_host_untrack(host);
    kfree(host);
    module_put(THIS_MODULE);
    return ret;
}

int mishare_wonder_host_vdev_create_locked(struct mishare_wonder_host *host)
{
    struct hdd_adapter *adapter;
    int ret;

    if (!host)
        return -EINVAL;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    ret = wlan_hdd_validate_context(host->hdd);
    if (ret)
        return ret;
    if (host->session.closing)
        return -ESHUTDOWN;
    adapter = host->adapter;
    if (netif_running(adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, adapter->deflink->link_flags))
        return -EBUSY;
    return mishare_runtime_create(host->pdev, adapter->mac_addr.bytes,
                                   adapter->deflink, adapter->dev->ieee80211_ptr,
                                   &host->runtime);
}

int mishare_wonder_host_vdev_destroy_locked(struct mishare_wonder_host *host)
{
    int ret;

    if (!host)
        return -EINVAL;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    if (netif_running(host->adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &host->adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, host->adapter->deflink->link_flags))
        return -EBUSY;
    host->session.closing = true;
    return mishare_runtime_destroy(&host->runtime);
}

int mishare_wonder_host_session_step_locked(struct mishare_wonder_host *host,
                                            u32 freq, u8 nss_2g, u8 nss_5g)
{
    int ret;

    if (!host)
        return -EINVAL;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    if (host->session.closing)
        return -ESHUTDOWN;
    ret = wlan_hdd_validate_context(host->hdd);
    if (ret)
        return ret;
    if (netif_running(host->adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &host->adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, host->adapter->deflink->link_flags))
        return -EBUSY;
    return mishare_session_step(&host->session, host->runtime,
                                 freq, nss_2g, nss_5g);
}

int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **owner)
{
    struct mishare_wonder_host *host;
    struct osif_vdev_sync *sync;
    struct hdd_adapter *adapter;
    int ret;

    if (!owner)
        return -EINVAL;
    host = *owner;
    if (!host)
        return 0;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    adapter = host->adapter;
    /* Never treat a started adapter as a disposable host allocation. */
    if (netif_running(adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, adapter->deflink->link_flags))
        return -EBUSY;
    host->session.closing = true;
    ret = mishare_runtime_destroy(&host->runtime);
    if (ret)
        return ret;
    sync = osif_vdev_sync_unregister(adapter->dev);
    if (WARN_ON(sync != host->sync)) {
        /* Restore the registry we observed; retain the owner for diagnosis. */
        if (sync)
            osif_vdev_sync_register(adapter->dev, sync);
        return -EIO;
    }
    osif_vdev_sync_wait_for_ops(sync);
    /* Closing reclaims adapter/netdev: do not dereference either afterwards. */
    hdd_close_adapter(host->hdd, adapter, true);
    osif_vdev_sync_destroy(sync);
    mishare_host_unpin_parents(host);
    mishare_host_untrack(host);
    kfree(host);
    *owner = NULL;
    module_put(THIS_MODULE);
    return 0;
}

int mishare_wonder_host_reclaim_ssr_locked(struct mishare_wonder_host **owner)
{
    struct mishare_runtime_reclaim_item item = {0};
    struct mishare_wonder_host *host;
    struct hdd_adapter *adapter;
    int ret;

    if (!owner)
        return -EINVAL;
    host = *owner;
    if (!host)
        return 0;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    if (!cds_is_driver_recovering())
        return -ESHUTDOWN;
    adapter = host->adapter;
    if (netif_running(adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, adapter->deflink->link_flags))
        return -EBUSY;
    host->session.closing = true;
    /* Transfer the authoritative token only for this serialized call. Native
     * completions own runtime tokens, never a pointer to this host slot.
     * Restore the result on EVERY return, including partial/error progress.
     */
    item.owner = host->runtime;
    host->runtime = NULL;
    ret = mishare_runtime_reclaim_batch(host->psoc,
                                       item.owner ? &item : NULL,
                                       item.owner ? 1 : 0);
    host->runtime = item.owner;
    if (ret)
        return ret;
    if (host->runtime)
        return -EUCLEAN;
    /* Batch success includes exact-psoc registry emptiness and real final-free.
     * Ordinary host close now has no runtime/firmware cleanup to submit.
     */
    return mishare_wonder_host_destroy_locked(owner);
}

int mishare_wonder_host_reclaim_handoff_ssr_locked(struct hdd_context *hdd)
{
    struct mishare_wonder_host *host;
    int ret;

    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    ASSERT_RTNL();
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    if (!cds_is_driver_recovering())
        return -ESHUTDOWN;
    ret = mishare_host_idle_candidate(hdd, &host);
    if (ret)
        return ret;
    while (host) {
        /* The registry, not a discarded caller slot, owns the host here.
         * The existing bridge restores updated runtime tokens on EVERY
         * result and admits only qualified, exact-registry SSR retirement.
         */
        ret = mishare_wonder_host_reclaim_ssr_locked(&host);
        if (ret)
            return ret;
        ret = mishare_host_idle_candidate(hdd, &host);
        if (ret)
            return ret;
    }
    /* No host is not proof of no runtime. Empty-batch preflight rejects an
     * omitted standalone owner; it never takes over another owner's token.
     */
    ret = mishare_runtime_reclaim_batch(hdd->psoc, NULL, 0);
    if (ret)
        return ret;
    return mishare_wonder_host_stop_ready_locked(hdd);
}
