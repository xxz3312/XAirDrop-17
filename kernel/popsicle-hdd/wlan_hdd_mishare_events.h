/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_EVENTS_H
#define WLAN_HDD_MISHARE_EVENTS_H
#include "wlan_hdd_mishare_txn.h"
struct wlan_objmgr_psoc;
struct wlan_objmgr_vdev;
struct mishare_event_owner;
/* Poison all matching transactions without clearing pending/reply evidence. */
void mishare_events_quiesce_psoc(struct wlan_objmgr_psoc *psoc);

enum mishare_event_origin {
    MISHARE_EVENT_FIRMWARE,
    MISHARE_EVENT_TIMEOUT,
};

/* Bind only a newly created PASSTHRU vdev, with its previous event stream drained.
 * Caller holds a valid vdev reference and serializes owner-handle API calls.
 * An additional object-manager reference is held until unbind. Unbind before
 * vdev deletion/HDD teardown. No start, timer, firmware or free-vdev operation.
 */
int mishare_events_bind(struct wlan_objmgr_vdev *vdev,
                        struct mishare_event_owner **owner);
void mishare_events_unbind(struct mishare_event_owner **owner);
int mishare_events_begin(struct mishare_event_owner *owner,
                         enum mishare_txn_command command, u64 *ticket);
/* Atomically require the exact bound vdev before starting a transaction. */
int mishare_events_begin_vdev(struct mishare_event_owner *owner,
                              struct wlan_objmgr_vdev *vdev,
                              enum mishare_txn_command command, u64 *ticket);
int mishare_events_submitted(struct mishare_event_owner *owner, u64 ticket,
                             enum mishare_txn_delivery delivery);
int mishare_events_snapshot(struct mishare_event_owner *owner,
                            struct mishare_vdev_txn *snapshot);
/* Called at native response/timer origins, never from the ambiguous common
 * MLME STOP callback. Does not retain pointers or invoke external callbacks.
 * Registry lock serializes notifications against removal and transaction APIs.
 */
int mishare_events_notify(struct wlan_objmgr_psoc *psoc, u8 vdev_id,
                          enum mishare_txn_command command,
                          enum mishare_event_origin origin, bool success);
#endif
