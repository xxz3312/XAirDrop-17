# 0187 配置状态的资源所有权与历史来源准入

0186 `4a269a1b4269e3e7ec59356aa213a04b85b04c5d` / Actions 43383874228 八项必需 CI 全部通过。Optional ICNSS 跳过，不计入必需项。

本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch 和 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。沿用原生参数与原厂 CNSS2，不将上游结果当成本机通过。

## 修复

现有 pure configuration observation 已检查 rate/retry/BSSID/PE/channel 和主要 radio phase，但仅有 NEW phase/未 host_up 不能证明没有执行过 command/fence/retirement；已完成状态也缺少 DP cookie 和 stats ownership 检查。

新增 `mishare_start_radio_pristine` 按命名字段检查 radio 的当前 phase/command/work、首次 fence、预启动取消/中止和 DOWN timer/controller 退役历史均为初始状态，不能仅将 phase 改回 NEW 冒充未启动。Configuration 同时拒绝 runtime 中 DOWN observation/release 与 timer/PE/context/DP recovery 历史；成熟配置必须保有非空 DP cookie 和 stats_owned。

不修改原生 beacon/DTIM 参数合同。Native builder 直接复制 MLME 字段且无非零约束，本批仍沿用原生返回值与已有逐字段一致性检查；不能为 PAS 增加未验证的 timing 下限。

检查仍只读，不保留 readiness ticket、不提交 START、不开放 public init 或 configured runtime START。实际 host caller 的新 scope、父级/当前 regulatory/readback 和完整请求身份检查保持。

## 验证

- 原有 16 readiness 正常、56 边界、32 plan 正常及35 plan 边界继续执行；mock ready snapshot 补全真实成功状态必需的 DP/stats ownership。
- 新增141边界：45类 radio/fence/recovery 历史以及两类 DP所有权损坏，分别覆盖无plan、preview与committed plan三种观察。每次都要求返回对应错误且输入快照不变。
- 四项正例保留原生 beacon/DTIM 零值的逐字段一致性，不误加非零门槛。
- 三项新增变异遗漏 radio pristine、DP cookie 和 stats ownership 门禁；原有九项配置、六项 plan 变异继续运行。

CI 将这组纯 C/sanitizer 验证移到 bridge-controller 的首个检查步骤，后续原桥接/host/native/factory/SSR回归保留。Pure predicate 的配置/native state 是显式模型；不等同实际radio/固件就绪或手机证明。

本地105项Python、py_compile、测试源/差异检查通过；C/sanitizer与目标构建集中交由Actions，提交时待观察。保留原厂CNSS2，不触碰init_boot，手机无需操作。
