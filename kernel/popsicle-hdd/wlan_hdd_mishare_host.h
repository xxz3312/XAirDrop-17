/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_HOST_H
#define WLAN_HDD_MISHARE_HOST_H
#include <linux/types.h>
struct hdd_context;
struct hdd_adapter;
struct mishare_wonder_host;
/* Caller owns RTNL and an exclusive parent psoc transition throughout each call.
 * Owner access is serialized by that caller. Destroy before HDD context teardown.
 * Success means a DOWN host adapter only, never Wonder/radio initialization.
 */
int mishare_wonder_host_create_locked(struct hdd_context *hdd, const u8 *mac,
                                    struct mishare_wonder_host **owner);
int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **owner);
/* Internal HDD factory, also requires RTNL and the parent transition. */
struct hdd_adapter *hdd_mishare_host_adapter_open(struct hdd_context *hdd, u8 *mac);
#endif
