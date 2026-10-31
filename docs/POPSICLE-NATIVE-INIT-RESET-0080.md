# 0080：原生 INIT 拒绝后的 SSR 回收

0079 保守地保留所有已标记原生入口的对象。本轮只开放一个有原生来源证明的例外：原始 SSR 发生在 INIT START 参数校验之前，native INIT 仍处于 INIT/IDLE，未转 START、未尝试 START/STOP/DOWN，没有回复事务。原生校验失败虽返回 handled=true 并通知 down-complete，但该通知不等于 DOWN。

新增 0036 补丁只对 PAS 在固定原生 INIT 的失败分支中、down-complete 通知之后调用内部 origin。两段有界插入移除后，整个原生文件逐字节恢复固定上游版本。生产 controller 要求 active 原生调用内依次观察到 validation 拒绝、down 拒绝及原生 origin；额外、乱序、迟到回调永久标记异常。仅在实际 wlan_vdev_mlme_sm_deliver_evt 完整成功返回后才完成私有证明，该 API 在返回前释放原生 SM 锁。不改变 native 状态，不伪造 DOWN/ACK，不清除 native-entry 历史。

回调先退出 runtime work，释放请求、reservation、pending，最后发布单独的 runtime origin，不再访问 controller。全部七种取消来源互斥；重复或混合通知保持 sticky completion_error。显式回收仍要求精确父资源、原始 caller 串行协议、MC/HIF/HTC/RX 停止及 WMI 阻塞/排空的合格窗口。七项原生计划、INIT/IDLE、零 users/pending、空事务在 timer drain 前后重检，随后沿用 controller → PE → peer → 实际 DP final-free → WMA/legacy → 对象 final-free。

新 Actions 模型执行固定原生 INIT handler 与真实 API 的 lock/dispatch/unlock wrapper，保留旧阶段回归。新增双频、inline/deferred DP、batch 和窗口关闭后的 final-free、24 类来源/状态/身份拒绝、七项计划与 timer 漂移、失败 API 返回/乱序及额外回调/子状态漂移、六类重复混合来源。两个负对照分别移除原生分支 origin 和原生 API unlock，必须均被识别。

CI 待验证。

QDF/锁、通用 SM 引擎/START_REQ dispatch glue/其他状态、完整 WMA 后处理、PE 分配及其余 cleanup、DP/peer 物理生命周期、父资源仍有模型。生成模型哈希记录自 CI，不在本地编译或独立重建。该例外不支持实际进入 START 状态、发出 START、等待响应、UP、失败/部分准备；自动 shutdown/父资源协调和完整 monitor/RX 未完成。backend 关闭，无新手机包，没有手机加载、固件/RF 或 AirDrop 成功证明。
