# 0091：peer worker 期间的原生 PDEV 引用保留

本阶段增加独立的 parent/queue fixture：执行原生 PDEV get/try/release、VDEV attach/detach、PDEV 逻辑删除与最终 free 七个函数体，以及 0090 中原生 peer 队列/QDF work 的十四个函数体。使用原始引用 ID 枚举。PDEV 在 host heap 创建，VDEV attach 持有原生 OBJMGR 引用，fixture 调用方额外取得原生 HDD 引用；根对象逻辑删除后拒绝新引用，worker 内的 VDEV detach 归还 attachment 引用，但不能提前销毁仍被调用方引用的 PDEV。

覆盖 50 个序列：一/两个 VDEV、直接/队列分发、立即/延后 worker、根引用提前/延后释放、额外引用及两种最终归还顺序，另含两项取消后重提交流程；八项负对照检查调用方 pin、attach pin、detach put、最终减零、引用 ID、逻辑删除准入、排空和生产者关闭。排空后在 worker 外归还最后父引用，原生 PDEV free 依次执行 PSOC detach、PDEV 锁销毁、原生 queue deinit/QDF cancel、队列锁销毁和实际 host heap free。

该 fixture 独立于完整 0090 WMA/DP/MLME 组合，后者继续单独回归。这里的 peer 析构端点模拟最后 VDEV detach；PDEV 组件析构分发器为调用原生 free 的受控端点，PSOC detach、Linux workqueue/锁/原子/链表仍为模型。额外 PDEV 引用只能保留存储，不能阻止 native 组件先行关闭；实际 PSOC 生命周期、全局迟到生产者、真实 DP 图和自动停机协调尚未实现。原生合并计数与列表插入行为没有修改，计数不作为排空证据。生产内核不变，backend 关闭，手机无需操作。

CI 与产物独立校验待完成。
