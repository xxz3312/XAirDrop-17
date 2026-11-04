# 0110 Native post-disable qualified host reclamation

## Production path

Patch 0042 replaces the recovery-only post-disable ownership snapshot with `mishare_wonder_host_ssr_prepare_locked()`. The native call occurs after CDS post-disable succeeds and before the later notifier/DP/PDEV/PSOC close operations. The existing private-error branch returns before this call on a failed CDS disable. No changes are made to ordinary idle or mode-change calls.

The production wrapper observes the existing combined host/runtime/parent-identity admission first. An empty registry preserves the native path. Busy ownership requires recovering state and exact registry ownership already explicitly handed off; standalone runtimes, caller-owned hosts and foreign/replaced parents are not adopted. RTNL is acquired with trylock only while the caller retains the native exclusive PSOC transition, then the existing qualified SSR bridge runs. RTNL is released for every result. The bridge still enforces original SSR fence, MC/work drain, qualified window and supported native state through runtime batch policy, preserves updated tokens on all errors/waits, and requires both registries empty for success.

Immediate qualified completion can now continue native parent stop through the real post-disable call. EINPROGRESS, lock contention, missing qualification, coverage errors or sync-close failure retain registry ownership and native parents at the 0109 boundary. The existing sticky failure gate continues to reject replay/reinit after an unsuccessful attempt. This stage does not schedule a later poll or resume the remaining native stop after asynchronous completion.

## Validation status

Production C fast validation passed in [Actions 41917643897](https://github.com/xxz3312/XAirDrop-17/actions/runs/41917643897) on `6f80bff`: 18 wrapper cases, seven new and 45 previous mutation controls, and existing host/native cases passed with sanitizers. 53 Python checks passed. Compact ZIP digest, production/native hashes, regenerated fixture and wrapper hash, bounded patch 0042 and inherited source audits match. Full diagnostic build and remaining regressions are still running; this is not full offline acceptance. The host fixture now lets the actual native post-disable section invoke production preparation and qualified reclamation. The fake CDS callback only supplies modeled qualification outcomes; it no longer performs retirement itself. The immediate-success and metadata-retired/pending-parent cases therefore depend on the installed production call.

Eighteen direct wrapper cases cover empty/invalid/standalone/caller-owned/changed-parent admission, non-recovery refusal, already-held or contended RTNL, three qualification/error results, incomplete coverage, token retention, sync mismatch after runtime retirement and a later complete close. Seven new controls target lock/error/recovery/ownership admission, qualified-vs-ordinary cleanup, unlock and replacing the native callback with a snapshot. Previous 45 controls, 62 native adapter reset cases, 15 native shutdown/reinit scenarios and 36 direct host identity refusals remain.

Qualification primitives, runtime batch completion, real lock/IRQ/DMA timing and later native parent/probe operations remain model boundaries in this host fixture; the existing separate production runtime/native fixtures continue. Full WLAN builds require the new wrapper symbol. Workflow concurrency is scoped by ref and source commit so a newer stage does not cancel an older source validation; duplicate runs for the same commit retain cancellation behavior.

## Remaining integration

Automatic backend handoff is not installed; active caller-owned sessions remain protected rather than seized. Native runtime policy still rejects unsupported active START/UP or quarantine states. A pending qualified retirement must later resume the partially completed stop without replaying CDS teardown, complete parent destruction and acknowledge completion before the 0109 failure gate can safely permit reinit. No automatic async resume or force-clear is added. Physical remove/close and complete parent-component lifetime coordination remain pending. The radio backend remains disabled; no phone operation or Apple discovery/handshake/two-way file result is enabled.

See [validation checkpoint](research/popsicle-ssr-prepare-0110-validation.json).
