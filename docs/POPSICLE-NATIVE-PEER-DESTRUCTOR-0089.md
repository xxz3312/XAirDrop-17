# 0089：原生 self-peer 析构与 VDEV peer detach

在 [0088](POPSICLE-NATIVE-REFERENCE-RELEASE-0088.md) 组合上接入 12 个原生函数体：peer 普通版 get/try/release、debug-ID 检查助手、逻辑删除、组件状态汇总/正序分发/异步 detach、非延迟销毁入口、peer 最终 free，以及 VDEV peer detach。保留原生 peer type 枚举。peer 由模型在 heap 创建并登记，持有真实执行的 0088 VDEV OBJMGR 引用和 peer OBJMGR/DP 引用；unmap 端点释放 DP 引用，由 native peer release 的减零分支触发析构。

原生 peer free 先临时持有 VDEV，原生 VDEV peer detach 清理 self/BSS 指针、移除 peer、递减 VDEV/PDEV 计数并归还 peer 的 VDEV 引用，再完成 PSOC detach、peer 存储释放和最后的临时 VDEV put。DP VDEV 完成模型等待实际 host peer free 与临时 pin 归还，代替原先仅根据标志归并 peer gone 的做法。

普通与 trace 两个 VDEV 配置继续执行完整 0088 套件。新增 24 个用例：peer 组件异步成功、组件失败、VDEV 列表移除失败、PSOC detach 失败、错误异步完成参数、unmap 后额外 peer 引用仍在，各在提前/延迟 unmap 下运行，并由两种 VDEV trace 配置分别执行。列表失败可能已清理 self/BSS，PSOC 失败发生在 VDEV detach 和 peer pin 归还后，检查已发生的部分效果而不伪造回滚。新增五项负对照，累计 29 项。

CI 待完成；本地仅重建生成源码与独立核对原生函数，不执行 C 编译。通过后补充验证记录。

peer 引用选择非 trace API 与原生 debug-ID 检查分支；peer trace 数据库和 FEATURE_DELAYED_PEER_OBJ_DESTROY 工作队列版本未认证。peer 创建、VDEV attach、处理器注册、两个组件测试处理器、QDF lock/atomic、DP unmap 生产者、PSOC/链表与 PDEV 计数端点仍为平台模型。原生 VDEV peer detach 本体、peer 存储 free 和 0088 VDEV 引用函数确实执行，但不代表完整真实 DP→对象管理器异步调用图、并发或自动父资源租约已完成。STA/BSS 递归引用、临时 peer 和非 self peer 通知分支不在本阶段认证范围。受控 BUG 分支只记录模型 trap；失败子用例保留剩余资源至进程结束。

活动 START/UP SSR 恢复、native shutdown 自动协调、完整 AWDL 收包与实机验证仍待后续工作。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
