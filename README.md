# XAirDrop-17

小米 17 Pro Max（popsicle / SM8850）的实验性 AirDrop 移植工程，以 [Leekin2/XAirDrop](https://github.com/Leekin2/XAirDrop) 的 MiShare 完整链路为适配主线，复用其底层来源 [Weverses/OPAirDrop](https://github.com/Weverses/OPAirDrop) 的 Wonder/WLAN 实现。

**当前为手动实机测试阶段，尚无可日用的 AirDrop 整合安装包。17 Pro Max 已验证自编译 WLAN 启动/联网、原生 LPC → Wonder 收包和一次实验 vendor Action token 完成回写。Apple 发现与文件互传未实现/验证；其他机型（包括 17 Pro）未认证。**

最新进展：[0080 原生 INIT 拒绝后的 SSR 回收](docs/POPSICLE-NATIVE-INIT-RESET-0080.md)。新增原生 INIT START 校验被原始 SSR 拒绝后的显式回收：必须依次确认 validation 拒绝、down 通知被拒绝、原生分支 origin、成功返回且 SM 已解锁，并保持 INIT/IDLE、空事务及零 pending/users。保留 BLOCKED/ESHUTDOWN 和入口历史，不冒充 DOWN；七项原生计划在 timer drain 前后重检。新增原生 API wrapper 执行、双频与异常来源/状态/回调顺序检查，以及缺失原生 origin、缺失 SM unlock 两个负对照。CI [41200864386](https://github.com/xxz3312/XAirDrop-17/actions/runs/41200864386) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；十组模型生产哈希、九个 native 文件哈希、九项 START 回收入口实际链接及模块记录已复核。真正进入 START 状态/发送 START/等待响应/UP 的回收、自动父资源协调及完整接收路径仍未完成，backend 关闭，手机无需操作。完整状态见[进度表](docs/POPSICLE-PROGRESS.md)。

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
