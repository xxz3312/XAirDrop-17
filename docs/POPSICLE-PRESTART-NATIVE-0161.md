# 0161：准备控制器、owned MC 和原生退出组合

0160 八项必选 CI 已全部通过。本轮不扩大公开初始化/START 范围；新增完整准备到普通退出的内部组合验收，并修复无发送尝试的工作完成发布期间可能过早开始 PE 清理的问题。

## 上游与原生来源

修改前重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，核对 fixed-rate 与 stop/deinit 顺序；读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`，保持原厂 CNSS2 和手动恢复合同。

复用锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 加现有补丁的 selected native CREATE/context/PE/channel、普通 peer/VDEV/DP/WMA/legacy 退出及 SM/VDEV final-free 体。rate 的 configure bridge 和 owned MC work 使用完整生产 C 文件；速率 WMA/WMI 执行边界仍由模型提供，不声称本夹具执行了实际固件发送。

## 修复

rate_ordinary_check 对已尝试配置会检查 work 引用；但未尝试发送的完成（例如 MC flush）可直接使用既有普通清理策略。其完成回调运行时仍持有 work reservation，普通 ndi_drain 原先可能先提交 PE 删除，再到较后的 host 删除门禁等待。

现在 ndi_drain 在任何 native radio/PE/peer 操作之前，在 registry 锁内先保留 blocked/completion 错误，再检查所有 work_pending/work_users；仍有工作返回 EINPROGRESS，既不删除 PE，也不重发请求。该门禁不将 pending 当作错误，不清除既有错误，不授予 SSR 或父级释放资格。

## 组合与预期

新增 Actions-only 单体夹具从空 runtime owner 开始，经实际 prestart/session controller 调用 CREATE/context、异步 PE 和 channel。channel 完成通知发布时重入只读 poll，验证其 work 引用未归还前不会提交 rate。

rate configure 调用实际 rate_work，scheduler 模型保持独立队列；完成使用实际 callback/flush、runtime work enter/exit/put 及 VDEV ref。完成发布时再次 poll，验证不能提前报告成功；并尝试退出，验证原始 owner/PE 留存，直到引用归还。成功/部分发送错误都保留原始回执，再执行普通 PE→peer→VDEV→DP→WMA/legacy→host→SM/VDEV 最终释放。

512 组：两个频段 × 四种执行结果（成功/第一/第二/第三命令失败）× 32 种 peer ACK、物理 unmap、DP、DELETE inline 和 flush-service/外部引用组合 × rate inline/异步完成。

另有 12 组：post queue 失败、分配失败、ref 获取失败、工作 flush、SSR 到达时待执行工作、重复完成，各测两种外部引用配置。前四类执行普通完整退出；SSR/重复完成类刻意保留资源并结束子进程，不把子进程退出写成资源回收。四项变异控制移除 channel work 等待、请求冻结、rate work_put 或本轮普通退出 work 门禁；要求行为断言失败而非编译失败。

## 验证与边界

本地 100 项 Python 回归、语法/diff 和组合源码生成通过；本地未编译大 native fixture。新增组合、ASan/UBSan 和四项变异已通过 Actions 独立步骤，完整目标编译仍在运行。

完整 native 调用链仍有明确模型边界：PE 创建/频道 pre-start、WMA rate executor、scheduler/transport、固件回执、DP/unmap/ref/锁等物理原语。caller 保留父级；没有自动跨调用 parent lease、完整 managed config transaction、START/UP、手机/RF 或 Apple 发现/握手/双向传输认证。公开入口保持关闭，无新手机操作或包。

## 已验证结果

源码提交 `8ee246a580674f188d7167548aefae02aa79c645`，Actions 42618977716、stop-admission 作业 129165901204 的 `Native prestart configuration and ordinary retirement with sanitizers` 步骤 success，覆盖 512 组组合、12 组异常场景和四项变异；其中移除普通退出 work 门禁会在实际零尝试 flush 完成发布处失败，验证本轮修复。紧随其后的 peer-completed SSR 独立步骤也 success。

bridge-controller 作业已通过。完整 stop-admission 作业、其余生命周期回归与目标构建仍在运行，不记作全门禁通过。上述边界仍是离线组合，未认证手机或空口行为。
