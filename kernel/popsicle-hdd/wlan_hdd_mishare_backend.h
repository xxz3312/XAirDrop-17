/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_BACKEND_H
#define WLAN_HDD_MISHARE_BACKEND_H
struct hdd_context;
/* Optional, default-disabled metadata-only binding. No radio initialization. */
int mishare_wonder_backend_register(struct hdd_context *hdd);
/* Nonzero keeps owner/descriptor: caller must retain native parents. Current
 * backend init cannot create resources; active-radio removal is not enabled. */
int mishare_wonder_backend_unregister(struct hdd_context *hdd);
#endif
