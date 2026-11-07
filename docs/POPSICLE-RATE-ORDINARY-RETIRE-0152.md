# 0152：已配置、未 START 的普通异步清理

0151 的八项必选 CI 已全部通过（Actions 42380495651，包括完整目标编译、严格链接及布局检查）。本轮为已结束 owned rate 批次、尚未请求 START-plan/radio 的 owner 接入已有普通 PE → peer DELETE → VDEV DELETE → DP final-free → WMA/legacy → host final-free 清理链。公开 init/START 仍关闭，手机无需操作。

## 上游参考与差异

重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）：普通 stop 先请求 PE 删除、等待完成，再 stop/deinit adapter。重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`），保持原厂 CNSS2 与手动加载/恢复边界。

本项目持有独立的异步 owner，而非同步 HDD adapter，复用此前已验证的普通原生清理，不照搬上游同步等待或 SSR no-FW force detach。固定速率只设置 VDEV 参数，普通删除整个 VDEV 消除其作用域；不会发送“恢复默认速率”命令，不会将速率提交成功当作固件 ACK。

## 行为

- 新增 `ordinary_admitted/ordinary_completed`，与 SSR 的两个标记互斥。仅接受完成且可信的 rate 回执、无 START-plan/radio、正常运行态、无 sticky 错误、owned MC reservation 已退出的 owner。
- 首次普通清理仍要求完整 referenced VDEV/events、PE/channel、timer/DP、WMA/legacy 上下文。标记不构成 native 身份或状态资格，现有 native helper 检查和回调门禁继续生效。
- PE DELETE 完成后才能删 self-peer；peer 的真实 reply origin 后才能发 VDEV DELETE；VDEV reply 后才能 detach DP。回调超时、flush、发送错误和未知/重复完成保留 owner 及尚未释放的资源，不清除原始错误。
- 只有普通上下文清理完成才记录 `ordinary_completed`。host 删除前再次检查 PE/peer/VDEV 完成、DP 提交及 final-free、timer/stats/WMA/legacy 已释放。外部 VDEV 引用继续阻止最终退休，事件解绑与本模块引用沿用原路径。
- 请求和速率原始 receipt/masks 全程不清零。START-plan/START 继续拒绝。已开始普通清理后出现 SSR，或已走 SSR 后尝试普通清理，保持所有权；本轮不增加混合路径。

## 验证

本地实际 scalar runtime block/configure/MC wrapper 的状态模型及 11 项变异检查通过；100 项 Python 回归、语法、diff 检查通过。原生组合源码从锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 生成并检查，本地未编译。

新增 Actions-only 原生 C 组合：复用完整 ordinary cleanup fixture，额外执行两个频段 × 四种速率提交结果 × 32 种串行回调/引用组合，共 256 组；24 组 native 错误保留及 5 种入口拒绝；3 项配置清理变异控制。检查 native PE 析构、普通 WMA peer remove/objmgr remove、DELETE/DP wrapper 和 native SM 生命周期。保留既有普通生命周期回归。实际 C 结果与完整目标构建待本轮 CI。

速率 WMI 结果、firmware ACK 来源、物理 peer 引用/unmap/DP 完成依赖、组件析构调用方和锁仍由模型提供。父级由 fixture/caller 保留，不等于自动 native parent lease 或手机认证；尚无混合 SSR/普通清理、已配置 START/UP、完整配置接入、RF 或 Apple 发现/握手/互传证明。无手机安装包。
