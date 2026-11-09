// SPDX-License-Identifier: GPL-2.0-only
#include <linux/errno.h>
#include "wlan_hdd_mishare_runtime_retry.h"
static void mishare_runtime_retry_done(void *owner,
                      const struct mishare_retry_submission *receipt, int result)
{
    mishare_runtime_retry_complete(owner, receipt, result);
}
int mishare_runtime_retry_configure(struct mishare_runtime_owner *owner,
                                     u8 data_limit, u8 mgmt_limit)
{
    struct wlan_objmgr_vdev *vdev;
    int ret = mishare_runtime_retry_begin(owner, data_limit, mgmt_limit, &vdev);
    if (ret)
        return ret;
    ret = mishare_retry_post(vdev, owner, data_limit, mgmt_limit,
                              mishare_runtime_retry_done);
    mishare_runtime_retry_posted(owner, ret);
    return ret ? ret : -EINPROGRESS;
}
