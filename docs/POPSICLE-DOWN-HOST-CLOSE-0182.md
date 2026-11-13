# 0182 实际 host 终端关闭与 native DOWN 退役组合

0181 `ee0efb1917bc09328a325d8dfc017f7beb11e27f` / Actions 43354582023 八项必需 CI 全部通过。Optional ICNSS 跳过，不计入八项。

上游本批核对 OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch，以及 XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 module/action.sh：延续原生 adapter stop、原厂 CNSS2 与失败恢复原则；上游运行结果不能替代本机异步生命周期组合验证。

## 变化

0181 的最终 host destroy 为显式结果模型。0182 直接运行生产 `mishare_wonder_host_destroy_locked`、parent pin/unpin 和 tracked metadata free，连同已有六个真实 host 函数、runtime/batch、原生 CDS/SM/WMA/PE/peer/DP/context 退役链在同一进程执行；函数内容逐一对照并记录散列，不改生产代码或门禁。

实际 destructor 必须先观察 runtime 完整退役，再注销 sync。返回 sync 不等于原所有对象时，按照实际代码恢复观察到的非空注册项，返回 EIO 并保留 adapter、sync、metadata、device/PSOC/PDEV pins 和 host module ref。不存在注册项时也不能当成关闭成功。

成功顺序由实际生产调用驱动：unregister → wait_for_ops → adapter close → sync destroy → PDEV/PSOC/device put → registry 下 metadata free → host module put。同步、ref 和 adapter 的底层接口仍为显式物理原语模型，但 adapter/netdev/link/sync/metadata 均真正分配和释放堆存储，ASan 可检测不合法后续访问。Runtime 与 host 的两份 module pin 分别保留到各自实际退役。

## 覆盖

- 原 64 组双频/substate/早回复/DP/额外 VDEV 引用组合和 16 类 host/native 保留边界继续运行；foreign-PSOC 并发覆盖继续保留。
- 两项新增终端边界：sync registry 为空、host 预期 sync 与实际注册对象不同。Runtime 已真实完成后仍保留全部 host 资源与 pins；重复失败不误放父级。
- 六项新变异：遗漏 sync drain、sync destroy、parent puts、host module put、恢复实际观察到的注册项、metadata free。每项必须触发具体次序或所有权断言。

本地 105 项 Python、py_compile、C 组合源构造和生产四个新函数内容对照通过；C/sanitizer 和目标编译交由统一 Actions，提交时待观察。

## 边界

初始 HDD factory 构造、底层 adapter 关闭函数内部、Linux loader/真实 refs 与 OSIF/RTNL、物理 IRQ/固件/PM/DP 仍不是实机证明。新增 native/helper 代码虽实际执行，不能称完整原厂驱动在手机上通过。本批为组合验证，不修改生产功能、configured START/public init、UP/WAIT/失败来源回收。原厂 CNSS2、init_boot 原则不变，手机无需操作。
