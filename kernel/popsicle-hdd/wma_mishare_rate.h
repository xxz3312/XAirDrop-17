/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WMA_MISHARE_RATE_H
#define WMA_MISHARE_RATE_H
#include <wlan_objmgr_vdev_obj.h>
#include <wlan_vdev_mlme_api.h>
#include <wlan_vdev_mlme.h>
#include "wlan_hdd_mishare_ndi.h"
/* Included by native wma_main.c. MC-thread-only private VDEV command path.
 * The caller owns a runtime work reservation and the referenced exact VDEV.
 * Unlike CLI posting, this returns the actual native WMI submission status
 * and does not create a second untracked scheduler message. No firmware ACK.
 */
int mishare_ndi_rate_command(struct wlan_objmgr_vdev *vdev, u32 param, u32 value)
{
    tp_wma_handle wma = cds_get_context(QDF_MODULE_ID_WMA);
    struct vdev_mlme_obj *mlme;
    u8 id;

    if (!vdev || !wma || !wma->interfaces || !wma->wmi_handle ||
        wma->psoc != wlan_vdev_get_psoc(vdev))
        return -ENODEV;
    id = wlan_vdev_get_id(vdev);
    if (id >= wma->max_bssid || wma->interfaces[id].vdev != vdev || !wma_is_vdev_valid(id))
        return -ENODEV;
    mlme = wlan_vdev_mlme_get_cmpt_obj(vdev);
    if (wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE || !mlme ||
        mlme->vdev != vdev || !mlme->ext_vdev_ptr ||
        mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI || mlme->mgmt.generic.subtype)
        return -EOPNOTSUPP;
    if (param != wmi_vdev_param_fixed_rate && param != wmi_vdev_param_sgi &&
        param != wmi_vdev_param_chwidth)
        return -EINVAL;
    if ((param == wmi_vdev_param_sgi && value > 3) ||
        (param == wmi_vdev_param_chwidth && value))
        return -EOPNOTSUPP;
    return qdf_status_to_os_return(wma_vdev_set_param(wma->wmi_handle, id, param, value));
}
#endif
