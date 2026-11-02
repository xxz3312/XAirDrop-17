# 0093：peer/VDEV 组合中的原生 PDEV 最终析构与堆释放

在 0092 的选定 parent/peer/VDEV 序列中，用 host heap PDEV 替代静态父存储，并执行原生 PDEV object_status、组件 detach、最终 destroy dispatcher 与最终 free 四个函数体。此前六个原生 PDEV 引用/attachment 函数体保持执行。PDEV registry 中的两个 sentinel handler 验证原生正序组件分发；异步组件完成后通过原生 component_detach 恢复最终 free。

调用方关闭私有生产者、确认 work/list 空闲、归还最后父引用后，由原生最终 free 执行 PSOC detach、父锁销毁、原生延迟 peer queue deinit/QDF cancel、队列锁销毁及实际 host heap free。调用方不提前 deinit 队列。其余 0090 baseline 使用静态 fallback。

0092 的 40 个序列迁移到堆父对象；另外 16 个序列覆盖两种 VDEV trace、有/无额外父引用，以及父组件异步、组件失败、PSOC detach 失败和错误异步 token。五项既有负对照继续执行，新增六项检查 PSOC detach、锁/队列关闭、实际释放、组件顺序与异步等待。

PDEV 分配/初始化、组件注册与 sentinel handler、PSOC detach、锁/列表及 Linux workqueue 仍为模型。未执行原生 PDEV create 或真实组件实现，真实 DP unmap/完成图、PSOC 生命周期、并发迟到生产者、自动停机协调与活动 START/UP SSR 恢复仍未完成。生产内核未修改，backend 关闭，手机无需操作。

CI 与独立验收待完成。
