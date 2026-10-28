/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RUNTIME_H
#define WLAN_HDD_MISHARE_RUNTIME_H
#include <linux/types.h>
#include "wlan_hdd_mishare_ndi.h"
#include "wlan_hdd_mishare_radio.h"
struct wlan_objmgr_pdev;
struct wlan_objmgr_psoc;
struct wlan_objmgr_vdev;
struct wireless_dev;
struct mishare_runtime_owner;
enum mishare_quiesce_reason {
    MISHARE_QUIESCE_NONE,
    MISHARE_QUIESCE_SSR,
    MISHARE_QUIESCE_REMOVE,
    MISHARE_QUIESCE_MODULE_STOP,
    MISHARE_QUIESCE_UNAVAILABLE,
};
struct mishare_runtime_status {
    bool allocated;
    bool freed;
    bool draining;
    bool blocked;
    enum mishare_quiesce_reason quiesced;
    unsigned int work_pending;
    unsigned int work_users;
    int work_error;
    bool mc_stop_seen;
    bool mc_drained; /* Owned MC work only; NOT IRQ/timer/firmware proof. */
    bool host_reclaim;
    bool host_delete_accepted; /* Logical delete + event unbind accepted. */
    int reclaim_error;
    bool recovery_window;
    bool recovery_window_closed;
    bool ndi_reclaim_started;
    bool recovery_timer_attempted;
    bool recovery_timer_released;
    bool recovery_dp_attempted;
    bool recovery_dp_freed;
    bool ndi_reclaim_ready;
    bool ndi_completed_reclaim; /* Ordinary DELETE + DP free already observed. */
    int recovery_error; /* Sticky reset-cleanup or recovery DP origin error. */
    int create_error;
    struct mishare_ndi_status ndi;
    struct mishare_radio_status radio;
};
/* Close admission permanently for existing owners of this exact psoc.
 * Nonblocking and allocation-free; native shutdown must still drain scheduler,
 * IRQ, timers and in-flight work. This is NOT a quiescence or firmware barrier.
 * Never synthesizes DOWN/delete/free or clears quarantine after reinit.
 * Returns affected owners (including already fenced ones). No reset API.
 */
unsigned int mishare_runtime_quiesce_psoc(struct wlan_objmgr_psoc *psoc,
                                          enum mishare_quiesce_reason reason);
/* Native HDD health check; not a reference, exclusive transition or lease. */
bool mishare_runtime_platform_available(struct wlan_objmgr_psoc *psoc);
/* Called only after native scheduler_disable returns success. Records a
 * per-owner MC observation; readiness also requires every reservation to exit.
 * Does not acknowledge firmware, stop IRQ/timers or free native NDI resources.
 */
void mishare_runtime_mc_stopped(struct wlan_objmgr_psoc *psoc);
/* Explicit, serialized recovery of a never-wired pure host object only.
 * Requires shutdown fence + MC evidence, matching PAS/INIT/no extension, and
 * live parents under the same RTNL/exclusive psoc contract as normal destroy.
 * EINPROGRESS waits for actual host final-free; EUCLEAN retains ambiguous/native
 * NDI owners. No retry/reset after a reclaim error; no new firmware commands.
 */
int mishare_runtime_reclaim_host(struct mishare_runtime_owner **owner);
/* Internal SSR-only origin: qualified stopped HIF/HTC/RX + blocked WMI with
 * work queues flushed. Closes irrevocably before native CDS DP close or HDD /
 * dispatcher pdev component close; cds_close also closes it as a fallback.
 * These fences revoke admission, not hold parent references or wait for an
 * active reclaim call. Caller must serialize teardown with all reclaim polls.
 * No firmware ACK or ownership reset is manufactured.
 */
