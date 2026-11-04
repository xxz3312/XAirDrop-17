# 0109 Retain private SSR parents on stop failure

## Native production changes

Patch 0041 inserts recovery-only admission at the end of the native CDS post-disable call in `hdd_wlan_stop_modules()`, before subsequent notifier, DP/PDEV/PSOC close. If CDS post-disable failed while private ownership remains, the function returns that failure before the original assertion/teardown continuation. If post-disable succeeded but the existing combined host/runtime/identity snapshot still refuses stop, its error is returned before the later close operations. This does not undo shutdown work already performed inside CDS post-disable.

`hdd_wlan_shutdown()` captures private ownership before calling module stop. A failed private stop is converted by the native QDF errno converter and returned before the normal completion tail. The capture is deliberately retained even if runtime/host metadata disappears during the lower call: empty metadata cannot prove that the remaining native parent stop completed.

The native internal SoC SSR shutdown arms a private-stop failure flag under the existing exclusive SSR PSOC transition before cleanup/HIF lookup, including early HIF-missing or unsupported EPPING exits. Only successful completion of that same private shutdown attempt clears it. A retained failure refuses duplicate shutdown execution, prevents the recovery reinit callback from entering native reinit, and reports the failure to start-complete waiters. No-private-owner behavior retains the existing vendor error/completion handling. No force-clear API or automatic retry is installed; metadata retirement alone cannot authorize reinit.

## Validation status

Production C fast validation passed in [Actions 41913522724](https://github.com/xxz3312/XAirDrop-17/actions/runs/41913522724) on `aefa112`: 15 SSR scenarios, eight new and 37 previous mutation controls, and existing host checks passed with sanitizers. 53 Python checks passed. Native/production source hashes, regenerated fixture and five native-body hashes, ZIP digest, three-file patch reversal and inherited source audits match. Full diagnostic build and remaining regressions are still running; this is not full offline acceptance. The host fixture adds 15 controlled shutdown scenarios. It executes the entire patched native power shutdown, internal SoC shutdown and recovery-reinit callback, the bounded module-stop post-disable section, the existing complete native adapter-reset function and the unchanged native QDF errno-to-status converter with its original enum.

Scenarios cover retained owners on failed/successful CDS disable, pending stop, missing HIF, EPPING, duplicate stop refusal, reinit denial and failure notification, successful MODEL future qualified cleanup, metadata-retired-but-parent-stop-pending, no-owner legacy behavior, and suspend/IPA/capture branches. Eight new mutation controls remove the CDS-error/parent boundary, drop private error propagation or ownership capture, clear arming, replay shutdown, enter reinit or report false completion. All previous 37 controls and 62 native reset cases remain.

CDS stop, remaining parent close/probe, IRQ/HIF operations and references/locks remain model boundaries. A model callback inside the fake CDS window exercises one successful qualified cleanup and one metadata-retired/pending-stop case; this callback is NOT installed in production. The fixture does not execute the entire module-stop function or real parent teardown. Exact bounded reversals recover the pre-stage source and inherited whole-file audits; full WLAN builds require the native power shutdown symbol.

## Boundaries

This is private SSR failure containment and propagation, not a completed recovery coordinator. Actual qualified retirement at the CDS window, asynchronous continuation of a partially stopped parent, completion acknowledgement and a safe way to resume a failed attempt remain to be integrated. The failure flag is intentionally sticky after an unsuccessful attempt and cannot be cleared by merely emptying the owner registry. Physical remove/exit/close callers remain unchanged and still need coordination. Parent allocation references are not HDD/component/firmware leases. The radio backend remains disabled; no phone operation or Apple discovery/handshake/file transfer is enabled by this stage.

See [validation checkpoint](research/popsicle-ssr-stop-0109-validation.json).
