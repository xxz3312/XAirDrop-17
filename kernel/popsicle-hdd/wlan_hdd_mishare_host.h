/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_HOST_H
#define WLAN_HDD_MISHARE_HOST_H
#include <linux/types.h>
#include "wlan_hdd_mishare_module_lease.h"
struct hdd_context;
struct hdd_adapter;
struct mishare_wonder_host;
struct wlan_objmgr_psoc;
struct wlan_objmgr_pdev;
struct device;
struct wondertap_init_params;
struct mishare_init_request;
/* One-shot handoff receipt, zero-initialized and never copied/reset while
 * live. Contains no borrowed HDD/host pointer. The serial cannot be reused
 * within this module lifetime; the independent lease pins text until poll
 * observes actual host retirement. Caller also pins text through API return.
 */
struct mishare_host_retirement {
    u64 serial;
    struct mishare_module_lease module_lease;
};
/* Same qualified ordinary-idle handoff contract as handoff_idle_locked.
 * Success transfers the host and publishes a receipt; it is NOT destruction.
 * Failure preserves caller ownership and leaves an empty receipt.
 */
int mishare_wonder_host_handoff_receipt_locked(struct mishare_wonder_host **owner,
                                               struct mishare_host_retirement *receipt);
/* Serialized receipt-owner access, no RTNL/PSOC/HDD needed. EINPROGRESS while
 * that exact host is registered; 0 consumes the receipt only after host free.
 * Does not initiate cleanup, prove global registry emptiness or grant SSR.
 */
int mishare_wonder_host_retirement_poll(struct mishare_host_retirement *receipt);
/* Ordinary process-context poll of one handed-off host under RTNL/exclusive
 * PSOC transition. No global stop, forced reset or SSR qualification implied.
 */
int mishare_wonder_host_retire_receipt_locked(struct hdd_context *hdd,
                                              struct mishare_host_retirement *receipt);
/* Internal instance factory/progression: no public Wonder init caller yet.
 * Factory owns a device allocation reference and text lease, not native
 * component lifetime. Caller pins text and serializes its handle throughout
 * calls. step is process context outside RTNL/native ops/transition; 0 means
 * radio UP only. poll-retire never waits for native locks or frees metadata;
 * process-retire clears *handle only after actual host/receipt/instance free.
 */
int mishare_wonder_managed_create(struct device *dev, void **handle);
/* Immutable metadata preparation under a fresh native scope. NSS arguments
 * must be platform-validated by the caller; this checks their numeric domain
 * only. Success is NOT country/regulatory/rate/RX/TX or native parent lifetime
 * authorization. Prepared requests cannot enter the raw step shortcut.
 */
int mishare_wonder_managed_prepare(void *handle, const struct wondertap_init_params *params,
                                   u8 nss_2g, u8 nss_5g);
/* Internal process-context typed preparation. Caller is outside native ops,
 * transition and RTNL and retains HDD/components/firmware across polls.
 * Instance serializes its one authoritative raw/typed owner, owns text/device
 * pins, and re-enters a fresh native scope each call. Zero means only BSSID,
 * MAC/channel/fixed-rate/retry prestart submissions, never public init or UP.
 * Retire through existing managed retire/process entries, even after errors.
 * An attempted typed instance now remains visible to native parent-stop gates
 * until actual instance retirement, even with no host after allocation failure.
 * Fresh scopes reject replacement HDD/PSOC/PDEV identities. This is a parent
 * retirement fence, NOT firmware readiness. The native qualified post-disable
 * path can now claim and retire this typed owner, closing it permanently;
 * metadata remains for caller process-retire. No public init is installed.
 */
int mishare_wonder_managed_prestart_step(void *handle);
/* Internal read-only observation under a fresh scope; zero is current
 * pre-START configuration consistency, not radio UP or START authorization. */
int mishare_wonder_managed_start_ready(void *handle);
/* Internal owned-MC native START encoder preview, zero means a summary only.
 * Public initialization, actual NDI START-plan and radio START remain closed. */
int mishare_wonder_managed_plan_step(void *handle);
/* Internal adoption of an already completed preview, with fresh full-request
 * checks on every poll. Neither creates a preview nor starts the radio. */
int mishare_wonder_managed_plan_commit_step(void *handle);
int mishare_wonder_host_plan_commit_step_locked(struct mishare_wonder_host *host,
                                                const struct mishare_init_request *request,
                                                u8 nss_2g, u8 nss_5g);
