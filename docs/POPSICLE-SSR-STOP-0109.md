# 0109 Retain private SSR parents on stop failure

## Native production changes

Patch 0041 inserts recovery-only admission at the end of the native CDS post-disable call in `hdd_wlan_stop_modules()`, before subsequent notifier, DP/PDEV/PSOC close. If CDS post-disable failed while private ownership remains, the function returns that failure before the original assertion/teardown continuation. If post-disable succeeded but the existing combined host/runtime/identity snapshot still refuses stop, its error is returned before the later close operations. This does not undo shutdown work already performed inside CDS post-disable.

`hdd_wlan_shutdown()` captures private ownership before calling module stop. A failed private stop is converted by the native QDF errno converter and returned before the normal completion tail. The capture is deliberately retained even if runtime/host metadata disappears during the lower call: empty metadata cannot prove that the remaining native parent stop completed.

The native internal SoC SSR shutdown arms a private-stop failure flag under the existing exclusive SSR PSOC transition before cleanup/HIF lookup, including early HIF-missing or unsupported EPPING exits. Only successful completion of that same private shutdown attempt clears it. A retained failure refuses duplicate shutdown execution, prevents the recovery reinit callback from entering native reinit, and reports the failure to start-complete waiters. No-private-owner behavior retains the existing vendor error/completion handling. No force-clear API or automatic retry is installed; metadata retirement alone cannot authorize reinit.

## Validation status

[Actions 41913522724](https://github.com/xxz3312/XAirDrop-17/actions/runs/41913522724)（`aefa112`）七项作业全部通过：53 项 Python 检查、15 组 SSR 场景、45 项变异控制、既有原生组合、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。快速/完整构建报告一致，57 份含生产源码的报告、七份精简 ZIP 摘要、五个原生体和重建夹具/原生源码哈希、旧审计及原生电源停机最终模块符号已核对。

The host fixture adds 15 controlled shutdown scenarios. It executes the entire patched native power shutdown, internal SoC shutdown and recovery-reinit callback, the bounded module-stop post-disable section, the existing complete native adapter-reset function and the unchanged native QDF errno-to-status converter with its original enum.

Scenarios cover retained owners on failed/successful CDS disable, pending stop, missing HIF, EPPING, duplicate stop refusal, reinit denial and failure notification, successful MODEL future qualified cleanup, metadata-retired-but-parent-stop-pending, no-owner legacy behavior, and suspend/IPA/capture branches. Eight new mutation controls remove the CDS-error/parent boundary, drop private error propagation or ownership capture, clear arming, replay shutdown, enter reinit or report false completion. All previous 37 controls and 62 native reset cases remain.

CDS stop, remaining parent close/probe, IRQ/HIF operations and references/locks remain model boundaries. A model callback inside the fake CDS window exercises one successful qualified cleanup and one metadata-retired/pending-stop case; this callback is NOT installed in production. The fixture does not execute the entire module-stop function or real parent teardown. Exact bounded reversals recover the pre-stage source and inherited whole-file audits; full WLAN builds require the native power shutdown symbol.

## Boundaries

This is private SSR failure containment and propagation, not a completed recovery coordinator. Actual qualified retirement at the CDS window, asynchronous continuation of a partially stopped parent, completion acknowledgement and a safe way to resume a failed attempt remain to be integrated. The failure flag is intentionally sticky after an unsuccessful attempt and cannot be cleared by merely emptying the owner registry. Physical remove/exit/close callers remain unchanged and still need coordination. Parent allocation references are not HDD/component/firmware leases. The radio backend remains disabled; no phone operation or Apple discovery/handshake/file transfer is enabled by this stage.

See [offline validation record](research/popsicle-ssr-stop-0109-validation.json).
