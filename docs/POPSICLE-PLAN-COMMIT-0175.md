# 0175 已完成编码回执的 START-plan 提交与退出

0174 修正版 `b96931379b16c0011bdd07bf079b02f66b5c225f` 的 [Actions 43213576160](https://github.com/xxz3312/XAirDrop-17/actions/runs/43213576160) 八项必需任务全部 success，包含完整目标构建、严格链接、host/native 生命周期回归。

本批重新核对两个上游主分支，均未变化：Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 lifecycle patch 0006；Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。复用已移植的原生 START 参数构建和 native 退出，继续保留原厂 CNSS2，不触碰 init_boot。

## 实现

新增内部 `mishare_runtime_start_plan_commit(owner, freq)`：先在 registry 认证 opaque owner，核对关闭状态、工作排空、完整成功的 preview/rate/retry/BSSID、活跃 owned context 和退出历史，原子复制已完成的七字段原生编码摘要到 NDI START-plan，登记 preview.committed。不存在预览、仍在排队、预览失败、改频、外来 owner、既有计划冲突分别等待或保留原始错误。重复提交只验证同一记录，不分配、不 post、不调用 builder、不发送 WMI。

preview.committed 必须对应 requested/posted/completed 的成功 preview 和完整成功的 NDI plan；所有七字段逐项匹配，不比较 C 结构 padding。这个 scalar 合同从提交一直检查到 native final-free 后，完整性错误保留 owner。普通 never-radio 退出及 qualified prepared SSR 允许这种来源明确的计划，继续执行已有 native PE/peer/timer/VDEV/DP 清理；不能仅靠伪造 start_plan_requested 取得资格。

已有独立 raw START-plan、configured radio START、公开 init/poll 门禁保持。提交只是主机计划记录，不重新检查随时间变化的 native encoder/监管状态，不是供将来 START 复用的 readiness lease；真正 START 调用必须重新验证 native 输入、当前完整请求/父级策略，并先完成 active START/UP 的退出和 SSR 合同。本批尚未接入 managed/request caller；已有 0174 managed_plan_step 仍只做 preview。

peer-only、late-peer、late-DELETE、ordinary-tail 的混合 SSR 不在本批放行：即使 plan 已提交，这些未验证的组合继续保留。无状态重置或 radio 历史伪造。

## 验证

新 Actions fixture 在 0174 的生产 runtime、真实 owned MC callback、原生 encoder 和既有 native ordinary/prepared SSR 组合中加入真实提交：192 组 SSR、160 组普通退出（只有成功 preview 才能提交；错误仍按原结果退出），覆盖异步/inline、flush/拒绝/构建/post 失败、DP/最后引用时序。普通 native 清理仍每个进程只运行一个生命周期。另加 12 类提交拒绝、原九类 preview 边界、七项新提交变异、原六项 preview 变异及原生恢复/SM 变异。

本地执行 Python 回归、语法/diff 检查和两套 native fixture/13 项 runtime 变异构造；不在本地编译 C。原生执行、sanitizer 和完整目标构建集中交给本轮 Actions，提交时结果待观察。调度、锁、引用/IRQ、物理 DP 和固件原语仍有模型边界，不构成手机/RF/Apple 验收。

下一步是接入完整请求 caller，并验证真正 START/UP 后普通退出、失败/SSR 回收；之后才可开放初始化、过滤/数据面与 Apple 互通。手机无需操作。
