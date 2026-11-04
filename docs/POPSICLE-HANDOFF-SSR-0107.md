# 0107 Qualified SSR polling for handed-off hosts

## Production changes

`mishare_wonder_host_reclaim_handoff_ssr_locked(hdd)` lets a caller holding RTNL, the exclusive PSOC transition and the complete native parent lifetime advance a host whose sole owner was previously handed off to the registry. It rejects missing recovery state, caller-owned hosts and mismatched HDD/device/PSOC/PDEV identity before handing any token to the existing qualified SSR bridge.

The existing `mishare_wonder_host_reclaim_ssr_locked()` remains the cleanup authority. It validates exact runtime-registry coverage, delegates original SSR fence/MC-drain/recovery-window policy to `mishare_runtime_reclaim_batch()`, restores updated runtime tokens on every result and closes the host only after runtime retirement. The new entry preserves registry ownership through omitted-owner rejection, asynchronous polls, policy/quarantine errors and sync-close failure after runtime completion. No discarded caller slot is retained or required. It uses an empty runtime-batch preflight and the combined host/runtime admission check before reporting completion; standalone runtimes are never adopted.

A shared-preflight bug is also fixed: a retained host pointing to the same HDD but its old PSOC must not disappear from consideration when that HDD now names another PSOC. Ordinary native idle now rejects that migration before any cleanup attempt. The idle/mode stop admission snapshot separately checks all retained hosts of this same HDD against their pinned parents, so a migrated PSOC cannot bypass the mode gates either. Genuinely foreign HDD/PSOC pairs retain their existing behavior.

## Validation

[Actions 41875529467](https://github.com/xxz3312/XAirDrop-17/actions/runs/41875529467)（`0e57e50`）七项作业全部通过：53 项 Python 检查、生产 host/runtime 快速夹具、32 项变异控制、36 次父身份拒绝及 SSR 序列、完整 WLAN 编译、CNSS、严格链接、七项布局与模块记录检查通过。快速/完整构建报告一致，57 份含生产源码的报告、七份精简 ZIP 摘要和新增 SSR API 的最终模块符号已核对。

The production-host fixture adds missing-recovery and identity refusal, caller ownership preservation, standalone-runtime coverage, nine repeated policy/wait results, runtime retirement followed by sync failure and subsequent successful registry-owned close, plus runtime-free host coverage. The model tracks actual allocated runtime tokens and checks that creation/destruction/batch retirement balance them. Six new mutation controls target migrated-parent admission, SSR admission, qualified-vs-ordinary retirement, error propagation and preflight refusal; all previous 26 controls and 36 direct host parent-identity refusals remain. Full object/module checks now require the new API symbol.

The fixture runs the actual production host functions. Runtime batch results, synchronization, references and parent storage are models here; the existing separate runtime and native cleanup fixtures continue to exercise their production policy/native bodies. This does not constitute a single end-to-end native SSR teardown test.

## Integration still required

No native SSR/remove caller, idle trigger or automatic backend handoff is installed. Current native SSR resets adapters before its qualified CDS recovery window; module-stop and some upper teardown paths also continue despite lower errors. Those entry/exit/error paths must retain parents and handle asynchronous retirement before an automatic call is safe. The new explicit poll alone does not fix that orchestration, qualify active START/UP recovery, permit physical removal, clear quarantine or authorize backend activation. References retain allocations, not HDD/components/firmware. Backend remains disabled; no phone operation or Apple discovery/handshake/file-transfer success is claimed.

See [offline validation record](research/popsicle-handoff-ssr-0107-validation.json). The first run passed production cases but a deliberate error-suppression mutation triggered an earlier adapter-running assertion without its expected marker. Adding that marker let all controls complete; production C was unchanged.
