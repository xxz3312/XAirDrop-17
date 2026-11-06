# 0124：PCIe 类型化执行边界准备

实际目标为 PCIe/CNSS2。新增独立 `register_pcie_v3` 描述符和四个类型完全匹配的 provider 入口：reinit、shutdown、idle_restart、idle_shutdown。重启类保留原始 `pci_dev *` / `const pci_device_id *`，不转换回调函数指针、不丢弃设备 ID。旧 IPCI v2 描述符布局保持不变。

两种总线共享注册锁、owner、关闭、执行计数及注销作用域。仅允许一份注册；错总线入口返回 EPROTOTYPE；回调开始时取模块引用并复制描述符，所有 WLAN 栈帧返回后才在外部 provider 释放引用。成功清理同步清空两份描述符。真实模块导出门禁由 12 项扩展为 17 项。

补丁 0056 修复四个原生 PCIe 回调对全局 context/ops 的空指针访问；idle_shutdown 改为检查它实际调用的 idle_shutdown 指针。新的 Actions C 夹具抽取完整的四个原生函数，仅撤销这两类已审阅变更后与固定源码逐字比较。夹具连接真实 provider，通过模型 CNSS2 槽位调用原生函数；覆盖 ID 原样传递、最后引用释放、描述符复制、错总线拒绝、关闭与四类回调并发、空 context/ops、模块拒绝准入和六项错误注入，启用 ASan/UBSan/leak detection。

**接入边界：生产 pld_pcie_ops 仍使用原生入口，尚未切换到新 provider。** 平台 `cnss_wlan_unregister_driver` 仍为 void，其事件 handler 与清空状态/断电尾部尚未接入 checked remove 回执。当前只完成类型化边界和原生回调修复，不能称为 CNSS2 生命周期接通或实机保护完成。下一步需要实现 checked CNSS2 事件及 PCIe→PLD→HDD 拒绝传播，再成套切换注册槽位。

本地 57 项 Python 回归、源码夹具组装、0053–0056 独立补丁正向应用和 0056 反向检查通过。Actions 结果单独记录；未运行的检查不计为通过。手机未操作，无线后端仍关闭。原生 CNSS2 调度器、PCIe remove/热拔插、module-exit 失败、模块加载/ABI/KCFI 与无线行为均未认证。

[Actions 42198546212](https://github.com/xxz3312/XAirDrop-17/actions/runs/42198546212) 的 stop-admission 作业已通过，新增 PCIe 六项错误注入及四类并发回调场景通过，既有四套回归通过。产物 SHA256 与五套重新组装夹具、原生片段、provider/header/host 生产哈希一致。七项默认作业均已通过；完整紧凑产物摘要、五个模块的记录检查、选定布局和 provider 实际 17 项导出已核对。这是默认模块构建验收，仍未切换 CNSS2 实验消费者或认证实机。详见 [机器证据](research/popsicle-pcie-boundary-0124-validation.json)。
