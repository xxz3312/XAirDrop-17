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
/* Exact registered adapter-pointer ownership only; NULL/pending adapter is not
 * a match. No adapter/HDD dereference, allocation or cleanup. Caller retains
 * its adapter/netdev reference and serializes parent transitions through the
 * resulting reset decision. Covers caller-owned and handed-off hosts until
 * registry retirement. Not a lease, radio readiness or SSR/remove clearance.
 */
bool mishare_wonder_host_adapter_owned(struct hdd_adapter *adapter);
/* Idle/mode-change stop admission only. Caller drains operations and holds
 * the exclusive driver/psoc transition through the native stop call. Covers
 * hosts before runtime creation AND standalone runtime owners. EBUSY retains
 * every object; no cleanup, firmware command or quarantine reset is attempted.
 * EUCLEAN rejects a retained host whose same HDD now names different parents,
 * including PSOC migration that would otherwise evade an exact-PSOC scan.
 * Zero is a serialized empty-registry observation, not SSR/remove clearance.
 */
int mishare_wonder_host_stop_ready_locked(struct hdd_context *hdd);
/* Explicit ordinary-idle ownership handoff. Same RTNL/exclusive parent
 * transition and lifetime contract as create/destroy. Success closes admission,
 * transfers the sole owner into the host registry and NULLs the caller slot;
 * caller must discard all aliases. It does not start/wait for cleanup or retain
 * the slot address. Invalid/recovering/open adapters leave ownership unchanged.
 * HDD/native components must remain alive until the registry is empty.
 * No automatic transfer is installed in Wonder or any other session caller.
 */
int mishare_wonder_host_handoff_idle_locked(struct mishare_wonder_host **owner);
/* Native ordinary idle entry only: caller holds exclusive PSOC transition and
 * has drained operations. Every exact-PSOC host must have explicitly handed
 * off ownership and still match this HDD/device/PDEV. Uses RTNL trylock only;
 * contention or asynchronous cleanup defers idle. Never steal ordinary owners,
 * clear quarantine, adopt standalone runtimes or authorize SSR/remove. Errors
 * retain registry ownership and pins; parent teardown remains blocked. Success
 * includes the existing host/runtime empty-registry admission check.
 */
int mishare_wonder_host_idle_prepare_locked(struct hdd_context *hdd);
/* Caller owns RTNL and an exclusive parent psoc transition throughout each call.
 * Owner access is serialized by that caller. Destroy before HDD context teardown.
 * Host holds device/PSOC/PDEV allocation references until successful close;
 * all three HDD identities must still match at every subsequent entry. Failed
 * creation unwinds pins; pending/error destruction retains them with the host.
 * References do not retain HDD, component state, firmware or transport. Caller
 * must prevent native parent teardown, including between asynchronous polls.
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
 * recovery policy and real final-free before adapter/sync close. Fully prepared
 * INIT with observed PE success and completed channel/START-plan preparation
 * may use the qualified reset path. A queued START actually flushed before
 * callback execution, or an exact pre-insertion scheduler rejection, can retire
 * its controller first. A callback refused by work admission after the original
 * SSR fence is also supported. Admitted work aborted before the serialized
 * preparation-entry gate can retire with its own provenance. Successful matching
 * preparation without any SM commitment has its own checked retirement route.
 * Committed intent denied by the native-entry gate can also retire; marked
 * native entry, failed/partial preparation and START/UP
 * stays unsupported.
 * Errors retain host and the updated runtime token; EINPROGRESS needs polling
 * after releasing locks. This permanently closes the session on admission.
 * Allocation pins do not hold native components, reset quarantine or authorize
 * physical remove; caller must still retain the full native parent lifetime.
 */
int mishare_wonder_host_reclaim_ssr_locked(struct mishare_wonder_host **owner);
/* Explicit SSR poll for hosts already handed off to the registry by the idle
 * handoff API. Requires RTNL, exclusive PSOC transition, exact HDD/parents and
 * the full native SSR qualification/lifetime contract of reclaim_ssr_locked.
 * Never adopts caller-owned hosts or standalone runtime tokens. Incomplete
 * registry coverage, pending cleanup and errors preserve authoritative host
 * ownership and updated runtime tokens for a later qualified poll. Success
 * includes empty runtime-batch preflight and combined registry admission.
 * No native SSR/remove caller, scheduling or blocking wait is installed.
 */
int mishare_wonder_host_reclaim_handoff_ssr_locked(struct hdd_context *hdd);
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
