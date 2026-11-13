# 0184 恢复期间的新 host/VDEV 创建门禁

0183 最终 `66068d26c402fee6085248d4574285a9523f740b` / Actions 43364591966 八项必需 CI 全部通过。Optional ICNSS 跳过，不计入八项。

本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch 和 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。延续原生创建/停止及原厂 CNSS2 恢复原则，不将上游运行结果写成本机证明。

## 问题及行为

host create 在持有 PSOC transition 时，原先直接进行 validate_context 和 adapter lookup，然后申请 module ref、metadata、parent pins、sync 与 adapter；它没有在入口明确拒绝 recovery。VDEV create 原先也在 validate_context 之后才检查 session closing，并依赖后续 runtime platform 检查拒绝不安全父级。持有 teardown 的 transition 仅表明串行/保留父级，不能授权新的创建。

现在 host create 在原生 PSOC assertion 后立即检查 recovering，返回 ESHUTDOWN，早于 native context lookup、adapter lookup 和任何 allocation/pins。VDEV create 在 exact parent identity 后、context lookup 前检查 session closing 或 recovering，同样返回 ESHUTDOWN。正常创建与原有 destroy/reclaim 路径保持其既有合同；没有新增 reopen/reset API，也没有放开 configured START 或公开 init。

## 验证

实际 host C fixture 新增入口与回滚检查：

- recovery 中 host 创建拒绝：owner/registry/adapter/sync/module/runtime/parent pins 全不变化，context validation 和 module-get 次数不增加。
- 已有 host 的 recovery/closing VDEV 创建拒绝：保持原 host、sync 和父级 pins，不取得 runtime，不执行 context lookup。关闭旧 host 后，在新对象的健康作用域验证创建与退出。
- 九类现有 factory 失败：metadata allocation、sync、adapter、context、已有 adapter、device、PSOC、PDEV pin 及父级身份拒绝，均留下空 owner/registry 和平衡引用；每类之后用新健康对象重新创建、关闭。
- 三项变异分别遗漏 host recovery、VDEV recovery、VDEV closing 门禁，须触发对应零副作用断言。

CI 增加 --creation-only 快速模式：仍运行完整 host baseline，但只追加这三项变异；后续原完整 host job 与所有既有变异继续执行，不替代全量回归。Host 模型的 runtime/adapter/sync/module/ref 原语边界仍明确；本批不是完整初始 HDD factory 与原生 runtime 同进程或实机证明。

本地 105 项 Python、py_compile、源检查和 diff 通过；原生/sanitizer 与完整目标编译交由统一 Actions，提交时待观察。保留原厂 CNSS2，不触碰 init_boot，手机无需操作。
