# 0128：注册失败回滚与加载图保留

补丁 0062 处理实际 PEACH PCIe / CNSS2 的注册失败路径。此前 PCIe 后续总线注册失败会调用 void 注销并清空 PLD；HDD 加载失败又会继续销毁同步、组件和全局状态。即使底层拒绝注销，上层也可能释放仍被回调引用的数据。

候选 GKI 的 `do_init_module()` 在初始化返回负值后直接进入 `free_module()`；单独增加模块引用不能让该错误路径保留模块代码。固定源码及摘要见 [加载器来源](research/popsicle-registration-loader-0128.json)。这也是本阶段保留整个加载图、显式报告错误的依据，并非已经证明原厂手机加载器完全相同。

| 路径 | 新行为 |
|---|---|
| 尚未到达任何回调发布点 | checked 注册回执为 false，撤销 provider 描述符；干净 EAGAIN 可按原逻辑重试，完整 HDD 清理返回后释放临时加载引用 |
| 可能已经发布回调，但注册失败 | 回执在三处发布点之前置 true；关闭 provider 准入，CNSS2 进入 terminal；HDD 停止重试并保留同步、组件、PLD、全局状态及模块代码 |
| 后续任一总线注册失败 | 首先执行 checked PCIe 注销；失败原样上抛，其他总线及共享状态不清理；成功才按已注册位逆序清理 |
| 控制设备创建等较晚加载步骤失败 | checked 注销受阻立即保留整个加载图，不进入公共资源销毁 |
| 保留状态的模块初始化 | 初始化入口返回 0 使代码驻留，0444 只读 `mishare_load_error` 保存实际失败；HDD 完成通知仍报告失败，禁止重新加载和切换模式 |
| 成功加载 | 持续持有一个模块引用，防止直接 rmmod 进入无法返回错误的 module-exit；受控 live-unload 释放路径尚未实现 |

注册私有接口新增 `cnss_wlan_register_driver_checked_v1(driver, bool *may_hold_wlan)`。原始注册入口保留签名和导出，默认 WLAN 消费者不切换。配对构建要求原厂 81 项导出记录保持精确一致，仅允许两个明确列出的 checked 扩展，并要求实际 WLAN 强导入两者，拒绝旧 register/unregister 导入及未解析符号。没有改写 CRC、放宽 modpost 或设置运行时后端。

验证覆盖真实 CNSS 注册内部函数及 checked 回执、PCIe 注册、完整 PLD 注册回滚、HDD retry/load/module-init；GPIO、固件、电源事件、资源原语和 Linux 加载器本身仍为模型或独立源码分析。新增 19 个隔离场景与 6 项错误注入，保留失败的场景使用独立子进程，不添加生产强制复位接口。已有真实 CNSS2 注销夹具另行覆盖注销链，避免把新的模型注销函数计为平台实现验收。

[Actions 42228659964](https://github.com/xxz3312/XAirDrop-17/actions/runs/42228659964) 的 stop-admission 作业通过：八套 C 夹具、全部错误注入和 ASan/UBSan/leak detection 通过；八套组装源码、原生片段、provider/header、平台及 SSR 源码哈希均与下载产物核对一致。63 项本地 Python 回归和独立完整补丁应用、七文件精确正反检查通过。

[配对构建 42228489983](https://github.com/xxz3312/XAirDrop-17/actions/runs/42228489983) 成功，下载后再次独立检查：

| 检查 | 结果 |
|---|---|
| 原厂 CNSS2 导出 | 81/81 CRC、许可证类别、命名空间匹配；81 个入口前置数据字匹配 |
| checked 扩展 | 注销 CRC 0x45b39d2b；注册回执 CRC 0x6d86a905；没有其他额外导出 |
| 实际模块导入记录 | provider 13、CNSS2 364、WLAN 601 项匹配 |
| WLAN 依赖/入口 | 强依赖 cnss2/provider；导入两个 checked 接口；没有旧 register/unregister 导入或未解析符号；四个 SSR/idle 槽位直达外部 provider |
| 错误参数 | 实际 ELF 的 __param_mishare_load_error 权限为 0444，modinfo 类型为 int |
| 下载产物 | 完整及紧凑 ZIP 摘要、三份模块 SHA256、全部已捕获 type-inputs 一致 |

完整默认诊断工作流仍另行运行，本阶段不将它计为全部通过。机器证据见 [0128 验收记录](research/popsicle-registration-0128-validation.json)。入口前置字与记录检查只覆盖列出的范围，不认证所有 KCFI 调用点、完整私有 ABI 或实际加载器执行。

当前仍是实验构建。正常成功加载后的受控卸载、跨电源/恢复协调、部署替换与回退、全部私有 ABI/KCFI 和原厂加载器行为仍需继续验收；尚未操作手机，也未验收 Apple 发现、握手、双向文件传输。
