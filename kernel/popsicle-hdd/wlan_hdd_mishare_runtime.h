/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RUNTIME_H
#define WLAN_HDD_MISHARE_RUNTIME_H
#include <linux/types.h>
struct wlan_objmgr_pdev;
struct wlan_objmgr_psoc;
struct wlan_objmgr_vdev;
struct wireless_dev;
struct mishare_runtime_owner;
struct mishare_runtime_status {
    bool allocated;
    bool freed;
    bool draining;
    bool blocked;
    int create_error;
};
/* Host-only raw object-manager factory. No SME self-peer/post-setup or WMI.
 * Caller owns RTNL, an exclusive parent psoc transition, and a live netdev/DP
 * interface matching mac throughout creation AND until destroy returns 0.
 * Serialize all owner-handle calls, and finish before HDD/pdev teardown.
 * EINPROGRESS/EUCLEAN may return a non-NULL owner even on create failure:
 * retain all parent resources and poll destroy. EUCLEAN needs diagnosis/drain,
 * never a blind retry/delete/ref reset. No sleeping wait or automatic worker.
 */
int mishare_runtime_create(struct wlan_objmgr_pdev *pdev, const u8 *mac,
                           void *osif, struct wireless_dev *wdev,
                           struct mishare_runtime_owner **owner);
int mishare_runtime_destroy(struct mishare_runtime_owner **owner);
int mishare_runtime_snapshot(struct mishare_runtime_owner *owner,
                             struct mishare_runtime_status *status);
/* Native object-manager origins; no pointer retention/ref acquisition here.
 * prepare_free captures a stable OWNER token before deallocation; the owner
 * cannot be freed until that one final-free notification arrives. Never match
 * post-free events by a reusable vdev address.
 */
void mishare_runtime_allocated(struct wlan_objmgr_vdev *vdev);
bool mishare_runtime_prepare_free(struct wlan_objmgr_vdev *vdev,
                                   unsigned long *owner_token);
void mishare_runtime_freed(struct wlan_objmgr_psoc *psoc, unsigned long owner_token);
#endif
