# 小米 15 XAirDrop 用户态来源

固定来源：Leekin2/XAirDrop，提交 eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76。
作者：Leekin2、mertcqnkld。按上游 GPL-3.0 授权，协议全文见仓库根 LICENSE。
provenance.json 记录每个原始文件的 SHA-256。原文件保持不变。

src/ 保存 Bridge、NetworkBroker、WifiControl 的原始 Java 代码。
reference/ 中的构建与启动脚本仅为带 .txt 后缀的原始参考，不执行、不安装。
这里没有小米 15/一加 13 的 .ko，也不运行 CRC 或 module 布局修补器。

小米 17 构建由 tools/xiaomi15/port.py 完成：保留现有 BLE 补丁，移植可选的
Wi-Fi 会话兼容配置，NetworkAgent、地区与分享面板继续使用本机原逻辑。
生成的 Bridge 和 broker 是明确标记的衍生副本，原始与衍生哈希进入构建报告。

broker 仅处理认证后的 Wi-Fi HOLD/RESTORE；它不注册 xos0 网络。进程/套接字
退出时按 holder 和 generation 恢复 Wi-Fi，部分失败保留恢复文件。APK 补丁
保留原 reconnect 方法并以 finally 关闭会话。构建不会启动 root broker。

NDI type 7、WMI RAW TX 和 peer/RX 参数从参考 action.sh 直接提取，保存到
移植配置中。它们是小米 15 的实际配置，不是小米 17 固件已经支持的结论。
