/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RUNTIME_H
#define WLAN_HDD_MISHARE_RUNTIME_H
#include <linux/types.h>
#include "wlan_hdd_mishare_ndi.h"
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
    struct mishare_ndi_status ndi;
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
/* Optional one-shot resource CREATE, not START/UP or radio ready. The caller
 * must supply platform-validated per-band NSS (range 1..2), own the same RTNL /
 * exclusive psoc transition as create/destroy, and retain parent resources.
 * After any attempted wire CREATE, never retry on this owner. Destroy drives
 * real DELETE then DP final-free; EINPROGRESS needs polling, EUCLEAN needs
 * diagnosis/parent recovery, never a forced free. No live backend caller yet.
 */
int mishare_runtime_ndi_create(struct mishare_runtime_owner *owner,
                               u8 nss_2g, u8 nss_5g);
/* Prepare only owned legacy locks/timer, WMA slot/ref and DEFAULT self-peer.
 * No CSR session, START/UP, channel or TX/RX. Same caller serialization/lifetime
 * contract; failed attempted peer create quarantines. Destroy now consumes the
 * exact owned peer-delete request before issuing vdev DELETE.
 */
int mishare_runtime_ndi_prepare(struct mishare_runtime_owner *owner);
/* One-shot asynchronous native MC-thread PE create. Poll snapshot for
 * pe_completed/pe_ready; return 0 from post means queue acceptance only.
 * Destroy waits for completion and confirmed PE deletion before self-peer
 * teardown. Request flush releases its VDEV ref; delete flush quarantines.
 * No channel parameters, START/UP, TX/RX or runtime caller yet.
 */
int mishare_runtime_ndi_session(struct mishare_runtime_owner *owner);
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
