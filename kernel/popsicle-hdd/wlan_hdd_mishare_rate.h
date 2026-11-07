/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RATE_H
#define WLAN_HDD_MISHARE_RATE_H
#include "wlan_hdd_mishare_wonder_api.h"

struct wlan_objmgr_vdev;
/* Fresh zeroed storage for ONE newly created firmware VDEV. Caller serializes
 * all access and retains the exact VDEV/MLME, parents, firmware and WLAN text
 * through the entire call, including synchronous transport callbacks. No reset,
 * retry, rollback, free or lifetime authority is provided by this receipt.
 */
struct mishare_rate_submission {
    bool busy;
    bool attempted;
    bool complete; /* All three commands queued; NOT firmware acknowledgement. */
    u8 vdev_id;
    u8 attempted_mask; /* bit 0 fixed rate, bit 1 GI, bit 2 bandwidth */
    u8 submitted_mask;
    int first_error;
};

/* Internal dormant executor. Caller independently proves owned firmware CREATE
 * and current regulatory/channel/NSS admission. Host INIT/legacy pointer alone
 * proves neither. No automatic managed/public backend caller is installed.
 * Supports HT/VHT/HE/EHT, HT20 and at most two streams; legacy rate ambiguity,
 * MCS14/15, wider channels and RA masks are not supported here.
 * Error after attempted=true means a command might have escaped: retain the
 * VDEV and receipt for ordinary qualified teardown, never retry this sequence.
 * A completed call returns EALREADY on replay; an earlier failure is sticky.
 */
int mishare_rate_submit(struct wlan_objmgr_vdev *vdev,
                         const struct wondertap_fixed_tx_rate_params *params,
                         struct mishare_rate_submission *receipt);
#endif
