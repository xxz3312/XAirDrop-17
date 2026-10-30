/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_HOST_H
#define WLAN_HDD_MISHARE_HOST_H
#include <linux/types.h>
struct hdd_context;
struct hdd_adapter;
struct mishare_wonder_host;
struct wlan_objmgr_psoc;
/* Host lifetime observation for the native idle-shutdown path. The caller must
 * hold the exclusive psoc transition after draining operations, through its
 * decision and module stop. Creation/retirement use that same transition.
 * Covers allocation before runtime creation, asynchronous drain and close.
 * Not a reference, SSR/remove barrier, firmware or radio readiness predicate.
 */
bool mishare_wonder_host_psoc_busy(struct wlan_objmgr_psoc *psoc);
/* Caller owns RTNL and an exclusive parent psoc transition throughout each call.
 * Owner access is serialized by that caller. Destroy before HDD context teardown.
 * Success means a DOWN host adapter only, never Wonder/radio initialization.
 */
int mishare_wonder_host_create_locked(struct hdd_context *hdd, const u8 *mac,
                                    struct mishare_wonder_host **owner);
int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **owner);
/* Explicit SSR-only retirement bridge; no automatic shutdown caller. Same
 * RTNL/exclusive psoc serialization as create/destroy. Retain exact parents
 * and serialize teardown through EVERY asynchronous poll. Requires native
 * SSR qualification; a recovering flag alone is not an IRQ/MC/DP barrier.
 * The single runtime token must cover the complete exact-psoc registry; extra
 * owners return EBUSY. Batch enforces original SSR fence, MC drain, supported
 * recovery policy and real final-free before adapter/sync close. Prepared/UP
 * recovery stays unsupported unless ordinary cleanup already completed.
 * Errors retain host and the updated runtime token; EINPROGRESS needs polling
 * after releasing locks. This permanently closes the session on admission.
 * This does not hold parents, reset quarantine or authorize physical remove.
 */
int mishare_wonder_host_reclaim_ssr_locked(struct mishare_wonder_host **owner);
/* Optional host vdev attachment. Retain host/adapter on EINPROGRESS/EUCLEAN;
 * destroy_locked also drains this attachment before freeing the netdev.
 * No SME session, firmware CREATE/DELETE, START/STOP or radio operation.
 */
int mishare_wonder_host_vdev_create_locked(struct mishare_wonder_host *host);
int mishare_wonder_host_vdev_destroy_locked(struct mishare_wonder_host *host);
/* Progress the existing host-owned runtime through NDI CREATE, self-peer, PE,
 * channel, START plan and radio START. Same RTNL/exclusive psoc contract.
 * One submission per call, no waiting. EINPROGRESS requires releasing caller
 * locks before polling; 0 requires observed radio UP + host_up, not RX ready.
 * NSS must come from platform validation, freq from the intended session.
 * Config is fixed at first call. Errors are sticky; drain via existing destroy
 * APIs while retaining parents. Destroy permanently closes this host session.
 * No automatic Wonder/backend caller is installed by this API.
 */
int mishare_wonder_host_session_step_locked(struct mishare_wonder_host *host,
                                            u32 freq, u8 nss_2g, u8 nss_5g);
/* Internal HDD factory, also requires RTNL and the parent transition. */
struct hdd_adapter *hdd_mishare_host_adapter_open(struct hdd_context *hdd, u8 *mac);
#endif
