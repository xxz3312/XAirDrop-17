/* SPDX-License-Identifier: GPL-2.0-only */
/* Included only at native HDD vendor-command table. */
#include <linux/capability.h>
#include "wlan_hdd_object_manager.h"
#include "mishare_raw_protocol.h"
int mishare_raw_tx_sync(struct wlan_objmgr_vdev *vdev, unsigned int freq,
                        const unsigned char *frame, size_t len,
                        unsigned int *native_status);
static int mishare_raw_vendor_tx(struct wiphy *wiphy, struct wireless_dev *wdev,
                                 const void *data, int data_len)
{
    const unsigned char *request = data;
    struct hdd_adapter *adapter;
    struct osif_vdev_sync *sync;
    struct wlan_objmgr_vdev *vdev;
    struct sk_buff *reply;
    unsigned char response[MISHARE_RAW_HEADER] = {0};
    unsigned int freq, length, status = 0;
    int ret;

    if (!capable(CAP_NET_ADMIN))
        return -EPERM;
    if (!wdev || !wdev->netdev || !data || data_len < (int)MISHARE_RAW_HEADER)
        return -EINVAL;
    freq = mishare_raw_word(request + 4);
    length = mishare_raw_word(request + 8);
    if (mishare_raw_word(request) != MISHARE_RAW_VERSION ||
        mishare_raw_word(request + 12) || length > MISHARE_RAW_MAX ||
        data_len != (int)(MISHARE_RAW_HEADER + length) ||
        !mishare_raw_frame_valid(request + MISHARE_RAW_HEADER, length))
        return -EINVAL;
    ret = osif_vdev_sync_op_start(wdev->netdev, &sync);
    if (ret)
        return ret;
    adapter = WLAN_HDD_GET_PRIV_PTR(wdev->netdev);
    ret = wlan_hdd_validate_context(WLAN_HDD_GET_CTX(adapter));
    if (ret)
        goto stop;
    vdev = hdd_objmgr_get_vdev_by_user(adapter->deflink, WLAN_HDD_ID_OBJ_MGR);
    if (!vdev) {
        ret = -ENODEV;
        goto stop;
    }
    ret = mishare_raw_tx_sync(vdev, freq, request + MISHARE_RAW_HEADER,
                              length, &status);
    hdd_objmgr_put_vdev_by_user(vdev, WLAN_HDD_ID_OBJ_MGR);
    if (ret)
        goto stop;
    reply = cfg80211_vendor_cmd_alloc_reply_skb(wiphy, sizeof(response));
    if (!reply) {
        ret = -ENOMEM;
        goto stop;
    }
    mishare_raw_set_word(response, MISHARE_RAW_VERSION);
    mishare_raw_set_word(response + 4, status);
    mishare_raw_set_word(response + 8, length);
    mishare_raw_set_word(response + 12, 1); /* Actual native completion observed. */
    skb_put_data(reply, response, sizeof(response));
    ret = cfg80211_vendor_cmd_reply(reply);
stop:
    osif_vdev_sync_op_stop(sync);
    return ret;
}
