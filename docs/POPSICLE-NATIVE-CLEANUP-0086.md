# 0086：普通 DOWN 后完整清理组合验证

0085 的完整 WMA/SM 生命周期继续经过原生 PE 析构、普通 WMA peer 删除、固件 peer/VDEV DELETE 响应、DP 完成、WMA/legacy 释放、原生 SM 销毁与 VDEV 最终释放。普通路径使用完整原生 `wma_remove_peer` 和 `wma_remove_objmgr_peer`，以独立端点模型编译为 clean_native_*；不复用 SSR/no-FW force detach。

新增 32 种串行回调/引用组合：peer ACK、peer unmap、DP VDEV 完成、VDEV DELETE ACK 的提前或延迟，及外持 VDEV 引用。外持引用与 flush-service 能力共用一个测试位，两分支都有覆盖，不宣称六个独立维度的全部组合。保留 16 种 WMA 主流程和三次 ratemask 流程，均继续完成清理。

六类失败覆盖 PE DELETE flush、peer 发送错误后晚到响应、peer 超时、VDEV 超时、DP detach 拒绝、host 对象删除拒绝；检查尚未完成的资源保留，而非宣称已释放的资源回滚。新增移除生产 peer ACK 等待和 DP 完成等待的两个负对照，连同此前九项负对照运行。

本阶段 CI 尚待完成；生成源码可从固定源码快照与既有补丁重建，本地不运行 C 编译。通过后补充报告与独立哈希核对结果。

peer 引用/逻辑删除/unmap、DP teardown/callback、WMI transport、component destructor 调用方与父列表仍是平台模型。模型明确将 DP VDEV 最终完成延迟至 peer unmap/逻辑删除完成；这不能认证真实 DP/peer 对象析构图或硬件顺序。原生 SM 销毁在模型组件析构的 VDEV 零引用处执行，先于原生父列表 detach、VDEV storage free 与 runtime 最终通知。父资源由测试框架保留，不代表自动 native parent lease/coordinator。

活动 START/UP SSR 恢复、真实并发停机与安全模块卸载、完整 AWDL 收包仍待后续工作。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
