# 0075：START 队列拒绝后的显式 SSR 回收

扩展 0074 的从未执行 START 回收，覆盖原生 scheduler 明确返回错误、消息从未插入队列的分支。固定 WLAN 版本的 scheduler_post_msg_by_priority 在所有错误分支中都尚未插入消息；正常/高优先级插入后均返回成功。本轮不增加 native patch，也不改 scheduler 行为。

生产 radio 只在实际 scheduler 返回失败、归还 pending/work reservation 并释放请求内存后记录私有 start_post_error。请求分配失败或 work_get 拒绝不会取得该事实。runtime 单独保留 radio_submit_error，SSR 不覆盖它；关闭准入时仅为原 CANCELLED、原错误匹配、零 pending/users/执行/回复的 controller 捕获候选。

合格 SSR 窗口中的 check/release 核对活 registry、精确身份、私有拒绝错误、未入队/未 flush/未执行/未 preflight、INIT 和空事务。runtime 在关闭响应定时器前核对原始错误，关闭后重新验证并退休 controller，再沿用 PE → peer → 实际 DP final-free → WMA/legacy → 对象实际 final-free。迟到回调即使 users 回到零也会阻止退休。保留 radio_requested、radio_submit_error、BLOCKED 和原错误，仅记录明确的启动前撤销；不制造 flush、SM/WMI/PM 操作、DOWN、普通 DELETE ACK 或重试。

新增 Actions 模型保留 0074/0073 回归，覆盖双频、inline/deferred DP、batch、额外对象引用、15 类私有/身份/错误/回调拒绝、timer drain 期间回调、请求分配/工作预留失败和非 SSR fence。负对照移除私有错误精确匹配，必须被 controller 在错误事实不匹配时被退休的用例发现。另一个独立模型直接执行固定版本原生 scheduler post 函数，覆盖 10 类错误分支与两种成功优先级；队列/context/QDF/message duplication 为模型，并非执行完整 scheduler 线程。生产 radio 的端到端拒绝测试仍使用 transport 模型，不能把两项测试宣称为完整 native 集成。

53 项 Python 检查通过，C 模型、完整编译、严格链接和七项布局检查待 CI。原生自动 shutdown/父资源生命周期协调仍未接入；显式 caller 必须在全部异步 poll 中保留并串行原始父资源。实际 START/等待响应/UP、失败或 pending 的 PE/channel/plan、完整 monitor 尚未支持。backend 关闭，不制作手机测试包；不证明驱动加载、固件/空口或 AirDrop。