int mishare_wonder_host_plan_step_locked(struct mishare_wonder_host *host,
                                          const struct mishare_init_request *request,
                                          u8 nss_2g, u8 nss_5g);
int mishare_wonder_host_start_ready_locked(struct mishare_wonder_host *host,
                                            const struct mishare_init_request *request,
                                            u8 nss_2g, u8 nss_5g);
int mishare_wonder_managed_step(void *handle, const u8 *mac, u32 freq,
                                u8 nss_2g, u8 nss_5g);
int mishare_wonder_managed_retire(void **handle);
int mishare_wonder_managed_retire_process(void **handle);
/* Host lifetime observation for the native idle-shutdown path. The caller must
 * hold the exclusive psoc transition after draining operations, through its
 * decision and module stop. Creation/retirement use that same transition.
 * Covers allocation before runtime creation, asynchronous drain and close,
 * plus attempted typed instances until process retirement.
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
 * hosts before runtime creation, attempted typed instances AND standalone
 * runtime owners. EBUSY retains
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
/* Native recovery post-disable entry, after successful CDS post-disable and
 * before DP/PDEV/PSOC close. Caller retains the exclusive PSOC transition and
 * all exact native parents. Empty registries preserve the original stop path.
 * Attempted typed managed instances can be claimed/closed and reclaimed through
 * their authoritative owner slot; busy, malformed or migrated instances retain
 * parents. Existing handed-off hosts remain eligible; raw caller-owned hosts
 * are never adopted. Actual retirement detaches a typed instance parent fence,
 * retaining closed metadata/module/device pins for later process-retire.
 * Uses RTNL trylock only and releases it on every result. Pending/error retains the
 * authoritative registry tokens and must prevent parent close/reinit. This
 * does not schedule retries, resume a partial stop or clear failure admission.
 */
int mishare_wonder_host_ssr_prepare_locked(struct hdd_context *hdd);
enum mishare_ssr_stop_phase {
    MISHARE_SSR_STOP_EMPTY,
    MISHARE_SSR_STOP_PREFIX,
    MISHARE_SSR_STOP_POST_DISABLED,
    MISHARE_SSR_STOP_PARENTS,
};
/* Native module-stop journal, initially zero. One native slot deliberately
 * fails closed for a second HDD while a private stop is retained. Serialized
 * internally against other PSOCs; the caller also owns its exclusive PSOC
 * transition and retains HDD/native parents. These are borrowed identities,
 * not allocation/component leases. The independent module_lease retains code
 * until successful native module completion; failures/waits retain it. Never
 * copy, zero or reuse a retained slot.
 * A qualified POST_DISABLED wait may explicitly resume the native suffix.
 * No reset interface; the SoC/power completion gate is separately authoritative.
 */
struct mishare_ssr_stop_checkpoint {
    struct mishare_module_lease module_lease;
    struct hdd_context *hdd;
    struct device *parent_dev;
    struct wlan_objmgr_psoc *psoc;
    struct wlan_objmgr_pdev *pdev;
    enum mishare_ssr_stop_phase phase;
    int first_error;
    int driver_status;
    bool paused;
};
int mishare_ssr_stop_begin_locked(struct mishare_ssr_stop_checkpoint *checkpoint,
                                 struct hdd_context *hdd, bool *tracked);
int mishare_ssr_stop_step_locked(struct mishare_ssr_stop_checkpoint *checkpoint,
                                struct hdd_context *hdd,
                                enum mishare_ssr_stop_phase phase,
                                int result, bool tracked);
int mishare_ssr_stop_finish_locked(struct mishare_ssr_stop_checkpoint *checkpoint,
                                  struct hdd_context *hdd, int result,
                                  bool modules_closed, bool tracked);
/* Only EINPROGRESS/EAGAIN at POST_DISABLED is retryable. Pause retains the
 * phase and exact native parents without turning a wait into a permanent
 * failure. Resume atomically consumes that wait; a second claimant, earlier
 * prefix failure, parent-close failure or changed native state is refused.
 * Caller retains the original exclusive transition/full parent lifetime;
 * these APIs do not schedule work or establish a new recovery window.
 */
int mishare_ssr_stop_pause_locked(struct mishare_ssr_stop_checkpoint *checkpoint,
                                 struct hdd_context *hdd, int result, bool tracked);
int mishare_ssr_stop_resume_locked(struct mishare_ssr_stop_checkpoint *checkpoint,
                                  struct hdd_context *hdd, bool *tracked);
