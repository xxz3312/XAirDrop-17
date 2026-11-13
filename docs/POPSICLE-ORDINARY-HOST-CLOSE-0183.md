# 0183 普通 radio 退出到真实 host idle close 的组合

0182 `a7436056caf1e07d41d73f6f7b7930aea15513fc` / Actions 43359590092 八项必需 CI 全部通过。Optional ICNSS 跳过，不计入必需项。

本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch，与 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh。继续复用原生 adapter stop 与原厂 CNSS2 原则。没有用上游成功代替小米17原生异步回执和 owner 顺序验证。

## 本批内容

复用已有普通 native peer cleanup 模型和完整 `wma_remove_peer/wma_remove_objmgr_peer` 原生函数，将它们与实际 host handoff、ordinary idle prepare、destroy、pin/unpin/metadata free、runtime/radio、原生 SM/WMA START/STOP/PE destructor 与 DELETE 通知路径在同一进程运行。运行中唯一 owner 槽仍由实际 host 驱动；不是将原 SSR 回收结果改名为普通退出。

实际 host handoff 后的 idle poll 驱动 UP→STOP，观察真实 STOP/DOWN 后再释放 controller、post PE delete；真实 PE 回调完成后才发送 peer delete，真实 peer 回执后才发 VDEV DELETE，真实 DELETE 回执后才提交 DP detach。physical peer unmap 未完成时模型延迟 DP 最终完成；之后普通 runtime drain 观察 DP free，释放 WMA/legacy/stats、VDEV/原生 SM，最后执行真实 host sync 注销/排空/adapter close/pins/metadata/module 退役。

所有正常组合都要求没有 SSR reason、没有 recovery window、没有 recovery DOWN observation；不会借 reset force-delete 或合成普通 ACK 完成退出。configured START 与公开 init 门禁保持不变。

## 覆盖及边界

- 256 组合：双频、两种初始 native substate、START/STOP 普通或早响应；32 种 peer 回执、peer unmap、DP、flush capability/额外 VDEV 引用以及 VDEV DELETE 早响应组合。
- 六类故障沿实际 host 调用保留资源：PE flush、peer 发送失败、peer timeout、VDEV DELETE timeout、DP detach 失败、native VDEV delete 失败。Host metadata/adapter/sync/parents 始终保留，禁止误当成关闭成功。
- 两项行为变异删除 peer ACK 与 VDEV DELETE ACK 门禁，要求被具体时序断言拦截。先前 SSR、host close 和 native peer/object-manager 专项测试保持独立运行。

firmware 投递、DP peer unmap/对象引用、OSIF/RTNL、adapter/sync/parent/module 物理原语与初始 factory 构造仍有明确模型；本测试不宣称完整原生 peer object-manager 在此组合中执行，也不是手机/RF/Apple 互传证明。生产代码未修改，未开放 UP/WAIT/失败来源 SSR。

本地 105 项 Python、py_compile、C 源构造和 diff 通过；原生/sanitizer 和目标编译集中由 Actions 验证，提交时待观察。保留原厂 CNSS2，不触碰 init_boot，手机无需操作。
