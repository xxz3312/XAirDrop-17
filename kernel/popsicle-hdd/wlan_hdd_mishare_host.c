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
#include "wlan_reg_ucfg_api.h"
#include "wlan_reg_services_api.h"
#include "wlan_hdd_mishare_host.h"
#include "wlan_hdd_mishare_runtime.h"
#include "wlan_hdd_mishare_session.h"
#include "wlan_hdd_mishare_prestart.h"
#include "wlan_hdd_mishare_bridge.h"
#include "wlan_hdd_mishare_bridge_scope.h"
#include "wlan_hdd_mishare_init.h"
#include "wlan_hdd_mishare_request_bridge.h"
#include "wlan_hdd_mishare_rate.h"

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
    struct mishare_prestart prestart;
    bool idle_owned;
    u64 retirement_serial;
};

/* The psoc transition serializes allocation/retirement against idle shutdown.
 * This small registry covers host allocations even before a runtime exists.
 * Never hold its lock across native allocation, adapter close or a callback.
 */
static DEFINE_SPINLOCK(mishare_host_lock);
static struct mishare_wonder_host *mishare_hosts;
static u64 mishare_retirement_serial;

struct mishare_managed_instance {
    struct mishare_managed_instance *next;
    struct device *dev;
    struct mishare_module_lease module_lease;
    struct mishare_bridge bridge;
    bool busy;
    bool request_prepared;
    struct mishare_init_request request;
    u8 request_nss_2g, request_nss_5g;
};
static struct mishare_managed_instance *mishare_instances;

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

int mishare_wonder_host_handoff_receipt_locked(struct mishare_wonder_host **owner,
                                               struct mishare_host_retirement *receipt)
{
    struct mishare_wonder_host *host;
    unsigned long flags;
    u64 serial;
    int ret;

    if (!owner || !*owner || !receipt)
        return -EINVAL;
    if (receipt->serial || receipt->module_lease.held)
        return -EBUSY;
    host = *owner;
    ASSERT_RTNL();
    ret = mishare_host_parent_identity(host);
    if (ret)
        return ret;
    if (host->retirement_serial)
        return -EBUSY;
    ret = mishare_module_lease_get(&receipt->module_lease);
    if (ret)
        return ret;
    spin_lock_irqsave(&mishare_host_lock, flags);
    if (mishare_retirement_serial == ~(u64)0) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        mishare_module_lease_put(&receipt->module_lease);
        return -EOVERFLOW;
    }
    /* Reserve before dropping the global lock. Failed handoffs burn a serial;
     * never reuse it or wrap, including concurrent handoffs on other PSOCs.
     */
    serial = ++mishare_retirement_serial;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    ret = mishare_wonder_host_handoff_idle_locked(owner);
    if (ret) {
        mishare_module_lease_put(&receipt->module_lease);
        return ret;
    }
    /* Exclusive PSOC transition + RTNL still exclude native retirement here.
     * Publish the receipt only after the sole owner was transferred.
     */
    spin_lock_irqsave(&mishare_host_lock, flags);
    host->retirement_serial = serial;
    receipt->serial = serial;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return 0;
}

