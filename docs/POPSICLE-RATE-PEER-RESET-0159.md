# 0159：peer 已确认、未提交 VDEV DELETE 的受限 SSR 回收

0158 八项必选 CI 已全部通过。本阶段实现生产 runtime 独立的 peer-reset 事务，公开 init/START 继续关闭，无手机安装包或操作。

## 参考与差异

修改前重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，核对 PE 等待、stop/deinit adapter 顺序；读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`，沿用原厂 CNSS2 和手动部署/恢复合同。上游脚本没有本项目配置后 peer-only 的异步 SSR 事务。

复用锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 加现有补丁的 prepared timer deinit、prepared DP detach 与 reset context finish。无需新增原生 patch，不重复删除已被普通路径删除的 PE/self-peer，不发送 VDEV DELETE。0158 已独立验证计时器 helper 的复用合同。

## 事务与证据

- 健康原始 SSR fence 前 peer ACK 已到，且普通 PE 删除已完成、VDEV DELETE/DP 从未提交时记录 peer_reset_armed；fence 后 ACK 只复用 0157 精确 owner/PSOC/ID/MAC 的真实 late-peer 完成来源。REMOVE、先前异常、缺失/超时/重复回执不授予资格。
- 准入检查不等于 recovery window。MC 必须停机排空、没有 runtime pending/user；只有原生 CDS 的 HIF/HTC/RX/WMI 停机与 reset 条件才能开窗。caller 继续保留父级并串行所有 poll。
- 在同一 owner/events/cookie、quarantined 无 pending event 的精确状态下，一次性标记 timer 尝试，再调用 native timer 同步 cancel/重检/deinit。只有成功返回才设置 timer_released，并返回 EINPROGRESS 形成独立步骤。
- 下一次 poll 一次性标记 DP 尝试；native helper 检查物理 peer count 为零和相同 DP SOC cookie，成功提交才记录 submitted/stats 释放。独立的 peer-reset DP callback 在 token registry 内匹配、校验原始 peer ACK 与无 VDEV DELETE 状态，只记录实际 physical final-free。inline 完成仍必须经过提交成功返回后才允许 context finish。
- 真实 DP free 之后，native context finish 检查 recovering/blocked WMI、PSOC/SOC/VDEV/MLME/WMA slot、INIT、peer count、BSS STOPPED，再执行 WMA/legacy 释放。记录实际部分结果；任何失败 sticky，禁止重试。
- peer_reset_completed 独立于 ordinary_completed/reset_completed。VDEV DELETE 的 pending/submitted/replied 全程保持 false，阻止伪造 ACK。host delete 接受后仅 metadata retirement 可跨关窗继续，仍等待真实 VDEV final-free；individual/final/batch 入口使用同一路线的完成证据。

## 验证与限制

本地 23 项 scalar 变异检查、100 项 Python 回归、语法/diff 检查通过。大 native fixture 本地只生成源码，不编译。

新增独立 Actions-only 夹具：两个频段 × 四种速率结果 × 八种 unmap/DP inline/flush-service 组合 × ACK 在 SSR 前后 × individual/batch，共 256 组。36 组保留场景覆盖关窗、物理 peer 未释放、DP cookie 错误、timer 待响应/cancel 漂移/ops 缺失、缺失或重复 peer ACK、reset 未完成、stats 缺失、速率完整性错误、DP 提交失败、DP 重复回调、WMA finish 错误、timer/DP 后关窗、fence 前异常及 REMOVE。四项 native 变异控制移除 armed、timer 完成记录、DP 提交返回隔离或物理完成 callback 准入。完整 native 矩阵已通过独立步骤，目标编译和更大范围生命周期回归仍在运行。

0157 观察及 0158 timer-only 测试随新准入更新：在没有 native window 时依旧不能清理，健康 peer ACK 可以成为候选；原有故障场景继续保留。选定 native timer/DP/context/SM 函数体实际执行，但 transport/ACK/peer unmap/DP/ref/locks 原语仍是模型。没有自动跨调用 parent lease、配置后 START/UP、手机/RF 或 Apple 发现/握手/双向互传认证。

首轮 CI 42447741287 发现候选枚举误将未配置速率 owner 的通用零返回值作为新路径资格，已补上 ordinary_admitted 前提，并在原 native INIT 拒绝回归中增加未配置 owner 非候选断言。同时修正 stats 缺失场景在 MC 尚未排空时应先返回 EINPROGRESS 的夹具预期；MC 排空后仍拒绝。修正后重跑验收。

独立 native 步骤在修正后的 679c049 运行中已通过；追加终态候选枚举检查，明确排除已完成或已尝试 context finish 的 peer-reset owner，保证 metadata-only retirement 不会重新开窗。每个成功组合在关窗后验证候选为零、recovery_open 不重新开窗，再释放最后一个外部引用。完整修订继续执行 CI。

## 已验证结果

最终代码提交 `e6f19b11e1b3a0123ffd5cbe456a74ecc3f29e0d`，Actions 42448119773、stop-admission 作业 128631291717 的 `Native peer-completed SSR retirement with sanitizers` 步骤 success，包含 256 组组合、36 组保留场景和四项 native 变异；所有成功组合还验证了完成后的 metadata-only owner 不会重新成为回收候选或重新开窗。完整作业与目标编译尚未结束，不记作全门禁通过。

前一代码运行 42447974844 已通过新增回收、原有 timer 和 late-peer 三个独立步骤；最终代码重跑中。故障夹具已保留主动注入的 integrity_error，同时逐字节检查原始请求与回执不变；没有通过清除错误来满足历史断言。
