# 0082：原生通用 SM 引擎

0081 验证了选定原生 entry/event 函数，但层级分派和 transition 由适配器代替。固定版本通用引擎实际上只调用当前状态 handler；未处理即返回 E_INVAL，没有自动向父状态回退。本轮同步纠正旧适配器，并增加直接执行整个原生 wlan_sm_engine.c 的 Actions 模型。

新模型使用原始引擎 header、完整 sm_info 表、事件名数组、真实 state/event 枚举，以及原生 mlme_vdev_sm_transition_to、mlme_vdev_sm_deliver_event 和已有 API lock/dispatch/unlock wrapper。选定原生 entry/event 函数沿用 0081，补入对应原生 exit 函数；其余状态的函数指针保留在完整表中，但绑定中止 stub，不能冒充 STA/MLO/DFS/restart 已运行。SM 创建/删除使用实际通用引擎 API；实际驱动 MLME create/destroy wrapper 仍未执行。

模型覆盖 2437/5240 MHz、普通和提前响应的 START→UP→DOWN→STOP→INIT，实际 controller 退役并排队 PE 删除，父资源保持存活；不把 SSR 专用物理 peer 清理模型用于普通清理。另用真实通用引擎验证新建 INIT/0 遇 SSR 时保持资源，不能冒充已进入 INIT/IDLE 的回收证明。没有主动 START/UP 的 SSR 恢复或强制状态 reset。

独立引擎契约用例验证默认 child entry、child→parent exit 顺序、未处理事件不向父状态回退、无效 event sentinel、状态表编号和父层级循环拒绝。三个负对照分别移除默认 child 选择、添加不存在的父状态回退、移除首次 START 的初始子状态匹配，必须均被捕获。该模型不调用 wlan_sm_reset 作为恢复手段。

CI [41239617189](https://github.com/xxz3312/XAirDrop-17/actions/runs/41239617189)（`6aa5333`）已通过 53 项 Python 检查、原生引擎模型及三项负对照、旧回归、完整编译、CNSS 名称检查、严格模块链接、七项选定布局及最终模块记录检查。新旧模型的公共生产源码哈希已交叉核对，并与该提交的五个生产文件独立匹配；WLAN 未解决依赖为空。见[验证记录](research/popsicle-native-engine-0082-validation.json)。该已通过构建覆盖 INIT/0 的四种双频/响应组合；后续 `005ee1b` 扩展到 INIT/0 与 INIT/IDLE 的八种组合，CI [41244837690](https://github.com/xxz3312/XAirDrop-17/actions/runs/41244837690) 尚在运行，不能沿用前一提交的成功结论。

历史记录、日志、分配、原子、锁和 MLME 对象字段仍有平台模型；native MLME callback adapter、完整 WMA 后处理、物理 DP/peer 生命周期及父资源自动协调未由此执行。完整表不等于所有 handler 都是原生或所有状态均已覆盖。没有生产功能激活或新 native patch；backend 关闭，无新手机包，没有固件/RF 或 AirDrop 成功证明。
