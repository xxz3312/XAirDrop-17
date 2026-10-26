/* SPDX-License-Identifier: GPL-2.0 */
#ifndef WONDER_POPSICLE_MAC80211_ABI_H
#define WONDER_POPSICLE_MAC80211_ABI_H

#include <linux/build_bug.h>
#include <linux/stddef.h>
#include <net/mac80211.h>

/*
 * Offsets read by ieee80211_alloc_hw_nm in the captured stock mac80211.ko:
 * SHA256 01b40a32346277f30b807d31c4acd7011e18c38bdff594282f5e835d40f40dec.
 * See docs/research/popsicle-mac80211-allocator-audit.json.
 * These check allocator callback slots only, not complete mac80211 ABI safety.
 * Do not add padding or edit callback layouts to satisfy a failed assertion.
 */
#define POPSICLE_OP_SLOT(member, byte_offset) \
	static_assert(offsetof(struct ieee80211_ops, member) == (byte_offset), \
		      "stock mac80211 callback offset mismatch: " #member)

POPSICLE_OP_SLOT(tx, 0x000);
POPSICLE_OP_SLOT(start, 0x008);
POPSICLE_OP_SLOT(stop, 0x010);
POPSICLE_OP_SLOT(add_interface, 0x030);
POPSICLE_OP_SLOT(remove_interface, 0x040);
POPSICLE_OP_SLOT(config, 0x048);
POPSICLE_OP_SLOT(bss_info_changed, 0x050);
POPSICLE_OP_SLOT(vif_cfg_changed, 0x058);
POPSICLE_OP_SLOT(link_info_changed, 0x060);
POPSICLE_OP_SLOT(configure_filter, 0x080);
POPSICLE_OP_SLOT(sta_add, 0x108);
POPSICLE_OP_SLOT(sta_remove, 0x110);
POPSICLE_OP_SLOT(sta_state, 0x128);
POPSICLE_OP_SLOT(add_chanctx, 0x250);
POPSICLE_OP_SLOT(remove_chanctx, 0x258);
POPSICLE_OP_SLOT(change_chanctx, 0x260);
POPSICLE_OP_SLOT(assign_vif_chanctx, 0x268);
POPSICLE_OP_SLOT(unassign_vif_chanctx, 0x270);
POPSICLE_OP_SLOT(wake_tx_queue, 0x2f0);

#undef POPSICLE_OP_SLOT
#endif
