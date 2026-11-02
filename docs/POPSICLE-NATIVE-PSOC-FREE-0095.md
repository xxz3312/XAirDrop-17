# 0095：原生 PSOC 最终析构与堆释放组合

**代码已集中实现，待统一编译验证。**

在 0094 的引用与映射合同上，选定用例的 PSOC 改为 host heap 存储，保留 static fallback 运行既有 baseline。新增执行原生 PSOC object_status、component_detach、最终 dispatcher、peer_list_deinit 和最终 free 五个函数体；此前六个 PSOC 引用/map/逻辑删除及 10 个 PDEV 原生函数体保持执行。

最后 PSOC caller 引用在实际 PDEV host heap free 之后归还；由原生 dispatcher 正序调用两个模型组件处理器，成功后原生 free 调用模型全局 detach、原生 peer-list deinit，逐个销毁原始头文件规定的 64 个空哈希桶，再销毁 PSOC 锁并实际释放 PSOC host heap。异步组件完成通过原生 component_detach 恢复最终 free；组件失败、全局 detach 失败及错误异步 token 保留尚未释放的资源，不伪造回滚。

此前 72 个序列迁移到堆 PSOC；新增 16 个 PSOC 异步/失败/错误完成组合，共 88 个序列。保留 17 项既有负对照，新增九项检查全局 detach、哈希锁、64 桶完整清理、最终锁、实际 heap free、组件顺序与成功/异步状态门。

分配/初始化、组件 registry/sentinel handler、全局 PSOC 注册与 detach、空哈希桶、锁和原子仍是模型。未执行原生 PSOC/PDEV create、原生 peer-list init、真实 PSOC peer/VDEV 引用图、真实组件、真实 DP unmap/完成回调及 Linux 并发。失败子进程保留未完成资源，QDF_BUG 是受控模型端点。只模拟私有父资源整体停机，真实共享 PSOC 的关闭准入仍需协调。生产内核未修改，backend 保持关闭，手机无需操作。
