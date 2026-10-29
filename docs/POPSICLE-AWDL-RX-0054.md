# 0054：AWDL 接收过滤细分

0053 已实机收到 1043 包，AWDL observed=0、ignored=1043。Wonder RX 同为 1043，invalid=0，运行与清理成功。但旧 ignored 合并所有来源和普通帧拒绝，不能区分来源过滤与真实帧格式不匹配。

0054 不放宽原有来源/格式限制。新增 awdl_rx_filters，按首次失败位置把每包分入 16 类，所有字段总和应等于 summary.packets：observed、short_address、wrong_interface、wrong_hardware、outgoing、unknown_origin、packet_truncated、radiotap_error、tx_metadata、short_frame、bad_frame_version、non_action、non_vendor_action、non_apple_vendor、bad_awdl、unsupported_awdl。额外拒绝带 radiotap TX_FLAGS 的本机发送元数据，避免底层 TX 回显被当作接收观察。

awdl_rx_frame_types 是经过来源/radiotap 检查后的帧类型统计，和上述结果会重叠，不应再相加。management_subtypes 的索引就是 802.11 管理帧 subtype，例如 8=Beacon、13=Action。public_actions=category 4，vendor_actions=127，other_actions=其他分类。畸形/不完整 Action 可能只记管理帧类型，未到 category 统计。

awdl_rx_first_metadata 仅记录第一个包的 sockaddr 长度、硬件类型、packet_type、包长度和接口匹配布尔值，不输出 MAC、SSID 或原始载荷。controller 另存前后 Wi-Fi 链路和 channels.txt；频道前后相同不能证明期间从未改变。

## 运行步骤

沿用原厂 WLAN、同一 Wi-Fi 和附近 Apple 设备条件，不先调整频道。确认上一轮已退出、没有 Wonder/旧 monitor 会话。本包包含匹配的工具、Wonder 和 controller。

解压到 Download 后，root 终端逐块执行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-AWDL-RX-0054 /data/local/tmp/xairdrop-0054
cd /data/local/tmp/xairdrop-0054
sha256sum -c SHA256SUMS
chmod 755 action-tx-0054
```

连接 Wi-Fi，暂时停用 p2p0，保留原状态；本地测试期间不使用 Wi-Fi Direct：

```sh
P2P_FLAGS=$(cat /sys/class/net/p2p0/flags)
ip link set p2p0 down
```

附近 Apple 设备打开隔空投送接收或分享界面。运行约 60 秒，只接收、不注入：

```sh
cd /data/local/tmp/xairdrop-0054
sh popsicle-awdl-rx-test.sh "$PWD" "$PWD/result-0054-01"
```

正常结束显示 RX_OBSERVATION_COMPLETE。若 CLEANUP_FAILED，先保留现场并发输出，不强制卸载或切换驱动。正常清理后，在同一个终端恢复原 P2P 状态并复制日志：

```sh
if [ "$((P2P_FLAGS & 1))" != 0 ]; then ip link set p2p0 up; fi
cp -R /data/local/tmp/xairdrop-0054/result-0054-01 /sdcard/Download/
```

日志目录必须为新目录；重复测试用 02。上传整个结果目录压缩包，主要分析 awdl-rx.log、channels.txt 和 RX 前后计数。无需原始 pcap。Wi-Fi 链路和 dmesg 可能包含设备信息，仅私下反馈。

本轮仍没有时间同步、选举、跳频或文件传输。observed 只是符合受支持头格式和 TLV 边界的帧，不认证 Apple 设备或内部 TLV 语义。0 帧也不是故障证明。
