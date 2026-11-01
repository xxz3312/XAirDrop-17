# 0090：原生 peer 延迟销毁与显式排空合同

在 0089 组合上启用固定源码的 FEATURE_DELAYED_PEER_OBJ_DESTROY 分支，执行原生 worker、enqueue、destroy、init、deinit 五个函数体，以及 QDF 的九个 work 封装函数体。Linux schedule_work/flush_work/cancel_work_sync、锁和链表仍为确定性平台模型。

保留完整 0089 套件；新增九种情形，各覆盖提前/延迟 unmap 与普通/trace VDEV 配置，共 36 个组合：手动排空、未排空拒绝 deinit、入队参数失败后原生直接析构、非 atomic 直接析构、取消后重新提交、组件异步完成、组件失败、额外 peer 引用、入队返回前 worker 已执行。新增六项负对照，累计 35 项。排队期间检查 peer heap、VDEV peer pin、DP VDEV 和 native SM 未提前回收。

固定版本的 qdf_destroy_work 调用 cancel_work_sync，取消待执行工作并不排空 peer 列表。模型调用方只在父 PDEV/PSOC 仍存活、生产者已关闭、显式 flush 至工作空闲且列表空后调用原生 deinit。该调用方合同仅在 fixture 中实施，尚未接入生产停机协调器。

原生已知行为单独记录：两次 enqueue 合并成一次 worker 后 active_work_cnt 可残留 1，不能作为精确 peer 数或静止条件；worker 执行期间再次提交可能需要第二次 flush；列表满时 enqueue 未检查 insert 返回值，仍返回成功。多条目、重入队和容量诊断使用模拟 peer 析构端点；不宣称这些生产行为已修复，也不认证饱和队列安全。

CI [41338423652](https://github.com/xxz3312/XAirDrop-17/actions/runs/41338423652)（`e444e3d`）已全部通过：53 项 Python 检查、原生 peer 延迟队列模型及 36 个新增组合、累计 35 项负对照、0089 至 0082 独立模型与旧 C 回归、完整编译、CNSS 检查、严格链接、七项选定布局及模块记录检查。43 份模型报告的生产源码哈希均已核对，其中 37 份与本模型共享主生产文件；37 个路径别名与 Git blob/SHA-256 一致。14 个新增原生函数体及四份固定输入的 Git blob 身份已独立匹配，完整生成源码重建哈希与 CI 一致，0089 生成源码也保持一致；本地未执行 C 编译。报告 ZIP 校验通过，布局候选对应最终链接 WLAN，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。离线验收完成，见[验证记录](research/popsicle-native-peer-queue-0090-validation.json)。

atomic 标志仅为销毁入口探针；入队验证失败后的直接析构只验证原生控制流，不认证所有真实 atomic 上下文的睡眠/析构安全。

生产内核不变，backend 关闭，无新手机包。父对象最终引用在 worker 内释放、全局迟到生产者、真实 DP 回调图、Linux kworker 并发、活动 START/UP SSR 恢复和完整 AirDrop 尚未完成。
