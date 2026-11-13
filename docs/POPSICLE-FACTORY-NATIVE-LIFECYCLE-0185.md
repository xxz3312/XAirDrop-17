# 0185 实际 host factory 到 native 普通退出的一体组合

0184 `52f3199be9243a5f7d127b5a3fd334b5c23aeb84` / Actions 43374571813 八项必需 CI 全部通过。Optional ICNSS 跳过，不计入八项。

上游本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch 和 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh，保留原生 host/adapter 创建停止和原厂 CNSS2 原则；本机异步 owner 与 native 生命周期仍须独立验证。

## 新组合

上一批普通退出组合的初始 host/adapter/sync 和 runtime 关联由测试构造。0185 改为执行生产 host create、track、pin、sync/adapter 发布和 host VDEV create，再进入实际 runtime/native VDEV constructor。实际 adapter MAC、deflink 与 wireless_dev 传入 native constructor，检查真实 OSIF 关联。之后沿已有 raw NDI/PE/plan/radio、实际 handoff、普通 host idle/destroy、原生 START/UP/STOP/DOWN、普通 PE/peer/DELETE/DP、VDEV/SM、pins/metadata/module 退役。

初始 caller host slot 由实际 factory 发布，handoff 后实际清空；不复制 runtime owner 或制造 ready 状态。生产函数内容逐一对照并记录散列，没有改动实际初始化门禁。

## 覆盖

- 既有 256 组合全部经实际 factory 与 host VDEV 入口创建，而不直接拼装 host/runtime 关联；六类普通退出失败也保留。
- 十四类创建失败：context、已有 adapter、module get、metadata allocation、device/PSOC/PDEV pin、PDEV→PSOC 身份、sync、adapter open、runtime allocation、带真实延迟引用的部分 native VDEV constructor、recovery、closing。
- 前十项与 recovery 拒绝均要求空 caller slot/registry 和完整引用平衡。Runtime 申请失败或 closing 拒绝保留已创建 host，允许实际 host destroy 收回。
- 部分 native constructor 返回 EINPROGRESS 时，host 的权威 runtime slot 保持；提前 host destroy 继续等待并保留全部 host 资源。释放实际最后 VDEV 引用，原生 final-free 通知到达后，才允许 runtime 和 host 真实析构。
- 三项 factory 变异检查丢失 caller-slot 发布、丢失 registry track、遗漏 parent pins。原有独立 factory 门禁、普通退出与 SSR job 全部继续执行。

## 边界

这里运行实际 host factory/helper 和 native runtime constructor，但 adapter open 内部、OSIF sync、device/object/module 引用原语、firmware delivery、DP peer unmap 与对象引用 helpers 仍为明确模型。不能宣称完整 HDD adapter factory 底层或手机/RF/Apple 通过。本批不放开 configured START/public init，不新增 SSR UP/WAIT/失败回收。

本地 105 项 Python、py_compile、C 源构造、三个新增生产函数内容对照与 diff 通过；原生/sanitizer 和目标构建集中交给 Actions，提交时待观察。保留原厂 CNSS2，不触碰 init_boot，手机无需操作。
