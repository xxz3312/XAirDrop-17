## 最新阶段 0097（离线验收完成）

0096 组合接入未改写的原生 `dp_peer_unref_delete()`。DP peer 使用独立 host heap，原生函数执行模块引用递减、最终引用和 peer-ID/AST 检查、inactive 列表移除、清理与锁销毁调用、实际 peer heap free，随后归还 DP VDEV CHILD 引用并进入原生 VDEV finalizer；VDEV heap free 后经既有 checking trampoline 调用生产运行时完成回调。额外 TX/RX 引用尚存时保留 peer 与 CHILD；覆盖 RX 模块计数绕过规则。

相关代码和用例集中完成后统一验证，[CI 41488890858](https://github.com/xxz3312/XAirDrop-17/actions/runs/41488890858)（`c4926c2`）两项作业成功：120 组组合、46 项失败控制、0096/0095/0094/0093/0092 五项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。六份生成组合源码、两个 DP 原生函数/Git blob/enum 与 HTT 常量来源及 49 份报告中的生产源码、37 个路径别名和两个 ZIP digest 已独立核对。见[0097 说明](POPSICLE-NATIVE-DP-PEER-FREE-0097.md)及[验证记录](research/popsicle-native-dp-peer-free-0097-validation.json)。

DP peer/VDEV 构造、初始引用、peer-ID map 失效、peer-gone gate、释放调度及清理端点/列表/锁/原子操作仍为模型；没有执行固件 `dp_rx_peer_unmap_handler()`。DP peer 与 ObjMgr peer 为不同对象，未声称其间已有生产引用桥。真实组件、生产停机协调、真实并发、活动 START/UP SSR、完整 AWDL 收包及整机验证仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0096（离线验收完成）

0095 组合接入未改写的原生 `dp_vdev_unref_delete()`，选定 passthru 路径执行模块引用递减、最后引用判断、清理调用、inactive 列表移除、可选删除通知、实际 DP VDEV host heap free，再经检查 trampoline 把原始令牌交给既有生产运行时完成回调。额外 HTT 引用尚存时必须保留存储；模型 peer 清理失败时保留 DP 资源，禁止完成。

相关代码和用例集中写齐后统一验证，[CI 41441718233](https://github.com/xxz3312/XAirDrop-17/actions/runs/41441718233)（`07f0c79`）两项作业成功：104 组组合、34 项负对照、0095/0094/0093/0092 独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。首次运行的最后一个错误令牌负对照有测试变体花括号问题，修正后全部重跑成功，原生函数体未改。五份生成组合源码、DP 原生函数/Git blob/enum 来源及 48 份报告中的生产源码、37 个路径别名和两个 ZIP digest 已独立核对。见[0096 说明](POPSICLE-NATIVE-DP-VDEV-FREE-0096.md)及[验证记录](research/popsicle-native-dp-vdev-free-0096-validation.json)。

DP 分配、attach/detach 设置、初始引用取得、peer-gone gate、迟到 HTT put、清理端点、列表/锁/原子操作仍为模型；未执行真实 DP peer unmap/ref-delete，也不声明 DP 与 ObjMgr 间存在已验证的直接引用释放桥。继承的父资源构造/真实组件、生产停机协调、真实并发、活动 START/UP SSR、完整 AWDL 收包和整机验证仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0095（离线验收完成）

选定序列的 PSOC 改为 host heap，原生 object_status、component_detach、最终 dispatcher、peer_list_deinit 和最终 free 五个函数体接入；此前六个 PSOC 引用/map/逻辑删除及 10 个 PDEV 原生函数体保持执行。原生 PSOC dispatcher 正序调用两个模型组件处理器，成功后原生 free 依次执行模型全局 detach、原生 peer-list deinit 的 64 个空模型桶和锁清理、最终 PSOC 锁销毁及实际 host heap free。异步组件经原生 completion 恢复 free；失败保留未完成部分。

相关实现、失败处理、边界用例和 CI 入口集中完成后统一验证。[CI 41436339138](https://github.com/xxz3312/XAirDrop-17/actions/runs/41436339138)（`cc815e1`）两项作业均成功：88 个组合序列、26 项负对照、0094/0093/0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局及模块记录检查均通过。完整新/旧组合源码、11 个 PSOC 和 10 个 PDEV 原生函数体、PSOC 文件/Git blob 身份及 47 份报告中的生产源码已核对，37 个路径别名、源码清单及两份 ZIP digest 匹配。见[0095 说明](POPSICLE-NATIVE-PSOC-FREE-0095.md)及[验证记录](research/popsicle-native-psoc-free-0095-validation.json)。

全局 PSOC 注册/detach、分配初始化、registry/sentinel handler、空哈希桶和平台原语仍是模型；未执行原生 PSOC/PDEV create、原生 peer-list init、真实 PSOC peer/VDEV 引用图或真实组件。只验证私有父资源整体停机合同；真实 DP unmap/完成图、并发迟到生产者、生产父资源协调、活动 START/UP SSR 恢复及完整 AWDL 收包仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0094（离线验收完成）

将六个原生 PSOC 引用、PDEV attach/detach 和逻辑删除函数体接入 0093 的堆 PDEV 组合。原生 attach 维护 ID/map/count 并取得 PSOC attachment 引用；原生 PDEV free 调用原生 PSOC detach 后，fixture caller 仍持有 PSOC HDD 引用，直到 PDEV 队列关闭及 host heap free 完成才归还。原有 56 个序列迁移到该合同，另有 16 个 PSOC OSIF 引用与归还顺序组合，共 72 个序列、17 项负对照；单槽合同检查满表与无效已脱离 ID。

[CI 41424409521](https://github.com/xxz3312/XAirDrop-17/actions/runs/41424409521)（`1d8aec3`）两项作业均成功：新增组合、0093/0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局及模块记录检查均通过。完整新/旧组合源码、六个 PSOC 和 10 个 PDEV 原生函数体、PSOC 原始文件/Git blob 身份及 46 份报告中的生产源码已核对，37 个路径别名、源码清单与两份 ZIP digest 匹配。见[0094 说明](POPSICLE-NATIVE-PSOC-LEASE-0094.md)及[验证记录](research/popsicle-native-psoc-lease-0094-validation.json)。

PSOC 最终 destroy/free 及存储仍是静态模型端点，未执行真实 PSOC 组件、PSOC peer/VDEV attachment 引用或 PSOC heap free。移除 caller pin 的负对照在原生最后引用分支进入模型端点时检测到 PDEV 仍存活，不构成实际内核 UAF 复现。容量 1 为 Kbuild 默认选择；原生 attach 的逻辑删除准入及 detach 的有效槽位 owner 检查没有修改，仅选取私有、串行化、已核对归属的映射合同。真实 DP 完成图、PSOC 最终析构、迟到生产者、自动停机协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0093（离线验收完成）

将 0092 的选定父对象改为 host heap PDEV，执行原生 PDEV object_status、component_detach、最终 dispatcher 和最终 free 四个函数体，并保留此前六个原生引用/attachment 函数体。成功路径由原生最终 free 依次执行 PSOC detach、父锁销毁、原生延迟 peer queue deinit/QDF cancel、队列锁销毁及实际 host heap free，fixture 调用方不提前 deinit。0092 的 40 个序列迁移到堆父对象，另外 16 个覆盖父组件异步、组件失败、PSOC detach 失败及错误异步 token；共 56 个序列、11 项负对照。

[CI 41416403715](https://github.com/xxz3312/XAirDrop-17/actions/runs/41416403715)（`61d86cb`）两项作业均成功：新增组合、0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局及模块记录检查均通过。独立重建的新/旧组合源码、10 个原生 PDEV 函数体、原始文件与 Git blob 身份均匹配；45 份报告中的生产源码、37 个路径别名和固定源码清单已核对，两份 ZIP digest 匹配。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖。见[0093 说明](POPSICLE-NATIVE-PDEV-FREE-0093.md)及[验证记录](research/popsicle-native-pdev-free-0093-validation.json)。

PDEV 分配/初始化、组件 registry/sentinel handler、PSOC detach、锁/列表及 Linux workqueue 仍为模型；QDF_BUG 为受控捕获端点，异步完成由 fixture 选择进程上下文。原生 PDEV create、真实组件/DP unmap 生产者与完成图、PSOC 生命周期、并发迟到生产者、自动停机协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待继续。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0092（离线验收完成）

将六个原生 PDEV 引用、VDEV attach/detach 和逻辑删除函数体接入选定的 0090 peer/VDEV/native SM 析构组合。VDEV 分配端点取得原生 PDEV attachment pin；原生 VDEV 最终 free 调用原生 PDEV detach 归还它。显式调用方持有 HDD 引用，等 peer/VDEV 存储清理和队列 deinit 完成后再归还；可选 OSIF 引用继续推迟父对象最终减零端点。新增 32 个成功序列和八项失败保留序列，覆盖两种 VDEV trace，另有五项负对照；0090 baseline 保留。

[CI 41408965293](https://github.com/xxz3312/XAirDrop-17/actions/runs/41408965293)（`69e6d0f`）两项作业均成功：新增组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局和模块记录检查均通过。独立重建的完整测试源码及六个原生 PDEV 函数体哈希与 CI 一致；新组合与 43 份 diagnostic 模型报告所列生产源码均匹配，37 个路径别名及固定源码清单已核对，两份验证 ZIP digest 匹配。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖。见[0092 说明](POPSICLE-PARENT-PEER-COMPOSITE-0092.md)及[验证记录](research/popsicle-parent-peer-composite-0092-validation.json)。

PDEV/PSOC 存储仍为静态模型，父对象最终组件分发/free 是受控标记端点；没有执行组合中的原生 PDEV free，也没有父 heap 释放认证。VDEV 创建、DP unmap 生产者/完成门、工作队列及平台原语保留既有模型边界。真实 DP 回调、迟到生产者、PDEV/PSOC 最终析构、自动停机协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0091（离线验收完成）

独立 parent/queue fixture 执行七个原生 PDEV 引用、attach/detach、逻辑删除和最终 free 函数体，以及十四个原生 peer queue/QDF work 函数体。50 个序列及八项负对照验证：调用方保留 PDEV 引用，worker 内 VDEV detach 后父存储仍存活，关闭生产者并在进程上下文显式排空后归还最后引用；原生 free 按序关闭队列并释放 host heap。

[CI 41348908513](https://github.com/xxz3312/XAirDrop-17/actions/runs/41348908513)（`10eaf90`）通过 53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、严格链接、七项布局和模块记录检查。独立核对四份原生文件、21 个函数体、引用枚举和完整 fixture 哈希；43 份生产源码报告及 37 个路径别名均匹配仓库，报告 ZIP 校验通过，布局候选对应链接 WLAN，五个模块无版本记录不匹配或缺版本依赖。见[0091 说明](POPSICLE-NATIVE-PDEV-QUEUE-0091.md)及[验证记录](research/popsicle-native-pdev-queue-0091-validation.json)。

本阶段是独立引用合同验证，并未把实际 peer/VDEV/DP 析构图接入父对象回收；组件分发、PSOC detach 和平台原语仍有模型端点。持有引用仅保留父存储，不能阻止组件关闭。真实 DP 回调、全局迟到生产者、自动停机协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待实现。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0090（离线验收完成）

在 0089 组合上执行原生 peer 延迟工作队列五个函数体与九个 QDF work 适配函数体。排队期间检查 peer heap、VDEV peer pin、DP VDEV 和 native SM 保留；worker 解开列表锁后才调用原生 peer 析构。新增 36 个队列/组件/引用组合，普通与 trace VDEV 配置分别重跑完整 0089 套件，累计 35 项负对照。

CI [41338423652](https://github.com/xxz3312/XAirDrop-17/actions/runs/41338423652)（`e444e3d`）已全部通过：53 项 Python 检查、原生 peer 延迟队列模型及 36 个新增组合、累计 35 项负对照、0089 至 0082 独立模型与旧 C 回归、完整编译、CNSS 检查、严格链接、七项选定布局及模块记录检查。43 份模型报告的生产源码哈希均已核对，其中 37 份与本模型共享主生产文件；37 个路径别名与 Git blob/SHA-256 一致。14 个新增原生函数体及四份固定输入的 Git blob 身份已独立匹配，完整生成源码重建哈希与 CI 一致，0089 生成源码也保持一致；本地未执行 C 编译。报告 ZIP 校验通过，布局候选对应最终链接 WLAN，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。离线验收完成，见[验证记录](research/popsicle-native-peer-queue-0090-validation.json)。

本阶段验证的是父对象仍存活、私有 peer 生产者已结束后，显式 flush 至工作空闲且列表空，再调用原生 deinit 的 fixture 调用方合同。原生 qdf_destroy_work 同步取消工作，不能代替排空。合并调度后的 active_work_cnt 残留、运行期间重入队需再次 flush、列表满时 enqueue 忽略 insert 失败均已在模型中观察；没有修改这些生产行为，也不以计数授权停机。

Linux workqueue/锁/链表和若干 DP/对象管理器端点仍为模型。父对象最终引用在 worker 内释放、全局迟到生产者、真实 DP 回调图、native shutdown 自动协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0090](POPSICLE-NATIVE-PEER-QUEUE-0090.md)。

## 阶段 0089（离线验收完成）

12 个原生函数体进入 self-peer 回收组合：非 trace peer 引用 API 与 debug-ID 检查、逻辑删除、正序组件分发/状态汇总/异步 detach、非延迟销毁入口、peer 最终 free，以及 VDEV peer detach。unmap 端点释放真实执行的 native peer DP 引用，由原生计数减零触发析构。原生 peer free 临时持有 VDEV，移除 VDEV/PSOC 归属并释放 peer 存储，最后归还临时 VDEV 引用。

CI [41332655703](https://github.com/xxz3312/XAirDrop-17/actions/runs/41332655703)（`b1de1f3`）已全部通过：53 项 Python 检查、新原生 self-peer 回收模型、24 个新增组件/引用用例、累计 29 项负对照、0088/0087/0086/0085/0084/0083/0082 独立模型与旧 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。42 份模型报告所列生产源码哈希均已与仓库源码核对，其中 36 份与本模型共享主生产文件；37 个路径别名均与相应 Git blob 及 SHA-256 一致。12 个函数体从固定源码独立匹配，peer type 枚举及三份原始 native 输入的 Git blob 身份也已核对。完整生成源码已从固定快照与既有补丁重建，SHA-256 与 CI 一致；本地未执行 C 编译。报告 ZIP 校验值、实际链接 WLAN 模块和布局候选哈希已核对；WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-peer-destructor-0089-validation.json)。

新增 24 个组件异步/失败、列表/PSOC detach 失败、错误完成参数与额外 peer 引用用例，分别经过提前/延迟 unmap 和两种 VDEV trace 配置；BSS 指针与 unmap 共用测试位，不宣称独立全组合。失败保留已经发生的部分效果，不伪造回滚。peer 创建/注册/组件处理器、QDF atomic/锁、DP 生产者、PSOC/链表与 PDEV 计数端点仍为模型；peer trace 数据库及延迟销毁队列尚未覆盖。完整真实 DP 回调图、native shutdown 自动协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0089](POPSICLE-NATIVE-PEER-DESTRUCTOR-0089.md)。

## 阶段 0088（离线验收完成）

普通/trace 两套原生 get_ref、try_get_ref、release_ref 与完整 obj_delete 已进入组合执行，保留原生 109 个引用 ID。原生逻辑删除先关闭准入再释放 OBJMGR 引用，原生 aggregate 减零才进入 0087 析构分发器；旧 refs 仅是被核对的镜像，不独立触发销毁。两种版本各重跑完整套件，并各覆盖三个额外引用的六种释放顺序、带/不带外持引用，共 24 个新增完整序列。新增九项负对照，总计 24 项。

CI [41328315517](https://github.com/xxz3312/XAirDrop-17/actions/runs/41328315517)（`16f4599`）已全部通过：53 项 Python 检查、普通与 trace 两个版本各自完整执行 0087 套件、24 个新增多引用释放序列、累计 24 项负对照、0087/0086/0085/0084/0083/0082 独立模型及既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局和最终模块记录检查。41 份报告所列生产源码哈希均已与仓库源码核对，其中 35 份与本模型共享主生产文件；37 个路径别名均与相应 Git blob 和 SHA-256 一致。七个函数体和完整引用 ID 枚举独立匹配固定源码。完整生成源码已从固定快照与既有补丁重建，SHA-256 与 CI 一致；本地未执行 C 编译。报告 ZIP 校验值、实际链接 WLAN 模块与布局候选哈希已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-reference-release-0088-validation.json)。

保持原生差异：raw get_ref 本身没有状态准入门槛，try_get_ref 才会拒绝八种非 CREATED 状态；受控 QDF_ASSERT/BUG 仅为隔离契约。紧凑调用方标签映射到原生 HDD/OSIF/WMA/MAC ID，不能认证全部真实调用方。atomic/锁、trace 数据库、创建与组件注册仍为平台模型；真实 DP/peer 析构图、自动父资源协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0088](POPSICLE-NATIVE-REFERENCE-RELEASE-0088.md)。

## 阶段 0087（离线验收完成）

0086 的零引用清理继续进入原生 VDEV 析构分发器、组件状态汇总、component detach 和完整 MLME destroy handler。保留原生 54 个组件槽位与对象状态枚举，MLME 为原生处理器体，另外两个槽为逆序检查的测试处理器。新增 12 个带/不带外持引用用例，覆盖异步成功、组件失败、MLO detach 拒绝、错误逻辑状态、MLME detach 不匹配和错误异步完成参数。

CI [41284004867](https://github.com/xxz3312/XAirDrop-17/actions/runs/41284004867)（`e6d68ca`）已全部通过：53 项 Python 检查、新原生析构模型、12 个新增组件/外持引用用例、15 项负对照、0086/0085/0084/0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。40 份模型报告所列生产源码哈希均已与仓库源码核对，其中 34 份与本模型共享 runtime/radio 等主文件；不同路径别名也已对照相应 Git blob 验证。四个原生函数体与两组枚举独立匹配固定版本，四份 native 输入的原始 Git blob 身份一致。完整生成源码在实现时从固定快照与既有补丁重建，SHA-256 与 CI 匹配；本地未执行 C 编译。报告 ZIP 校验值、实际链接模块与布局候选哈希均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-object-destructor-0087-validation.json)。

原生 MLME 处理器忽略 detach 错误时，生产 final-free 的 attached-pointer veto 仍挡住 VDEV/父资源释放；已释放的 SM/MLME 不伪造回滚。实际引用获取/释放、计数和处理器注册/创建仍为平台模型，真实 release_ref/debug 与 registration init 尚未编入；DP/peer 真实析构图、自动父资源协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0087](POPSICLE-NATIVE-OBJECT-DESTRUCTOR-0087.md)。

## 阶段 0086（离线验收完成）

普通 DOWN/INIT 后，0085 完整 WMA/SM 主流程继续经过原生 PE 析构、普通 WMA peer 删除、固件 peer/VDEV DELETE 响应来源、DP 完成、WMA/legacy 释放、原生 SM 销毁与 VDEV 最终释放。新增 32 种串行回调/引用组合、六类失败保留和两个生产等待门槛负对照；外持引用与 flush-service 共用测试位，不能宣称六个独立维度的全部组合。

CI [41275178699](https://github.com/xxz3312/XAirDrop-17/actions/runs/41275178699)（`388b029`）已全部通过：53 项 Python 检查、16 种 WMA 主流程与三次 ratemask 流程接续完整清理、32 种新增回调/引用组合、六类新增失败保留、既有八类 WMA 失败保留、11 项负对照、0085/0084/0083/0082 独立模型与旧 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。39 份模型报告的公共生产源码哈希一致，五个生产文件已独立核对；两个普通 WMA 删除函数与固定源码独立匹配，owned peer 删除入口与 0017 补丁一致。完整生成源码在本地从固定快照与既有补丁重建，SHA-256 与 CI 匹配；本地未执行 C 编译。报告 ZIP 校验值及实际链接模块/布局候选均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-cleanup-0086-validation.json)。

peer 引用/逻辑删除/unmap、DP 完成、component destructor 调用方和父列表仍为平台模型；模型明确将 DP VDEV 完成延迟至 peer unmap/逻辑删除完成，不认证真实 DP/peer 析构图或硬件并发顺序。真实对象管理器析构调用方、父资源停机自动协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待后续工作。backend 关闭，手机无需操作。见[0086](POPSICLE-NATIVE-CLEANUP-0086.md)。

## 阶段 0085（离线验收完成）

完整原生 WMA START 响应函数及 MAC/DP 更新、频道响应、ratemask 转换三个助手已进入 PAS/NDI 复合模型。覆盖频道复制、TX streams、MAC/功率和原生指针长度事件参数；检查早期失败、部分字段已更新、UP 后失败及 SM 拒绝事件时 controller 封锁并保留资源。原生 ratemask 发送失败仅记录继续、越界配置跳过的行为保持原样。

CI [41273213537](https://github.com/xxz3312/XAirDrop-17/actions/runs/41273213537)（`82baf02`）已全部通过：53 项 Python 检查、新完整 WMA 响应模型、16 种主流程、3 次额外 ratemask 流程、6 项类型映射契约、8 类失败保留、九项负对照、0084/0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。38 份报告的公共生产源码哈希一致，五个生产文件已独立核对；四个函数体从固定源码加 0015 补丁重建后匹配，ratemask 类型、回调/PAS 表与独立模型哈希一致。完整生成源码也已在本地从固定源码快照与补丁重建，与 CI 生成源码哈希一致；本地未执行 C 编译。报告 ZIP 校验值及实际链接模块/布局候选均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 见[0085](POPSICLE-NATIVE-WMA-START-0085.md)与[验证记录](research/popsicle-native-wma-start-0085-validation.json)。

DP/policy/ratemask transport、上下文/config 等端点仍是平台模型；非 PAS 分支和 AP MCC 条件配置未由本阶段认证。delivery bridge 的观察/拒绝探针明确记录，不将源函数体覆盖写成全部传递调用或实际固件执行。物理 PE/peer 完整清理、原生 object-manager 调用方、父资源停机自动协调、活动 START/UP SSR 恢复及完整 AWDL 收包仍需后续实现/验证。backend 关闭，手机无需操作。

## 阶段 0084（离线验收完成）

原生 12 个 inline 回调、完整 ops 类型及 32 槽 PAS 表已进入模型执行。每个 adapter 覆盖 NULL ops/slot 默认 SUCCESS、参数和三类返回值传播；完整绑定检查及两个新增负对照避免把缺回调的默认成功当作动作完成。八种主流程与既有五项负对照保留，validation/down 两个竞态测试探针明确记录。

CI [41270857085](https://github.com/xxz3312/XAirDrop-17/actions/runs/41270857085)（`01b6203`）已全部通过：53 项 Python 检查、新原生回调模型、12 个 adapter 的 60 项空槽/参数/返回值契约检查、完整 32 槽绑定、八种主流程、七项负对照、0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局和最终模块记录检查。37 份模型报告的公共生产源码哈希一致，五个生产文件已独立核对；12 个函数与原生 ops 类型哈希匹配，PAS 表从 0011/0022 补丁独立重建后匹配。整个 ops 头文件与原始固定源码的差异来自既有 0007 补丁的 PASSTHRU 类型宏/注释，重建后的整文件哈希也匹配，ops 声明没有差异。报告 ZIP 校验值与实际链接模块/布局候选记录均已复核，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 见[0084](POPSICLE-NATIVE-CALLBACKS-0084.md)及[验证记录](research/popsicle-native-callbacks-0084-validation.json)。

完整 WMA 后处理、真实 object-manager 调用方、物理 PE/peer 生命周期、实际 START/UP SSR 恢复、父资源自动协调与完整 AWDL 收包仍需后续工作。平台字段/锁/minidump/transport 仍有模型；backend 关闭，手机无需操作。

## 阶段 0083（离线验收完成）

新增模型实际执行原生 `mlme_vdev_sm_create/destroy`，覆盖创建分配失败、VM-id 名称/初始状态、minidump 与锁建立/释放顺序、三次成功配对释放，并包围八种主流程和拒绝用例。CI [41247250279](https://github.com/xxz3312/XAirDrop-17/actions/runs/41247250279)（`22cd90f`）已全部通过：53 项 Python 检查、新原生创建/销毁模型、八种启动组合、五项负对照、0082 独立引擎模型、既有 C 回归、完整 WLAN/Wonder/provider 编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。36 份模型报告的公共生产源码哈希一致；两个原生 wrapper 函数哈希与固定源码独立匹配，五个生产文件哈希、报告 ZIP 校验值及实际链接模块/布局候选记录均已核对。WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 见[0083](POPSICLE-NATIVE-SM-OWNER-0083.md)与[验证记录](research/popsicle-native-sm-owner-0083-validation.json)。

锁/minidump 仍是平台模型，真实 object-manager 调用方、MLME callback adapter、完整 WMA 后处理和物理 PE/peer 生命周期仍未覆盖。实际 START/UP 的 SSR 恢复、父资源/停机自动协调及完整 AWDL 收包仍未完成；backend 关闭，无新手机操作。

## 阶段 0082（验收完成）

原生通用状态机引擎、完整原始状态/事件表及真实枚举已进入模型执行，原生 transition/deliver 桥接替代层级适配器。首次 START 允许匹配的 INIT/0 或 INIT/IDLE，初始子状态漂移拒绝；新建 INIT/0 遇 SSR 保留资源。CI [41244837690](https://github.com/xxz3312/XAirDrop-17/actions/runs/41244837690)（`005ee1b`）已全部通过：53 项 Python 检查、原生引擎八种启动组合、三项负对照、既有 C 回归、完整 WLAN/Wonder/provider 编译、CNSS 名称检查、严格模块链接、七项选定结构布局及最终模块记录检查。35 份模型报告的公共生产源码哈希已交叉匹配，五个生产文件与已验证源码独立核对；WLAN 未解决依赖为空，五个模块均无版本记录不匹配或缺版本依赖。报告 ZIP 的 SHA-256 已核对，布局候选模块哈希与实际链接 WLAN 模块一致。 详见[0082](POPSICLE-NATIVE-ENGINE-0082.md)和[验证记录](research/popsicle-native-engine-0082-validation.json)。

本阶段的离线验收已完成。实际 START/UP 的 SSR 恢复、父资源自动协调、真实 MLME create/destroy/callback adapter 与完整 monitor/AWDL 收包仍需后续实现和验证，backend 关闭，手机无需操作。

## 阶段 0081

START/STOP 发送现在同时要求精确原生子状态，INIT 校验要求 INIT/IDLE。新增模型编入 23 段原生 entry/event 函数及原生 INIT/API，普通主流程经过其中 20 段，贯通 START→UP→DOWN→STOP→INIT、双频与提前响应，检查原生 handled=true 掩盖回调失败时 controller 仍隔离资源。两个负对照移除 START/STOP 子状态门槛，必须均被识别。CI [41208058251](https://github.com/xxz3312/XAirDrop-17/actions/runs/41208058251) 已通过 53 项 Python 检查、新原生主流程模型及两个子状态负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；11 组模型公共生产哈希、23 段原生函数哈希、9 个 native 文件哈希、实际链接符号和模块记录已复核。通用状态机引擎/层级分派/transition 仍有模型，实机和固件未验证；不扩大 SSR 回收范围，backend 关闭，手机无需操作。见[0081](POPSICLE-NATIVE-LIFECYCLE-0081.md)。

## 阶段 0080

新增原生 INIT START 校验被原始 SSR 拒绝后的显式回收：必须依次确认 validation 拒绝、down 通知被拒绝、原生分支 origin、成功返回且 SM 已解锁，并保持 INIT/IDLE、空事务及零 pending/users。保留 BLOCKED/ESHUTDOWN 和入口历史，不冒充 DOWN；七项原生计划在 timer drain 前后重检。新增原生 API wrapper 执行、双频与异常来源/状态/回调顺序检查，以及缺失原生 origin、缺失 SM unlock 两个负对照。CI [41200864386](https://github.com/xxz3312/XAirDrop-17/actions/runs/41200864386) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；十组模型生产哈希、九个 native 文件哈希、九项 START 回收入口实际链接及模块记录已复核。真正进入 START 状态/发送 START/等待响应/UP 的回收、自动父资源协调及完整接收路径仍未完成，backend 关闭，手机无需操作。见[0080](POPSICLE-NATIVE-INIT-RESET-0080.md)。

## 阶段 0079

新增 START SM 意图提交与原生入口间的共享锁门槛，原始 SSR 封锁先到则不调用 native dispatch，保存独立 SM-entry-abort 来源并沿用计划重检/显式回收；入口标记先到则继续保留资源。模型实际执行固定版本 INIT START handler，覆盖 PAS 校验失败 handled=true、额外 down-complete 通知且仍不回收的行为。新增双频、20 类拒绝、七项计划/当前参数与 timer 漂移、入口后拒绝、两个负对照。CI [41197736928](https://github.com/xxz3312/XAirDrop-17/actions/runs/41197736928) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希、新 origin 实际链接和模块记录已复核。真正进入 SM/START/UP 后的回收、自动父资源协调和完整接收路径仍未完成，backend 关闭，手机无需操作。见[0079](POPSICLE-SM-ENTRY-RESET-0079.md)。

## 阶段 0078

新增 START 准备成功、七项原生编码器摘要与原计划完全匹配、尚未提交任何 SM 的 SSR 回收。计划按值拷贝，不借用 caller 存储；准备、SM 提交、SSR 封锁使用明确的记录。回收预检与 timer drain 后重新构建并比较当前原生摘要，漂移则保留 controller/PE/DP。新增双准备边界、20 类拒绝、全部七项参数/当前参数漂移、caller 拷贝、SM 已提交但仍 INIT 的拒绝及两个负对照。CI [41193377121](https://github.com/xxz3312/XAirDrop-17/actions/runs/41193377121) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；生产/native 哈希、新 origin 实际链接及模块记录已复核。失败/部分准备、SM/START/UP、自动父资源协调和完整接收路径仍未完成，backend 关闭，手机无需操作。见[0078](POPSICLE-COMPLETED-PREPARE-RESET-0078.md)。

## 阶段 0077

新增已获准 START 在准备入口前遇到 SSR 的显式回收：共享 radio 锁保护 preparation-entry 与封锁观察，work_exit、reservation 和 pending 释放后才发布独立 body-abort origin。已进入准备函数的情况继续保留资源；准备返回后的复核若发现已封锁，不会覆盖 BLOCKED 或继续进入 SM。新增双边界零准备/SM 计数、18 类拒绝、准备中/准备后 fence、混合来源及私有事实负对照。CI [41190764518](https://github.com/xxz3312/XAirDrop-17/actions/runs/41190764518) 已通过 53 项 Python 检查、新模型与私有 abort 负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希、新 origin 实际链接和模块记录已复核。实际准备已执行/START/UP 的 reset 回收、自动父资源协调和完整接收路径仍未完成，backend 关闭，手机无需操作。见[0077](POPSICLE-ABORTED-START-RESET-0077.md)。

## 阶段 0076

新增 SSR 先封锁已排队 START、回调后进入但 work_enter 在 radio_execute 前拒绝 ESHUTDOWN 时的显式回收。私有拒绝事实、原始 SSR、单独 runtime origin、INIT/空事务/零 users/pending 共同核对；保留 BLOCKED/ESHUTDOWN 和请求历史，不冒充 flush、队列失败或 DOWN。新增准备/SM 边界计数、16 类拒绝、封锁时序与私有事实负对照。CI [41187930152](https://github.com/xxz3312/XAirDrop-17/actions/runs/41187930152) 已通过 53 项 Python 检查、新模型与私有 refusal 负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希、新 origin 实际链接及模块记录已复核。START 回调内准备/SM 已执行及 START/UP 的 reset 回收、自动父资源协调和完整 monitor 仍未完成，backend 关闭，手机无需操作。见[0076](POPSICLE-REFUSED-START-RESET-0076.md)。

## 阶段 0075

新增 START 被原生 scheduler 明确拒绝、未入队未执行后的显式 SSR 回收。私有 pre-insertion 拒绝事实、原错误、runtime 提交历史、INIT/空事务共同核对，保留 radio_requested 和原始错误；不制造 MC flush、DOWN 或 ACK。新增 native scheduler post 分支模型、失败回收模型及私有错误匹配负对照，CI [41184172003](https://github.com/xxz3312/XAirDrop-17/actions/runs/41184172003) 已通过 53 项 Python 检查、新回收模型及私有错误负对照、原生 scheduler post 模型、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希和模块记录已复核。实际 START/UP、自动父资源协调和完整 monitor 仍未完成，backend 关闭，手机无需操作。见[0075](POPSICLE-REJECTED-START-RESET-0075.md)。

## 阶段 0074

新增 queue-accepted START 被原生 MC 停机 flush、回调从未执行时的 SSR controller 回收。实际 flush origin、私有 controller 事实、INIT/零事务/零 callback users 双重核对；先 unlink/ref release，再接续 PE/peer/DP/WMA/对象清理。保留 radio_requested 和 BLOCKED/ESHUTDOWN，仅记录启动前撤销，不造 DOWN/ACK。新增原生队列 flush C 模型、13 类拒绝及私有事实负对照；CI [41175604451](https://github.com/xxz3312/XAirDrop-17/actions/runs/41175604451) 已通过 53 项 Python 检查、新模型及私有 flush 负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；生产/native 哈希、三个新增入口实际链接与模块记录已复核。实际 START/UP、自动父资源协调和完整 monitor 仍未完成，无线 init 关闭，手机无需操作。见[0074](POPSICLE-QUEUED-START-RESET-0074.md)。

## 阶段 0073

显式 SSR 回收扩展到 channel 与可选 START plan 已完成、从未请求 radio START 的 INIT。捕获并复核 PE/desired HT20 几何后，沿用原生 PE 析构及分阶段资源释放；保留准备历史，不重跑准备或伪造 ACK；重复通知以独立 completion_error 保留，不能被 SSR 封锁标记掩盖。新增 2.4 GHz/5240 MHz、9 类原生拒绝、20 类失败/矛盾/重复通知历史及频率检查负对照，并保留 0072 回归；CI 41173256945 已通过 53 项 Python 检查、新模型及负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；native/生产源码哈希、helper 实际链接和模块记录已复核。radio START/UP 回收、自动父资源协调和完整 monitor 尚未完成，无线 init 关闭，手机无需操作。见[0073](POPSICLE-PRE-RADIO-RESET-0073.md)。

## 阶段 0072

扩展显式 SSR 回收到 PE 已成功、尚未请求 channel/START 的 INIT：严格原生会话身份/IDLE/确认定时器预检 → 同步关闭 NDI 响应定时器 → 原生完整 PE 析构 → 0070 分阶段 peer/DP/WMA/legacy/对象回收。保留创建事实，不伪造普通 PE DELETE ACK。新增原生 C 模型、22 类拒绝与 SAE 负对照；CI 41155181814 已通过 53 项 Python 检查、新 PE reset/原生析构模型及负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；两项新 helper 的实际链接、生产与 native 哈希已复核。尚无自动父资源协调、channel/START/UP 回收或完整 monitor，无线 init 保持关闭，手机无需操作。见[0072](POPSICLE-PRE-CHANNEL-PE-RESET-0072.md)。

## 阶段 0071

修复私有 PAS 的 PE 删除错误触及共享 SAE 认证定时器：仅私有类型跳过普通 SAE cleanup，其他类型保留原生行为。新增执行原生完整 PE 析构的 Actions 模型：生产 owner/MC 请求回归复用真实 `pe_delete_session`，检查全部可选分配、DPH 借用数组、确认定时器、MAC VDEV 引用释放顺序，并以漏掉引用释放、撤销 SAE 隔离的两个负对照验证。CI 41123670326 已通过 53 项 Python 检查、原生 PE 析构模型及两个负对照、既有 C 模型、完整编译、严格链接和七项布局检查；生产与 native 哈希已复核。本轮补齐验证，不扩大 SSR 准入；手机无需操作。见[0071](POPSICLE-NATIVE-PE-DESTRUCTOR-0071.md)。

## 阶段 0070

新增 pre-PE prepared NDI reset 回收：能力/归属预检 → 同步关闭响应定时器 → 原生 no-FW force peer detach/object-peer 组件析构 → 实际 DP final-free → WMA/legacy 释放 → 对象实际 final-free。完整 prepare 成功、从未请求 PE/START 的 INIT 才可进入；PE/UP 状态仍不支持。CI 41118167241 已通过 53 项 Python 检查、native WMA 分支/两阶段回收 C 模型与 no_fw=false 负对照、完整 WLAN/Wonder/provider 编译、严格链接及 7 项选定布局。5 个新增入口实际链接与生产源码/native 源码哈希已复核。见[0070](POPSICLE-PREPARED-RESET-0070.md)。

native shutdown 自动协调与父资源租约、PE/UP 回收和完整 monitor 仍未完成；无线 init 保持关闭，无新手机测试。

## 阶段 0069

新增显式 SSR host 回收入口：完整 registry coverage、owned MC、合法恢复策略和实际 final-free 由既有 runtime batch 执行，成功后才关闭 adapter/sync；每次返回恢复最新 runtime 句柄，等待与错误均保留 host 和 idle inhibition。CI 41110041682 已通过 53 项 Python 检查、host 与既有 runtime C 模型、完整 WLAN/Wonder/provider 编译、严格链接及 7 项选定布局；新增入口实际链接、生产源码和重建 C 模型输入哈希已复核。见[0069](POPSICLE-HOST-SSR-RETIRE-0069.md)。

这尚无自动 native shutdown caller，不构成 SSR/remove 父资源租约，也未新增 prepared/UP 回收。无线 init 和完整 monitor 仍未启用，无新手机测试。

## 阶段 0068

原生空闲关机增加专用 DOWN host 生命周期检查：在独占 psoc transition 和 operations 排空后，有 host 即返回 EAGAIN，不进入 module stop。登记覆盖 runtime 创建前、异步清理以及 adapter/sync 最终释放；创建失败撤销登记。完整生产 host + 原生 idle 函数 C 模型已扩展；53 项 Python 检查和精确源审计通过。CI 41101029685 已成功，C 模型、完整编译、严格链接及 7 项选定布局检查通过。见[0068](POPSICLE-IDLE-HOST-GUARD-0068.md)。

这仅保护普通 idle shutdown，不代表 SSR/remove 父资源租约完成。prepared/UP SSR 回收、完整 monitor 和实际无线初始化仍未启用，无新手机测试。

## 阶段 0067

默认关闭的HDD元数据绑定通过私有provider传递managed companion，component master实际安装/解除绑定。发布ops前关闭准入，CLAIM成功后开放；清除前quiesce，有归属时保留component/descriptor/claim，显式retire后才解绑，最终free拒绝仍有归属的实例。公开ops/priv ABI不变。CI 41089242566已通过完整编译、严格链接、3个provider导出、6个Wonder入口和7项选定布局检查；私有/通用两模式C模型通过。

HDD init仍返回EOPNOTSUPP，不创建固件会话。目标remove是void，native caller尚不能以EBUSY阻止父资源拆除；创建/启动接线仍须等父资源租约和prepared/UP SSR恢复完成。完整monitor未接通，无新手机测试。见[0067](POPSICLE-MANAGED-BINDING-0067.md)。

## 阶段 0066

Wonder入口新增显式managed生命周期：启动一次后poll，部分失败保留句柄，retire实际完成才DOWN，错误/虚假成功隔离，待完成阶段冻结配置；绑定/实例分别保持回调模块/Wonder模块引用。上游ops/priv ABI和默认同步路径不变。CI 41065931217的53项Python检查、生产入口C模型、完整编译/严格链接和7项选定布局检查通过。

尚未安装managed绑定调用方，host glue、父资源/SSR/remove/实例释放与完整monitor仍未接通，无新手机入口或AWDL成功证明。见[0066](POPSICLE-WONDER-LIFECYCLE-0066.md)。

## 阶段 0065

0064普通管理帧路径活跃：静置WMA +2，扫描窗口WMA/分发 +34、PE入口 +15；AWDL事件0。监听时断网，手动阶段未进入，已恢复原厂。无需重跑。

0065新增生产专用会话controller和host显式入口，将已有NDI创建、准备、PE、频道、START计划、radio启动按实际完成状态推进。固定配置、单次提交、错误保留及销毁后禁止重启。Wonder入口、完整monitor、地址过滤与native RAW仍未接通，无手机入口、无AirDrop成功证明。详见[0065](POPSICLE-UPSTREAM-SESSION-0065.md)。

## 历史阶段 0058

新增默认关闭的单STA完整管理帧实验路径、标准nl80211接收工具和一键60秒观察脚本，不依赖monitor/LPC。仅显式run-mgmt-rx启用；加入MAC上下文消失时关闭路由且不调用SME的停机保护。修正版内核[40926997789](https://github.com/xxz3312/XAirDrop-17/actions/runs/40926997789)、工具[40927043957](https://github.com/xxz3312/XAirDrop-17/actions/runs/40927043957)、打包[40927044125](https://github.com/xxz3312/XAirDrop-17/actions/runs/40927044125)均通过。53项内核host Python检查、生产owner helper模型、15项切换脚本与4项观察脚本测试通过，严格链接无未解决依赖，7项选定布局匹配；这些不认证完整私有ABI或固件。

已生成并校验0058测试包（7,488,393字节）。完整MIF接收、超过256字节的有效AWDL帧、AWDL同步/选举与文件互传仍待实机验证。SME注册仅为PE主机队列提交，不是固件过滤命令。见[0058步骤](POPSICLE-FULL-MGMT-RX-0058.md)与[构建证据](research/popsicle-full-mgmt-rx-0058-build-pass.json)。只对既有popsicle/6.12.69测试环境提供实验包，不能推广为小米17 Pro适配认证。

## 最新阶段 0057

0056实机首次完整解析1帧PSF（247字节、7个TLV）；208候选TLV越界，首个MIF样本256字节但至少需277字节。0057已在固定WLAN源定位header DMA固定256字节设置和header-copy路径；新增可重复静态审计和推断边界回归。尚未修改/修复完整MIF接收，无新手机包、不需重跑旧测试。后续要探索原生完整管理帧指示和广播RX路由，或完整monitor packet DMA；SME/PE注册仅为主机队列提交，不能称作固件过滤命令；不能直接增大不存在的枚举。见 [0057源码定位](POPSICLE-CAPTURE-LIMIT-0057.md)。

## 最新阶段 0056

0055 实机 OCC 请求接受后收到609 Action（591 Apple OUI候选，全部bad_awdl），监听共16045包，无来源/radiotap错误、正常清理。0056保持全部校验，新增候选拒绝原因细分与每类首个有界数值样本，不保存身份/载荷。尚未收到通过解析的AWDL，不认证Apple接收或全频道范围。见 [0056测试步骤](POPSICLE-AWDL-PARSE-0056.md)。

## 最新阶段 0055

0054 实机：7733 包全部通过来源/格式检查，其中 583 Beacon、7150 DATA，Action=0。源码审计确认默认 LPC 是客户端/BSS 采集，新增显式 OCC 工作频道采集请求（RX 三类+operating_type=1），不自动回退。SET/GET 无模式读回，且 SUBFILTER 分支可能忽略模式属性，故始终 mode_verified=false；OCC 实际范围待验证。见 [0055 测试步骤](POPSICLE-CAPTURE-SCOPE-0055.md)。

## 最新阶段 0054

0053 实机运行约 60 秒：Wonder RX=1043、invalid=0，监听 packets=1043、observed=0、ignored=1043，无解析/运行错误且正常清理。由于旧 ignored 合并了来源过滤和帧类型过滤，不能据此认定频道上没有 AWDL。0054 新增 16 类互斥过滤结果、帧类型/Action 分类与首包非身份元数据，并记录测试前后 STA 频道；仍只读、不换频、不认证 Apple 身份。见 [0054 测试说明](POPSICLE-AWDL-RX-0054.md)。

## 最新阶段 0053

新增只读 AWDL Action 接收识别与离线解析、单终端 LPC/Wonder 采集控制器；识别 Apple OUI、PSF/MIF 和有界 TLV 链。不是 AWDL 同步/选举或 Apple 互传；本阶段 CI/实机证据分别记录。见 [0053 使用步骤](POPSICLE-AWDL-RX-0053.md)。

# 小米 17 Pro Max AirDrop 移植进度（2026-10-29）

当前完成了用户态兼容载荷构建、驱动资源/上下文生命周期、初始频道参数、owned NDI 启停路径、停机准入栅栏、被跟踪 MC 排空证据、纯 host 及早期 NDI 回收、父资源拆除前窗口撤销及显式 SSR 批量回收（含准入错误优先级及最终记账状态预检）的离线验证，并补齐普通 DP/DELETE 与 SSR DP 完成事件校验及普通资源已完成后的 NDI host 收尾和普通 host 删除后的最终记账。
实机已确认 MiShare 对临时 XOS 服务的 Binder 元数据访问、LPC/OCC接收和1帧AWDL PSF结构解析；完整AWDL同步与文件互传尚未实现。
“离线通过”指源码、模型测试、编译与链接等检查，不代表手机加载或固件接受。

最新实机结果：0049 自编译 WLAN 已完成加载、/dev/wlan 注册、HAL 开启、AP 连接和 DHCP。0050 工具沿用同一驱动完成一次 45 字节实验广播 vendor Action：native_status=0、send_exit=0，随后 STOCK_RESTORED。此前一次 errno 110 本次未复现，尚不能据此确定旧超时成因。此结果只证明收到原生完成回调，不证明独立空口捕获、对端接收、Apple AWDL 或长期稳定。0051 已新增显式 vendor-action-relay --feedback，原生成功按 token 回写 NOACK，错误/超时回写 FAILED，禁止升级为 peer ACK；CI 40890855957 通过，0052 手机已确认完整 token 闭环：native_status=0，NOACK=1，completed/reported=1，failed/rejected=0，Wonder 已卸载且 STOCK_RESTORED；monitor 删除出现一条 DP peer 状态警告，待跟踪。详见 [0051 测试步骤](POPSICLE-VENDOR-FEEDBACK-0051.md)。

| 模块 | 状态 | 已完成与剩余边界 |
| --- | --- | --- |
| GitHub Actions 与缓存 | 已完成 | 自动编译、工具链/bindgen 缓存、诊断报告 |
| XOS/Binder 与权限 | 部分实机验证 | MiShare 主进程/UI 元数据访问通过；无线业务未验证 |
| 小米 15 MiShare 兼容逻辑 | 离线构建通过 | 已移植应用补丁、BLE/会话兼容载荷；待上机联调 |
| Wi-Fi 会话协调 | 离线构建通过 | root broker 持有、断连/恢复逻辑；未在手机运行 |
| Wonder/AWDL 参考代码 | 部分完成 | 参考代码已构建；未接通目标 WLAN 收发 |
| Wonder/WLAN 后端接口 | 部分完成 | 类型表、注册和生命周期具备；完整 NDI 无线 init/set_freq/rate 等回调仍未接通，默认后端 capabilities=0；另有可独立启动的原生 monitor 接收模式 |
| Host VDEV 与引用管理 | 离线验证通过 | 对象创建、引用、最终释放跟踪与失败保留 |
| NDI CREATE/DP/DELETE | 离线验证通过 | 提交结果、真实 DELETE 事件与 DP 回收；新增普通 DP token/顺序校验及完成错误保留；固件未实测 |
| legacy/WMA/self-peer | 离线验证通过 | 上下文、绑定、peer 创建及对称删除路径 |
| PE session | 离线验证通过 | MC 异步创建/删除、完成回执、引用与 flush 回收 |
| 初始频道参数 | 离线验证通过 | 2.4/5GHz HT20、法规/并发/扫描检查及原生参数准备；不发 START |
| START 原生参数准备 | 离线验证通过 | 重查 WMA/self-peer/法规/并发；原生 START 参数构造与摘要，不提交固件命令 |
| START/host-only UP/STOP/DOWN | 离线构建/模型验证通过 | owned controller 接入专用 MLME 回调、真实响应与 PM 清理；accepted DOWN + INIT 后才删资源；完整原生 SM/WMA 运行及固件未实测，默认调用门关闭 |
| 动态换频与并发硬件模式 | 原生频道跟随首版已实现 | 新增 opt-in STA home channel 跟随、同 PHY monitor 同步与旧帧排空；AWDL 时间槽跳频、硬件模式/DBS 和原子频道预留仍待实现 |
| RAW TX / vendor Action TX | vendor Action 一次原生完成实机通过；DATA 待固件 | 0050/0049 返回 native_status=0（45 字节广播实验帧），独立空口/对端接收未验证；Action 帧工具已具备；新增 opt-in WMI RAW DATA vendor 入口与 raw-send/raw-relay，限同频道非 MLO STA、已有 peer、6Mbps/20MHz；新增 opt-in 原始 skb/token 完成桥；独立 NDI 待接入 |
| Monitor/native RAW RX | 原生 LPC → Wonder → 用户态已实机通过 | 0041 修正嵌套请求并确认接口并发限制，0042 修正 RX 协议值门槛；Wonder RX 增加 1277，invalid=0，wonder0 pcap 帧头可解析；0055显式OCC收到Action，0056解析1帧247字节PSF。默认LPC仍为当前BSS捕获；MIF受256字节header限制，完整管理帧路径待实机验证 |
| 统一收发会话入口 | 首版已实现，待实机 | relay-all 单进程分派 Action/RAW；前台会话按需创建 monitor、核对频道、统一启动/清理；新增 --tx-feedback 选择原始帧完成桥；独立 NDI 初始化仍待接通 |
| mac80211 发送状态回写 | 外部 monitor 路径首版已实现，待实机 | 原始 skb 有界队列、owner/token 匹配、完成/超时/退出处理；Action 明确 ACK 才回写 ACK，RAW 不推断单播 ACK；默认 full backend 旧路径未改 |
| 纯 host 隔离回收 | 离线验证通过 | 限从未发送固件命令的 PAS/INIT 对象；记录被跟踪 MC 排空，等实际 final-free 再释放 owner；NDI/未知发送资源拒绝回收 |
| 早期 NDI 隔离回收 | 离线验证通过 | 限 CREATE/完整 DP attach、尚无 WMA/self-peer/PE/START；资格化 SSR 窗口内释放 timer，等 DP final-free 后删 host；会话中与部分 attach 拒绝回收 |
| 普通 DELETE/DP 完成后收尾 | 离线验证通过 | 限未准备/未 START、普通 host 删除尚未开始的 NDI；合格 SSR 窗口内只删 host 并等最终释放，保留普通完成历史 |
| 普通 host 删除后最终记账 | 离线验证通过 | 删除接受、持有关系解除、MC 排空且无永久错误；等真实 VDEV final-free 后释放 owner，不再调用原生清理 |
| 父资源拆除前窗口撤销 | 离线验证通过 | CDS DP / HDD pdev / dispatcher pdev 关闭前永久撤销回收窗口；仍非父资源 lease 或在途调用屏障 |
| 显式 SSR 批量回收 | 离线验证通过 | 校验完整句柄表；漏列、已记录永久错误及 accepted-delete 记账状态矛盾优先于等待；逐项保留结果，全部清空才成功；父资源仍由调用方保留 |
| SSR/卸载/异常恢复 | 部分完成 | 已实现准入栅栏、被跟踪 MC 排空、早期及普通资源已完成的 NDI 收尾、拆除前窗口撤销及显式批量步骤；会话内 WMA/peer/PE/PM、父资源协调与安全卸载仍待实现 |
| 固件能力与端到端实测 | 待验证 | 驱动加载、NDI/RAW 实际支持、Apple 发现与双向传输、稳定性和安装包 |

最近内核构建源提交：`188246a0008a986741379b105fcfde92d64b8d88`。
[Actions 40768050808](https://github.com/xxz3312/XAirDrop-17/actions/runs/40768050808)
已通过 44 项 Python 检查、26 组原生 fixture、完整 WLAN 编译与严格链接；
85 个要求符号存在，575 条版本记录无不匹配、未解决依赖为空，7 项选定布局 MATCH。
以上不构成完整私有 ABI/KCFI、手机加载或 AirDrop 可用认证。

已补齐纯 host 与早期 NDI 的显式回收、拆除前窗口撤销和批量步骤。启用调用方前，仍需已准备/STARTed 会话的 WMA/peer/PE/PM 恢复、跨轮询父资源协调、活动 owner 卸载、psoc 复用和并发/硬件模式资源预留；随后接通换频、收发与 Wonder 后端，再做固件与整机联调。
新增回归执行原生 target-if 启停发送/响应、owned WMA wrapper 和 PM helper；完整原生 SM 与 WMA START 后处理在回归中仍为模型。
新增 MC 回归执行原生 scheduler_disable/queue flush 和 owned PE callback；QDF 线程/事件/队列原语、完整 native MC 线程及组件析构仍为模型。
早期 NDI 回归还执行 CDS post-disable、WMI 工作清理和原生 timer deinit；HIF/HTC/QDF 与完整 DP detach/free 仍为模型，真实内核与固件未验证。
父资源撤销回归还执行完整原生 CDS DP / HDD / dispatcher pdev close；其调用的 DP、IRQ、timer 和组件拆除为模型，完整 HDD 停机/回退仅做源码审计。
批量回归使用不同 MAC/VDEV ID 的多对象模型；准入检查不修改表，准入后的步骤可部分完成，错误项仍保留。批量接口没有持有父引用或自动接入 HDD。批量优先级回归覆盖十组双 owner 顺序/错误组合；历史批量函数负对照被既有断言拒绝。
普通完成事件回归覆盖有效 inline/延迟/栅栏后 DP 完成、未知及释放后 token、过早/重复/错误路由和 DELETE 异常；完整 DP/QDF/组件拆除仍为模型，地址复用与模块回调文本寿命未认证。
新收尾分支要求普通 DELETE 回执、DP detach 成功返回和 DP final-free 都已观察；inline free 后提交返回失败仍拒绝。它保留普通历史，不写 SSR timer/DP 执行标记。普通 host 删除已接受且持有关系已解除时，新增显式最终记账入口；无接受来源、永久错误及窗口后的晚到完成仍不自动接管。
最终记账回归覆盖纯 host、普通 NDI 和已正常清理 prepared 上下文；允许窗口关闭后等待实际 free，但父实例仍须保留到通知到达，不执行准备态恢复。
窗口撤销不能中止已进入的 reclaim；父资源仍须由调用方保留并串行化。CDS 返回错误也不会让现有 HDD 调用点统一停止拆除。
DOWN 没有固件 ACK，accepted DOWN 只表示原生提交成功及 PM 清理，不能称为固件确认。
详细证据见 [频道准备报告](research/popsicle-owned-channel-build-pass.json) 和
[启停响应检查报告](research/popsicle-start-stop-response-build-pass.json)，以及
[START 参数准备报告](research/popsicle-owned-start-plan-build-pass.json) 和
[启停生命周期报告](research/popsicle-owned-radio-lifecycle-build-pass.json) 和
[停机准入栅栏报告](research/popsicle-shutdown-admission-build-pass.json) 和
[MC 排空与纯 host 回收报告](research/popsicle-owned-mc-drain-reclaim-build-pass.json) 和
[早期 NDI SSR 回收报告](research/popsicle-early-ndi-reset-reclaim-build-pass.json) 和
[父资源拆除窗口报告](research/popsicle-parent-teardown-window-build-pass.json) 和
[显式 SSR 批量回收报告](research/popsicle-ssr-batch-reclaim-build-pass.json) 和
[批量准入错误优先级报告](research/popsicle-batch-preflight-priority-build-pass.json) 和
[普通 NDI 完成事件报告](research/popsicle-ndi-completion-integrity-build-pass.json) 和
[普通资源已完成 NDI 收尾报告](research/popsicle-completed-ndi-host-reclaim-build-pass.json) 和
[host 最终记账报告](research/popsicle-host-final-bookkeeping-build-pass.json)。

最新批量回归新增 48 个最终记账异常组合与 4 个有效等待对照；直接 final 与批量预检共用纯元数据校验。矛盾状态在任何逐项操作前拒绝，正常 final-free 等待仍保留逐项语义。移除新校验的负对照被表未改变断言拒绝。证据见 [批量最终记账预检报告](research/popsicle-batch-final-preflight-build-pass.json)。

SSR DP 回调现已校验已知 token 的恢复来源与普通路径混用；15 种异常保留永久错误，直接 host/NDI/final 与批量入口均拒绝继续回收。合法晚到 free 保留已有错误和窗口关闭状态，未知/释放后 token 忽略。旧回调负对照在新错误断言失败。证据见 [SSR 完成事件校验报告](research/popsicle-recovery-completion-integrity-build-pass.json)。

开发重点已转向功能打通：新增原生 monitor 接收模式及手动试运行包，先验证模块启动和真实收包，再接 RAW TX、频道控制及 NDI 会话。见 [接收模式运行说明](POPSICLE-RX-BRINGUP.md) 和 [编译证据](research/popsicle-external-monitor-rx-build-pass.json)。新模式尚未在手机执行；已有 26 组原生回归不等于新模式运行认证。

管理帧工具阶段提交：`7e53a21a5af27c22ebe6c91eab4ef956b3420116`。新增 Android arm64 `action-tx`，支持单帧发送和 Wonder 出站 Action 帧中继，复用原生 nl80211，不替换 WLAN。 [Actions 40749179035](https://github.com/xxz3312/XAirDrop-17/actions/runs/40749179035) 已通过主机协议测试及 Android 编译；本轮未改内核源码，接收模块沿用上述内核构建。见 [Action TX 使用说明](POPSICLE-ACTION-TX.md) 与 [构建证据](research/popsicle-native-action-tx-build-pass.json)。实际发射、RAW 数据帧、mac80211 完成状态回写与完整 AWDL 待实现/验证。

RAW DATA 阶段提交：`57184ea2203dfa05ab33c3c7171a2ade31675e2d`。RAW DATA 驱动入口与 Android 工具已接通编译链，完整 WLAN 编译/严格链接和两个工具/模型测试均通过；native_status 只由真实原生完成回调产生。需要新驱动显式启用 mishare_raw_tx=1，旧接收包/stock WLAN 不具备入口。手机加载、WMI DATA 接受和实际发射待验证。见 [RAW TX 首版说明](POPSICLE-RAW-TX-BRINGUP.md) 与 [构建证据](research/popsicle-native-raw-tx-build-pass.json)。

统一会话阶段提交：`8f4a8afa609a687f48c79746329507afe094fbe3`。统一收发会话入口与 Action/RAW 单进程分派已实现。[Actions 40757236509](https://github.com/xxz3312/XAirDrop-17/actions/runs/40757236509) 通过 13 项会话命令模型测试、协议/RAW 提交模型和 Android arm64 编译。本轮未改内核，完整 WLAN 证据仍为 0036。见 [统一会话说明](POPSICLE-SESSION-BRINGUP.md) 与 [构建证据](research/popsicle-unified-session-build-pass.json)。独立 NDI 初始化、动态换频、mac80211 状态回写及手机互通仍待完成。

频道跟随阶段：功能提交 `2f95a88a8a2affd2dabe987fbfd39c2cb2e827d5`，最终验证提交 `b32354789133462815de0d16fc1a6241301a9e2a`。新增 `--follow-channel`，持续跟随原生 STA/P2P client 当前频道并同步 monitor，换频与发送串行执行；掉线、同步失败和设置后再次换频停止会话。此为 home channel 跟随，不含 AWDL 时间槽调度。[Actions 40763644465](https://github.com/xxz3312/XAirDrop-17/actions/runs/40763644465) 已通过 15 项会话命令测试、频道跟随/Action/RAW 模型与 Android arm64 编译。见 [使用说明](POPSICLE-CHANNEL-FOLLOW.md) 与 [验证报告](research/popsicle-channel-follow-build-pass.json)。本轮未改内核，完整 WLAN 构建证据仍沿用 0036；手机收发未验证。

发送状态回写阶段提交：`218a67c2e451172268acc9657b6b141f4fb8c769`。新增 `external_tx=1`、工具 `--feedback` 与会话 `--tx-feedback`，原始 skb 按 owner/token 关联到原生完成；默认外部 monitor 仍只接收。16 项会话命令测试、队列所有权/ACK 证据模型、频道/协议/RAW 模型及 Android arm64 编译通过。见 [使用说明](POPSICLE-TX-FEEDBACK.md) 与 [构建证据](research/popsicle-tx-feedback-build-pass.json)。独立 NDI、AWDL 时间槽跳频和手机实际收发仍待完成。

0039 完整内核验证已完成：[Actions 40768050808](https://github.com/xxz3312/XAirDrop-17/actions/runs/40768050808) 通过 44 项 Python、26 组原生 fixture、WLAN/Wonder 编译与严格链接；Wonder 107 条版本记录、WLAN 575 条记录无不匹配/无缺版本依赖，85 个要求符号存在、7 项选定布局 MATCH。0039 工具最终验证源为 `1a1166b8816b151f36a4f6a7b464e70e1a43dc53`，与内核分别记录，不代表手机加载或固件认证。

0040 已整理首轮手动实机包 `XAirDrop-17-Device-Trial-0040.zip`（2,656,084 字节），SHA-256 `fb1888dcf8fd5db4f36d5a5a779e863fb09d55e0dd2040e6a1c6ffcde7c4b008`。复用 0039 新 Wonder，新增仅限 Wonder PHY 的 Action 注入入口和实验广播测试帧；[Actions 40822824724](https://github.com/xxz3312/XAirDrop-17/actions/runs/40822824724) 通过 16 项会话模型、协议/频道/队列/RAW 模型和 Android 编译。包内无 WLAN 替换驱动、无自动安装，尚未上机；按加载/收包、原生 Action、token 回写分步测试。见 [首轮测试说明](POPSICLE-DEVICE-TRIAL-0040.md) 和 [打包证据](research/popsicle-device-trial-0040.json)。

0040 首轮手机反馈：Wonder 成功加载、注册 PHY 并绑定原生 monitor RX handler；两次 RX 计数均为 0，尚未验证收包。STA 活动时标准 monitor 换频返回 EBUSY。QCA GET_MONITOR_MODE 已可查询，返回当时未运行；显式 SET 进一步出现 expected nested data，定位为 nl80211 外层嵌套格式拒绝，不是固件接收失败的证明。原始上传日志未提交到公共仓库。

0041 提交 `6700e2b418e2e39dbc3eb1b8044a51117bdd4900`，新增 capture-start/status，修正 QCA SET 的 NLA_F_NESTED 标志，GET 保持 RAW；不再让用户用 iw raw 数据发送结构化 SET。[Actions 40827521911](https://github.com/xxz3312/XAirDrop-17/actions/runs/40827521911) 通过 16 项会话、协议/频道/队列/RAW 模型及 Android 编译。补丁仅含工具和源码，沿用 0040 Wonder，不替换 WLAN，不改频道；修正版实机效果待反馈。见 [使用说明](POPSICLE-LPC-FIX-0041.md) 与 [验证报告](research/popsicle-lpc-nested-fix-build-pass.json)。

## 0052 单终端测试控制器

新增单终端 vendor Action token 测试：就绪后单次注入、频道复查、NOACK 证据检查和有归属的逆序清理；复用 0049/0051 二进制。CI 40898427028 已通过；0052 实机单帧发送和 token NOACK 回写、资源清理及原厂驱动恢复已通过。见 [0052 操作说明](POPSICLE-VENDOR-FEEDBACK-0052.md)。

## 0042 原生 RX 与桥接修正

原生 LPC 已采集到 Beacon 和 QoS 数据帧；20 秒内原生 RX 增加 1813 包而 Wonder RX/invalid 仍为 0。外部 monitor 的 skb 协议值门槛已修正，构建 40832922219 成功；模块实机验证尚未完成。详见 [0042 测试步骤](POPSICLE-RX-FIX-0042.md)。此进展不代表 AWDL 或 Apple 文件互传已通过。

## 0043 原生 Action 完成事件

Public Action 实机提交返回 cookie=256，iw 观察到 cookie 0x100 的 acked 状态；旧工具逐字节帧匹配导致超时。原生驱动会填写 12-bit 序列号；0043 只放宽这 12 位，继续严格校验其余帧内容、接口和 cookie。Actions 40836954137 编译回归通过，工具实机待测。广播状态不证明 Apple 收到；非 Public AWDL 帧仍受 STA 入口限制。详见 [0043](POPSICLE-TX-STATUS-FIX-0043.md)。

## 0044 完成回传闭环与回包解析

0043 原生 49-byte Public Action 发送已实机匹配状态并退出 0；52-byte 测试帧经 Wonder token 队列 → 原生发送 → token 完成回传，completed=1、reported=1、failed=0、rejected=0。49-byte 队列回复此前触发 EBADMSG，0044 修正最终 netlink 消息/属性可省略末尾填充的解析；49/50/51/52-byte、截断和部分填充回归与 Android 编译通过（Actions 40840072145）。0044 原长度闭环仍待实机验证。详见 [0044](POPSICLE-FEEDBACK-FIX-0044.md)。广播完成不证明对端收到，AWDL 与 Apple 互传仍未验证。

## 0045 独立原生 vendor Action 入口

0044 原始 49-byte 帧的完整 token 回路已实机通过：completed=1、reported=1、failed=0、rejected=0。0045 新增显式 vendor-action-send 和默认关闭、独立加载参数 mishare_action_tx；通过原生 WMI MGMT 发送 category 127，限非 MLO STA 当前频道并保留源地址/peer 检查。用户态回归/Android 构建 40841130477 与完整 WLAN 构建 40841130362 均成功；86 必需符号、575 WLAN 导入记录与所选布局检查通过。原生 WLAN 替换、固件接受、空口接收、NDI/AWDL 时槽/身份和 Apple 互传仍待验证。下一步先运行只读 WLAN 加载预检，详见 [0045](POPSICLE-VENDOR-ACTION-0045.md)。

## 0046 参考小米 15 的运行时切换流程

重新核对 Leekin2/XAirDrop 当前 main（eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76）的 action/service/customize 实现。按其 Wi-Fi/HAL 停止、RAM 中正常切换驱动、失败恢复流程适配 17；初次测试仅手动触发，不启用上游 boot_completed 后自动调用。原系统模块/启动文件不修改，重启仍走系统原驱动。controller 6f1e2bff9c75c6564879c98213c8ad2b26f38be9，10 个实际 shell 模拟路径通过；打包构建 40844885387 成功，原生 WLAN 仍来自 0045 已通过的构建。只在 CI 移除调试信息，模块约 21.5 MB，测试 ZIP 约 7.4 MB。实机驱动切换、固件 Action、PAS/NDI 与 Apple 互传仍未验证。详见 [0046 手动测试与恢复](POPSICLE-WLAN-TRIAL-0046.md)。
