// SPDX-License-Identifier: GPL-2.0-only
/* One-shot fixed-rate bridge. Actual runtime registry owns the scalar state. */
#include <linux/errno.h>
#include "wlan_hdd_mishare_runtime_rate.h"
#include "wlan_hdd_mishare_rate.h"

static void mishare_runtime_rate_done(void *owner,
                                      const struct mishare_rate_submission *receipt,
                                      int result)
{
    struct mishare_runtime_rate_result r = {
        .busy = receipt->busy,
        .attempted = receipt->attempted,
        .complete = receipt->complete,
        .attempted_mask = receipt->attempted_mask,
        .submitted_mask = receipt->submitted_mask,
        .result = result,
        .first_error = receipt->first_error,
    };
    mishare_runtime_rate_complete(owner, &r);
}

int mishare_runtime_rate_configure(struct mishare_runtime_owner *owner,
                                   const struct wondertap_fixed_tx_rate_params *params)
{
    struct mishare_runtime_rate_request request;
    struct wondertap_fixed_tx_rate_params frozen = {0};
    struct wlan_objmgr_vdev *vdev;
    int ret;

    if (!params)
        return -EINVAL;
    frozen.preamble = params->preamble;
    frozen.bw = params->bw;
    frozen.gi = params->gi;
    frozen.nss = params->nss;
    frozen.mcs = params->mcs;
    ret = mishare_rate_check(&frozen);
    if (ret)
        return ret;
    request.preamble = frozen.preamble;
    request.bw = frozen.bw;
    request.gi = frozen.gi;
    request.nss = frozen.nss;
    request.mcs = frozen.mcs;
    ret = mishare_runtime_rate_begin(owner, &request, &vdev);
    if (ret)
        return ret;
    /* begin already latched requested: an inline callback cannot race a
     * missing caller checkpoint, and cleanup waits for posted to be recorded.
     */
    ret = mishare_rate_post(vdev, owner, &frozen, mishare_runtime_rate_done);
    mishare_runtime_rate_posted(owner, ret);
    return ret ? ret : -EINPROGRESS;
}
