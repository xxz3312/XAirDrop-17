/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_NDI_H
#define WLAN_HDD_MISHARE_NDI_H
/* Admission check for referenced MC work. Identity is matched in the registry;
 * owner is an opaque token, never dereferenced. Not an in-flight work barrier.
 */
#include <linux/types.h>
struct wlan_objmgr_vdev;
struct wlan_objmgr_psoc;
bool mishare_runtime_work_allowed(struct wlan_objmgr_vdev *vdev, void *owner);
/* Each owned MC message gets one reservation before posting. Enter/exit spans
 * native execution; put follows its completion publication. Caller holds a
 * VDEV reference until after put. None is a wait or an object reference itself.
 */
int mishare_runtime_work_get(struct wlan_objmgr_vdev *vdev, void *owner);
int mishare_runtime_work_enter(struct wlan_objmgr_vdev *vdev, void *owner);
void mishare_runtime_work_exit(struct wlan_objmgr_vdev *vdev, void *owner);
void mishare_runtime_work_put(struct wlan_objmgr_vdev *vdev, void *owner);
/* Distinct START flush/refusal/pre-prepare-abort origins, after request free/work put/pending
 * release. Opaque tokens are matched before dereference; no resource release.
 */
void mishare_runtime_radio_start_flushed(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token);
void mishare_runtime_radio_start_refused(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token);
void mishare_runtime_radio_start_aborted(struct wlan_objmgr_psoc *psoc,
                                         struct wlan_objmgr_vdev *vdev,
                                         void *owner, void *radio_token);
struct wlan_objmgr_psoc;
struct vdev_mlme_obj;
struct vdev_create_params;
struct vdev_start_response;
/* Transport acceptance is not firmware CREATE confirmation. A failed DP attach
 * may have published resources: do not infer absence from its return status.
 */
struct mishare_ndi_create_result {
    bool timer_ready;
    bool wire_attempted;
    bool wire_accepted;
    bool dp_attempted;
    bool dp_attached;
    bool stats_owned;
    unsigned long dp_cookie; /* Exact attach-time DP soc identity, not a ref. */
    u8 stats_id;
};
/* Scalars copied from the native target START parameter builder. No cached
 * transport buffer, pointer or future authorization to send a command. */
struct mishare_ndi_start_summary {
    u32 freq;
    u32 center_freq;
    u32 phy_mode;
    u32 tx_streams;
    u32 rx_streams;
    u32 beacon_interval;
    u32 dtim_period;
};
struct mishare_ndi_reset_context_result {
    bool peer_released;
    bool wma_unbound;
    bool legacy_released;
};
int mishare_ndi_reset_context_check(struct wlan_objmgr_vdev *vdev,
                                     unsigned long dp_cookie);
int mishare_ndi_reset_prepared_timer_deinit(struct wlan_objmgr_vdev *vdev);
/* SSR-only pre-radio context retirement after any PE session was released.
 * Caller holds the qualified reset window and exact parents; partial facts
 * survive errors, never retry.
 */
/* Final stage: owner has observed actual DP final-free and submit return. */
int mishare_ndi_reset_context_finish(struct wlan_objmgr_vdev *vdev,
                                      unsigned long dp_cookie,
                                      struct mishare_ndi_reset_context_result *result);
int mishare_ndi_reset_prepared_dp_detach(struct wlan_objmgr_vdev *vdev,
                                          unsigned long dp_cookie,
                                          void (*callback)(void *), void *context);
/* First stage releases only the peer; WMA/legacy remain until DP final-free. */
int mishare_ndi_reset_context_release(struct wlan_objmgr_vdev *vdev,
                                       unsigned long dp_cookie,
                                       struct mishare_ndi_reset_context_result *result);
struct mishare_ndi_status {
    int completion_error; /* Sticky invalid/duplicate native completion. */
    bool active;
    bool blocked;
    bool delete_pending;
    bool delete_submitted;
    bool delete_replied;
    bool dp_detaching;
    bool dp_detach_submitted; /* Ordinary detach returned success, not free. */
    bool dp_freed;
    bool legacy_ready;
    bool wma_bound;
    bool peer_create_attempted;
    bool peer_created;
    bool peer_delete_pending;
    bool peer_delete_submitted;
    bool peer_delete_replied;
    bool pe_requested;
    bool pe_submitted;
    bool pe_completed;
    bool pe_ready;
    bool pe_delete_requested;
    bool pe_delete_submitted;
    bool pe_delete_completed;
    bool channel_requested;
    bool channel_submitted;
    bool channel_completed;
    bool channel_prepared;
    bool radio_requested;
    int radio_submit_error;
    bool start_plan_requested;
    bool start_plan_submitted;
    bool start_plan_completed;
    bool start_plan_ready;
    int start_plan_error;
    struct mishare_ndi_start_summary start_plan;
    u32 channel_freq;
    int channel_error;
    int pe_error;
    int context_error;
    int create_error;
    struct mishare_ndi_create_result create;
};
/* Internal cross-layer functions; not exported, no automatic callers. Result
 * storage is zeroed by the exclusive owner before first use, never for retry.
 */
