# 0081：原生主流程与发送子状态门槛

固定原生 START_START_PROGRESS 和 STOP_STOP_PROGRESS handler 在调用发送回调后直接返回 handled=true，没有传播发送错误。0081 因此进一步收紧生产发送入口：顶层 START/STOP、对应子状态及原有 controller phase/事务/身份检查必须全部满足；INIT 校验同时要求 IDLE。错误子状态在建立 wire transaction、设置 attempt 和调用 target-if 之前拒绝，不发命令。保留现有错误隔离，不强制 reset，不制造 START_REQ_FAIL/DOWN/ACK。

新增 Actions 模型执行 23 段原生 entry/event 函数，配合已有原生 INIT handler 与 API lock/dispatch/unlock wrapper，覆盖 PAS 非 MLO 的 START→UP→DOWN→STOP→INIT 普通流程。生产 radio/runtime、原生 target-if TX/RX、NDI host-only UP 和 PM helpers 共同执行；双频 2437/5240 MHz、普通/提前响应均完成实际 controller 与 PE/对象清理。另验证错误 START/STOP 子状态不会发命令，发送失败或 host UP 失败即使 native handled=true 仍使 controller 隔离。两个负对照分别省略生产 START/STOP 子状态门槛，要求捕获误发。

原生函数正文保持原样，hash 与固定版本加已有补丁后的整个 SM 文件核对。层级分派、transition/default-child、锁与 QDF 平台、通用状态机引擎仍有模型，不能称为完整原生 SM 引擎运行。STA/MLO/restart/DFS 等非本轮路径的 helper 一旦到达即中止模型，不伪装通过。

53 项 Python 检查通过，完整 CI 待验证。

无新 native patch，无新的 SSR 回收来源或范围；实际 START/UP 的 SSR 恢复、自动 shutdown/父资源协调、完整 monitor/RX 仍未完成。实际固件传输、完整 WMA 后处理、DP/peer 物理生命周期和父资源未由此认证。backend 关闭，不发新手机包，没有手机加载或 AirDrop 互传成功证明。
