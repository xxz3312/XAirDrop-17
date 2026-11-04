# 0104 Production idle and mode-change stop admission

离线验收完成：[CI 41796505527](https://github.com/xxz3312/XAirDrop-17/actions/runs/41796505527)（`b55d01c`）七项作业成功。

Production `mishare_runtime_psoc_busy()` observes every exact-PSOC runtime owner under its registry lock, including construction before a VDEV exists, asynchronous drain, freed-but-not-retired metadata and quarantine. `mishare_wonder_host_stop_ready_locked()` combines the host and runtime registries without nesting their locks; invalid parent identity returns EINVAL and any owned object returns EBUSY.

Patch 0038 routes the existing native idle gate through this combined predicate and adds gates before module stop in both mode-change callbacks. A fourth gate rejects the top-level mode request before idle-timer or adapter-stop side effects; same-mode no-ops still return success. Regular idle maps refusal to EAGAIN; mode-change returns the actual refusal without clearing the inner mode-change flag. Empty registries preserve native module-stop results. No firmware command or forced cleanup is added. The caller must retain the existing exclusive parent/driver transition through observation and stop; these are snapshots, not references or leases.

The actual production host/runtime files and three complete patched native entry functions and the mode-request admission prefix run in Actions fixtures. Runtime tests cover standalone/pending/draining/quarantined owners and foreign PSOC exclusion. Host tests cover runtime-only, host-only, invalid context, mode flag retention, native error propagation and ordinary idle behavior. Six targeted mutation controls remove either registry check or each of the four call-site gates. A fast independent Actions job runs these tests alongside all previous jobs; final module symbol checks require both new production helpers.

This is stop admission for idle/mode change, not a complete automatic shutdown coordinator. Some native remove/SSR callers ignore lower stop failures, so those paths are not made safe by returning an error here and are unchanged. Global owner-handle transfer, native parent component lifetime, real IRQ/DMA/callback drain and physical HTT free remain outstanding. No new radio init, backend activation or phone test is enabled.

## 验证记录

[CI 41796505527](https://github.com/xxz3312/XAirDrop-17/actions/runs/41796505527)（`b55d01c`）七项作业成功。生产 host/runtime 准入检查、四个原生准入入口及六项变异控制、53 项 Python 检查、全部既有组合、完整 WLAN 编译、CNSS、严格链接、七项布局和模块记录检查通过。十二份组合源码、两个生产 helper、四个停机入口、55 份报告中的生产源码、37 个路径别名及七份验证 ZIP 摘要均核对；快速作业两份报告与完整构建对应报告一致。0038 独立重放与有界原生改动还原检查通过。

生产补丁 0038 将原有 idle 保护扩展为 host/runtime 两个登记表联合检查，并接入两条模式切换停机回调；模式切换总入口在停止适配器之前也拒绝存活 owner。独立 runtime、构造中、等待释放、已 final-free 但尚未退登记以及隔离错误对象均保持阻止停机。普通 idle 返回 EAGAIN；模式切换直接返回拒绝错误，内层标志在拒绝时保持原值。登记表为空时保留原生停止返回值。

这些检查依赖调用方保持既有独占 driver/psoc transition，既不持有父引用，也不自动回收对象。部分 remove/SSR 上层忽略停止返回值，本轮未接入这些路径，不能认定完整 remove/SSR 已安全。真实 IRQ/DMA/迟到回调、物理 HTT 释放及完整父资源停机协调仍待继续。backend 保持关闭，手机无需操作。

见[完整验收记录](research/popsicle-stop-admission-0104-validation.json)。
