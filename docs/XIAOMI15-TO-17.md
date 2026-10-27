# 小米 15 → 小米 17 的完整链路移植

当前以 Leekin2/XAirDrop 的 MiShare 路线为主线，固定提交
`eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76`。原始 Java、构建和启动脚本直接
纳入 `third-party/xairdrop15/`，逐文件 SHA-256 及许可保留在 provenance.json。
应用层实现直接复用；SM8750/6.6 的二进制 WLAN 模块不进入 17 的构建。

## 一条完整链路与当前缺口

| 环节 | 复用与适配 | 17 的现状 |
| --- | --- | --- |
| MiShare 发现 | 上游 Apple BLE payload 修正 | 已有精确 DEX 补丁与全类校验 |
| Wi-Fi 会话 | 上游 Bridge / NetworkBroker / WifiControl | 本轮构建可选的暂停/恢复载荷；未在手机启用 |
| 网络注册 | MiShare 原生 NetworkAgent | 本机已授权 NETWORK_FACTORY，保留原路径 |
| 系统服务 | 参考 DomesticXOsComm / libxos / VINTF | 已验证加载、注册及真实 MiShare 元数据访问；无线未运行 |
| 无线会话 | PAS 主机 + NDI 固件，self-peer、START、host-only UP | 主机 owner 已有；17 的固件会话未接通 |
| 发现/数据 TX | 参考 WMI 管理帧及 RAW DATA 路径 | 待对齐 17 的参数、DMA、完成通知与 peer |
| RX 与频道 | 辅助 monitor、地址过滤、native RX/BA 与 set_freq | 待移植并验证完整通路 |

## 明确采用小米 15 的实际无线配置作为首选参考

`reference/action.sh.txt` 实际加载参数包括 `passthru_fwtype=7`、
`passthru_ndi_peer=1`、`passthru_ndi_no_up=1`、`passthru_awdl_wmi_raw=1`、
`passthru_aux_monitor=1` 与 `passthru_awdl_native_rx=1`。全部参数从脚本提取到
`tools/xiaomi15/profile.json`，构建验证其与固定脚本一致。

因此应优先移植 PAS 主机 + NDI 固件会话、WMI RAW TX 和 RX 的完整实现，
不再把“小米 17 固件原生接受 type 9”当作默认前提。17 代码中预置的 mgmt.type=9
仍是未提交固件的占位；采用 NDI 时需调整类型选择及相关检查，不能把这个
占位值当作固定协议要求。NDI type=7 也是参考路线，
不能据此宣称 17 固件已经验证支持该组合；需要结合 self-peer、真实 START/
STOP/DELETE 响应、频道与收发验证。

现有 owner、引用回收、版本记录和 ABI 检查作为完整移植的检查基础保留。
后续工作围绕参考 HDD init/set_freq/TX/RX/stop 接口逐项接线，不再新增独立
诊断模块作为主线。其他机型的强制模式、策略绕过和重写 CRC 不迁入默认路径。

## 本轮应用层直接复用的构建

Actions：`.github/workflows/xiaomi15-port.yml`。
入口：`tools/xiaomi15/port.py`。它在 Linux/Actions 使用现有的 Apktool、公开
同 DEX 参考 APK 和 Android 36 / build-tools 36.0.0，编译前保存缓存。
没有在本地编译 Java/DEX，也没有重新触发整个 WLAN 构建。

这是一个单独、可选的 **Wi-Fi 全频段会话兼容配置**。现有 BLE-only 工作流
和本机默认 Wi-Fi 策略保持原样；是否需要全频段暂停，须在 17 无线后端可用
后实测决定。该配置只改变 `a.u0`、`a.k0` 两个应用类，并增加 Bridge DEX：

- BLE 复用已经验证的版本字节和联系人哈希偏移修改。
- Wi-Fi conflict manager 复用 15 的发现/暂停/恢复接法，保留原 reconnect 方法，
  新 wrapper 用 try/finally 确保结束时释放 hold。
- AwdlServiceClient、原生 NetworkAgent、地区、可用性与系统分享面板不变。
- Wi-Fi-only root broker 复用原有 UID/peer 凭据校验与 generation 恢复机制，
  去掉 xos0 NetworkAgent 注册。HOLD 请求在同一个 socket 上完成暂停并保持
  会话，进程/套接字退出才释放；多 holder 未结束时不恢复 Wi-Fi。
- 部分暂停/恢复错误不会报告成功；恢复文件仍保留。没有 broker 时客户端
  返回失败，不直接断开 Wi-Fi。原始代码仍保留，衍生副本哈希写入构建报告。

主机 JVM fixture 使用真实衍生 broker 的 holder 方法和假的 WifiControl，
验证首个/重复/并发 holder、错误保留与旧 generation 排除。它不执行真实
Android socket、Binder、IWifiManager 或 Wi-Fi 操作。真实 helper 同时编译为
DEX；应用 DEX 重建后再反汇编，逐类比较，Wi-Fi 类逐方法比较完整指令与
类/字段，只有方法排序和分组注释不参与其哈希。

构建输出为 `classes.dex`（以及需要时其他已变更 DEX）、`classes3.dex`、
`xairdrop17-wifi-broker.dex` 和 manifest.json。**它们是代码载荷，不是可安装
APK 或可刷模块。**不输出参考资源拼装的 APK，不挂载应用，不启动 broker，
不改 SELinux，不启用 wonder_enable，也不发送无线命令。

## 接线顺序

1. 复用的 MiShare 会话、服务和原生网络注册形成单一用户态构建入口。
2. 对照 15 的 PAS/NDI 实现，补齐 17 的固件会话与 self-peer/完成事件。
3. 将真实 WMI RAW TX、频道和 RX 路径接入 Wonder，再做端到端实测。
4. 只有无线后端可用且恢复/权限验证完成后，才制作整合启动和安装包。

目前 AirDrop 不可用；本轮无需手机安装或执行新命令。

## 已完成构建与独立复核

应用层构建 [40488962018](https://github.com/xxz3312/XAirDrop-17/actions/runs/40488962018)
在提交 `f6ad95ef216035502b906b8715cde3cc559099e7` 成功。8 项新增 Python 测试、
6 项原有测试、真实衍生 broker 的主机 holder fixture、Java/D8 和 DEX 全类比较通过。
Apktool/参考 APK 与 Android 工具链缓存均命中。

下载的 Actions ZIP 为 3,179,063 字节，SHA-256 为
`8d69fdac8495622f9f4201573dff5fdccba3977c597fd793113cdeddb8416997`。
已在本地独立复核 ZIP、三个 DEX、衍生 Java 源码哈希和五个原始文件的上游 Git blob ID。
完整结果见 [构建报告](research/popsicle-xiaomi15-session-port-build-pass.json)。
这个结果证明构建与限定范围的代码比较通过，尚未验证手机上的 IWifiManager 调用与无线会话。

驱动接入位置与下一项完整修改见 [17 原生驱动移植分析](POPSICLE-NDI-RAW-PORT.md)。
