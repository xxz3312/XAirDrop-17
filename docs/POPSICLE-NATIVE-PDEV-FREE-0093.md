# 0093：peer/VDEV 组合中的原生 PDEV 最终析构与堆释放

在 0092 的选定 parent/peer/VDEV 序列中，用 host heap PDEV 替代静态父存储，并执行原生 PDEV object_status、组件 detach、最终 destroy dispatcher 与最终 free 四个函数体。此前六个原生 PDEV 引用/attachment 函数体保持执行。PDEV registry 中的两个 sentinel handler 验证原生正序组件分发；异步组件完成后通过原生 component_detach 恢复最终 free。

调用方关闭私有生产者、确认 work/list 空闲、归还最后父引用后，由原生最终 free 执行 PSOC detach、父锁销毁、原生延迟 peer queue deinit/QDF cancel、队列锁销毁及实际 host heap free。调用方不提前 deinit 队列。其余 0090 baseline 使用静态 fallback。

0092 的 40 个序列迁移到堆父对象；另外 16 个序列覆盖两种 VDEV trace、有/无额外父引用，以及父组件异步、组件失败、PSOC detach 失败和错误异步 token。五项既有负对照继续执行，新增六项检查 PSOC detach、锁/队列关闭、实际释放、组件顺序与异步等待。

PDEV 分配/初始化、组件注册与 sentinel handler、PSOC detach、锁/列表及 Linux workqueue 仍为模型。未执行原生 PDEV create 或真实组件实现，真实 DP unmap/完成图、PSOC 生命周期、并发迟到生产者、自动停机协调与活动 START/UP SSR 恢复仍未完成。生产内核未修改，backend 关闭，手机无需操作。

离线验收完成：[CI 41416403715](https://github.com/xxz3312/XAirDrop-17/actions/runs/41416403715)（`61d86cb`）两项作业均成功。0093 的 56 个堆父对象序列、11 项负对照、0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项选定布局和模块记录检查均通过。

完整测试源码已从固定 Xiaomi 快照与既有补丁独立重建，SHA-256 为 `744230933dfaf33bbf59f6740219b2717f831587edc5b6cc6f4a561f961b182f`，与 CI 一致；10 个原生 PDEV 函数体、原始 PDEV 文件 SHA-256 与 Git blob 身份均已核对。0092 独立组合的生成源码也匹配。45 份报告中的生产源码与仓库一致，核对 37 个路径别名，固定源码清单与仓库一致。两份验证 ZIP digest 匹配 Actions；布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。见[验证记录](research/popsicle-native-pdev-free-0093-validation.json)。

异步 PDEV 组件完成由 fixture 明确在进程上下文递送；组件失败的 QDF_BUG 为受控捕获端点，未认证实际内核故障恢复。失败用例保留尚未释放的 host 资源至子进程退出。下一步仍需真实 DP 完成图、PDEV create/真实组件与 PSOC 生命周期，以及生产父资源自动停机协调；本阶段不授权启用后端。
