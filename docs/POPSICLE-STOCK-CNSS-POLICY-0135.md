# 0135 原厂 CNSS2 ELF 验收与独立启动状态机

## 真实产物验收

[构建 42271965465](https://github.com/xxz3312/XAirDrop-17/actions/runs/42271965465) 的七个必选作业均成功，非本机目标的 ICNSS 可选作业跳过。构建源为 93d2ea7571c723159dff83253003e427fd5677b9。完整/精简 ZIP 下载后 SHA256 均与 GitHub digest 一致，其中 64 份 JSON 报告逐字一致。直接解析包内五个原始 ELF，名称、文件 SHA、版本记录数量和 build-id note 均复核。

实际 WLAN SHA256 为 c6ec40e51669c2c5175e4320603b915e6e6ced95c592ec241ff38b3cb678b3d2，含 590 条导入版本记录，无缺版本导入；64 项 CNSS2 导入全部与捕获的原厂导出 CRC 匹配，包含原厂 register/unregister 两接口。两个 checked_v1 及 live-unload arm 导入为空。重新运行本地 stock_cnss_audit 得到与 CI 相同的报告。

实际 provider 导出 22 项；WLAN 导入 managed_priv_data 和 execution_close，Wonder 导入 managed_control，route_b_probe 导入 set_wonder_priv_data，消费者 CRC 均与实际 provider ELF 导出一致。execution_close 仍是实际依赖；不能将“无 checked CNSS2/无 live arm”说成不再依赖 provider。原生 execution_close 在未注册 owner 时返回 0，不建立 checked 回调注册或 live-unload 许可。

CI 的模块布局/记录、完整 modpost、选定七种结构、cfg80211 选定回调槽等检查通过。五模块摘要、CNSS2 导入和 provider 实际导出另外独立复核；没有独立重跑全部 C 夹具或完整私有结构/KCFI 检查。停止准入归档的 41 项生产源码/provider/header 摘要已与当前源码核对。结果不代表手机加载、RF 或 Apple 功能通过。详细摘要见 [验证 JSON](research/popsicle-stock-cnss-0135-validation.json)。

## 独立部署核心

新增 tools/device/popsicle-stock-cnss-engine.sh，仅定义状态机函数，source 不触发任何操作。参考版本及差异见 [0134 上游合同](POPSICLE-STOCK-CNSS-DEPLOYMENT-DESIGN-0134.md)。允许的操作集合为 wifi-off、hals-stop、remove-wlan、insert-provider、insert-wlan、hals-start、wifi-restore；没有 CNSS2 装卸、live-unload 或热恢复操作。每项操作之前/之后均要求适配器确认原厂 CNSS2 的 live/note 身份，另外在 WLAN 卸载后检查 CNSS2 holders 为空、加载后恢复为 WLAN。

状态机要求只读前置门禁和无冲突事务，先保存快照，再执行副作用。每个副作用记录 intent、实际退出码 returned、成功后的 done。任一步骤、身份、观察或日志持久化失败立即停止，不自动回滚或重放；active 仅在 HAL/Wi-Fi 恢复且模块身份再次核对后记录。Wi-Fi 原先关闭时应保持关闭。

本地 12 项 shell 模型回归覆盖所有七个副作用的失败和 CNSS2 身份漂移、各 intent/returned/done 写入失败、状态观察失败、准备/完成持久化失败、重复执行拒绝，以及 sourcing 无副作用；另八项导入门禁测试通过。模型用普通 shell 变量替代设备动作，没有 insmod/rmmod 或实际设备系统调用。新增独立轻量 CI，不因纯部署核心变化重新编译 WLAN。

## 尚待实现

设备端 IO 适配器尚未实现；它必须核对 SHA/note、root 私有目录/清单、boot/固件、引用/holders、实际 HAL 状态和持久日志，并对原 pairctl 的遗留事务明确阻断。当前状态机不能单独用于手机，也没有安装入口或 KSU 包。初版恢复仍采用禁用实验入口后重启；没有证明普通原生 void 注销支持安全热回退。

下一阶段接入此适配器、默认关闭的 KSU 手动入口和严格产物打包合同。现有三模块 pairctl 和此次重构 ELF 不得混用。
