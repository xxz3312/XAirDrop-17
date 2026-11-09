/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RUNTIME_RETRY_H
#define WLAN_HDD_MISHARE_RUNTIME_RETRY_H
#include "wlan_hdd_mishare_retry.h"
struct mishare_runtime_owner;
struct mishare_runtime_retry_status {
    bool requested, posted, accepted, completed, integrity_error;
    u8 data_limit, mgmt_limit;
    struct mishare_retry_submission receipt;
    int result;
};
/* Pure evidence validator. A failed native group can have a partial AC prefix;
 * submitted bits record only completely accepted groups, never firmware ACK.
 */
static inline bool mishare_runtime_retry_receipt_valid(
                const struct mishare_runtime_retry_status *s,
                const struct mishare_retry_submission *r, int result, u8 id)
{
    u8 group, attempted = 0, submitted = 0, skipped = 0;
    if (r->busy || result > 0)
        return false;
    if (!r->attempted)
        return result < 0 && !r->complete && !r->vdev_id && !r->data_limit &&
               !r->mgmt_limit && !r->first_error && !r->attempted_mask &&
               !r->submitted_mask && !r->skipped_mask;
    if (r->vdev_id != id || r->data_limit != s->data_limit ||
        r->mgmt_limit != s->mgmt_limit || r->first_error != result ||
        r->complete != !result)
        return false;
    for (group = 0; group < 2; group++) {
        u8 bit = 1U << group;
        if (!(group ? s->mgmt_limit : s->data_limit)) {
            skipped |= bit;
            continue;
        }
        attempted |= bit;
        /* A failure ends exactly at this group; no later calls or skips. */
        if (result && r->attempted_mask == attempted)
            return r->submitted_mask == submitted && r->skipped_mask == skipped;
        submitted |= bit;
    }
    return !result && r->attempted_mask == attempted &&
           r->submitted_mask == submitted && r->skipped_mask == skipped;
}
int mishare_runtime_retry_begin(struct mishare_runtime_owner *owner,
                     u8 data_limit, u8 mgmt_limit, struct wlan_objmgr_vdev **vdev);
void mishare_runtime_retry_posted(struct mishare_runtime_owner *owner, int result);
void mishare_runtime_retry_complete(struct mishare_runtime_owner *owner,
                     const struct mishare_retry_submission *receipt, int result);
int mishare_runtime_retry_configure(struct mishare_runtime_owner *owner,
                                     u8 data_limit, u8 mgmt_limit);
#endif
