# 0126：实际 CNSS2 / provider / WLAN 配对构建

新增独立 Actions 工作流和严格配对脚本，目标为实际 PCIe/CNSS2。固定 GKI 核心符号表、原厂 vendor 导出、原始 81 个 CNSS2 导出和实际目标 profile/import 证据保持准入约束，不使用 ICNSS 作为目标替代。

从已验证 vendor_boot.img 的真实早期模块恢复 smem、minidump、pci_msm_drv、qcom_ipc_logging、mhi、memory_dump_v2、cmd_db、qcom_ramdump、qcom_aoss 九个提供者，共 141 个导出。51 个此前未覆盖的原厂 CNSS2 导入与这些实际导出的 CRC 全部匹配；合并固定官方核心和 29 个原厂模块后，原厂 CNSS2 未解析导入为零。没有根据消费者 CRC 合成提供者。源镜像、模块 SHA256、完整导出及对应关系已保存到 [提供者证据](research/popsicle-cnss2-providers-0126.json)。这证明输入覆盖，不证明新编译 CNSS2 已通过。

构建使用固定 canoe_gki CNSS2 配置、固定 SoC canoe_perf 中 PCI_MSM/MHI/IPC/SMEM/SOCINFO 设置。补丁 0059 仅在独立平台构建开关下选择原始 SoC MHI 头文件，按 SHA256 验证并通过符号链接引用，在原生 include 位置引入，不手写结构体或声明、不修改头文件内容、不在 pr_fmt 之前强制预包含。

顺序：prepare → provider → CNSS2 完整编译/严格 modpost → 原有 81 个导出的 CRC/许可证类别/命名空间与原厂完全一致且仅新增 checked 导出 → 模块记录/头部检查 → 开启独立 WLAN checked CNSS2 消费者编译 → 验证强导入新接口、不导入旧 void 注销接口、依赖 CNSS2/provider、版本记录与完整解析 → 严格链接 WLAN。任一步失败停止；不放宽 CRC/modpost、不新增 KABI 规则，不开启无线后端。真实错误日志、symtypes、生成 symvers、构建命令、配置和模块留作诊断。

当前本地 62 项回归通过（新增 5 项导出表准入测试），脚本/YAML、0059 正反检查及七个平台文件还原通过。真实配对构建待 Actions；尚未生成或认证可安装配对。默认 WLAN 消费者开关关闭，配对脚本显式开启且禁止与 checked ICNSS 同时开启。原厂 CNSS2/MHI 私有 ABI/KCFI、加载替换次序、原生恢复/电源并发协调、注册失败展开、module-exit 与 RF/Apple 互操作均未实测。
