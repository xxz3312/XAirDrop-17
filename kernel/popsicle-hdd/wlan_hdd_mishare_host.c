// SPDX-License-Identifier: GPL-2.0-only
/* Host allocation/lifetime only. No module init, firmware, channel or TX/RX. */
#include <linux/errno.h>
#include <linux/etherdevice.h>
#include <linux/rtnetlink.h>
#include <linux/slab.h>
#include "wlan_hdd_main.h"
#include "osif_psoc_sync.h"
#include "osif_vdev_sync.h"
#include "wlan_hdd_mishare_host.h"

struct mishare_wonder_host {
    struct hdd_context *hdd;
    struct hdd_adapter *adapter;
    struct osif_vdev_sync *sync;
};

int mishare_wonder_host_create_locked(struct hdd_context *hdd, const u8 *mac,
                                    struct mishare_wonder_host **owner)
{
    struct mishare_wonder_host *host;
    u8 address[ETH_ALEN];
    int ret;

    if (!owner || !hdd || !hdd->parent_dev || !mac || !is_valid_ether_addr(mac))
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
    host->hdd = hdd;
    *owner = host;
    return 0;

destroy_sync:
    osif_vdev_sync_destroy(host->sync);
free_host:
    kfree(host);
    return ret;
}

int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **owner)
{
    struct mishare_wonder_host *host;
    struct osif_vdev_sync *sync;
    struct hdd_adapter *adapter;

    if (!owner)
        return -EINVAL;
    host = *owner;
    if (!host)
        return 0;
    ASSERT_RTNL();
    osif_psoc_sync_assert_trans_protected(host->hdd->parent_dev);
    adapter = host->adapter;
    /* Never treat a started adapter as a disposable host allocation. */
    if (netif_running(adapter->dev) ||
        test_bit(DEVICE_IFACE_OPENED, &adapter->event_flags) ||
        test_bit(SME_SESSION_OPENED, adapter->deflink->link_flags))
        return -EBUSY;
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
    kfree(host);
    *owner = NULL;
    return 0;
}
