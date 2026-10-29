# 0053：AWDL 管理帧接收识别

0052 手机日志已核对：45 字节实验广播 native_status=0，token NOACK=1，completed/reported=1，failed/rejected=0，exit=0，Wonder 卸载和原厂 WLAN 恢复成功。monitor 删除时出现 DP peer 状态警告，接口仍正常删除；不据此认证长期稳定。restore 只确认 wlan0 存在，不证明重新关联 AP。

0053 新增 action-tx awdl-listen 与 awdl-inspect，以及单终端 RX controller。仅接收/解析，不发送 AWDL 帧，不开启 XOS，不建立 peer，不进行时间同步、选举或文件传输。外部数据全部作为不可信输入；只输出类型和计数，不输出 MAC、设备名称或 TLV 内容。

格式参考固定 seemoo-lab/owl tree 0ee3263f944ea721c355f826aa90d636d012a512 的 src/frame.h、src/rx.c、src/version.c。独立实现有界解析：普通 24 字节 Action 头、category 127、Apple OUI 00:17:f2、type 8、version 0x10、PSF 0/MIF 3、16 字节 AWDL Action 头，以及 type/u16LE-length/value TLV 链。未知 TLV 保留计数；已知 TLV 只统计类型，未校验内部语义。未知版本/子类型单独计数。格式匹配不能认证 Apple 身份。

awdl-listen 仅绑定已 UP 的 radiotap 接口；检查收包接口/硬件类型，排除 PACKET_OUTGOING、LOOPBACK 和未知来源类型，校验 radiotap/FCS，拒绝截断、保护/分片/扩展头和越界 TLV。重复接收帧仍分别计数，不表示多个 peer。最多 300 秒/1000 条观察；默认 60 秒/10 条。零观察可正常退出，必须查看 observed，不能称发现成功。

## 手机使用

0053 包包含新工具、沿用已实机通过的 Wonder、RX helper、controller 和源码。可直接使用原厂 WLAN，不必启动 0049 替换驱动。若仍在使用实验 WLAN，先按原流程恢复；确认没有旧 Wonder/relay 会话和 monitor。

解压到 Download 后 root 终端执行（每块分别复制）：

```sh
cp -R /sdcard/Download/XAirDrop-17-AWDL-RX-0053 /data/local/tmp/xairdrop-0053
cd /data/local/tmp/xairdrop-0053
sha256sum -c SHA256SUMS
chmod 755 action-tx-0053
```

连接 Wi-Fi，查看当前频道及 P2P 状态：

```sh
iw dev wlan0 link
ip -br link show p2p0
```

QCA LPC 需要次级接口不活动。若 p2p0 为 UP，记住这个状态，在没有使用 Wi-Fi Direct 的情况下手动暂时停用；controller 不自动操作 P2P/NAN：

```sh
ip link set p2p0 down
```

在附近 Apple 设备打开隔空投送接收界面或分享界面，然后执行：

```sh
cd /data/local/tmp/xairdrop-0053
sh popsicle-awdl-rx-test.sh "$PWD" "$PWD/result-0053-01"
```

等待约 60 秒或观察到 10 帧后自动结束并清理。controller 开启本次 monitor LPC，启动 Wonder RX，记录前后计数，运行只读监听器，再停止 Wonder 和删除本次 monitor。它不换频道；只观察 STA 当前频道。附近 Apple 不一定在同频道活动，observed=0 不能证明没有 Apple 或协议不支持。当前 AP 频道可能限制观察，后续再实现时槽与换频。

若之前手动把 p2p0 从 UP 改为 DOWN，清理成功后恢复：

```sh
ip link set p2p0 up
```

如果本来就是 DOWN，不执行这条。若出现 CLEANUP_FAILED，保留资源，发日志，不强制卸载、不切换 WLAN。日志目录必须为新目录；重复测试换为 result-0053-02。

复制结果：

```sh
cp -R /data/local/tmp/xairdrop-0053/result-0053-01 /sdcard/Download/
```

上传目录压缩包，重点为 awdl-rx.log、rx-before.txt、rx-after.txt、setup.txt、stop.txt、result.txt 和 dmesg.txt。默认不保存原始抓包。

离线解析可使用 awdl-inspect --frame FILE，radiotap 包额外加 --radiotap；输入是单个原始帧，不是 pcap。输出 source=offline_file 不作为空口接收证据。
