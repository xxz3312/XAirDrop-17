/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_COMMANDS_H
#define WLAN_HDD_MISHARE_COMMANDS_H
#include "wlan_hdd_mishare_events.h"
struct vdev_mlme_obj;
/* Internal submission APIs; no runtime caller yet.
 * Caller owns/serializes owner, the live vdev/MLME component, and command/config
 * transitions for the WHOLE call. No unbind/delete from synchronous callbacks.
 * Host-only components (no legacy context) are rejected. A legacy pointer is
 * not firmware CREATE proof: a future runtime caller must establish creation
 * ownership independently. No such runtime caller/context creator exists yet.
 * Channel/regulatory/concurrency configuration must already be established.
 * The native transport runs WITHOUT the registry lock, so its response can enter.
 * 0 means accepted submission only: query the transaction for actual completion.
 * A nonzero ticket on error means a submission was attempted: retain/quarantine
 * resources; it never authorizes vdev deletion. No create/UP/DOWN/delete here.
 */
int mishare_command_submit_start(struct mishare_event_owner *owner,
                                  struct vdev_mlme_obj *mlme, u64 *ticket);
int mishare_command_submit_stop(struct mishare_event_owner *owner,
                                 struct vdev_mlme_obj *mlme, u64 *ticket);
#endif
