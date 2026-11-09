// SPDX-License-Identifier: GPL-2.0-only
/* Owned MC batch: one reservation spans direct WMI submission and completion. */
#include <linux/errno.h>
#include <linux/slab.h>
#include <qdf_status.h>
#include <scheduler_api.h>
#include <wlan_objmgr_vdev_obj.h>
#include "wlan_hdd_mishare_ndi.h"
#include "wlan_hdd_mishare_retry.h"

struct mishare_retry_request {
    struct wlan_objmgr_vdev *vdev;
    void *owner;
    mishare_retry_complete_fn complete;
    u8 data_limit, mgmt_limit;
    struct mishare_retry_submission receipt;
};

static QDF_STATUS mishare_retry_finish(struct scheduler_msg *msg, bool flushed)
{
    struct mishare_retry_request *req = msg->bodyptr;
    struct mishare_retry_submission receipt;
    struct wlan_objmgr_vdev *vdev;
    mishare_retry_complete_fn complete;
    void *owner;
    int ret;

    if (!req)
        return QDF_STATUS_E_INVAL;
    vdev = req->vdev;
    owner = req->owner;
    complete = req->complete;
    ret = flushed ? -ECANCELED : mishare_runtime_work_enter(vdev, owner);
    if (!ret) {
        ret = mishare_retry_submit_mc(vdev, req->data_limit, req->mgmt_limit, &req->receipt);
        mishare_runtime_work_exit(vdev, owner);
    }
    receipt = req->receipt;
    msg->bodyptr = NULL;
    kfree(req);
    /* Owner cannot retire while the work reservation is still held. */
    complete(owner, &receipt, ret);
    mishare_runtime_work_put(vdev, owner);
    wlan_objmgr_vdev_release_ref(vdev, WLAN_LEGACY_MAC_ID);
    return QDF_STATUS_SUCCESS;
}

static QDF_STATUS mishare_retry_callback(struct scheduler_msg *msg)
{
    return mishare_retry_finish(msg, false);
}

static QDF_STATUS mishare_retry_flush(struct scheduler_msg *msg)
{
    return mishare_retry_finish(msg, true);
}

int mishare_retry_post(struct wlan_objmgr_vdev *vdev, void *owner,
                       u8 data_limit, u8 mgmt_limit,
                       mishare_retry_complete_fn complete)
{
    struct mishare_retry_request *req;
    struct scheduler_msg msg = {0};
    QDF_STATUS status;
    int ret;

    if (!vdev || !owner || !complete)
        return -EINVAL;
    req = kzalloc(sizeof(*req), GFP_KERNEL);
    if (!req)
        return -ENOMEM;
    status = wlan_objmgr_vdev_try_get_ref(vdev, WLAN_LEGACY_MAC_ID);
    if (QDF_IS_STATUS_ERROR(status)) {
        kfree(req);
        return -ENODEV;
    }
    req->vdev = vdev;
    req->owner = owner;
    req->complete = complete;
    req->data_limit = data_limit;
    req->mgmt_limit = mgmt_limit;
    ret = mishare_runtime_work_get(vdev, owner);
    if (ret)
        goto release;
    msg.bodyptr = req;
    msg.callback = mishare_retry_callback;
    msg.flush_callback = mishare_retry_flush;
    status = scheduler_post_message(QDF_MODULE_ID_HDD, QDF_MODULE_ID_PE,
                                     QDF_MODULE_ID_TARGET_IF, &msg);
    if (!QDF_IS_STATUS_ERROR(status))
        return 0; /* An inline callback may already have freed req. */
    /* Native scheduler failure is pre-publication; no completion callback. */
    ret = qdf_status_to_os_return(status);
    mishare_runtime_work_put(vdev, owner);
release:
    wlan_objmgr_vdev_release_ref(vdev, WLAN_LEGACY_MAC_ID);
    kfree(req);
    return ret;
}
