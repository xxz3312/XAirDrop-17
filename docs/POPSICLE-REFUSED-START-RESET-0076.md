# 0076：SSR 后 START 回调准入拒绝的显式回收

0074 处理实际 MC flush，0075 处理 scheduler 明确拒绝入队。本轮新增第三种互斥事实：SSR 在 START 回调进入前封锁 pristine NEW controller，随后回调进入，但 work_enter 返回 ESHUTDOWN，从未进入 radio_execute，因此未执行准备、状态机、START 或启动用 PM/定时器操作。

回调在原始 fence 候选、精确 controller 身份、单个 pending、零 users/回复/preflight/执行事实下记录私有 ssr_start_refused 和可观察 ssr_start_callback_refused；释放请求内存、work reservation、最后 pending 之后，才发布独立 runtime refusal origin，之后不再访问 controller。runtime 只接收精确 psoc/vdev/owner/controller 的原始 SSR，重复或混合通知记为 sticky completion_error，外来身份不解引用。通知不执行清理。

qualified SSR 窗口中的 check/release 再核对 registry、独立私有事实、回调进入但工作拒绝、无 flush/队列失败、INIT/空事务、零 users/pending、没有迟到 MLME 回调。runtime 在同步关闭响应定时器前匹配 observable refusal 与 runtime origin，关闭后重新检查；退休 controller 后沿用 PE → peer → 实际 DP final-free → WMA/legacy → 对象实际 final-free。保留 radio_requested、BLOCKED/ESHUTDOWN 和 refusal 历史，不伪造 DOWN、普通 DELETE ACK、flush 或 retry。

新增模型保留 0075 回归。在生产 radio 的 work_enter 边界注入精确封锁时序，并对原生准备函数与有界 SM dispatch 增加观察计数；支持的分支两者增量必须为零。覆盖双频、inline/deferred DP、batch、额外 final-free 引用、16 类私有/身份/来源/回调拒绝、timer drain 期间回调，以及原始 fence 晚于 callback-entry、工作已获准后再 fence、其他 work_enter 错误、准备函数已经执行失败和 REMOVE。负对照移除私有 refusal 检查后，必须被只有 runtime/observable 标记的用例发现。

53 项 Python 检查通过，C 模型、完整编译、严格链接和七项布局检查待 CI。没有新增 native patch，不修改公开 Wonder ops/priv ABI；新增 origin 编译进 WLAN，但没有自动停机/父资源协调 caller。

模型的 QDF/锁/定时器/完整 scheduler、完整原生 SM/WMA 后处理、PE 分配及其余 cleanup primitives、DP/peer 物理生命周期和父资源仍有替身。原生准备函数和生产 runtime/radio 执行不等于完整空口集成。显式 caller 必须在全部异步 poll 中保持并串行原始父资源。已执行准备/SM/START/UP 的 reset 回收仍不支持；backend 关闭，无新手机包，不证明加载、固件/RF 或 AirDrop。
