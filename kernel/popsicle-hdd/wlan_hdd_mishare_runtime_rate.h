/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RUNTIME_RATE_H
#define WLAN_HDD_MISHARE_RUNTIME_RATE_H
#include <linux/types.h>
struct mishare_runtime_owner;
struct wlan_objmgr_vdev;
struct wondertap_fixed_tx_rate_params;
struct mishare_runtime_rate_request { u8 preamble, bw, gi, nss, mcs; };
struct mishare_runtime_rate_result {
    bool busy, attempted, complete;
    u8 attempted_mask, submitted_mask;
    int result, first_error;
};
struct mishare_runtime_rate_status {
    bool requested, posted, accepted, completed, integrity_error;
    struct mishare_runtime_rate_request request;
    struct mishare_runtime_rate_result receipt;
};
/* Serialized internal one-shot API, after owned PE/channel preparation and
 * before START-plan/radio. Caller retains native parents across all polls.
 * EINPROGRESS means posted only; use runtime_snapshot for actual completion.
 * No automatic managed caller, firmware ACK or complete configuration claim.
 * Attempted submissions currently prohibit START and retirement: the safe
 * post-configuration teardown coordinator must be installed before enabling.
 */
int mishare_runtime_rate_configure(struct mishare_runtime_owner *owner,
                                   const struct wondertap_fixed_tx_rate_params *params);
/* Private bridge hooks. Only configure() may begin/post; the MC completion
 * callback publishes the receipt while its work reservation is still held.
 * These scalar hooks do not reference the public Wonder ABI or submit work.
 */
int mishare_runtime_rate_begin(struct mishare_runtime_owner *owner,
                               const struct mishare_runtime_rate_request *request,
                               struct wlan_objmgr_vdev **vdev);
void mishare_runtime_rate_posted(struct mishare_runtime_owner *owner, int result);
void mishare_runtime_rate_complete(struct mishare_runtime_owner *owner,
                                    const struct mishare_runtime_rate_result *result);
#endif
