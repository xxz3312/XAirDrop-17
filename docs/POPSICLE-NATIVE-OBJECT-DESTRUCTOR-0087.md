# 0087：原生 VDEV 析构分发与 MLME 组件销毁

0086 的零引用释放调用方改为完整原生 `wlan_objmgr_vdev_obj_destroy`。同时编入原生 object-status 汇总、component detach 和完整 `mlme_vdev_obj_destroy_handler`。沿用原生组件 ID 与对象状态枚举，54 个组件槽位；MLME 使用原生处理器体，另两个槽为检查逆序的测试处理器，其余关闭。

16 种 WMA 主流程、三次 ratemask 流程与 32 种普通清理组合继续执行；保留既有失败保留用例和 11 项负对照。新增 12 个带/不带外持引用用例，覆盖异步组件成功、组件失败、MLO detach 拒绝、错误逻辑删除状态、MLME detach 不匹配，以及错误异步完成参数。新增四项负对照，检查逆序分发、ASYNC 等待、组件失败门槛及 MLME→SM 销毁调用方。

保持原生状态汇总的实际行为：ASYNC 且 published pointer 非空不会单独触发 ASYNC；未列出的错误状态不被汇总为失败。异步测试处理器把上下文保留在 VDEV 外并清空 published slot 后返回 ASYNC；完成时通过原生 detach(NULL) 继续最终释放。错误完成参数保留剩余对象。原生 MLME 处理器忽略 detach 返回值，模型检查生产 final-free 的 attached-pointer veto 仍保留 VDEV 与父资源；不伪造已释放 SM/MLME 的回滚。

CI [41284004867](https://github.com/xxz3312/XAirDrop-17/actions/runs/41284004867)（`e6d68ca`）已全部通过：53 项 Python 检查、新原生析构模型、12 个新增组件/外持引用用例、15 项负对照、0086/0085/0084/0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。40 份模型报告所列生产源码哈希均已与仓库源码核对，其中 34 份与本模型共享 runtime/radio 等主文件；不同路径别名也已对照相应 Git blob 验证。四个原生函数体与两组枚举独立匹配固定版本，四份 native 输入的原始 Git blob 身份一致。完整生成源码在实现时从固定快照与既有补丁重建，SHA-256 与 CI 匹配；本地未执行 C 编译。报告 ZIP 校验值、实际链接模块与布局候选哈希均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-object-destructor-0087-validation.json)。

逻辑删除、引用获取/释放与计数、创建与处理器注册仍是平台模型；真实 release_ref/debug 与 registration init 未编入。本阶段执行真实析构分发器与 MLME 处理器体，不代表其完整底层调用图。CM、reconfig timer、ext-destroy endpoint、minidump、MLO detach、锁与父列表仍为模型。SM 观察适配器沿用既有 owner helper 执行原生 SM wrapper，并仅为测试清理 parent handle。受控 QDF_BUG 分支记录模型 trap 后返回以便检查，不认证实际内核 BUG 策略。错误子用例保留剩余资源至进程结束。

DP/peer 真实析构图、自动父资源停机协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待后续工作。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
