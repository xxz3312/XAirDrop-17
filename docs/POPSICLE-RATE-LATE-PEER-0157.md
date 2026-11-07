# 0157：原始 SSR 后记录真实 self-peer DELETE 回执

0156 八项必选 CI 已全部通过（Actions 42408125741），含原有生命周期/父级组合、完整编译、严格链接与布局检查。本轮仅补齐 peer 删除回执的受限观察，不开放 VDEV DELETE 或资源回收。公开 init/START 保持关闭，手机无需操作。

## 上游和原生来源

重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）的 teardown 等待与释放顺序，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）恢复路径。保持原厂 CNSS2 和现有手动部署合同。

本项目原生 WMA self-peer reply origin 使用原 hold-request 中的 owner、VDEV ID 和 MAC，并在原生 hold-request/timer/wake-lock 清理之后发布 runtime 完成通知。复用该来源；不将发送成功、SSR 或 peer unmap 等同于 firmware peer DELETE ACK。

## 实现与限制

- 首次 SSR fence 在同一 registry 锁内，仅对之前健康、已完成 PE 删除、native peer DELETE 已成功返回且回执未到、尚未提交 VDEV DELETE/DP 的配置 owner 记录 late_peer_armed。
- 只有精确 owner/PSOC/VDEV ID/MAC 匹配、firmware 来源、armed 且当前 in-flight 状态仍可信的回执，才在 SSR 封锁下记录 peer_delete_replied/late_peer_reply。普通未封锁路径不变；blocked、quiesced、原始速率回执与错误不清除。
- 与 late_delete_armed 的来源互斥；先前 blocked、首因 REMOVE、错误或未完成的 send、缺少上下文、异常/重复匹配通知都不能恢复准入。外来 token、MAC、ID 保持忽略。
- 收到 late peer reply 后仍然没有 VDEV DELETE 回执，现有 destroy/reclaim/batch 都继续保留 owner/VDEV/events/ref/DP/stats/WMA/legacy，不能开放 native recovery window、排新 MC 工作或发送 VDEV DELETE。本轮没有实现该阶段的完整 SSR 释放，不能将观察成功写成资源回收成功。
- MC 排空前后以及窗口关闭后的真实回执都只记录事实；MC 排空、物理 peer final-free 和 firmware ACK 是不同证据。

## 验证

本地实际 scalar rate/形状检查、19 项变异检查和 100 项 Python 回归通过；语法/diff 检查通过。native 组合源码已从锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 生成，本地未编译。

新增独立 Actions-only 观察组合：两个频段 × 四种速率结果 × 四种普通 peer unmap/flush-service 组合 × MC stop 前后两种时序，共 64 组；12 类故障各测两种时序，共 24 组保留场景。实际选择体执行原生 ordinary peer 删除及 native hold-request/timer/wake-lock 完成来源；核对 native request 已清理，再验证无 VDEV DELETE、无 DP detach、无 host delete、模块及剩余 native 资源保留。故障包含 fence 前异常、REMOVE、send 证据缺失、timeout、重复通知、错误 token/MAC/ID、回执缺失、完整性错误、异常 VDEV 通知以及关窗。三个原生变异控制移除 armed、延迟回执分支或 fence 前健康检查。新增 native 观察组合及三个变异控制已通过 Actions 42410649117、stop-admission 作业 128517831309 的独立步骤 Native late peer reply observation across SSR with sanitizers。本轮八项必选 CI 现已全部通过，含原有生命周期/父级回归、完整 WLAN 编译、CNSS 接口、严格链接、BTF 布局及产物检查；可选 ICNSS reference 按配置跳过。此验收继续是 observation-only，不授予 VDEV DELETE、DP 或 host 释放资格，也不是实机认证。

所有观察案例都刻意保留未完成对象，结束故障子进程不等于回收；物理 transport/ACK/DP/peer/ref/lock 原语仍由模型提供。父级由 caller/fixture 持有，没有完整自动 parent lease、该阶段后续无固件回收、配置后 START/UP 或手机/RF/Apple 互通认证。无手机安装包。
