# 0153：普通清理完成后的 SSR 元数据衔接

本阶段只处理：速率已配置、未请求 START-plan/radio，普通 PE/peer/VDEV/DP/WMA/legacy 清理全部完成，host 删除和事件解绑已接受，但外部 VDEV 引用使 final-free 尚未发生，此时遇到 SSR。扩展现有 `reclaim_final` 和整批回收的 metadata-only 路线；不续跑任何 native 清理。公开 init/START 保持关闭，手机无需操作。

## 上游与边界

本轮重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）：先完成 PE 会话 teardown 等待，再 stop/deinit adapter。重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）的恢复顺序，保留 stock CNSS2、手动加载和恢复边界。

上游同步 adapter 流程没有本项目独立异步 owner 的 final-free 等待，因此复用此前已建立的普通清理和 SSR final metadata API。该 API 不会再访问 native VDEV、重发 DELETE、调用 DP detach 或开启 recovery window；既有停机 fence、MC 排空与实际最终释放证据继续负责退休资格。

## 实现

- 抽取纯标量 `rate_ordinary_terminal`，普通清理和 SSR final 共用同一套 PE/peer/VDEV 完成、DP detach/final-free、timer/stats/WMA/legacy 已释放检查，不复制或清除原始记录。
- 新增 `rate_final_check`，仅接纳完整 ordinary admission/completion、原始 SSR fence、已接受 host 删除、draining/allocated 且无 VDEV/ref/events/PE/radio 句柄的对象。配置完整性、work/recovery/reclaim/completion 错误仍拒绝。
- `reclaim_final`、final-shape 验证及 batch 的 final-only 预检查复用这一资格；其他 owner 继续使用原 rate/SSR 规则。`reclaim_final` 与 batch 原有 MC 排空和真实 `freed` 门禁均保留，批次覆盖、身份及错误优先级不变。
- recovery window 从未开启或已经关闭都可等 final-free，因为 native 资源已经普通释放。无 ACK、DOWN、DP-free 或 SSR reset 标记被合成；原始配置错误与 masks 保留。
- 普通 destroy 在 SSR 后仍拒绝。普通清理未完成、host 删除未接受、第一停机原因非 SSR、未知/重复完成或证据缺失的对象继续保留；本阶段没有部分 PE/peer/VDEV/DP 清理的跨 SSR 续跑。

## 验证

本地实际 runtime scalar block/configure/MC wrapper 的状态模型、12 项变异检查及 100 项 Python 回归通过；语法与 diff 检查通过。原生组合源码从锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 生成，本地未编译。

新增 Actions-only 组合，保留完整既有普通清理回归，追加两个频段 × 四种速率结果 × 16 种含外部引用的回调组合 × direct/batch，共 256 组 SSR final 衔接；22 组终态保留故障，以及实际 PE DELETE 消息被 SSR 打断后的拒绝。检查 fence 前拒绝、MC 观察前等待、final-free 前保留模块引用、真实 SM/组件 final-free 后才退休、关窗后不重放 native 操作、未知已退休 token 拒绝。三个原生变异控制分别移除 final 路线、final-free 门禁、DP 完成证据。本轮 native C 和完整构建待 CI。

速率 WMI 结果、firmware ACK/DP/peer 物理原语、锁和外部引用仍由模型提供；native 普通清理/PE 析构/WMA peer/SM/final-free 选择体运行于该模型。父级由 caller/fixture 保留，无自动 parent lease、完整混合 SSR coordinator、已配置 START/UP、手机/RF 或 Apple 互传认证。0152 六项必选 CI 已通过，完整编译与父级组合在本阶段开始时仍运行。
