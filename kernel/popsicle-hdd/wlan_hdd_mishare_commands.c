// SPDX-License-Identifier: GPL-2.0-only
/* Native command submission to the existing vdev manager. Dormant until owned. */
#include <linux/errno.h>
#include <qdf_status.h>
#include <wlan_vdev_mlme.h>
#include <../../core/src/vdev_mgr_ops.h>
#include "wlan_hdd_mishare_commands.h"

static int mishare_command_submit(struct mishare_event_owner *owner,
                                  struct vdev_mlme_obj *mlme,
                                  enum mishare_txn_command command, u64 *ticket)
{
    QDF_STATUS status;
    int ret;

    if (!ticket)
        return -EINVAL;
    *ticket = 0;
    if (!owner || !mlme || !mlme->vdev)
        return -EINVAL;
    if (wlan_vdev_mlme_get_opmode(mlme->vdev) != QDF_PASSTHRU_MODE ||
        mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_PASSTHRU ||
        mlme->mgmt.generic.subtype != 0)
        return -EOPNOTSUPP;
    if (wlan_vdev_mlme_get_cmpt_obj(mlme->vdev) != mlme)
        return -EINVAL;
    /* Newly published PASSTHRU components are host-only. A legacy context is
     * required for this native command path; it is NOT firmware-create proof.
     * Runtime ownership/create completion must be established by the caller.
     */
    if (!mlme->ext_vdev_ptr)
        return -EOPNOTSUPP;
    ret = mishare_events_begin_vdev(owner, mlme->vdev, command, ticket);
    if (ret)
        return ret;

    /* begin releases the registry lock before any transport/native callbacks. */
    if (command == MISHARE_TXN_START)
        status = vdev_mgr_start_send(mlme, false);
    else
        status = vdev_mgr_stop_send(mlme);

    /* A general native error does not prove the command never escaped. */
    ret = mishare_events_submitted(owner, *ticket,
                                   status == QDF_STATUS_SUCCESS ?
                                   MISHARE_TXN_ACCEPTED : MISHARE_TXN_UNKNOWN);
    if (status != QDF_STATUS_SUCCESS)
        return qdf_status_to_os_return(status);
    return ret;
}

int mishare_command_submit_start(struct mishare_event_owner *owner,
                                  struct vdev_mlme_obj *mlme, u64 *ticket)
{
    return mishare_command_submit(owner, mlme, MISHARE_TXN_START, ticket);
}

int mishare_command_submit_stop(struct mishare_event_owner *owner,
                                 struct vdev_mlme_obj *mlme, u64 *ticket)
{
    return mishare_command_submit(owner, mlme, MISHARE_TXN_STOP, ticket);
}
