# 外部 monitor RX 协议门槛修正（0042）

实机已确认：0041 的 QCA LPC 配置在停用额外 UP 的 P2P 接口后成功，查询 running=true。原生 monitor 在 20 秒内增加 1813 个 RX 包，Wonder RX/invalid 均为 0。用户提供的限长 pcap 包含 20 个 radiotap 帧：8 个 Beacon、12 个 QoS 数据帧；radiotap 长度为 48、60 或 70 字节。此证据证明原生收包，不证明 AWDL 互通；pcap 也不包含 skb->protocol，不能据此断言其运行时值。

外部 monitor 已限定绑定 ARPHRD_IEEE80211_RADIOTAP 网络设备，但旧 Wonder 仍要求 skb->protocol == ETH_P_802_2 才进入接收校验。原生驱动的 monitor 交付路径没有在该处明确设置此值。0042 在 external_monitor 模式下直接调用已有的 radiotap/802.11 校验函数，保留长度、版本和帧类型检查；其他模式保持原逻辑。这个修正针对可疑的软件门槛，实机结果仍待验证。

源码：02ad81ce653fbc541438c89146bfca74b6420f71。
GitHub Actions：40832922219，job 123311002350，成功。
模块 SHA256：8e1d629cfe2a32f552d0190dac09912fb68c4756268ab53f18d0b3bb3f6532ea。
模块大小：1960120 字节。107 条导入版本记录无已记录不匹配；这不构成完整 ABI、固件或实机认证。

补丁包只含新 Wonder 模块、对应源码、许可和构建报告，复用 0040 的脚本与 0041 工具，不安装原生 WLAN/mac80211。

解压到 Download 后，在仍保留原生 monitor 和 LPC 会话的 root 终端执行：

```sh
cd /data/local/tmp/xairdrop-0040
cp /sdcard/Download/XAirDrop-17-RX-Fix-0042/wonder.ko ./wonder-0042.ko
./action-tx-lpc capture-status --dev wlan0 --require-running
sh popsicle-rx-start.sh stop && sh popsicle-rx-start.sh start "$PWD/wonder-0042.ko" misharemon0
```

若查询不是 running=true，或 stop/start 出错，先保留输出，不继续后续收包测试。不重复 capture-start，不设置固定频道。

启动成功后执行以下观察，等待期间浏览网页产生流量：

```sh
(
  echo BEFORE
  ip -s link show misharemon0
  sh popsicle-rx-start.sh status
  sleep 20
  echo AFTER
  ip -s link show misharemon0
  sh popsicle-rx-start.sh status
  ./action-tx-lpc capture-status --dev wlan0
) > rx-0042.txt 2>&1
dmesg > rx-0042-dmesg.txt
cp rx-0042.txt rx-0042-dmesg.txt /sdcard/Download/
cat rx-0042.txt
```

观察 opairshare_wonder_rx、opairshare_wonder_rx_invalid 和 wonder0 RX 的变化。只有实测计数或 wonder0 抓包才能确认桥接修复。即使成功，也仅证明当前本地捕获桥接，不代表完整 AWDL 收发和 Apple 文件互传。

需要回退时，在同一 root 工作目录执行：

```sh
sh popsicle-rx-start.sh stop && sh popsicle-rx-start.sh start "$PWD/wonder.ko" misharemon0
```
