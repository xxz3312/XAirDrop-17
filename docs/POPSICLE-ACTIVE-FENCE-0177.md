# 0177 原生 START/UP/STOP/DOWN 的首次封锁记录

0176 修正版 `2ce56a73d6355defee8aed3b45091c4ae7e9ee91` 的 [Actions 43259916582](https://github.com/xxz3312/XAirDrop-17/actions/runs/43259916582) 八项必需任务全部 success，含完整目标构建、严格链接、host/调用链和原生生命周期回归。

本批核对两个上游主分支，均未变化：Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（原生 adapter start/stop）；Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（原厂 CNSS2/启动失败恢复）。继续复用锁定 MiCode 的原生 SM/回调/WMA/退出代码，不开放未经验证的 active 恢复、不触碰 init_boot。

## 为什么先保留首次来源

现有 radio 封锁会将各阶段统一改成 BLOCKED。恢复实现需要分辨原先是 WAIT_START、UP、正在 STOP、已经 DOWN，还是已经失败，不能把之后的 BLOCKED 当作原始状态，也不能把它当作原生 INIT 或停止证明。

新增 `mishare_radio_fence_status`，在同一 radio registry 锁内、首次显式 quiesce 修改 closing/phase/error **之前**，冻结 controller-local 阶段、错误、closing、START/STOP/UP/DOWN 标志、pending/users、native dispatch 是否进入/仍在调用栈，以及回复排队/应用标志。已经由普通 STOP/DOWN 设置 closing 的实例仍会记录首次 parent fence；用独立 recorded 判断，重复 fence 和迟到回调不覆盖。runtime 的原始 quiesce reason 仍由原有 sticky 字段保存，radio 记录不单独宣称 SSR 来源。

这只是带有来源的观察记录，不是新回收资格。现有 pre-START 撤销检查、active 状态的拒绝门禁、WMI/SM/PM/对象释放顺序全部保持。snapshot/retire receipt 自然携带新增标量。它只在 radio 锁下有一致性，不保证与 runtime/event/native SM/IRQ/固件状态跨锁原子一致，也不授权后续 START 或 SSR 清理。

## 集中验证

新增 Actions 原生组合使用生产 radio/runtime/event registry、真实通用 SM 引擎与原生状态表、选定 PAS entry/event/exit 和完整 WMA START-response 等原生函数体。测试使用原有 **raw/unconfigured** 内部生命周期，不伪造成功的配置回执、不移除 configured START 门禁：

- 88 组 active SSR：2 个频段 × INIT/0 或 IDLE × 11 个切点 × 迟到回调执行/排队工作 flush 两种后续。
- 11 切点：WAIT_START、START reply 排队、UP、STOP 排队、WAIT_STOP、STOP reply 排队、DOWN、START send 失败、WMA 在 UP 后失败、STOP send 失败、DOWN send 失败。
- 4 组在真实 native START-send 调用栈中的 fence：有 pending=1/users=1、native dispatch active 的首次来源在返回及工作引用释放后保持不变。
- 8 组 REMOVE/MODULE_STOP：非 SSR 的原始 reason 不会被后续重复 fence 改写。
- 所有切点核对 foreign PSOC 无影响、首次字段匹配、重复封锁不覆盖、迟到/flush 不重发命令、不变造 DOWN、不能冒充 pre-START cancellation。真实 native CDS qualification 不为这些 active owner 开窗；普通 drain、runtime destroy/reclaim 继续拒绝并保留原 controller、PE/peer/DP/VDEV/SM 与引用。故障子进程结束时有意保留 native 资源，不宣称零泄漏的物理回收。
- 11 项新增行为变异：遗漏记录、覆盖首次记录、错写 phase/start/UP/error/pending/users/native-entry/native-call-active、错用 PSOC；保留原 native generic engine/状态机变异及原健康流程基线。

本地 100 项 Python 回归、语法/diff、原生源码与变异构造检查通过；C/sanitizer 执行和完整目标构建集中交给本轮 CI，提交时尚未观察结果。调度、引用、锁、定时器/PM、物理 DP/固件与 IRQ 原语仍为模型；完整文本不意味着所有条件分支/传递调用都已执行。

## 边界与后续

本批没有实现 active START/UP 的 SSR 物理回收，也不把 raw/native 模型写成 configured init 已通过。它补齐恢复实现所需的首次阶段事实和 native 保留矩阵。后续需依据实际 native SM/timer/PM/peer 状态实现分阶段恢复，验证失败/普通退出与父级 teardown 协调，再放开 configured radio；公开 init/poll、过滤/数据面、手机射频与 Apple 互传仍未验收。手机无需操作。
