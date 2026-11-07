// SPDX-License-Identifier: GPL-2.0-only
/* Fixed-rate submission derived from OPAirDrop stage3 HDD ops. No auto caller. */
#include <linux/errno.h>
#include <wlan_objmgr_vdev_obj.h>
#include <wlan_vdev_mlme_api.h>
#include <wlan_vdev_mlme.h>
#include "wlan_hdd_main.h"
#include "wma_api.h"
#include "wlan_hdd_mishare_rate.h"

static int mishare_rate_encode(const struct wondertap_fixed_tx_rate_params *p,
                                u32 *rate, u8 *gi)
{
    u8 preamble;
    int ret = mishare_rate_check(p);

    if (ret)
        return ret;
    switch (p->preamble) {
    case WONDERTAP_RATE_PREAMBLE_HT: preamble = WMI_RATE_PREAMBLE_HT; break;
    case WONDERTAP_RATE_PREAMBLE_VHT: preamble = WMI_RATE_PREAMBLE_VHT; break;
    case WONDERTAP_RATE_PREAMBLE_HE: preamble = WMI_RATE_PREAMBLE_HE; break;
    case WONDERTAP_RATE_PREAMBLE_EHT: preamble = WMI_RATE_PREAMBLE_EHT; break;
    default: return -EOPNOTSUPP;
    }
    switch (p->gi) {
    case WONDERTAP_RATE_GI_SHORT: *gi = 1; break;
    case WONDERTAP_RATE_GI_1_6_US: *gi = 2; break;
    case WONDERTAP_RATE_GI_3_2_US: *gi = 3; break;
    default: *gi = 0; break;
    }
    *rate = hdd_assemble_rate_code(preamble, p->nss - 1, p->mcs);
    return 0;
}

int mishare_rate_submit(struct wlan_objmgr_vdev *vdev,
                         const struct wondertap_fixed_tx_rate_params *params,
                         struct mishare_rate_submission *receipt)
{
    struct vdev_mlme_obj *mlme;
    u32 rate;
    u8 gi;
    int ret;

    if (!receipt)
        return -EINVAL;
    if (receipt->busy)
        return -EINPROGRESS;
    if (receipt->attempted)
        return receipt->first_error ? receipt->first_error : -EALREADY;
    if (!vdev)
        return -EINVAL;
    ret = mishare_rate_encode(params, &rate, &gi);
    if (ret)
        return ret;
    mlme = wlan_vdev_mlme_get_cmpt_obj(vdev);
    if (wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE || !mlme ||
        mlme->vdev != vdev || !mlme->ext_vdev_ptr ||
        mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI || mlme->mgmt.generic.subtype)
        return -EOPNOTSUPP;

    receipt->busy = true;
    receipt->attempted = true;
    receipt->vdev_id = wlan_vdev_get_id(vdev);
    receipt->attempted_mask = BIT(0);
    ret = wma_cli_set_command(receipt->vdev_id, wmi_vdev_param_fixed_rate, rate, VDEV_CMD);
    if (ret)
        goto finish;
    receipt->submitted_mask = BIT(0);
    receipt->attempted_mask |= BIT(1);
    ret = wma_cli_set_command(receipt->vdev_id, wmi_vdev_param_sgi, gi, VDEV_CMD);
    if (ret)
        goto finish;
    receipt->submitted_mask |= BIT(1);
    receipt->attempted_mask |= BIT(2);
    ret = wma_cli_set_command(receipt->vdev_id, wmi_vdev_param_chwidth,
                              WONDERTAP_RATE_BW_20, VDEV_CMD);
    if (ret)
        goto finish;
    receipt->submitted_mask |= BIT(2);
    receipt->complete = true;
finish:
    receipt->first_error = ret;
    receipt->busy = false;
    return ret;
}
