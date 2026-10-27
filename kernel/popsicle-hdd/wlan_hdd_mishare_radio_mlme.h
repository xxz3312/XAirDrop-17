/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_RADIO_MLME_H
#define WLAN_HDD_MISHARE_RADIO_MLME_H
#include <qdf_status.h>
#include <wlan_vdev_mlme.h>
#define MISHARE_RADIO_OP(name) \
QDF_STATUS name(struct vdev_mlme_obj *mlme, uint16_t len, void *data)
MISHARE_RADIO_OP(mishare_radio_validate);
MISHARE_RADIO_OP(mishare_radio_start_send);
MISHARE_RADIO_OP(mishare_radio_start_continue);
MISHARE_RADIO_OP(mishare_radio_up_send);
MISHARE_RADIO_OP(mishare_radio_up_complete);
MISHARE_RADIO_OP(mishare_radio_stop_send);
MISHARE_RADIO_OP(mishare_radio_stop_continue);
MISHARE_RADIO_OP(mishare_radio_down_send);
MISHARE_RADIO_OP(mishare_radio_down_complete);
#undef MISHARE_RADIO_OP
QDF_STATUS mishare_radio_beacon(struct vdev_mlme_obj *mlme,
                                enum beacon_update_op op, uint16_t len, void *data);
QDF_STATUS mishare_radio_disconnect(struct vdev_mlme_obj *mlme, uint16_t len,
                                    void *data, bool legacy_only);
QDF_STATUS mishare_radio_start_rsp(struct vdev_mlme_obj *mlme,
                                   struct vdev_start_response *rsp);
QDF_STATUS mishare_radio_stop_rsp(struct vdev_mlme_obj *mlme,
                                  struct vdev_stop_response *rsp);
#endif
