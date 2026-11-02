# XAirDrop-17

小米 17 Pro Max（popsicle / SM8850）的实验性 AirDrop 移植工程，以 [Leekin2/XAirDrop](https://github.com/Leekin2/XAirDrop) 的 MiShare 完整链路为适配主线，复用其底层来源 [Weverses/OPAirDrop](https://github.com/Weverses/OPAirDrop) 的 Wonder/WLAN 实现。

**当前为手动实机测试阶段，尚无可日用的 AirDrop 整合安装包。17 Pro Max 已验证自编译 WLAN 启动/联网、原生 LPC → Wonder 收包和一次实验 vendor Action token 完成回写。Apple 发现与文件互传未实现/验证；其他机型（包括 17 Pro）未认证。**

最新进展：[0094 原生 PSOC 引用与 PDEV 释放期间的父对象保留](docs/POPSICLE-NATIVE-PSOC-LEASE-0094.md)已完成离线验收。[CI 41424409521](https://github.com/xxz3312/XAirDrop-17/actions/runs/41424409521) 两项作业通过：72 个组合序列、17 项负对照、0093/0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整编译、严格链接和七项选定布局。原生 PSOC PDEV map/引用已接入，fixture caller 将最后 PSOC 引用保留至 PDEV 队列关闭及实际 host heap free 之后。完整生成源码、六个 PSOC/10 个 PDEV 原生函数体及 46 份报告中的生产源码已独立核对；见[验证记录](docs/research/popsicle-native-psoc-lease-0094-validation.json)。PSOC 最终析构/存储仍是模型，真实 DP 回调与生产自动停机协调尚未完成；活动 START/UP SSR 恢复及完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。完整状态见[进度表](docs/POPSICLE-PROGRESS.md)。

- [小米 17 适配进度、离线审计与待办](docs/POPSICLE-PORT.md)
- [小米 15 → 17 的复用与构建入口](docs/XIAOMI15-TO-17.md)
- [源码版本记录](docs/popsicle-source-lock.json)
- [GitHub Actions 编译](docs/POPSICLE-ACTIONS.md)
- [上游说明（其中机型、功能和安装说明适用于上游）](docs/UPSTREAM-README.md)

仓库保留上游 Oplus 安装逻辑和构建入口，但它们不是小米 17 的整合安装方案。当前按测试包的手动流程验证，不直接安装上游模块。

## 当前内容

保留 OPAirDrop 的 Wonder、provider、驱动补丁及用户态源码。新增小米 17 的离线模块审计、6.12 导出解析修复、实验性 Kbuild 入口，以及参考 XAirDrop 的可用性节点源码。节点默认关闭，节点出现不代表 AWDL 已实现。

原厂固件、设备日志、工具链和本地构建产物不纳入仓库。

## 许可与来源

保留上游作者署名、GPL-3.0 许可及文件级许可。上游项目作者 TimelessU；XAirDrop 作者 Leekin2、mertcqnkld。sysctl 源码保留原文件 GPL-2.0 标识。详见 [LICENSE](LICENSE)、[LICENSING.md](LICENSING.md) 和各文件头。
