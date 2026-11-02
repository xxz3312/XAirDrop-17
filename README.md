# XAirDrop-17

小米 17 Pro Max（popsicle / SM8850）的实验性 AirDrop 移植工程，以 [Leekin2/XAirDrop](https://github.com/Leekin2/XAirDrop) 的 MiShare 完整链路为适配主线，复用其底层来源 [Weverses/OPAirDrop](https://github.com/Weverses/OPAirDrop) 的 Wonder/WLAN 实现。

**当前为手动实机测试阶段，尚无可日用的 AirDrop 整合安装包。17 Pro Max 已验证自编译 WLAN 启动/联网、原生 LPC → Wonder 收包和一次实验 vendor Action token 完成回写。Apple 发现与文件互传未实现/验证；其他机型（包括 17 Pro）未认证。**

最新进展：[0099 生产 HTT peer-unmap 解析与缓冲区所有权](docs/POPSICLE-HTT-UNMAP-0099.md)已完成离线验收。补丁 0037 增加短包/接收错误检查、对齐局部解析和精确 nbuf 释放，保留非 unmap 消息原路径。代码与用例集中完成后统一验证，[CI 41515796705](https://github.com/xxz3312/XAirDrop-17/actions/runs/41515796705) 两项作业通过：168 组组合、303 项解析合同、68 项失败控制、七项旧独立组合、53 项 Python 检查、完整 WLAN 编译、严格链接和七项布局。八份组合源码、生产补丁重放及 51 份报告中的生产源码均核对；见[验收记录](docs/research/popsicle-htt-unmap-0099-validation.json)。生产 parser helper 在主机模型中执行，真实 HTC/HIF 事件输送、完整 generic dispatcher 运行、整机兼容性和生产停机协调仍待继续；不代表 AirDrop 可用。backend 保持关闭，手机无需操作。完整状态见[进度表](docs/POPSICLE-PROGRESS.md)。

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
