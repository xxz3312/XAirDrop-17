# 0090：原生 peer 延迟销毁与显式排空合同

在 0089 组合上启用固定源码的 FEATURE_DELAYED_PEER_OBJ_DESTROY 分支，执行原生 worker、enqueue、destroy、init、deinit 五个函数体，以及 QDF 的九个 work 封装函数体。Linux schedule_work/flush_work/cancel_work_sync、锁和链表仍为确定性平台模型。

保留完整 0089 套件；新增九种情形，各覆盖提前/延迟 unmap 与普通/trace VDEV 配置，共 36 个组合：手动排空、未排空拒绝 deinit、入队参数失败后原生直接析构、非 atomic 直接析构、取消后重新提交、组件异步完成、组件失败、额外 peer 引用、入队返回前 worker 已执行。新增六项负对照，累计 35 项。排队期间检查 peer heap、VDEV peer pin、DP VDEV 和 native SM 未提前回收。

固定版本的 qdf_destroy_work 调用 cancel_work_sync，取消待执行工作并不排空 peer 列表。模型调用方只在父 PDEV/PSOC 仍存活、生产者已关闭、显式 flush 至工作空闲且列表空后调用原生 deinit。该调用方合同仅在 fixture 中实施，尚未接入生产停机协调器。

原生已知行为单独记录：两次 enqueue 合并成一次 worker 后 active_work_cnt 可残留 1，不能作为精确 peer 数或静止条件；worker 执行期间再次提交可能需要第二次 flush；列表满时 enqueue 未检查 insert 返回值，仍返回成功。多条目、重入队和容量诊断使用模拟 peer 析构端点；不宣称这些生产行为已修复，也不认证饱和队列安全。

CI 与独立产物校验待完成。生产内核不变，backend 关闭，无新手机包。父对象最终引用在 worker 内释放、全局迟到生产者、真实 DP 回调图、Linux kworker 并发、活动 START/UP SSR 恢复和完整 AirDrop 尚未完成。
