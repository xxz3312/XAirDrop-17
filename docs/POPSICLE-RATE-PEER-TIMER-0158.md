# 0158：peer 回执之后的 VDEV 计时器原生合同验收

本阶段新增测试，不改生产 runtime 准入。0156/0157 各八项必选 CI 已全部通过；本阶段 native 验收待 Actions。公开 init/START 保持关闭，手机无需操作。

## 上游与复用

重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。沿用原生 teardown 顺序和原厂 CNSS2；上游手动恢复脚本没有本阶段精确的 peer-only SSR 事务。

MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 加现有补丁中的 `mishare_ndi_reset_prepared_timer_deinit` 已支持有 legacy extension 的 PAS/NDI INIT 实例，不要求 self-peer 仍存在，可以复用。它验证 timer 的 PSOC/VDEV 身份、inuse、rsp_status 和 PM lock，同步 cancel 后重新检查，再调用真正的 timer/rt-lock deinit。此 helper 本身不证明 SSR 父级停机或授予回收资格。

## 本阶段验证什么

新增 Actions-only 组合从普通真实 PE/native self-peer 删除进入，在原始 SSR fence 前或后经已有 native hold-request 完成来源收到 peer ACK。确认 request/timer/wake-lock 清理完毕时，VDEV response timer 仍在。随后在隔离的子进程中直接检验现有 native timer helper，成功只释放这个计时器；再次调用被拒绝，不二次释放。尚有物理 peer 时，现有 native prepared DP helper 必须拒绝，并且没有 DP 调用。

64 组成功组合：两个频段 × 四种速率结果 × 四种 unmap/flush-service 组合 × ACK 在 fence 前后两种时序。20 组拒绝场景：待处理响应、cancel 期间状态漂移、缺少 timer ops、PM lock、错误 PSOC、错误 VDEV ID、未占用计时器、错误 subtype、非 INIT、缺少 legacy extension，各测两种 ACK 时序。三个 native 变异控制检查 cancel 前状态、cancel 后状态和真正 deinit 缺失。

## 边界与下一步

这只是现有 native helper 的合同测试；生产 runtime 未接入新的 timer/DP 路线。fixture 不打开 recovery window，不设置假的 VDEV DELETE 回执、不发送新的固件命令、不推进 WMA/legacy/host retirement。子进程保留 owner/events/VDEV/DP/stats/WMA/legacy；其中直接成功释放计时器的子进程不再返回生产 runtime，避免将过期的 runtime timer 元数据当成正常状态。退出子进程不代表对象已回收。

下一步需要把这段 timer drain 接入受限 peer-completed SSR 事务：独立准入和一次性尝试记录、合格原生 recovery window、真实 DP final-free 回调，再完成 WMA/legacy 与 host/final-free。完整自动 parent lease、配置后 START/UP 和 Apple 互通仍未完成。

本地仅生成和检查组合源码，未编译大 native fixture；编译、ASan/UBSan 和变异执行只在 Actions。transport/ACK/ref/lock/physical primitives 仍由模型提供，不是手机/RF/Apple 认证。
