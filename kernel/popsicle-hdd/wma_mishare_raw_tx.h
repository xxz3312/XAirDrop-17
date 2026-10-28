/* SPDX-License-Identifier: GPL-2.0-only */
/* Included by native wma_data.c after wma_update_tx_send_params(). */
#ifndef MISHARE_RAW_TEST
#include <linux/completion.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/errno.h>
#include <linux/refcount.h>
#include <linux/slab.h>
#include "mishare_raw_protocol.h"
#endif
int mishare_raw_tx_sync(struct wlan_objmgr_vdev *vdev, unsigned int freq,
                        const unsigned char *frame, size_t len,
                        unsigned int *native_status);
static bool mishare_raw_tx;
module_param(mishare_raw_tx, bool, 0444);
MODULE_PARM_DESC(mishare_raw_tx, "Experimental native on-channel WMI RAW DATA vendor TX");
struct mishare_raw_pending {
    struct completion done;
    refcount_t refs;
    unsigned int status;
};
static void mishare_raw_put(struct mishare_raw_pending *p)
{
    if (refcount_dec_and_test(&p->refs))
        kfree(p);
}
static QDF_STATUS mishare_raw_complete(void *context, qdf_nbuf_t buf,
                                      uint32_t status, void *params)
{
    struct mishare_raw_pending *pending = context;
    (void)params;
    cds_packet_free(buf);
    WRITE_ONCE(pending->status, status);
    complete(&pending->done);
    mishare_raw_put(pending);
    return QDF_STATUS_SUCCESS;
}
/* Native mgmt_txrx owns its descriptor, peer reference and completion after a
 * successful submit. Waiter/callback hold separate context refs; timeout does
 * not release the native packet or invent completion. No retries/peer create. */
int mishare_raw_tx_sync(struct wlan_objmgr_vdev *vdev, unsigned int freq,
                        const unsigned char *frame, size_t len,
                        unsigned int *native_status)
{
    struct mishare_raw_pending *pending;
    struct wlan_objmgr_peer *peer;
    struct wmi_mgmt_params params = {0};
    tp_wma_handle wma = cds_get_context(QDF_MODULE_ID_WMA);
    qdf_nbuf_t packet;
    unsigned char *data;
    QDF_STATUS status;
    unsigned int id;
    int ret;

    if (!mishare_raw_tx)
        return -EOPNOTSUPP;
    if (!vdev || !native_status || !mishare_raw_frame_valid(frame, len))
        return -EINVAL;
    if (!wma || wma_validate_handle(wma))
        return -ENODEV;
    id = wlan_vdev_get_id(vdev);
    if (id >= wma->max_bssid || wma->interfaces[id].vdev != vdev ||
        wlan_vdev_mlme_get_opmode(vdev) != QDF_STA_MODE ||
        wlan_vdev_mlme_is_mlo_vdev(vdev) ||
        wlan_vdev_is_up_active_state(vdev) != QDF_STATUS_SUCCESS ||
        wma->interfaces[id].ch_freq != freq || freq < 2400 || freq > 5900 ||
        memcmp(frame + 10, wlan_vdev_mlme_get_macaddr(vdev), 6))
        return -EINVAL;
    if (!wma->psoc || !wma->pdev)
        return -ENODEV;
    peer = wlan_objmgr_get_peer(wma->psoc,
                wlan_objmgr_pdev_get_pdev_id(wma->pdev),
                (unsigned char *)frame + 4, WLAN_MGMT_NB_ID);
    if (!peer)
        peer = wlan_objmgr_get_peer(wma->psoc,
                wlan_objmgr_pdev_get_pdev_id(wma->pdev),
                wlan_vdev_mlme_get_macaddr(vdev), WLAN_MGMT_NB_ID);
    if (!peer)
        return -ENOTCONN;
    if (wlan_peer_get_vdev(peer) != vdev) {
        wlan_objmgr_peer_release_ref(peer, WLAN_MGMT_NB_ID);
        return -EXDEV;
    }
    pending = kzalloc(sizeof(*pending), GFP_KERNEL);
    if (!pending) {
        wlan_objmgr_peer_release_ref(peer, WLAN_MGMT_NB_ID);
        return -ENOMEM;
    }
    init_completion(&pending->done);
    refcount_set(&pending->refs, 2);
    status = cds_packet_alloc((uint16_t)len, (void **)&data, (void **)&packet);
    if (QDF_IS_STATUS_ERROR(status)) {
        wlan_objmgr_peer_release_ref(peer, WLAN_MGMT_NB_ID);
        mishare_raw_put(pending);
        mishare_raw_put(pending);
        return -ENOMEM;
    }
    memcpy(data, frame, len);
    params.tx_frame = packet;
    params.frm_len = len;
    params.vdev_id = id;
    params.pdata = data;
    params.qdf_ctx = cds_get_context(QDF_MODULE_ID_QDF_DEVICE);
    params.tx_type = GENERIC_NODOWLOAD_ACK_COMP_INDEX;
    params.use_6mbps = 1;
    params.tx_params_valid = true;
    wma_update_tx_send_params(&params.tx_param, RATEID_6MBPS);
    params.tx_param.frame_type = 1; /* Native tx_send_params: DATA=1. */
    params.tx_param.bw_mask = BIT(2); /* 20 MHz */
    params.tx_param.retry_limit = 1;
    status = wlan_mgmt_txrx_mgmt_frame_tx(peer, pending, packet, NULL,
                mishare_raw_complete, WLAN_UMAC_COMP_MLME, &params);
    wlan_objmgr_peer_release_ref(peer, WLAN_MGMT_NB_ID);
    if (QDF_IS_STATUS_ERROR(status)) {
        /* Native API failure leaves the packet with the caller; no callback. */
        cds_packet_free(packet);
        mishare_raw_put(pending);
        mishare_raw_put(pending);
        return -EIO;
    }
    ret = -ETIMEDOUT;
    if (wait_for_completion_timeout(&pending->done, msecs_to_jiffies(1000))) {
        *native_status = READ_ONCE(pending->status);
        ret = 0;
    }
    mishare_raw_put(pending);
    return ret;
}