int mishare_wonder_host_retirement_poll(struct mishare_host_retirement *receipt)
{
    struct mishare_wonder_host *host;
    unsigned long flags;

    if (!receipt)
        return -EINVAL;
    if (!receipt->serial)
        return receipt->module_lease.held ? -EUCLEAN : 0;
    if (!receipt->module_lease.held)
        return -EUCLEAN;
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (host = mishare_hosts; host; host = host->next) {
        if (host->retirement_serial == receipt->serial) {
            spin_unlock_irqrestore(&mishare_host_lock, flags);
            return -EINPROGRESS;
        }
    }
    receipt->serial = 0;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    mishare_module_lease_put(&receipt->module_lease);
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
           c->psoc || c->pdev || c->driver_status || c->module_lease.held ||
           mishare_hosts;
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
    if (c->phase != MISHARE_SSR_STOP_EMPTY || c->module_lease.held) {
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
    if (c->phase != MISHARE_SSR_STOP_EMPTY || c->module_lease.held) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return -EBUSY;
    }
    ret = mishare_module_lease_get(&c->module_lease);
    if (ret) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return ret;
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
    struct mishare_module_lease completed_lease = {0};

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
    if (!ret && !c->module_lease.held)
        ret = -EUCLEAN;
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
        /* Move the completed receipt out before unlocking. The final put
         * must not run under the registry lock or touch a reused slot.
         */
        c->module_lease.held = false;
        completed_lease.held = true;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    mishare_module_lease_put(&completed_lease);
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
    if (c->phase == MISHARE_SSR_STOP_EMPTY && !c->first_error && !c->paused &&
        !c->module_lease.held)
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

static void mishare_host_free_tracked(struct mishare_wonder_host *host)
{
    struct mishare_wonder_host **link;
    unsigned long flags;

    spin_lock_irqsave(&mishare_host_lock, flags);
    for (link = &mishare_hosts; *link; link = &(*link)->next) {
        if (*link == host) {
            *link = host->next;
            /* Receipt polling takes this same lock. Absence must become
             * visible only after the final host metadata allocation is freed.
             * kfree does not sleep; native teardown has already finished.
             */
            kfree(host);
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
    mishare_host_free_tracked(host);
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
    if (host->prestart.selected)
        return -EBUSY; /* Configured preparation cannot use the raw START shortcut. */
    return mishare_session_step(&host->session, host->runtime,
                                 freq, nss_2g, nss_5g);
}

int mishare_wonder_host_retry_step_locked(struct mishare_wonder_host *host,
                                           u8 data_limit, u8 mgmt_limit)
{
    struct mishare_runtime_status state;
    const struct mishare_runtime_retry_status *r = &state.retry;
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
    if (!host->prestart.selected || !host->prestart.posted ||
        host->session.stage != MISHARE_SESSION_PLAN)
        return -EBUSY;
    if (host->session.error)
        return host->session.error;
    ret = mishare_runtime_snapshot(host->runtime, &state);
    if (ret)
        return ret;
    if (state.quiesced || state.draining || state.freed)
        return -ESHUTDOWN;
    if (state.blocked || state.ndi.blocked || state.work_error ||
        state.ndi.completion_error || r->integrity_error)
        return mishare_session_fail(&host->session, -EUCLEAN);
    if (r->requested && (r->data_limit != data_limit || r->mgmt_limit != mgmt_limit))
        return -EBUSY;
    if (!r->requested) {
        if (state.work_pending || state.work_users)
            return -EINPROGRESS;
        ret = mishare_runtime_retry_configure(host->runtime, data_limit, mgmt_limit);
        if (ret != -EINPROGRESS)
            return mishare_session_fail(&host->session, ret ? ret : -EUCLEAN);
        return -EINPROGRESS; /* Separate submit-return and completion polls. */
    }
    if (!r->posted || !r->completed)
        return -EINPROGRESS;
    if (r->result)
        return mishare_session_fail(&host->session, r->result);
    if (!r->accepted || !r->receipt.attempted || !r->receipt.complete)
        return mishare_session_fail(&host->session, -EUCLEAN);
    if (state.work_pending || state.work_users)
        return -EINPROGRESS;
    return 0; /* Submission evidence only; no START or firmware ACK. */
}

int mishare_wonder_host_prestart_step_locked(struct mishare_wonder_host *host,
                                            u32 freq, u8 nss_2g, u8 nss_5g,
                                              const struct wondertap_fixed_tx_rate_params *params)
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
    return mishare_prestart_step(&host->prestart, &host->session, host->runtime,
                                  freq, nss_2g, nss_5g, params);
}

int mishare_wonder_host_bssid_bind_locked(struct mishare_wonder_host *host,
                                            const u8 *bssid)
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
    return mishare_runtime_bssid_bind(host->runtime, bssid);
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
    mishare_host_free_tracked(host);
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

int mishare_wonder_host_retire_receipt_locked(struct hdd_context *hdd,
                                              struct mishare_host_retirement *receipt)
{
    struct mishare_wonder_host *host;
    unsigned long flags;

    if (!hdd || !hdd->parent_dev || !receipt || !receipt->serial ||
        !receipt->module_lease.held)
        return -EINVAL;
    ASSERT_RTNL();
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    if (cds_is_driver_recovering())
        return -ESHUTDOWN;
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (host = mishare_hosts; host; host = host->next)
        if (host->retirement_serial == receipt->serial)
            break;
    if (host && (host->hdd != hdd || !host->idle_owned ||
        host->parent_dev != hdd->parent_dev || host->psoc != hdd->psoc ||
        host->pdev != hdd->pdev)) {
        spin_unlock_irqrestore(&mishare_host_lock, flags);
        return -EUCLEAN;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    /* The caller's exact parent transition excludes native retirement of this
     * host after the lookup. Other PSOCs cannot adopt its serial/HDD pair.
     */
    return host ? mishare_wonder_host_destroy_locked(&host) : 0;
}

int mishare_wonder_managed_create(struct device *dev, void **handle)
{
    struct mishare_managed_instance *instance;
    unsigned long flags;
    int ret;

    if (!dev || !handle)
        return -EINVAL;
    if (*handle)
        return -EBUSY;
    instance = kzalloc(sizeof(*instance), GFP_KERNEL);
    if (!instance)
        return -ENOMEM;
    ret = mishare_module_lease_get(&instance->module_lease);
    if (ret)
        goto free_instance;
    instance->dev = get_device(dev);
    if (!instance->dev) {
        ret = -ENODEV;
        mishare_module_lease_put(&instance->module_lease);
        goto free_instance;
    }
    spin_lock_irqsave(&mishare_host_lock, flags);
    instance->next = mishare_instances;
    mishare_instances = instance;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    *handle = instance;
    return 0;
free_instance:
    kfree(instance);
    return ret;
}

/* Authenticate the opaque pointer without dereferencing it first. No native
 * function is called under the registry lock. A busy owner remains registered
 * and cannot be freed by another callback, even if the outer caller is wrong.
 */
static int mishare_instance_claim(void *handle, struct mishare_managed_instance **out)
{
    struct mishare_managed_instance *instance;
    unsigned long flags;
    int ret = -ENOENT;

    *out = NULL;
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (instance = mishare_instances; instance; instance = instance->next) {
        if (instance != handle)
            continue;
        ret = instance->busy ? -EINPROGRESS : 0;
        if (!ret) {
            instance->busy = true;
            *out = instance;
        }
        break;
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    return ret;
}

static void mishare_instance_release(struct mishare_managed_instance *instance)
{
    unsigned long flags;

    spin_lock_irqsave(&mishare_host_lock, flags);
    instance->busy = false;
    spin_unlock_irqrestore(&mishare_host_lock, flags);
}

/* Read current native policy inside ONE scope. This is deliberately not a
 * country setter: a global country transaction needs restoration/parent
 * lifetime coordination before it can be exposed to a managed caller.
 */
static int mishare_init_regulatory_check(struct hdd_context *hdd,
                                        const struct mishare_init_request *request,
                                        u8 nss_2g, u8 nss_5g)
{
    const struct wondertap_init_params *p = &request->params;
    u8 country[3] = {0};
    u8 nss;
    int ret;

    ret = qdf_status_to_os_return(ucfg_reg_get_current_country(hdd->psoc, country));
    if (ret)
        return ret;
    /* Alpha2 only: the native third byte may contain an environment suffix.
     * A requested 00 is a literal world domain, never a wildcard.
     */
    if (memcmp(country, p->country_code, 2))
        return -EOPNOTSUPP;
    if (wlan_reg_is_24ghz_ch_freq(p->channel.freq))
        nss = nss_2g;
    else if (wlan_reg_is_5ghz_ch_freq(p->channel.freq))
        nss = nss_5g;
    else
        return -EOPNOTSUPP; /* Owned channel path has no 6 GHz contract. */
    if (p->tx_rate.nss > nss)
        return -EOPNOTSUPP;
    /* No DFS/CAC or passive-channel transmit coordination is installed.
     * Missing CONFIG_REG_CLIENT returns INVALID and must fail closed too.
     */
    if (wlan_reg_get_bonded_channel_state_for_pwrmode(hdd->pdev, p->channel.freq,
            CH_WIDTH_20MHZ, 0, REG_CURRENT_PWR_MODE) != CHANNEL_STATE_ENABLE ||
        wlan_reg_is_passive_for_freq(hdd->pdev, p->channel.freq))
        return -EOPNOTSUPP;
    return 0;
}

int mishare_wonder_request_preflight_locked(struct hdd_context *hdd,
                                            const struct mishare_init_request *request,
                                            u8 nss_2g, u8 nss_5g)
{
    struct mishare_init_request canonical;
    int ret;

    if (!hdd || !hdd->parent_dev || !hdd->psoc || !hdd->pdev || !request ||
        !nss_2g || nss_2g > 2 || !nss_5g || nss_5g > 2)
        return -EINVAL;
    ret = mishare_init_parse(&request->params, &canonical);
    if (ret)
        return ret;
    if (canonical.params.channel.bandwidth != WONDERTAP_RATE_BW_20 ||
        canonical.params.rate_adaptation_enable)
        return -EOPNOTSUPP;
    ret = mishare_rate_check(&canonical.params.tx_rate);
    if (ret)
        return ret;
    ASSERT_RTNL();
    osif_psoc_sync_assert_trans_protected(hdd->parent_dev);
    ret = wlan_hdd_validate_context(hdd);
    if (!ret && cds_is_driver_recovering())
        ret = -ESHUTDOWN;
    if (!ret && hdd_get_conparam() != QDF_GLOBAL_MISSION_MODE)
        ret = -EOPNOTSUPP;
    if (!ret)
        ret = mishare_init_regulatory_check(hdd, &canonical, nss_2g, nss_5g);
    return ret;
}

int mishare_wonder_managed_prepare(void *handle, const struct wondertap_init_params *params,
                                   u8 nss_2g, u8 nss_5g)
{
    struct mishare_init_request request;
    struct mishare_managed_instance *instance;
    struct mishare_bridge_scope scope = {0};
    int ret = mishare_init_parse(params, &request);

    if (ret)
        return ret;
    if (!nss_2g || nss_2g > 2 || !nss_5g || nss_5g > 2)
        return -EINVAL;
    /* Current owned channel controller encodes HT20 only. Do not silently
     * narrow a wider request or confuse valid public syntax with support.
     */
    if (request.params.channel.bandwidth != WONDERTAP_RATE_BW_20 ||
        request.params.rate_adaptation_enable)
        return -EOPNOTSUPP;
    ret = mishare_rate_check(&request.params.tx_rate);
    if (ret)
        return ret;
    ret = mishare_instance_claim(handle, &instance);
    if (ret)
        return ret;
    if (instance->bridge.closing) {
        ret = -ESHUTDOWN;
        goto release;
    }
    if (instance->bridge.attempted || (instance->request_prepared &&
        (!mishare_init_equal(&instance->request, &request) ||
         instance->request_nss_2g != nss_2g || instance->request_nss_5g != nss_5g))) {
        ret = -EBUSY;
        goto release;
    }
    ret = mishare_bridge_scope_begin(&scope, instance->dev);
    if (ret)
        goto release;
    ret = wlan_hdd_validate_context(scope.hdd);
    if (!ret && cds_is_driver_recovering())
        ret = -ESHUTDOWN;
    if (!ret && hdd_get_conparam() != QDF_GLOBAL_MISSION_MODE)
        ret = -EOPNOTSUPP;
    if (!ret)
        ret = mishare_init_regulatory_check(scope.hdd, &request, nss_2g, nss_5g);
    if (!ret) {
        instance->request = request;
        instance->request_nss_2g = nss_2g;
        instance->request_nss_5g = nss_5g;
        instance->request_prepared = true;
    }
    mishare_bridge_scope_end(&scope);
release:
    mishare_instance_release(instance);
    return ret;
}

int mishare_wonder_managed_step(void *handle, const u8 *mac, u32 freq,
                                u8 nss_2g, u8 nss_5g)
{
    struct mishare_managed_instance *instance;
    int ret = mishare_instance_claim(handle, &instance);

    if (ret)
        return ret;
    if (instance->bridge.closing)
        ret = -ESHUTDOWN;
    else if (instance->request_prepared)
        ret = -EOPNOTSUPP; /* Full request application/lease is not installed. */
    else
        ret = mishare_bridge_step(&instance->bridge, instance->dev, mac, freq, nss_2g, nss_5g);
    mishare_instance_release(instance);
    return ret;
}

int mishare_wonder_managed_retire(void **handle)
{
    struct mishare_managed_instance *instance;
    int ret;

    if (!handle)
        return -EINVAL;
    if (!*handle)
        return 0;
    ret = mishare_instance_claim(*handle, &instance);
    if (ret)
        return ret;
    instance->bridge.closing = true;
    ret = instance->bridge.handed_off ?
          mishare_bridge_poll_retired(&instance->bridge) : 0;
    mishare_instance_release(instance);
    /* Metadata/device release belongs to the process-context entry, never a
     * callback whose outer RTNL/provider locks are unknown here.
     */
    return ret ? ret : -EINPROGRESS;
}

int mishare_wonder_managed_retire_process(void **handle)
{
    struct mishare_managed_instance *instance, **link;
    struct mishare_bridge_scope scope = {0};
    struct mishare_bridge *bridge;
    unsigned long flags;
    int ret;

    if (!handle)
        return -EINVAL;
    if (!*handle)
        return 0;
    ret = mishare_instance_claim(*handle, &instance);
    if (ret)
        return ret;
    bridge = &instance->bridge;
    bridge->closing = true;
    if (bridge->retire_broken) {
        ret = -EUCLEAN;
        goto retain;
    }
    if (bridge->handed_off) {
        ret = mishare_bridge_poll_retired(bridge);
        if (!ret)
            goto complete;
        if (ret != -EINPROGRESS)
            goto retain;
    } else if (!bridge->host) {
        /* Metadata-only factory, or a failed allocation with no native owner. */
        bridge->retired = true;
        goto complete;
    }
    ret = mishare_bridge_scope_begin(&scope, instance->dev);
    if (ret) {
        /* No native submission took place: admission contention is a wait. */
        if (ret == -EAGAIN || ret == -EBUSY)
            ret = -EINPROGRESS;
        goto retain;
    }
    if (!bridge->handed_off)
        ret = mishare_bridge_handoff_idle_locked(bridge, scope.hdd);
    else
        ret = -EINPROGRESS;
    if (ret == -EINPROGRESS && bridge->handed_off)
        ret = mishare_wonder_host_retire_receipt_locked(scope.hdd, &bridge->retirement);
    mishare_bridge_scope_end(&scope);
    if (!ret)
        ret = mishare_bridge_poll_retired(bridge);
    if (ret)
        goto retain;
complete:
    if (!bridge->retired || bridge->host || bridge->retirement.serial ||
        bridge->retirement.module_lease.held) {
        ret = -EUCLEAN;
        goto retain;
    }
    spin_lock_irqsave(&mishare_host_lock, flags);
    for (link = &mishare_instances; *link; link = &(*link)->next) {
        if (*link == instance) {
            *link = instance->next;
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_host_lock, flags);
    put_device(instance->dev);
    mishare_module_lease_put(&instance->module_lease);
    kfree(instance);
    *handle = NULL;
    return 0;
retain:
    mishare_instance_release(instance);
    return ret;
}
