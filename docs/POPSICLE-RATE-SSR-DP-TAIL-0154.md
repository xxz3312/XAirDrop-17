# 0154：普通 DP 删除尾段衔接 SSR

0153 的八项必选 CI 已全部通过（Actions 42391133072，含完整编译、严格链接、布局与父级组合）。本轮只扩大至 PE/peer/VDEV 普通删除已确认、普通 DP detach 已成功提交，但 DP 最终释放或 WMA/legacy 上下文收尾尚未完成的配置 owner。公开 init/START 继续关闭，手机无需操作。

## 上游与原生依据

重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）：先等待 PE teardown，再 stop/deinit adapter。重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）的恢复顺序，继续保留 stock CNSS2 与手动加载/恢复边界。

上游同步 adapter 的流程不能证明独立异步 owner 的 DP callback 已完成。本项目复用锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的 native CDS/HIF/HTC/WMI 窗口资格，以及既有 `mishare_ndi_reset_context_finish`：核对 recovering、有效且 blocked 的 WMI、同一 PSOC/DP cookie/VDEV/WMA slot、INIT/NDI、STOPPED BSS、无延迟 self-delete/物理 peer，再 unbind WMA 和销毁 legacy。

## 行为

- 新增 `rate_tail_check`，只接受原始 ordinary admission、无 START-plan/radio、无 sticky 错误、原始 SSR fence 和 MC 排空，以及已完成的 PE/peer/VDEV DELETE、已接受的 DP detach、已释放 timer/stats。没有删除完成证据的早期路径仍按原规则拒绝。
- 该资格仅让原有 native CDS 恢复流程发现候选；不能自行开窗。实际窗口未开放时等待，关窗后未完成尾段拒绝。普通 DP final-free 仍由原始 callback 记录，等待期间保留 WMA/legacy/事件/引用。
- 只有 DP final-free 与实际窗口同时成立，才核对 quarantine event transaction 并尝试一次 native context finish。`tail_attempted/tail_completed` 独立记录衔接，不设置任何 prepared-reset 的 timer/peer/DP 标记。
- native 返回的 WMA/legacy 释放事实逐项保留；失败写入 sticky recovery_error，不重试。全部完成才设置 ordinary_completed/tail_completed，再沿用 host 删除和真实 VDEV final-free 等待。
- direct、batch、延迟 host final-free 与关窗后的 metadata final retirement 接入已有规则。普通 PE/peer/VDEV/DP 历史及速率回执不清零，不再发送 firmware DELETE，不再 detach DP，不重复 timer deinit 或 force peer detach。

## 验证

本地实际 runtime scalar block/configure/MC wrapper 的 13 项变异检查、100 项 Python 回归、语法和 diff 检查通过。原生组合源码已从锁定源生成，本地未编译。

新增 Actions-only 原生 C 组合保留所有已有 ordinary/native 回归：两个频段 × 四种速率结果 × 32 种回调组合，共 256 组，direct/batch 随组合交替；覆盖普通 DP inline/deferred 与 peer unmap、外部 VDEV 引用、实际 native SSR context finish、关窗后 final-free。10 组故障保留覆盖关窗、WMA slot/DP cookie/物理 peer 计数漂移及 completion 错误；三个原生变异控制移除 DP 等待、尾段完成记录或 native 窗口候选。原生 C 和完整目标构建待本轮 CI。

物理 transport/firmware ACK/DP/peer/ref/lock 仍由模型提供，父级由 caller/fixture 持有。没有自动 parent lease 或完整 SSR coordinator，也未覆盖更早的 PE/peer/VDEV 删除中断、配置后 START/UP、手机/RF/Apple 互通认证。无手机安装包。
