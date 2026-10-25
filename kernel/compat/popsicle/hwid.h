/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Narrow interface recovered and rechecked for the recorded popsicle firmware.
 * Reference: cupid-development/android_kernel_xiaomi_sm8450 commit
 * 060fed194023de6ed41cb25e9a15cfa307b05469, drivers/misc/hwid/hwid.h.
 * A fresh candidate gendwarfksyms signature probe emits 0x0f600de8 for both
 * uint32_t(void) getters, matching the real stock WLAN import CRCs. Its
 * cm_fw_roam_invoke_fail relocation at .text+0x4dc95c calls the country getter;
 * the result is kept in w26 and tested against zero at .text+0x4dca08.
 * These observations only cover this narrow interface on the recorded
 * firmware. They do not establish general driver ABI or firmware compatibility.
 * This is not the complete Xiaomi header and supplies no implementations.
 */
#ifndef XAIR_DROP_POPSICLE_HWID_H
#define XAIR_DROP_POPSICLE_HWID_H
#include <linux/types.h>
#define CountryCN 0x00
uint32_t get_hw_country_version(void);
uint32_t get_hw_version_platform(void);
#endif
