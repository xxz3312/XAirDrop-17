# 小米 17：以 MiShare 为入口的接入路线

最终入口是 `com.miui.mishare.connectivity`，参考
[小米 15 XAirDrop 固定版本](https://github.com/Leekin2/XAirDrop/tree/eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76)。

## 参考项目实际做了什么

| 层 | 参考实现 | 小米 17 的状态 |
| --- | --- | --- |
| MiShare 应用 | `patches/build.py` 修改 DEX；Bridge 做网络注册回退与 Wi-Fi 会话控制，并修正 BLE 广播 | 需要检查本机 APK 的真实字节与方法体，尚未移植 |
| 系统服务 | `DomesticXOsComm`、`libxos`、VINTF 和权限，以及 root NetworkBroker | 尚未验证本机兼容性或运行 |
| 无线驱动 | 复用并适配 OPAirDrop 的 AWDL WLAN/Wonder 模块 | 本机仅通过 Wonder 绑定生命周期，实际 WLAN 收发仍未实现 |

参考项目明确没有使用 LSPosed。它对确切 APK 做 smali 修改，构建后以临时 bind mount
让应用进程加载补丁代码；不是把修改后的 APK 当正常签名更新包安装。
这条应用接入路线与下层驱动移植是不同工作，最终都需要完成。
仅绕过可用性检测或出现 Apple 入口，不代表有 AWDL 通道。

## MiShare 的确切匹配条件

参考版本 `module/apply-patches.sh` 只接受原始 APK SHA256：
`394203fc35714c4c5d4b4e0b6d17ecaab239f5562a79bcf0a449ca36316cfa44`。
版本号相同并不能证明 APK 相同，原始 APK 必须先核对。

参考补丁涉及 `AwdlServiceClient`、混淆后的 BLE advertiser/WifiConflictManager，
以及地区/设备检查。小米 17 国行不应直接照搬全套常量返回值或假定这些限制存在；
必须逐项分析原始方法，只修改本机实际需要的逻辑。
小米 15 Ultra 专用 MiIntentResolver 补丁也不能照搬到本机。

原始 APK 由用户从设备导出并私下提供，不提交到公开仓库。
拿到 APK 后先验证包名、版本、SHA256、DEX 类与目标方法，再制作 Linux/Actions 构建流程。
所有编译仍在 GitHub Actions，沿用工具缓存；本机签名与授权行为要单独验证。

## 对上一段生命周期草稿的处理

`reservation` 指预留网络 adapter，不是存储或闪存预留，也不是安装模块。
`opairshare` 是参考代码沿用的前缀，不表示把手机当作一加。
该 MONITOR adapter 创建/销毁草稿尚未推送主分支，已暂停并保留草稿。
它不是小米 15 项目的 MiShare 接入实现，不能作为应用层进展。

当前优先推进本机 MiShare APK 的分析与补丁适配。底层六组缺口保持记录，不能宣称已解决。
