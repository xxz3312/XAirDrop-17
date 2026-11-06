# 0126：实际 CNSS2 / provider / WLAN 配对构建

新增独立 Actions 工作流和严格配对脚本，目标为实际 PCIe/CNSS2。固定 GKI 核心符号表、原厂 vendor 导出、原始 81 个 CNSS2 导出和实际目标 profile/import 证据保持准入约束，不使用 ICNSS 作为目标替代。

从已验证 vendor_boot.img 的真实早期模块恢复 smem、minidump、pci_msm_drv、qcom_ipc_logging、mhi、memory_dump_v2、cmd_db、qcom_ramdump、qcom_aoss 九个提供者，共 141 个导出。51 个此前未覆盖的原厂 CNSS2 导入与这些实际导出的 CRC 全部匹配；合并固定官方核心和 29 个原厂模块后，原厂 CNSS2 未解析导入为零。没有根据消费者 CRC 合成提供者。源镜像、模块 SHA256、完整导出及对应关系已保存到 [提供者证据](research/popsicle-cnss2-providers-0126.json)。这证明输入覆盖，不证明新编译 CNSS2 已通过。

构建使用固定 canoe_gki CNSS2 配置、固定 SoC canoe_perf 中 PCI_MSM/MHI/IPC/SMEM/SOCINFO 设置。补丁 0059 仅在独立平台构建开关下选择原始 SoC MHI 头文件，按 SHA256 验证并通过符号链接引用，在原生 include 位置引入，不手写结构体或声明、不修改头文件内容、不在 pr_fmt 之前强制预包含。

顺序：prepare → provider → CNSS2 完整编译/严格 modpost → 原有 81 个导出的 CRC/许可证类别/命名空间与原厂完全一致且仅新增 checked 导出 → 模块记录/头部检查 → 开启独立 WLAN checked CNSS2 消费者编译 → 验证强导入新接口、不导入旧 void 注销接口、依赖 CNSS2/provider、版本记录与完整解析 → 严格链接 WLAN。任一步失败停止；不放宽 CRC/modpost、不新增 KABI 规则，不开启无线后端。真实错误日志、symtypes、生成 symvers、构建命令、配置和模块留作诊断。

当前本地 62 项回归通过（新增 5 项导出表准入测试），脚本/YAML、0059 正反检查及七个平台文件还原通过。真实 CNSS2 已编译/严格链接，旧导出门禁拒绝后续 checked WLAN 配对；当前没有满足原厂替换条件的可安装配对。默认 WLAN 消费者开关关闭，配对脚本显式开启且禁止与 checked ICNSS 同时开启。原厂 CNSS2/MHI 私有 ABI/KCFI、加载替换次序、原生恢复/电源并发协调、注册失败展开、module-exit 与 RF/Apple 互操作均未实测。

首轮 [Actions 42214178581](https://github.com/xxz3312/XAirDrop-17/actions/runs/42214178581) 完成固定源码/工具链准备和 provider 编译，但 CNSS2 C 编译拒绝三处错误：调试 switch 未处理新增 terminal 枚举、内部 cnss_read_debug_register 缺少静态声明、M=cnss2 未继承父级 Kbuild 的 CONFIG_MHI_BUF_LEN 默认值。补丁 0060 补调试枚举并仅将本文件内部函数设为 static；构建脚本按实际 parent Kbuild/Kconfig 的固定哈希引入 0x8000（32768）默认值。未关闭 Wswitch/Wmissing-prototypes，不修改 CRC。更新后的八个平台文件还原与 62 项本地回归通过，后续编译已完成，接口门禁结果如下。原厂 CNSS2 的全部 370 个导入版本记录亦已与真实核心/厂商提供者比对，差异为零。


第二轮 [Actions 42215079411](https://github.com/xxz3312/XAirDrop-17/actions/runs/42215079411)，源码 d06f8578563e64a9776499679ec0b25a570f1128，生成真实 cnss2.ko 并通过严格 modpost。ZIP 摘要已验证；原生 type streams、命令、配置、模块与报告已核对。只读记录检查显示 provider 13 项、CNSS2 362 项导入记录匹配、模块头部记录匹配；77 个共有导出的 AArch64 入口前置数据字一致。这些检查不替代旧导出门禁或实际 KCFI/私有 ABI 验证。

| 原厂接口门禁 | 结果 |
|---|---|
| 旧记录精确匹配 | 76 / 81 |
| 缺失 | cnss_register_tsf_captured_handler、cnss_unregister_tsf_captured_handler、cnss_set_vendor_wonder_priv_data、cnss_smmu_s1_enabled |
| 唯一 CRC 差异 | cnss_get_fw_cap：原厂 0x537ead95，当前 0x42d590ce |
| 额外旧接口 | cnss_get_wlan_tsf_gpio |
| 新 checked 导出 | 已真实导出，CRC 0x45b39d2b |
| 完整配对准入 | 拒绝，尚未编译 checked WLAN |

当前固定源码不含上述四个缺失函数的定义，不能仅通过切换现有配置解决。项目历史 Wonder 补丁提供的是另一种实验实现，不能直接视为原厂接口等价；私有 provider 仍使用 opairshare 命名，避免与原厂重复导出。下一步先定位目标 TSF/SMMU/Wonder 的完整行为与 cnss_get_fw_cap 类型差异（优先核对 cnss_fw_caps）；不为凑齐符号提供空实现，不修改版本记录，也不放宽此门禁。[机器证据](research/popsicle-cnss2-pair-0126-validation.json) 保存了两次构建、完整差异与只读记录检查。手机未操作，无线后端未启用。

最新源码 d06f857 的默认 stop-admission 作业亦已通过：新增 CNSS2 与既有五套 C 夹具全部通过 ASan/UBSan/leak detection，六套源码重新组装哈希和八个平台源文件还原/哈希已核对，真实 CNSS2 构建的所有已捕获 type-inputs 摘要亦已核对。默认完整诊断作业仍另行运行，不计为本次配对成功。
