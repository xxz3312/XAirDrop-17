/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_NDI_H
#define WLAN_HDD_MISHARE_NDI_H
#include <linux/types.h>
struct wlan_objmgr_vdev;
struct wlan_objmgr_psoc;
struct vdev_mlme_obj;
struct vdev_create_params;
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
    u8 stats_id;
};
struct mishare_ndi_status {
    bool active;
    bool blocked;
    bool delete_pending;
    bool delete_submitted;
    bool delete_replied;
    bool dp_detaching;
    bool dp_freed;
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
int mishare_ndi_release_stats(struct vdev_mlme_obj *mlme,
                              struct mishare_ndi_create_result *result);
/* Real DELETE origin only, after native timer/PM cleanup. Timeout is explicit.
 * Matching an owned ID suppresses the ordinary SME/WMA delete callback: this
 * owner has never taken their session references or published their context.
 */
bool mishare_runtime_ndi_delete_owned(struct wlan_objmgr_psoc *psoc, u8 id);
void mishare_runtime_ndi_delete_event(struct wlan_objmgr_psoc *psoc, u8 id,
                                      bool firmware);
#endif
