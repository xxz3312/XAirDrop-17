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
    bool ordinary_admitted, ordinary_completed; /* Pre-START ordinary DELETE only. */
    bool late_delete_armed, late_delete_reply; /* Original SSR fence and native reply. */
    bool tail_dp_attempted; /* One native DP helper attempt after ordinary DELETE reply. */
    bool tail_attempted, tail_completed; /* Ordinary DP tail in qualified SSR window. */
    bool reset_admitted, reset_completed; /* Qualified native SSR progress only. */
    struct mishare_runtime_rate_request request;
    struct mishare_runtime_rate_result receipt;
};
/* Serialized internal one-shot API, after owned PE/channel preparation and
 * before START-plan/radio. Caller retains native parents across all polls.
 * EINPROGRESS means posted only; use runtime_snapshot for actual completion.
 * No automatic managed caller, firmware ACK or complete configuration claim.
 * Attempted submissions prohibit START and direct metadata retirement.
 * Pre-START ordinary DELETE and qualified SSR use separate progress checks;
 * only qualified ordinary-tail SSR continuations are admitted. Other mixed
 * origins remain held. Public configuration is still disabled.
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
