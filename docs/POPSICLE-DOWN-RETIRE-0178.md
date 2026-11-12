# 0178 已完成 DOWN 的 controller 与原生响应定时器退役组件

0177 `eb9c13b221501e4e22b03409d354d59ba5567157` 的 [Actions 43280086420](https://github.com/xxz3312/XAirDrop-17/actions/runs/43280086420) 八项必需任务全部 success，含完整目标构建和 active 保留矩阵。

本批优先核对两个上游，主分支仍为 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`、Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，分别参考 lifecycle patch 0006 的原生 adapter stop、module/action.sh 的原厂 CNSS2/失败恢复。复用本项目已有 native response timer helper、原生 SM/WMA 和首次 fence 记录，不以同步上游 stop 替代异步/SSR 的独立证明。

## 实现范围

新增 component-only `mishare_radio_fenced_down_check/release`，专门处理正常 START→UP→STOP→DOWN 已完成、controller 尚未被普通 drain 移除时收到 parent fence 的情形。

- registry 先认证 opaque token 和 exact VDEV/events/owner/cookie/frequency；首次 fence 必须为无错误、零 pending/users 的完整 DOWN，current 状态保持 BLOCKED/ESHUTDOWN。完整 START/STOP/UP/DOWN、dispatch、reply 与初始/当前字段必须一致；混合 pre-START cancellation 来源拒绝。host_up 是历史记录，不清零假装没有启动过。
- native 对象仍为 PAS/NDI、精确 INIT/IDLE，event transaction 保留 serial=2 的一次 START/STOP、真实 submitted/replied 与 QUARANTINED 状态。原生 encoder 重新构造后七字段必须匹配旧计划。check 只读，不释放定时器。
- release 首次记录 timer_attempted，调用已有原生 `mishare_ndi_reset_prepared_timer_deinit` 同步取消/重检/释放，再核对全部 controller/native/transaction/plan 条件。任何 DOWN fence 后的 MLME callback 都永久撤销退役资格，包括 timer sync 内最后回调。
- 成功只 unlink controller、返回完整原始状态和真实 timer/controller 退役事实、释放其一个 VDEV 引用，不改写 DOWN、STOP 事务或预启动 cancellation。失败保留 controller 及 timer-attempt/error 历史；即使定时器已物理释放，后续也不重试。

本 API 没有接入 runtime recovery candidate/window 或自动 caller。与已有 controller 组件一样，显式 caller 必须保留/串行原始父级、establish native MC/IRQ/firmware 停止资格；radio 本地检查不是完整 native window 授权。生产 runtime 仍拒绝该 DOWN owner 的 SSR 回收。后续集成须发布返回的真实状态、同步 runtime timer ownership，再推进 PE/peer/DP/VDEV 及最终 metadata 释放，不能绕开这些合同。

## 验证

新 Actions fixture 执行实际 raw/unconfigured 原生 START/UP/STOP/DOWN、首次 fence、event 回执、原生响应定时器同步释放与 controller 引用退休，不移除 configured START 门禁、不伪造配置成功。

- 32 组：双频、INIT/0 或 IDLE、START/STOP 各自普通/提前响应、额外 VDEV 引用。
- 18 类边界：首次阶段/错误/工作未排空/未接受 DOWN、当前 DOWN 损坏、native IDLE 漂移、STOP serial/submitted 错误、迟到 MLME、native 几何/类型错误、定时器拒绝、sync 内最后 callback/计划变化、foreign owner、unknown token、半完成 timer 历史。
- 成功检查只释放真实 native response timer 和 controller 的一个引用，event transaction、原 fence 与命令计数保持，PE/peer/DP/VDEV/SM 图继续保留；native callback 在 controller unlink 后不能获取旧对象。runtime reclaim 仍拒绝，未宣称完整 SSR 成功。
- 十项新行为变异覆盖漏掉阶段/错误/工作/完成/回调/native IDLE/STOP serial 门禁，遗漏实际 native timer release、遗漏 timer-sync 后重检、遗漏 retirement receipt。0177 的 100 场景与原 native SM/WMA 健康/失败基线也保留。

本地 100 项 Python 回归、py_compile、diff 和 native/变异源构造通过；本地不编译 C，原生/sanitizer 和完整目标编译集中由本轮 Actions 执行，提交时待观察。IRQ/固件、锁/引用/PM/DP 物理原语仍有模型边界，故障和剩余资源由子进程有意保留，不称完整析构/无泄漏验收。

保留原厂 CNSS2，不触碰 init_boot。公开 init、configured radio START、UP/等待响应/失败状态的 SSR 回收、过滤/数据面和 Apple 互传仍未开放。手机无需操作。
