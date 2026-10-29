/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_MGMT_RX_H
#define WLAN_HDD_MISHARE_MGMT_RX_H
struct hdd_adapter;
struct wlan_hdd_link_info;
int mishare_mgmt_rx_register(struct hdd_adapter *adapter);
void mishare_mgmt_rx_unregister(struct hdd_adapter *adapter);
bool mishare_mgmt_rx_route(struct wlan_hdd_link_info *link,
                          const unsigned char *frame, unsigned int length);
#endif
