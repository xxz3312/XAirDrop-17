/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RATE_H
#define WLAN_HDD_MISHARE_RATE_H
#include <linux/errno.h>
#include "wlan_hdd_mishare_wonder_api.h"

/* Pure support check shared by managed preparation and native submission.
 * Does not authorize a frequency/NSS, read parents or submit a command.
 */
static inline int mishare_rate_check(const struct wondertap_fixed_tx_rate_params *p)
{
    u8 max_mcs;

    if (!p || (unsigned int)p->preamble >= WONDERTAP_RATE_PREAMBLE_MAX ||
        (unsigned int)p->bw > WONDERTAP_RATE_BW_320 ||
        (unsigned int)p->gi > WONDERTAP_RATE_GI_3_2_US ||
        !p->nss || p->nss > WONDERTAP_HE_NSS_MAX)
        return -EINVAL;
    if (p->bw != WONDERTAP_RATE_BW_20 || p->nss > 2)
        return -EOPNOTSUPP;
    switch (p->preamble) {
    case WONDERTAP_RATE_PREAMBLE_HT: max_mcs = 7; break;
    case WONDERTAP_RATE_PREAMBLE_VHT: max_mcs = 9; break;
    case WONDERTAP_RATE_PREAMBLE_HE: max_mcs = 11; break;
    case WONDERTAP_RATE_PREAMBLE_EHT: max_mcs = 13; break;
    default: return -EOPNOTSUPP; /* No unambiguous legacy encoding. */
    }
    if (p->mcs > max_mcs)
        return -EOPNOTSUPP;
    if (p->preamble <= WONDERTAP_RATE_PREAMBLE_VHT) {
        if (p->gi != WONDERTAP_RATE_GI_DEFAULT && p->gi != WONDERTAP_RATE_GI_SHORT)
            return -EOPNOTSUPP;
    } else if (p->gi == WONDERTAP_RATE_GI_SHORT) {
        return -EOPNOTSUPP;
    }
    return 0;
}

struct wlan_objmgr_vdev;
/* Fresh zeroed storage for ONE newly created firmware VDEV. Caller serializes
 * all access and retains the exact VDEV/MLME, parents, firmware and WLAN text
 * through the entire call, including synchronous transport callbacks. No reset,
 * retry, rollback, free or lifetime authority is provided by this receipt.
 */
struct mishare_rate_submission {
    bool busy;
    bool attempted;
    bool complete; /* All three submissions accepted; NOT firmware ACK. */
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
/* Same one-shot receipt, but MC-thread-only direct native WMI submission,
 * without nested CLI queueing. Caller supplies work/lifetime admission.
 */
int mishare_rate_submit_mc(struct wlan_objmgr_vdev *vdev,
                            const struct wondertap_fixed_tx_rate_params *params,
                            struct mishare_rate_submission *receipt);
typedef void (*mishare_rate_complete_fn)(void *owner,
                                        const struct mishare_rate_submission *receipt,
                                        int result);
/* Caller serializes one-shot posting for an existing runtime owner. Captures
 * scalar params, acquires a VDEV ref and runtime work reservation before MC
 * queue publication. Completion runs once while both are held; copy receipt
 * during that callback. Initialize caller state before posting: completion
 * can be inline. Never wait for work drain/retirement inside completion.
 * Pre-publication failure has no callback. Completion
 * does not prove firmware ACK. Owner/parents/firmware must stay retained until
 * owned work drains, then follow qualified native teardown. No public caller.
 */
int mishare_rate_post(struct wlan_objmgr_vdev *vdev, void *owner,
                       const struct wondertap_fixed_tx_rate_params *params,
                       mishare_rate_complete_fn complete);
#endif
