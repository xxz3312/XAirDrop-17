/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RADIO_H
#define WLAN_HDD_MISHARE_RADIO_H
#include <linux/types.h>
struct wlan_objmgr_vdev;
struct wlan_objmgr_psoc;
/* Close matching controllers; no PM cleanup, free or synthetic completion. */
void mishare_radio_quiesce_psoc(struct wlan_objmgr_psoc *psoc);
struct mishare_event_owner;
struct mishare_radio;
struct mishare_ndi_start_summary;
enum mishare_radio_phase {
    MISHARE_RADIO_NEW,
    MISHARE_RADIO_STARTING,
    MISHARE_RADIO_WAIT_START,
    MISHARE_RADIO_UP,
    MISHARE_RADIO_STOPPING,
    MISHARE_RADIO_WAIT_STOP,
    MISHARE_RADIO_DOWN,
    MISHARE_RADIO_CANCELLED,
    MISHARE_RADIO_BLOCKED,
};
struct mishare_radio_status {
    enum mishare_radio_phase phase;
    bool start_attempted;
    bool stop_attempted;
    bool host_up;
    bool down_attempted;
    bool down_accepted; /* Native send + PM cleanup, not a firmware DOWN ACK. */
    bool closing;
    unsigned int pending;
    unsigned int users;
    int error;
    bool ssr_cancelled_before_start; /* Proven never-executed START retirement. */
    int ssr_start_submit_error; /* Original scheduler rejection, zero for MC flush. */
    bool ssr_start_callback_refused; /* Callback entered, work_enter refused before body. */
    bool ssr_start_body_aborted; /* Work admitted, fenced before prepare entry. */
    bool ssr_start_prepared_aborted; /* Preparation matched, no START SM commitment. */
    bool ssr_start_sm_entry_aborted; /* Committed intent, fenced before native dispatch entry. */
    bool ssr_start_init_rejected; /* Native INIT rejected START, full dispatch returned. */
};
/* Internal one-shot owned radio controller. Caller keeps the exact event
 * registry, PE session and parent/exclusive psoc transition alive. No concurrent
 * owner-handle calls or external MLME/config/peer operations on this VDEV.
 * A non-NULL output on error must still be drained. No retries on this owner.
 * No automatic HDD/Wonder caller; active START/UP and remove recovery remain
 * unsupported. The explicit SSR interface below covers a queued START
 * flushed before its callback executes, an exact scheduler rejection, or a
 * callback refused by work admission after the original SSR fence. Work admitted
 * before fence can also retire only with proof it aborted before prepare entry.
 * Completed preparation may retire only if its native seven-field encoder plan
 * matches the copied plan and no START SM event was committed. A committed
 * intent can also retire only if the shared-lock native-entry gate refused
 * dispatch before its entry flag was set. Entry-marked native SM stays held.
 */
int mishare_radio_open(struct wlan_objmgr_vdev *vdev,
                       struct mishare_event_owner *events, void *owner,
                       unsigned long session_cookie, u32 freq,
                       const struct mishare_ndi_start_summary *plan,
                       struct mishare_radio **radio);
int mishare_radio_snapshot(struct mishare_radio *radio,
                           struct mishare_radio_status *status);
/* EINPROGRESS: poll, never sleep under RTNL/SM locks. EUCLEAN: keep every
 * parent/peer/PE/VDEV/DP resource. Success removes callbacks before ref release.
 */
int mishare_radio_drain(struct mishare_radio **radio,
                        struct mishare_radio_status *last);
/* Explicit SSR path for START flushed, scheduler-rejected, work-refused, early-aborted, prepared-without-SM or committed-but-not-entered.
 * Caller proves owned/native MC stop, qualified reset window and retains exact
 * parents under RTNL/exclusive psoc serialization. Check/release revalidate the
 * live identity, exact flush/rejection/refusal/body-abort provenance, INIT and untouched transaction.
 * No WMI/SM/PM/timer operation or synthetic DOWN/CANCELLED phase. Unknown tokens
 * and failed/partial preparation, any marked native SM entry or callback fault remain held. Snapshot storage is caller-owned.
 */
int mishare_radio_ssr_cancel_check(struct mishare_radio *radio,
                                   struct wlan_objmgr_vdev *vdev,
                                   struct mishare_event_owner *events, void *owner,
                                   unsigned long cookie, u32 freq);
int mishare_radio_ssr_cancel_release(struct mishare_radio **radio,
                                     struct wlan_objmgr_vdev *vdev,
                                     struct mishare_event_owner *events, void *owner,
                                     unsigned long cookie, u32 freq,
                                     struct mishare_radio_status *last);
#endif
