# XAirDrop-17

小米 17 Pro Max（popsicle / SM8850）的实验性 AirDrop 移植工程，基于 [Weverses/OPAirDrop](https://github.com/Weverses/OPAirDrop)，参考 [Leekin2/XAirDrop](https://github.com/Leekin2/XAirDrop)。

**目前处于源码与 ABI 适配阶段，没有适用于小米 17 的可安装包，尚未完成实机收发验证。**

- [小米 17 适配进度、离线审计与待办](docs/POPSICLE-PORT.md)
- [源码版本记录](docs/popsicle-source-lock.json)
- [上游说明（其中机型、功能和安装说明适用于上游）](docs/UPSTREAM-README.md)

此前临时工作区已丢失，本仓库先保存根据调查记录重建并重新检查的部分代码；详细恢复范围见适配进度。仓库中的上游 Oplus 安装逻辑和构建入口尚未迁移到小米 17，请勿直接构建安装。

## 当前内容

保留 OPAirDrop 的 Wonder、provider、驱动补丁及用户态源码。新增小米 17 的离线模块审计、6.12 导出解析修复、实验性 Kbuild 入口，以及参考 XAirDrop 的可用性节点源码。节点默认关闭，节点出现不代表 AWDL 已实现。

原厂固件、设备日志、工具链和本地构建产物不纳入仓库。

## 许可与来源

保留上游作者署名、GPL-3.0 许可及文件级许可。上游项目作者 TimelessU；XAirDrop 作者 Leekin2、mertcqnkld。sysctl 源码保留原文件 GPL-2.0 标识。详见 [LICENSE](LICENSE)、[LICENSING.md](LICENSING.md) 和各文件头。
