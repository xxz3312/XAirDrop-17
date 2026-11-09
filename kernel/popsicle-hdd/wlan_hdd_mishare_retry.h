/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RETRY_H
#define WLAN_HDD_MISHARE_RETRY_H
#include <linux/types.h>
struct wlan_objmgr_vdev;
/* Fresh zeroed receipt per owned firmware VDEV. Serialized MC caller retains
 * exact VDEV/MLME/WMA, parents, firmware and text plus work reservation through
 * submission. This dormant executor neither obtains nor releases those leases.
 * Group bit 0: data/AGGR; bit 1: management/NONAGGR, matching upstream labels.
 * Each native group may send four AC commands. A failed group may be partially
 * submitted; masks describe group calls, never individual ACs or firmware ACK.
 * Zero is upstream's skip semantics, NOT a command resetting retries to zero.
 */
struct mishare_retry_submission {
    bool busy, attempted, complete;
    u8 vdev_id, data_limit, mgmt_limit;
    u8 attempted_mask, submitted_mask, skipped_mask;
    int first_error;
};
/* No posting, automatic init caller, retry or rollback. After attempted=true,
 * retain receipt and owner for qualified teardown. Replay returns sticky error
 * or EALREADY, even with different arguments; never reuse the receipt.
 */
int mishare_retry_submit_mc(struct wlan_objmgr_vdev *vdev, u8 data_limit,
                            u8 mgmt_limit,
                            struct mishare_retry_submission *receipt);
#endif
