# 0077：工作已获准但准备入口前中止的 START 回收

新增与 0074 flush、0075 scheduler rejection、0076 work admission refusal 互斥的第四种来源：START callback 的 work_enter 已成功，但 SSR 在 radio 准备入口之前封锁 pristine NEW controller，radio_execute 因封锁返回，从未进入准备函数或 SM。

start_work_admitted 保留工作准入事实，start_prepare_entered 在准备函数调用前、与 SSR quiesce 相同的 radio 锁下记录。SSR 仅为 callback 已进入且准备入口尚未跨过的 pristine NEW、唯一 pending、零 MLME users/执行/回复实例记录 ssr_fenced_before_prepare。入口检查与封锁互斥：封锁先到则不能调用准备；准备入口先到则以后不能取得 pre-prepare 回收资格。准备成功后还在锁下复核 phase/closing，避免 fence 到达后将 BLOCKED 改回 STARTING 并发起 SM。

独立 radio_abort_before_prepare 只在准备调用前的退出点保存私有事实和 observable ssr_start_body_aborted；准备错误或准备后的 fence 不经过这个 helper。callback 先 work_exit，再释放请求、reservation、最后 pending，之后才发布独立 runtime body-abort origin，并不再访问 controller。通知只保存精确身份下的事实；混合/重复来源 sticky，外来身份不解引用。

qualified SSR 窗口中的预检、timer drain 后重检继续核对 registry、准入/准备门槛、私有/observable/runtime 三方事实、INIT/空事务/零 users/pending。四种来源要求恰好一项成立。退休 controller 后沿用 PE → peer → 实际 DP final-free → WMA/legacy → 对象 final-free；保留 radio_requested、BLOCKED/ESHUTDOWN 和 body-abort 历史，不制造 flush、work refusal、DOWN、普通 ACK 或 retry。caller 仍需在所有异步 poll 中保留并串行原始父资源。

新增模型保留 0076 回归，在 work_enter 成功后、以及 work_allowed 成功但 controller 快照前两个边界封锁；原生准备函数与有界 SM dispatch 的增量必须为零。覆盖双频、inline/deferred DP、batch、窗口关闭后的延迟对象 final-free、18 类私有/身份/来源/回调拒绝、timer drain 期间回调、重复/混合 origin；在准备入口处或准备成功返回后封锁时，准备计数为一、SM 为零，回收必须继续拒绝。移除私有 abort 检查的负对照必须失败。

53 项 Python 检查通过，C 模型、完整编译、严格链接和七项布局检查待 CI。没有新增 native patch 或公开 Wonder ABI 变化，新 origin 编译进原 WLAN，没有自动 shutdown/父资源 caller。

模型中的 QDF/锁/定时器/完整 scheduler、完整原生 SM/WMA 后处理、PE 分配和其余 cleanup、DP/peer 物理生命周期及父资源仍有替身。准备函数执行和边界注入不证明完整 native/RF 集成。START 准备已进入后的 reset、实际 START/UP、自动父资源协调和完整接收路径仍不支持；backend 关闭，无新手机包，不证明加载、固件或 AirDrop。
