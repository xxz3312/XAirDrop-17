/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Narrow interface recovered from the earlier popsicle investigation.
 * Reference: cupid-development/android_kernel_xiaomi_sm8450 commit
 * 060fed194023de6ed41cb25e9a15cfa307b05469, drivers/misc/hwid/hwid.h.
 * Previous offline checks recorded uint32_t(void) export CRC 0x0f600de8
 * for both getters and CountryCN == 0 in the stock WLAN call path.
 * Those checks must be repeated against the target before using this header.
 * This is not the complete Xiaomi header and supplies no implementations.
 */
#ifndef XAIR_DROP_POPSICLE_HWID_H
#define XAIR_DROP_POPSICLE_HWID_H
#include <linux/types.h>
#define CountryCN 0x00
uint32_t get_hw_country_version(void);
uint32_t get_hw_version_platform(void);
#endif
