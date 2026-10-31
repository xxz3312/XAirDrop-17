# 0079：START SM 入口门槛与原生 INIT 行为

0078 以 start_sm_committed 作为保守边界。本轮在其后、实际 native dispatch 调用前增加 start_sm_entered 门槛，与 SSR quiesce 共用 radio 锁。原始 SSR 封锁在入口标记之前被观察到，则不调用原生状态机，并记录私有/observable/runtime 三方 SM-entry-abort 事实。意图与入口分开；入口标记先成立时，即使原生函数尚未执行或 VDEV 仍为 INIT，也继续保留资源，不清除这个历史标记。

门槛再次检查工作准入、phase、closing、准备成功、preflight、提交历史和 callback users；不持有 radio 锁调用原生 SM，避免原生回调重入该锁。校验回调也要求原生入口标记。SM 入口被拒绝时保留 ESHUTDOWN 返回，callback 先 work_exit，再释放请求、reservation、最后 pending，之后发布独立 origin，不再访问 controller。所有六种取消来源互斥，重复/混合通知以 sticky completion_error 拒绝，外来身份不解引用。

显式回收仍要求合格 stopped-MC/HIF/HTC/RX/WMI 窗口、精确原始父资源和串行 caller。检查 controller/INIT/空事务/无 native entry/零 pending/users，且七项当前 native encoder 参数与值拷贝计划相同；timer drain 后再检查，随后才 unlink controller，再继续 PE → peer → 实际 DP final-free → WMA/legacy → 对象 final-free。保留请求、BLOCKED/ESHUTDOWN 和提交意图，不伪造 down、ACK 或 replay。

本轮还修正模型的一项边界：固定版本 mlme_vdev_state_init_event 在 START 参数校验失败时，非 STA（含 PAS）返回 handled=true 并调用 mlme_vdev_notify_down_complete；这不代表 START 成功、真正 DOWN 或资源可以删除。新模型执行这段原生函数，production validate/down_complete 回调拒绝误接管，入口已标记且发生此分支时保持资源。原生 transition、START_REQ 分派 glue、其他 SM 状态与完整通用状态机引擎仍为模型，不能称为完整 native SM 执行。

新增 Actions 模型保留 0078 回归；支持分支的 native dispatch 和 INIT down-notice 计数都不能增长。覆盖双频、inline/deferred DP、batch、窗口关闭后的延迟 final-free、20 类拒绝、七项计划/当前参数与 timer 漂移、入口标记后的 INIT 拒绝、五类重复/混合来源。负对照分别移除私有 SM-entry-abort 检查，以及原生 INIT 验证失败的 down notification，必须均被发现。前者校验释放门槛，后者证明模型实际经过原生特殊分支。

53 项 Python 检查通过，C 模型、完整编译、严格链接和七项布局检查待 CI。没有新增 native patch，不改变公开 Wonder ABI；新增内部 origin 编译进原 WLAN。

SM 入口标记是保守的不可回收边界，不是对完整 native dispatch 的原子中断。已进入 SM、已发 START、等待响应和 UP 的恢复、自动 shutdown/父资源协调、完整接收路径仍未完成。QDF/锁/定时器/完整 scheduler、SM 引擎/其余状态与完整 WMA 后处理、PE 分配及其余 cleanup、DP/peer 物理生命周期和父资源仍有模型。backend 关闭，无新手机包，不证明加载、固件/RF 或 AirDrop。