int mishare_ndi_native_create(struct vdev_mlme_obj *mlme,
                              struct mishare_ndi_create_result *result);
int mishare_ndi_tgt_create(struct vdev_mlme_obj *mlme,
                           struct vdev_create_params *params,
                           struct mishare_ndi_create_result *result);
int mishare_ndi_wire_create(struct wlan_objmgr_vdev *vdev,
                            struct vdev_create_params *params,
                            struct mishare_ndi_create_result *result);
int mishare_ndi_native_delete(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_native_dp_detach(struct wlan_objmgr_vdev *vdev,
                                 void (*callback)(void *), void *context);
int mishare_ndi_recovery_timer_deinit(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_recovery_dp_detach(struct wlan_objmgr_vdev *vdev,
                                   unsigned long dp_cookie,
                                   void (*callback)(void *), void *context);
int mishare_ndi_release_stats(struct vdev_mlme_obj *mlme,
                              struct mishare_ndi_create_result *result);
int mishare_ndi_radio_prepare(struct wlan_objmgr_vdev *vdev, void *owner,
                               unsigned long cookie, u32 freq);
int mishare_ndi_radio_start_response(struct vdev_mlme_obj *mlme,
                                      struct vdev_start_response *rsp);
int mishare_ndi_radio_host_up(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_radio_mark_down(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_radio_start_pm_release(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_start_plan_build(struct vdev_mlme_obj *mlme, u32 freq,
                                  struct mishare_ndi_start_summary *summary);
int mishare_ndi_start_plan_wma_check(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_start_plan_post(struct wlan_objmgr_vdev *vdev, void *owner,
                                 unsigned long cookie, u32 freq);
void mishare_runtime_ndi_start_plan_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                           void *owner, u32 freq, int result,
                                           const struct mishare_ndi_start_summary *summary);
int mishare_ndi_channel_post(struct wlan_objmgr_vdev *vdev, void *owner,
                              unsigned long session_cookie, u32 freq);
void mishare_runtime_ndi_channel_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                        void *owner, u32 freq, int result);
int mishare_ndi_pe_post(struct wlan_objmgr_vdev *vdev, void *owner,
                         bool create, unsigned long session_cookie);
/* Exact never-radio-started PE only, in the qualified stopped-MC SSR
 * window with original MAC/DP parents retained. Synchronous native teardown,
 * not an ordinary MC DELETE request or acknowledgement. Never retry errors.
 */
int mishare_ndi_reset_pe_check(struct wlan_objmgr_vdev *vdev, void *owner,
                               unsigned long cookie, unsigned long dp_cookie,
                               u32 expected_freq);
int mishare_ndi_reset_pe_release(struct wlan_objmgr_vdev *vdev, void *owner,
                                 unsigned long cookie, unsigned long dp_cookie,
                                 u32 expected_freq, bool *released);
void mishare_runtime_ndi_pe_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                   void *owner, bool create,
                                   unsigned long session_cookie, int result);
int mishare_ndi_legacy_prepare(struct vdev_mlme_obj *mlme);
int mishare_ndi_legacy_release(struct vdev_mlme_obj *mlme);
int mishare_ndi_wma_bind(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_wma_unbind(struct wlan_objmgr_vdev *vdev);
int mishare_ndi_self_peer_create(struct wlan_objmgr_vdev *vdev, bool *attempted);
int mishare_ndi_self_peer_delete(struct wlan_objmgr_vdev *vdev, void *owner);
void mishare_runtime_ndi_peer_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                    const u8 *mac, void *owner, bool firmware);
/* Real DELETE origin only, after native timer/PM cleanup. Timeout is explicit.
 * Matching an owned ID suppresses the ordinary SME/WMA delete callback: this
 * owner has never taken their session references or published their context.
 */
bool mishare_runtime_ndi_delete_owned(struct wlan_objmgr_psoc *psoc, u8 id);
void mishare_runtime_ndi_delete_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                      bool firmware);
#endif
