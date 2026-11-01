# 0089：原生 self-peer 析构与 VDEV peer detach

在 [0088](POPSICLE-NATIVE-REFERENCE-RELEASE-0088.md) 组合上接入 12 个原生函数体：peer 普通版 get/try/release、debug-ID 检查助手、逻辑删除、组件状态汇总/正序分发/异步 detach、非延迟销毁入口、peer 最终 free，以及 VDEV peer detach。保留原生 peer type 枚举。peer 由模型在 heap 创建并登记，持有真实执行的 0088 VDEV OBJMGR 引用和 peer OBJMGR/DP 引用；unmap 端点释放 DP 引用，由 native peer release 的减零分支触发析构。

原生 peer free 先临时持有 VDEV，原生 VDEV peer detach 清理 self/BSS 指针、移除 peer、递减 VDEV/PDEV 计数并归还 peer 的 VDEV 引用，再完成 PSOC detach、peer 存储释放和最后的临时 VDEV put。DP VDEV 完成模型等待实际 host peer free 与临时 pin 归还，代替原先仅根据标志归并 peer gone 的做法。

普通与 trace 两个 VDEV 配置继续执行完整 0088 套件。新增 24 个用例：peer 组件异步成功、组件失败、VDEV 列表移除失败、PSOC detach 失败、错误异步完成参数、unmap 后额外 peer 引用仍在，各在提前/延迟 unmap 下运行，并由两种 VDEV trace 配置分别执行。列表失败可能已清理 self/BSS，PSOC 失败发生在 VDEV detach 和 peer pin 归还后，检查已发生的部分效果而不伪造回滚。附加用例的 BSS 指针有/无与提前/延迟 unmap 共用测试位，不宣称这些维度的独立全组合。新增五项负对照，累计 29 项。

CI [41332655703](https://github.com/xxz3312/XAirDrop-17/actions/runs/41332655703)（`b1de1f3`）已全部通过：53 项 Python 检查、新原生 self-peer 回收模型、24 个新增组件/引用用例、累计 29 项负对照、0088/0087/0086/0085/0084/0083/0082 独立模型与旧 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。42 份模型报告所列生产源码哈希均已与仓库源码核对，其中 36 份与本模型共享主生产文件；37 个路径别名均与相应 Git blob 及 SHA-256 一致。12 个函数体从固定源码独立匹配，peer type 枚举及三份原始 native 输入的 Git blob 身份也已核对。完整生成源码已从固定快照与既有补丁重建，SHA-256 与 CI 一致；本地未执行 C 编译。报告 ZIP 校验值、实际链接 WLAN 模块和布局候选哈希已核对；WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-peer-destructor-0089-validation.json)。

peer 引用选择非 trace API 与原生 debug-ID 检查分支；peer trace 数据库和 FEATURE_DELAYED_PEER_OBJ_DESTROY 工作队列版本未认证。peer 创建、VDEV attach、处理器注册、两个组件测试处理器、QDF lock/atomic、DP unmap 生产者、PSOC/链表与 PDEV 计数端点仍为平台模型。原生 VDEV peer detach 本体、peer 存储 free 和 0088 VDEV 引用函数确实执行，但不代表完整真实 DP→对象管理器异步调用图、并发或自动父资源租约已完成。STA/BSS 递归引用、临时 peer 和非 self peer 通知分支不在本阶段认证范围。受控 BUG 分支只记录模型 trap；失败子用例保留剩余资源至进程结束。

活动 START/UP SSR 恢复、native shutdown 自动协调、完整 AWDL 收包与实机验证仍待后续工作。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
