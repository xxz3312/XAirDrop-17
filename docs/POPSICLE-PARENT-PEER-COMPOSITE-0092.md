# 0092：原生 PDEV 引用接入 peer/VDEV 析构组合

新增组合保留 0090 baseline，将六个原生 PDEV get/try/put、VDEV attach/detach、逻辑删除函数体接入选定的完整 peer/VDEV/native SM 序列。VDEV 分配端点调用原生 PDEV attach；原生 VDEV 最终 free 通过 fixture 包装调用原生 PDEV detach。测试调用方保留 HDD 引用，在 peer/VDEV/SM 清理和队列 deinit 完成后归还；额外 OSIF 引用应进一步延后父对象最终减零端点。

新增 32 个成功序列覆盖两种 VDEV trace、延后 worker/直接析构/取消后重提交/立即 worker、peer 同步或异步组件及额外父引用，另有八项 peer 组件失败、VDEV/PSOC detach 失败或错误异步完成的保留用例。五项负对照检查调用方 pin、原生 attach pin/detach put、最后归还和逻辑删除准入。

本阶段仍是 fixture 调用方集成。PDEV/PSOC 为静态存储，PDEV 最终组件分发与 free 是受控标记端点，没有执行原生 PDEV free 或释放父存储；VDEV 列表为单条目模型。真实 DP unmap 生产者、DP 完成门、平台工作队列与并发、PSOC 生命周期保留既有模型边界；0090 其他用例未启用新的 PDEV attach。没有生产内核改动，没有自动停机协调；backend 关闭，手机无需操作。

构建与独立验收待完成。
