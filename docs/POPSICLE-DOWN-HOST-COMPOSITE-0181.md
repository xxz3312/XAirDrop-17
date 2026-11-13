# 0181 raw DOWN 的实际 host/runtime/native 组合验证

## 已确认基线

0180 最终修复 `685c7805a426940889d825907d09544549224b11` / Actions 43347366011 八项必需 CI 全部通过，包括 host stop-admission 与目标 diagnostic。optional ICNSS 仍跳过，不计入必需项。

上游本批核对：OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch；XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。原生 adapter stop、原厂 CNSS2 和失败恢复原则延续；没有可替代本项目异步 owner/原生停止窗口组合证据的同等实现。

## 本批变化

0180 在 native CDS→runtime 测试中模拟 host observer，在实际 host 测试中模拟 runtime。0181 新增单进程组合测试，直接提取并运行生产 host 的六个函数：parent identity、handoff idle、registry candidate、DOWN observe、reclaim SSR 和 handoff reclaim SSR。结构体/函数内容取自实际源码并记录散列；runtime prepare/snapshot/batch/reclaim 不再由 host 边界结果模型代替。

真实 raw START/UP/STOP/DOWN 后、SSR fence 前调用实际 handoff：原 caller 槽变 NULL，registry 获得唯一 host 所有权。原生 MC/CDS 停止流程实际调用 host observer，再由真实 runtime/native 资格打开窗口。后续实际 host reclaim 将权威 runtime token 临时交给真实 batch，并在每次 pending/error 时恢复原槽；真实 timer/controller/PE/peer/DP/WMA/context/VDEV/SM 退役后才能进入终端 host 关闭原语。额外 VDEV 引用仍阻止最终物理释放；窗口关闭后只允许合格 final metadata 继续。

## 组合覆盖

- 64 组：双频、初始 substate、START/STOP 早响应、DP 同步/延迟以及额外 VDEV 引用。检查唯一 handoff、实际 STOP 回执、首次 fence、真实 native SM 物理析构顺序、runtime graph 完整退役和最终 host 关闭顺序。
- 16 类保留/失败：caller 未 handoff、父级迁移、RTNL 竞争、运行中/接口/session flag、session/prestart/configured rate、迟到 callback、STOP serial、未排空工作/错误、原生 reset 资格、timer sync 内最后 callback，以及 runtime 已实际释放后终端 host 关闭失败。
- 三项组合变异：丢失 caller 槽清空、丢失 authoritative runtime 槽恢复、接管 caller-owned host。
- 一个正常组合额外并发 2000 次 foreign-PSOC 节点发布/摘除/释放，与 200 次真实 observer 重叠，检查 registry traversal 对 foreign 节点的读取始终受锁保护。pthread/ASan/UBSan 仅为模型并发验证，不等同内核 race 认证。

## 边界

这是验证阶段，本批不修改生产生命周期或放开初始化。Host factory、父级 pins/PSOC transition/RTNL/adapter 字段及终端 HDD adapter/sync destruction 仍为明确的物理原语模型；不能宣称完整 HDD factory/destructor 一体运行。原生 IRQ/固件/引用/PM/DP 物理原语亦有模型。现有完整 host 和 0180 原生测试继续独立保留。

本地 105 项 Python 回归、py_compile、组合 C 源构造和 diff 检查通过；C/sanitizer 与目标构建集中由 Actions 验证，提交时待观察。保留原厂 CNSS2，不触碰 init_boot，无手机部署。configured START、UP/WAIT/失败状态回收及 Apple 发现/握手/双向传输仍未因此开放。
