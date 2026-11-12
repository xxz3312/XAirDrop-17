# 0179 完成 DOWN 的显式 runtime SSR 接线

## 上游依据与范围

核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch，及 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh；未发现可直接代替本项目异步对象/原生停止窗口证明的对应实现。沿用原厂 CNSS2 和已有原生 CDS 停止资格检查。

0178 当前七项必需任务通过，诊断目标构建仍在运行，尚不记录为完整通过。

## 接线合同

显式 process-context caller 保留并串行父级，在 SSR fence 与实际 MC stop 之后、第一次 native CDS recovery-window qualification 之前调用 `mishare_runtime_fenced_down_prepare`。先认证 owner registry，再核对 live handles、raw 未配置来源、完整 DOWN 首次 fence、原生 INIT/IDLE、真实 STOP receipt 和计划。此调用只观察和保存来源，不开放窗口、不释放资源。重复调用仍检查实际 controller。

已有 native CDS 停止流程必须独立满足 HTC/HIF/RX/WMI work 等条件，才能给该候选开放窗口。窗口未开放或已关闭，均不得清理。

有窗口后，runtime 先检查原生 context/PE，再调用 0178 timer/controller 组件，将其实际返回的 timer-attempt/released 与 controller-retired 状态同步发布。仅成功后继续已有原生 PE 释放、无新 firmware 命令的 peer 释放、DP detach 回调、WMA/legacy context finish，最后 host/VDEV/原生 SM 和 metadata 析构。额外 VDEV 引用仍阻止物理析构；实际释放后，最终纯 metadata 退役可发生在窗口关闭之后。

独立 `recovery_down_observed/released` 来源不复用 pre-START cancellation 字段。START/STOP/DOWN 历史、首次 fence 和 event serial=2 submitted/replied 原样保留，不制造 DELETE ACK，也不新增 WMI 命令。任何实际 timer 释放后发生的 callback/计划漂移，发布真实 partial 状态并保留 controller/后续资源，错误粘住，禁止重试。

自动 managed observation 调度尚未连接，本接口须由显式串行 caller 使用。configured rate/retry/preview owner、UP、WAIT、失败或混合来源不在本批回收范围，configured radio START 和公开 init 仍关闭。

## 验证

新增 Actions native fixture，选择真实 pinned native SM wrappers、START/STOP/WMA、MC stop、CDS 停止检查和已有原生释放函数；物理 IRQ/固件/锁/引用/PM/DP 等仍为模型。

- 64 组合：双频、两种初始 substate、START/STOP 各自早响应、DP 同步/异步回调及额外 VDEV 引用。成功路径检查完整图的实际释放计数和 native SM wrapper 析构顺序。
- 15 类拒绝或 partial 边界：MC 未停止、非 SSR、configured 来源、错误首次阶段/工作占用、原生停止资格拒绝、窗口关闭、STOP 事务损坏、迟到 callback、PE 几何漂移、timer sync 内 callback/计划漂移。失败不触碰后续 PE/DP，partial 事实准确发布且不重试。
- 六项新行为变异：遗漏 observation、MC/configuration 门禁、候选接线、真实 timer 状态发布、controller 退役状态发布。保留独立 0178/0177 与既有完整基线任务。

本地只执行 Python/源构造/差异检查；C 编译、sanitizer 和目标构建集中由 Actions 验证。提交时完整 CI 待观察，不能据此宣称实机、RF 或 Apple 双向传输通过。不触碰 init_boot，手机无需操作。
