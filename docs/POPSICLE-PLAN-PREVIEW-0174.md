# 0174 配置后的原生 START 参数预览与退出

## 基线和上游

0173 修正版 `ba9dba76c12362a2dfe0d1bd1e889ac9d40bca77` 的 Actions [43209176144](https://github.com/xxz3312/XAirDrop-17/actions/runs/43209176144) 八项必需任务全部 success，含完整目标编译/严格链接。

本批核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch` 和 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。上游同步初始化不能直接替代本项目异步配置/退出合同。沿用本项目已移植的原生 `mishare_ndi_start_plan_post`、MC work 保留、channel/WMA/PE 身份检查及 `vdev_mgr_start_param_update` 参数构建器；锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的全部现有补丁已在本地应用，仅用于非编译源码组合检查。

## 一批实现

- runtime 新增独立 `start_preview` 回执和 `mishare_runtime_start_preview`。先在 registry 中认证 opaque owner，核对现有 rate/retry/BSSID、PE/channel、原生对象及工作排空，再在原生 MC 队列中生成 START 编码器的七字段摘要。使用现有 native post/callback/work_get/put，不增加工作线程或固件命令。
- 第一次调用在 post 前记录不可重放的请求和 VDEV ID/frequency。排队接受、同步完成与 post-return 分离；成功提交仍先返回 EINPROGRESS。排队失败、flush、原生构建失败都保存原始终态，不重试。回调认证原 owner/PSOC/ID/frequency，重复/矛盾回调标记完整性错误。
- 独立回执不写入 `ndi.start_plan_requested`/`ndi.radio_requested`，不制造真实 START 历史。仍执行真实 channel host preparation 和原生参数编码器；当前 HT20/原生监管限制保持。
- runtime 退休门禁纳入预览回执形状和 owned-work 排空。正常或失败的终态只添加主机元数据，沿原普通 PE/peer/VDEV/DP 退出或 qualified prepared SSR 回收；坏回执保留原 owner。字段不在退出时清空或改写，VDEV 物理释放后的检查只读冻结标量，不解引用旧 VDEV。
- request/host/managed 新增内部 plan_step 接线，每轮保留完整请求/当前 policy 和父级身份检查。第一轮必须通过 0173 配置就绪，已经提交的预览通过相同权威 owner 轮询；scope/instance claim 正常释放。无请求/未绑定不会分配或准备新会话。

此路径只生成参数摘要，不调用 START 状态机或 WMI START。现有 `mishare_runtime_ndi_start_plan`/`mishare_runtime_ndi_start` 对 configured rate 的 EOPNOTSUPP 门禁保持；公开 init/poll、实际 START/UP、过滤与数据面仍不开放。保留原厂 CNSS2，不触碰 init_boot，不生成部署包。

## 本批验证

新 fixture 从已有真实原生组合构造两条路径，执行生产 runtime、真实 MC post/finish、参数构建器和选定原生退出函数：

- 192 组 SSR：2 个频段 × 4 种零/非零重试 × 6 种时序/结果（正常异步/inline、flush、fence 后拒绝、构建错误、post 错误）× 4 种 DP/最后引用释放时序。
- 160 组普通退出：相同频段/重试，正常异步/inline、flush、构建错误、post 错误 × 4 种原生退出时序。
- 9 类保留/拒绝边界：重复完成、posted/ID/summary 损坏、retry receipt 损坏、rate 完整性错误、未排空 work、请求改频、未 accepted 的速率。
- 6 项 runtime 预览变异，外加原 SSR 回收和原生 SM 变异。完整 host fixture 增加三个 plan 接线/scope/claim 变异；runtime rate 标量 fixture 直接提取新增的 production scalar structs，继续覆盖原有 gate。

本地 100 项 Python 回归、py_compile、diff、两套 native fixture 构造和九项新增变异构造检查通过。原生执行和完整目标构建集中交给本轮 CI，提交时尚未观察结果。rate WMI 执行、固件 ACK、物理 IRQ/DP/引用并发和平台锁/调度仍有模型边界；这不是本机射频或 Apple 认证。

后续仍需配置后真正 START/UP 的原生状态机退出/SSR 合同、公开初始化、过滤/数据面和 Apple 发现/握手/双向文件传输。手机无需操作。
