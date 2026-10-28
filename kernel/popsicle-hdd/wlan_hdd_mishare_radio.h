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
};
/* Internal one-shot owned radio controller. Caller keeps the exact event
 * registry, PE session and parent/exclusive psoc transition alive. No concurrent
 * owner-handle calls or external MLME/config/peer operations on this VDEV.
 * A non-NULL output on error must still be drained. No retries on this owner.
 * No automatic HDD/Wonder caller; SSR/remove recovery is not implemented.
 */
int mishare_radio_open(struct wlan_objmgr_vdev *vdev,
                       struct mishare_event_owner *events, void *owner,
                       unsigned long session_cookie, u32 freq,
                       struct mishare_radio **radio);
int mishare_radio_snapshot(struct mishare_radio *radio,
                           struct mishare_radio_status *status);
/* EINPROGRESS: poll, never sleep under RTNL/SM locks. EUCLEAN: keep every
 * parent/peer/PE/VDEV/DP resource. Success removes callbacks before ref release.
 */
int mishare_radio_drain(struct mishare_radio **radio,
                        struct mishare_radio_status *last);
#endif
