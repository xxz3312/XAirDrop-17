// SPDX-License-Identifier: GPL-2.0-only
/* Owned host lifetime and explicit NDI session progression. No auto caller. */
#include <linux/errno.h>
#include <linux/device.h>
#include <linux/etherdevice.h>
#include <linux/rtnetlink.h>
#include <linux/slab.h>
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

int mishare_wonder_host_stop_ready_locked(struct hdd_context *hdd)
{
    if (!hdd || !hdd->parent_dev || !hdd->psoc)
        return -EINVAL;
    /* The caller's exclusive parent/driver transition spans BOTH snapshots
     * and the native stop decision. Never nest the two registry locks.
     * Any owner counts, even before VDEV allocation or after a failed delete.
     */
    if (mishare_wonder_host_psoc_busy(hdd->psoc) ||
        mishare_runtime_psoc_busy(hdd->psoc))
        return -EBUSY;
    return 0;
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
    host = kzalloc(sizeof(*host), GFP_KERNEL);
    if (!host)
        return -ENOMEM;
    ret = mishare_host_pin_parents(host, hdd);
    if (ret) {
        kfree(host);
        return ret;
    }
    mishare_host_track(host, hdd);
    ret = osif_vdev_sync_create(hdd->parent_dev, &host->sync);
    if (ret)
        goto free_host;
    ether_addr_copy(address, mac);
    host->adapter = hdd_mishare_host_adapter_open(hdd, address);
    if (!host->adapter) {
        ret = -ENODEV;
        goto destroy_sync;
    }
    osif_vdev_sync_register(host->adapter->dev, host->sync);
    *owner = host;
    return 0;

destroy_sync:
    osif_vdev_sync_destroy(host->sync);
free_host:
    mishare_host_unpin_parents(host);
    mishare_host_untrack(host);
    kfree(host);
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