/* Explicit native module suffix only. Does not replay CDS/power/SoC prefixes,
 * run the remaining power-completion tail, clear the SoC blocked flag or
 * authorize reinit/remove. Must be called under the retained native transition
 * with drained operations and full native parents, in recovering mission mode.
 */
int hdd_mishare_resume_stop_modules(struct hdd_context *hdd);
/* Native power-layer continuation: module suffix success followed by the same
 * LPASS/SMMU completion tail as ordinary shutdown. Returns the original errno;
 * an empty module journal is not completion. Called by native recovery reinit
 * under its retained transition; no worker, timer or forced reset is installed.
 */
int hdd_mishare_resume_shutdown(struct hdd_context *hdd);
/* IPCI remove admission only, BEFORE PSOC sync unregister and after native
 * exclusive transition/operation drain. Does not reclaim an owner or bless
 * hot unplug. Failure retains the registered sync/transition and HDD parents.
 */
int mishare_ssr_stop_remove_ready_locked(struct mishare_ssr_stop_checkpoint *c,
                                        struct hdd_context *hdd);
int hdd_mishare_module_remove_ready(struct hdd_context *hdd);
int hdd_mishare_remove_prepare(struct device *dev);
/* Admission for explicit driver unload under its exclusive transition after
 * draining operations. Global registries and journal must be empty. This
 * cannot veto the kernel module exit callback or prevent physical removal.
 */
int hdd_mishare_module_unload_ready(bool upper_blocked);
int hdd_mishare_unload_ready(void);
int mishare_ssr_stop_unload_ready_locked(struct mishare_ssr_stop_checkpoint *c,
                                        bool upper_blocked);
/* Caller owns RTNL and an exclusive parent psoc transition throughout each call.
 * Owner access is serialized by that caller. Destroy before HDD context teardown.
 * Host holds device/PSOC/PDEV allocation references until successful close;
 * Each host also owns one THIS_MODULE reference through final registry removal;
 * this does not retain a standalone stop journal or upper power gate.
 * All three HDD identities must still match at every subsequent entry. Failed
 * creation unwinds pins; pending/error destruction retains them with the host.
 * References do not retain HDD, component state, firmware or transport. Caller
 * must prevent native parent teardown, including between asynchronous polls.
 * Success means a DOWN host adapter only, never Wonder/radio initialization.
 */
int mishare_wonder_host_create_locked(struct hdd_context *hdd, const u8 *mac,
                                    struct mishare_wonder_host **owner);
int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **owner);
/* Qualified SSR-only retirement bridge, used by post-disable preparation. Same
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
 * Native post-disable reaches this through ssr_prepare_locked; no automatic
 * retry, blocking wait or physical-remove coordinator is installed.
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
/* Internal pre-START preparation only; caller holds RTNL/exclusive native
 * transition and retains the same parents across polls. Zero is fixed-rate
 * submission completion, not radio UP or full Wonder initialization. */
/* Bind frozen BSSID to host MLME before firmware CREATE/PE. */
int mishare_wonder_host_bssid_bind_locked(struct mishare_wonder_host *host, const u8 *bssid);
struct mishare_init_request;
/* Read-only native admission under caller's exclusive transition + RTNL.
 * Does not set country, retain parents across calls or authorize full init. */
int mishare_wonder_request_preflight_locked(struct hdd_context *hdd,
                                            const struct mishare_init_request *request,
                                            u8 nss_2g, u8 nss_5g);
struct wondertap_fixed_tx_rate_params;
int mishare_wonder_host_retry_step_locked(struct mishare_wonder_host *host,
                                           u8 data_limit, u8 mgmt_limit);
int mishare_wonder_host_prestart_step_locked(struct mishare_wonder_host *host,
                                             u32 freq, u8 nss_2g, u8 nss_5g,
                                             const struct wondertap_fixed_tx_rate_params *params);
int mishare_wonder_host_session_step_locked(struct mishare_wonder_host *host,
                                            u32 freq, u8 nss_2g, u8 nss_5g);
#ifdef CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER
/* Complete HDD teardown result for a future external controller. The caller
 * must pin WLAN and exclude every load/mode/unload entry for the entire call.
 * No final module-reference release and no retry permission on failure.
 * Not exported, installed as a callback, or exposed to userspace yet.
 */
int hdd_mishare_driver_unload_checked(void);
#endif
/* Internal HDD factory, also requires RTNL and the parent transition. */
struct hdd_adapter *hdd_mishare_host_adapter_open(struct hdd_context *hdd, u8 *mac);
#endif
