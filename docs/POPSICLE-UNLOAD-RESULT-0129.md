# 0129：完整 HDD 卸载结果与部分清理失败保留

本阶段完成受控卸载所需的原生结果链。原来的 `hdd_driver_unload_internal()` 返回 void；两次 driver transition、卸载准入和 checked 注销都可能提前返回，上层无法区分“完整结束”与“中途拒绝”。较晚失败还可能让软卸载调用恢复标志后再次进入加载，接触已经部分清理的上下文。

补丁 0063 给内部函数增加可选的结果输出，入口先置 `-EINPROGRESS`，四处提前返回写入实际错误，只有完整清理尾部结束才置零。增加内部、未导出的 `hdd_mishare_driver_unload_checked()`，返回完整结果；原有 void 和软卸载入口继续保留。默认消费者仍关闭。

| 路径 | checked 行为 |
|---|---|
| 第一次 driver transition 失败 | 使用原生 QDF errno 转换返回错误，尚未改变全局卸载标志；标记软卸载拒绝 |
| 卸载准入拒绝 | 返回原错误，停止 transition，保留全部下游清理资源 |
| checked 注销失败 | 返回实际错误，保留组件与同步资源，进入已有只读错误/模块引用保留状态，阻止重新加载 |
| 注销后第二次 transition 失败 | 返回原生转换错误，保留剩余公共资源并阻止重新加载；不宣称撤销已经完成的清理 |
| 完整尾部结束 | 结果为零，模块引用仍保留 |

checked 分支在这两处 transition 错误前不再执行 `QDF_BUG`，使已有错误分支能够返回；默认分支保留原行为。新的结果输出不会释放模块引用，不安装用户入口、不导出内核 API、不自动调用卸载。未来外部控制器必须持续持有模块引用，排除所有加载/模式/卸载调用，并保证单次执行；成功后的 module-exit 分流、返回到外部后释放引用和部署回退仍待接入。本阶段不能算作正常 rmmod 已可用。

新增完整原生函数夹具，执行整个 HDD 卸载函数、typed entry、void/软卸载包装、已有 quarantine 以及原样 QDF 转换，覆盖 18 个隔离场景和 5 项错误注入。驱动同步、平台/provider 注销及组件销毁仍为模型；现有独立 CNSS2 夹具继续覆盖真实 checked 注销函数。旧 host 测试覆盖先前的准入前缀，新增测试覆盖实际完整卸载尾部，避免把前缀成功误计为完整清理成功。

63 项本地 Python 回归、补丁独立精确正反检查和原生函数还原通过。[Actions 42238860650](https://github.com/xxz3312/XAirDrop-17/actions/runs/42238860650) 的 stop-admission 作业通过：新增测试与原有八套回归全部通过 ASan/UBSan/leak detection。九套重新组装夹具、原生片段、生产文件及头文件哈希与下载产物一致。

[配对构建 42237940688](https://github.com/xxz3312/XAirDrop-17/actions/runs/42237940688) 已成功，下载后核对：

| 项目 | 实际结果 |
|---|---|
| CNSS2 原厂导出 | 81/81 CRC、许可证类别、命名空间及入口前置数据字匹配 |
| checked 扩展 | 仅注册回执与注销两项；实际 WLAN 同时强导入两者，不导入旧生命周期接口 |
| 模块导入记录 | provider 13、CNSS2 364、WLAN 601 项匹配，模块头记录匹配 |
| 新增卸载函数 | 实际 ELF 存在 hdd_mishare_driver_unload_checked，未导出 |
| 原有保护 | 四个 PCIe SSR/idle 槽位直达外部 provider；load_error 参数权限仍为 0444 |
| 产物核对 | 完整/紧凑 ZIP、三模块 SHA256 和全部已捕获 type-inputs 一致 |

入口前置字只核对明确范围，不认证所有 KCFI 调用点、完整私有 ABI、模块加载器或硬件并发。默认完整诊断工作流仍另行运行，尚未计为全部通过。机器证据见 [0129 验收记录](research/popsicle-unload-result-0129-validation.json)。

手机未操作，Apple 发现、握手和双向传输未实机验收。
