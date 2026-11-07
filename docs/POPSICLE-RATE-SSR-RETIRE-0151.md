# 0151：未 START 的已配置 owner 复用合格 SSR 回收

本轮仅打开已完成 owned rate 批次、尚未请求 START-plan/radio 的 SSR 回收路线。普通运行态配置后清理和公开初始化仍关闭，手机无需操作。0150 的六项必选作业已通过，完整目标编译和父级组合回归在本轮开始时仍运行，不提前写成全通过。

## 上游和原生资格依据

- 本轮重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）中 PE 删除、等待完成和 adapter/父级清理顺序。它是同步设备流程，不能替代本项目异步 owner 的排空和释放证据。
- 本轮重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`），保留原厂 CNSS2、手动加载和恢复边界，不改设备端脚本。
- 核对本项目锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的已打补丁 native CDS/WMA/PE/timer/DP 路径：`mishare_cds_recovery_window` 只在 HTC/IRQ/RX 停止之后，确认 recovering、有效且 blocked 的 WMI、HIF TARGET_STATUS_RESET，再成功关闭 WMI 工作队列后开放原有 recovery_window。
- 复用既有 `mishare_ndi_reset_context_check`、PE 几何/身份检查、native timer drain、no-FW self-peer force detach、实际 DP final-free、WMA/legacy finish 和 VDEV final-free。没有新增“根据一个布尔值跳过 native 检查”的接口，也不改窗口开放/关闭来源。

固定速率的直接 WMA 命令仅改变 VDEV 参数，不创建新的 host PE/DP 对象；在上述 transport/reset 资格和原 prepared INIT 检查全部成立后，可走原 no-FW 回收。不能由命令入队或 receipt.complete 推断普通运行态已经安全。

## 两阶段回收记录

- `rate_reset_check` 是纯元数据的候选资格检查，不开放 native window。要求 rate 回执终态且完整、无 integrity 错误、原始 SSR fence、无 radio/START-plan 请求，owned MC 已排空且无 sticky work/recovery/completion 错误。
- 初始候选必须仍有 referenced VDEV/events、完整 legacy/WMA/self-peer、完成的 PE/channel。候选被发现后，仍需 native CDS 的 HTC/HIF/WMI 资格开放窗口；窗口缺失只等待，不执行 timer/PE/DP 清理。
- 原生 event transaction、WMA context 和 PE identity/geometry 检查通过后，在 timer drain 之前记录 `reset_admitted`。处理中必须保持同一有效窗口；窗口关闭、身份漂移或部分 native 错误保留所有权及错误，不重试已尝试的释放。
- 仅在实际 timer、PE/self-peer、DP final-free、WMA/legacy finish 完成，且原始 INIT 被观察后，记录 `reset_completed`。终态门禁再次核对所有 native 尝试/释放事实与不再持有的上下文，不能单靠该标记释放 host。
- host destroy 的 reclaim 分支和 final metadata 只接纳已完成上述阶段的 owner；外部 VDEV 引用导致的 final-free 等待仍保留 owner/module。窗口关闭后只允许已经完成资源回收的元数据退休，不重新访问 native 上下文。
- 整批回收预检查用同一 SSR 资格判定，普通 destroy/host-only reclaim 仍用保守门禁。`requested/posted/accepted/completed`、请求字段、原错误与 attempted/submitted masks 全程不清零，不伪造普通 PE/VDEV DELETE ACK。

## 验证和边界

本地实际 runtime rate block、configure bridge 和 MC wrapper 的状态模型检查通过，加入 SSR fence、MC drain、radio/plan、closed window 和终态释放事实的拒绝检查。九项变异控制（原六项加三个 reset 条件）在编译后命中行为断言；100 项 Python 回归、语法和 diff 检查通过。

新增 Actions-only native composition：复用并保留既有 pre-radio 回归，实际 runtime rate begin/posted/complete 在真实工作 reservation 内记录模型 WMI 提交结果，随后执行原 CDS/HIF/WMI/PE/timer/DP/object 回收函数。覆盖两个频段、四种配置提交结果和 inline/deferred DP，共 16 组；包含 batch、外部 VDEV final-free 等待及窗口关闭后的 final retirement。另测六种 native 窗口资格缺失、七种资源保留故障、部分 peer 清理失败和原错误不变，并加入三个回收记录/候选资格变异控制。组合源码在本地通过生成/原生来源检查，没有在本地编译，实际 C 行为和目标构建待本次 CI。

native 函数的 IRQ/transport/firmware/DP 物理实现及引用/锁等仍为 fixture 模型，rate WMI 结果由模型提供，不能写成实机 SSR 或固件互通认证。没有普通配置后 teardown、START/UP 回收、完整 remove/父级租约、BSSID/重试/聚合/过滤/收发接入或公开启动。无手机安装包。
