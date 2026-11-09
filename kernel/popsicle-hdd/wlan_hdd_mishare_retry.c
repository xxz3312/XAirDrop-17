// SPDX-License-Identifier: GPL-2.0-only
/* OPAirDrop stage3 mapping; native SME -> WMA sends synchronously, no MC post. */
#include <linux/errno.h>
#include <wlan_objmgr_vdev_obj.h>
#include <wlan_vdev_mlme_api.h>
#include <wlan_vdev_mlme.h>
#include "wlan_hdd_main.h"
#include "wma.h"
#include "wma_api.h"
#include "wma_internal.h"
#include "sme_api.h"
#include "wlan_hdd_mishare_retry.h"

int mishare_retry_submit_mc(struct wlan_objmgr_vdev *vdev, u8 data_limit,
                            u8 mgmt_limit,
                            struct mishare_retry_submission *receipt)
{
    tp_wma_handle wma;
    struct vdev_mlme_obj *mlme;
    int ret = 0;
    u8 id, group, value;

    if (!receipt)
        return -EINVAL;
    if (receipt->busy)
        return -EINPROGRESS;
    if (receipt->attempted)
        return receipt->first_error ? receipt->first_error : -EALREADY;
    wma = cds_get_context(QDF_MODULE_ID_WMA);
    if (!vdev || !wma || !wma->interfaces || !wma->wmi_handle ||
        wma->psoc != wlan_vdev_get_psoc(vdev))
        return -ENODEV;
    id = wlan_vdev_get_id(vdev);
    if (id >= wma->max_bssid || wma->interfaces[id].vdev != vdev ||
        !wma_is_vdev_valid(id))
        return -ENODEV;
    mlme = wlan_vdev_mlme_get_cmpt_obj(vdev);
    if (wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE || !mlme ||
        mlme->vdev != vdev || !mlme->ext_vdev_ptr ||
        mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI ||
        mlme->mgmt.generic.subtype)
        return -EOPNOTSUPP;

    receipt->busy = true;
    receipt->attempted = true;
    receipt->vdev_id = id;
    receipt->data_limit = data_limit;
    receipt->mgmt_limit = mgmt_limit;
    for (group = 0; group < 2; group++) {
        value = group ? mgmt_limit : data_limit;
        if (!value) {
            receipt->skipped_mask |= BIT(group);
            continue;
        }
        receipt->attempted_mask |= BIT(group);
        ret = qdf_status_to_os_return(sme_set_vdev_sw_retry(id, value,
                  group ? WMI_VDEV_CUSTOM_SW_RETRY_TYPE_NONAGGR :
                          WMI_VDEV_CUSTOM_SW_RETRY_TYPE_AGGR));
        if (ret)
            break;
        receipt->submitted_mask |= BIT(group);
    }
    receipt->first_error = ret;
    receipt->complete = !ret;
    receipt->busy = false;
    return ret;
}
