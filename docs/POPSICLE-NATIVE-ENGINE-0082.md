# 0082：原生通用 SM 引擎

0081 验证了选定原生 entry/event 函数，但层级分派和 transition 由适配器代替。固定版本通用引擎实际上只调用当前状态 handler；未处理即返回 E_INVAL，没有自动向父状态回退。本轮同步纠正旧适配器，并增加直接执行整个原生 wlan_sm_engine.c 的 Actions 模型。

新模型使用原始引擎 header、完整 sm_info 表、事件名数组、真实 state/event 枚举，以及原生 mlme_vdev_sm_transition_to、mlme_vdev_sm_deliver_event 和已有 API lock/dispatch/unlock wrapper。选定原生 entry/event 函数沿用 0081，补入对应原生 exit 函数；其余状态的函数指针保留在完整表中，但绑定中止 stub，不能冒充 STA/MLO/DFS/restart 已运行。SM 创建/删除使用实际通用引擎 API；实际驱动 MLME create/destroy wrapper 仍未执行。

模型覆盖 2437/5240 MHz、普通和提前响应的 START→UP→DOWN→STOP→INIT，实际 controller 退役并排队 PE 删除，父资源保持存活；不把 SSR 专用物理 peer 清理模型用于普通清理。另用真实通用引擎重跑原始 SSR 导致的 INIT 拒绝及合格窗口显式回收，分阶段释放资源后显式删除模型引擎分配。没有主动 START/UP 的 SSR 恢复或强制状态 reset。

独立引擎契约用例验证默认 child entry、child→parent exit 顺序、未处理事件不向父状态回退、无效 event sentinel、状态表编号和父层级循环拒绝。两个负对照分别移除默认 child 选择、添加不存在的父状态回退，必须均被捕获。该模型不调用 wlan_sm_reset 作为恢复手段。

53 项 Python 检查通过，完整 CI 待验证。

历史记录、日志、分配、原子、锁和 MLME 对象字段仍有平台模型；native MLME callback adapter、完整 WMA 后处理、物理 DP/peer 生命周期及父资源自动协调未由此执行。完整表不等于所有 handler 都是原生或所有状态均已覆盖。没有生产功能激活或新 native patch；backend 关闭，无新手机包，没有固件/RF 或 AirDrop 成功证明。
