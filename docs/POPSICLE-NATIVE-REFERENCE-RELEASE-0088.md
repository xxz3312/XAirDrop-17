# 0088：原生 VDEV 引用准入、逻辑删除与最终释放

在 [0087](POPSICLE-NATIVE-OBJECT-DESTRUCTOR-0087.md) 析构组合上，编入原生 get_ref、try_get_ref、release_ref 的普通/trace 两个版本，以及完整 obj_delete，共七个函数体。完整保留 109 个 native ref ID 枚举值。每个原生总计数与 per-ID 计数由原子端点模型维护；旧 refs 字段仅作为核对镜像，不再独立减到零触发析构。

逻辑删除原生体先关闭对象状态准入、通知逻辑删除，再释放 OBJMGR 引用。组件测试处理器在逻辑删除前准备好；只有原生 release_ref 的 aggregate 减零分支进入观察适配器，再调用 0087 的原生析构分发器。尚未执行真实创建/注册 init。普通和 trace 版本各自重跑整个 0087 主套件及失败保留用例；另各覆盖三个额外持有引用的六种释放顺序、带/不带单独外持引用，共 24 个新增完整序列。

新增空指针、未持有 ID、总计数为零、全部八个非 CREATED 状态的原生契约。保留原生行为：raw get_ref 没有对象状态准入检查，try_get_ref 才有；拒绝后 print_cnt 仍随每次尝试递增。九个新增负对照分别移除两种版本的零引用门槛、per-ID 持有检查、per-ID 递减、CREATED 准入门槛，以及 obj_delete 中 OBJMGR 引用释放；连同此前 15 项负对照运行。

CI [41328315517](https://github.com/xxz3312/XAirDrop-17/actions/runs/41328315517)（`16f4599`）已全部通过：53 项 Python 检查、普通与 trace 两个版本各自完整执行 0087 套件、24 个新增多引用释放序列、累计 24 项负对照、0087/0086/0085/0084/0083/0082 独立模型及既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局和最终模块记录检查。41 份报告所列生产源码哈希均已与仓库源码核对，其中 35 份与本模型共享主生产文件；37 个路径别名均与相应 Git blob 和 SHA-256 一致。七个函数体和完整引用 ID 枚举独立匹配固定源码。完整生成源码已从固定快照与既有补丁重建，SHA-256 与 CI 一致；本地未执行 C 编译。报告 ZIP 校验值、实际链接 WLAN 模块与布局候选哈希已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-reference-release-0088-validation.json)。

紧凑调用方标签 1/2/3/4 通过适配器映射到原生 HDD/OSIF/WMA/MAC 枚举值，不能据此认证每个真实内核调用方的 ID。QDF atomic/锁、debug trace 数据库回调、对象创建、组件注册及 0087 的底层端点仍是平台模型；trace 回调只检查参数和调用计数。构造的非法计数和受控 QDF_ASSERT/BUG 为隔离契约，不宣称修复引用损坏或认证真实 panic 策略。提取的原生 obj_delete 包含未消费的 print_idx，局部编译告警抑制已明确限于该函数体。

真实 DP/peer 析构图、自动父资源停机协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待后续实现。backend 关闭，无新手机包或固件/RF/AirDrop 可用证明。
