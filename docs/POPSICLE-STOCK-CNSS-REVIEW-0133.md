# 0133 保留原厂 CNSS2：依赖审查与构建门禁

结论：源码具备恢复原厂 CNSS2 接口的独立分支，可以进入诊断重构/构建阶段；现有 0130/0131/0132 ELF 不可直接使用。尚未证明运行时兼容，更未修复或确定 0132 重启原因。本阶段不生成手机加载包，不改动手机。

## 实际依赖

审查对象为固定 WLAN 源 36df473046706a5259942e1bf7222108dbbb860f 加项目补丁至 0064，以及已验收的 0130 WLAN ELF（SHA256 cac81dee8b2cf99bef8f32bc977d0ca86833a9caa8585c7305c9d3eadc251dbf）。

实际 ELF 导入 62 个原厂 CNSS2 导出，版本 CRC 均匹配捕获记录。另外强导入 cnss_wlan_register_driver_checked_v1、cnss_wlan_unregister_driver_checked_v1；这两个扩展原厂没有，必须重新构建 WLAN。opairshare_wlan_live_unload_arm_v1 也在实际导入中，说明当前 ELF 使用配对外部卸载控制。完整报告见 [0130 ELF 反向验证](research/popsicle-stock-cnss-existing-0130.json)。cnss_utils_* 属于另一个捕获模块，不应误算为 CNSS2 缺失符号。

| 位置 | checked 变体 | 保留原厂分支 |
| --- | --- | --- |
| qcacld-3.0/core/pld/src/pld_pcie.c：register/unregister | checked_v1 强导入、注册保留回执 | cnss_wlan_register_driver / cnss_wlan_unregister_driver |
| 同文件 pld_pcie_ops | provider 的四个 PCIe execution 回调 | 原生 reinit/shutdown/idle_restart/idle_shutdown 回调 |
| 同文件 remove | 可拒绝的 remove 状态及隔离 | 原生 void remove 流程 |
| qcacld-3.0/core/hdd/src/wlan_hdd_main.c | PLD self-pin、注册失败隔离、外部 live-unload arm 和 module-exit 分流 | 原生 module-init 返回与 module-exit 清理分支 |
| tools/kernel/popsicle_trial_build.sh | POPSICLE_CHECKED_CNSS2=1 定义 CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER | 默认 0，不定义该宏；不能用 -D宏=0，因为源码使用 ifdef |
| tools/kernel/cnss2_checked_pair.py | 显式构建 CNSS2 替代品并移除原厂符号提供者 | 不作为保留原厂路线的构建入口 |

checked 注册/注销扩展服务于新增生命周期回执和可拒绝清理，并非 AWDL 数据面强制要求的固有接口。关闭该变体不会删除已有无线功能源码，但会失去 checked 路线的注册保留回执、四回调外部串行化、自持引用及受控热卸载保证。其他早期 host/runtime/SSR 扩展仍保留，并不等于全部回退为未经修改的上游。

## 已实施的构建约束

新增 tools/kernel/stock_cnss_audit.py，在默认 popsicle_ci.py 的实际 WLAN 链接完成后运行，输出 stock-cnss-imports.json。要求两个原厂 register/unregister 导入均存在、全部导入的原厂 CNSS2 CRC 匹配、依赖包含 cnss2/provider；拒绝 checked_v1 或外部 live-unload arm 残留，以及捕获表外的 cnss_* 扩展。没有 CRC 改写、符号伪造或放宽 modpost。原有完整依赖、模块布局及其他 ABI 门禁继续执行。

八项新测试覆盖正常与拒绝边界，包括仅版本表残留 checked 名称、额外 provider 的 cnss_utils、CRC 缺失/错误、依赖遗漏和重复原厂提供者。对实际 0130 ELF 运行门禁，按预期拒绝，并证明 62 项旧 CNSS2 导入 CRC 无差异。CI/模块报告相关既有测试另行通过。没有本地 C 编译、没有新 ELF 正向通过记录；完整编译仍待 CI 验证。

## 后续实施边界

1. 用默认诊断构建入口重新生成 WLAN/provider，保持 checked CNSS2 与 checked ICNSS 变体关闭；检查真实 ELF 门禁和 callback/private-layout 证据。已存在的条件分支优先复用。
2. 新建单独的“原厂 CNSS2 常驻”部署合同：启动前、替换 WLAN 后均核对同一原厂 CNSS2 note，绝不对 cnss2 发出 remove/insert。不能沿用现有 pairctl 的 apply/restore，也不能把新 ELF 塞进原 0131 清单。
3. 初始恢复方式采用禁用实验入口并重启；原生 void 注销没有 checked 完成回执，当前不能宣称受控热回退已移植。手动启用、意外重启后停用自动启动、持久日志方案需在 KSU 包中明确实现后才交付。
4. 仅在新构建及新部署合同通过后再安排实机；不以“保留 CNSS2”推定重启问题已解决。

上游参考固定为 Leekin2/XAirDrop 891ffe6ccf040fdc86975b4fc649add002dbebcb 的 module/action.sh、module/service.sh，以及 Weverses/OPAirDrop 28a3a1dbc9f515fa5705417a3973616e5ae6180d 的 module/bin/control.sh、module/service.sh。两者在开机后替换 WLAN 时保留 CNSS2，未采用首次加载前替换 CNSS2 的路线。