unsigned int mishare_runtime_recovery_candidates(struct wlan_objmgr_psoc *psoc);
void mishare_runtime_recovery_open(struct wlan_objmgr_psoc *psoc);
void mishare_runtime_recovery_close(struct wlan_objmgr_psoc *psoc);
/* Explicit serialized recovery of never-prepared NDI only: either early
 * CREATE/DP state, or ordinary DELETE + DP final-free already completed.
 * Both routes require the qualified SSR/WMI window before parent teardown.
 * The completed route submits no firmware/DP/timer operations and preserves
 * ordinary completion history; it only starts host deletion/final-free wait.
 * Caller retains RTNL/exclusive psoc and exact DP/timer parents throughout all
 * polls; stop CDS parent destruction until completion. No automatic caller.
 * Partial attach, peer/PE/radio and incomplete DELETE history stay held.
 */
int mishare_runtime_reclaim_ndi(struct mishare_runtime_owner **owner);
/* SSR-only owner bookkeeping after host deletion already succeeded and all
 * owner-held native handles/bindings/references were surrendered. No native
 * delete, component getter, DP/timer/WMI access or window reopening occurs.
 * Requires owned-MC drain, no sticky errors and the exact actual final-free
 * notification before clearing the handle. Caller retains parents until that
 * notification; window closure does not authorize early parent destruction.
 * Prepared/radio history may remain only after ordinary cleanup already
 * completed; this never performs prepared/STARTed recovery. Serialize owner
 * calls and teardown throughout. Unknown opaque tokens return ENOENT.
 */
int mishare_runtime_reclaim_final(struct mishare_runtime_owner **owner);
/* Bounded caller-owned handle table, not the native psoc vdev limit. */
#define MISHARE_RUNTIME_RECLAIM_BATCH_MAX 64U
struct mishare_runtime_reclaim_item {
    struct mishare_runtime_owner *owner;
    int result;
};
/* Explicit SSR batch step; no automatic caller or parent lifetime lease.
 * Items are the authoritative owner handles: successful reclaim clears them.
 * Caller retains exact parents and serializes create/destroy/reclaim/teardown
 * for this psoc throughout the batch and every asynchronous poll. No aliases.
 * Before any mutation, every non-NULL token must match this registry/psoc,
 * occur once, and cover ALL owners of that psoc (including final-free waits).
 * All must carry the original SSR fence and drained owned-MC evidence.
 * Full coverage is checked before owner policy; fatal policy/accounting errors
 * take precedence over waiting owners regardless of registry list order.
 * Accepted host-delete owners also pass the same metadata-shape check as
 * final retirement, before any item performs native work. Actual final-free
 * waits remain per-item; this check does not hold parents or drain callbacks.
 * Preflight errors leave every item unchanged. After admission, item results
 * describe a possibly partial step; unsupported owners remain retained.
 * EINPROGRESS waits for real callbacks; other errors require diagnosis with
 * parents retained. Zero means all items AND the exact psoc registry are empty
 * at this serialized instant, never permission to unload module text or FW ACK.
 */
int mishare_runtime_reclaim_batch(struct wlan_objmgr_psoc *psoc,
                                  struct mishare_runtime_reclaim_item *items,
                                  unsigned int count);
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
/* One-shot native MC HT20 parameter preparation for an owned PE session.
 * Snapshot channel_completed/prepared after EINPROGRESS; no START or radio.
 * Native regulatory/concurrency checks are instantaneous, not a lease for a
 * later START. All prior lifetime and caller-serialization rules still apply.
 */
int mishare_runtime_ndi_channel(struct mishare_runtime_owner *owner, u32 freq);
/* One-shot MC START parameter construction after channel preparation. No WMI,
 * native state transition, new peer, runtime caller or readiness guarantee.
 * Poll start_plan_completed/ready. Later START must revalidate and rebuild.
 */
int mishare_runtime_ndi_start_plan(struct mishare_runtime_owner *owner);
/* Explicit one-shot radio START; queue acceptance is not firmware/host UP.
 * No default backend caller. Destruction first drives real STOP/accepted DOWN.
 * All exclusive parent and serialized handle contracts above remain required.
 */
int mishare_runtime_ndi_start(struct mishare_runtime_owner *owner);
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
