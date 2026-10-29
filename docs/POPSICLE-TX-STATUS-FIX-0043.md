# 原生 Action 完成事件匹配修正（0043）

0042 实机证据已确认原生 LPC → Wonder → 用户态接收：20 秒内 Wonder 接收计数增加 1277、invalid 保持 0；wonder0 抓包含 13 个 Beacon、7 个 QoS 数据帧，帧头可解析。wonder0 自身的统计有重复记账，不能直接按它计算无线丢包率。

初始 action-smoke.bin 是 category 127 的非 Public Action，广播 DA/BSSID 无法通过普通已连接 STA 的标准 cfg80211 管理帧条件，实机返回 ENOTCONN。后续 Public vendor Action 实验帧成功返回 cookie=256，但旧工具仍超时；并行 iw event 记录 mgmt TX status cookie 100、acked。iw 用十六进制输出 cookie，0x100 等于 256。这是原生状态上报证据，不是 Apple 对端或广播 peer ACK 的证明。

锁定原生驱动中 components/p2p/core/src/wlan_p2p_off_chan_tx.c 的 p2p_populate_mac_header() 会改写 tx_ctx->buf 的序列号，完成回调又将此缓冲区交给 cfg80211_mgmt_tx_status。旧工具对完整帧做 memcmp，会拒绝序列号不同的回执。0043 只放宽序列控制字段的 12-bit sequence number，保持低 4-bit fragment number、其余所有帧字节、长度、接口和请求 cookie 匹配。ACK 请求确认、其他 cookie/接口、内容变更仍不能完成请求。仍使用有限缓存处理先于 cookie 回复到达的状态事件，不自动重发。

源码提交：d26d08dc8b78867af5d8d2eb0b9bbf783cec4ca3。
本阶段只更新 Android 用户态工具，继续使用 0042 wonder.ko，不需要内核重编译或重载模块。原生 Public Action 状态验证不解决 AWDL 非 Public Action 的独立发送后端问题。

解压 XAirDrop-17-TX-Status-Fix-0043.zip 到 Download 后，在原 root 工作目录运行：

```sh
cd /data/local/tmp/xairdrop-0040
cp /sdcard/Download/XAirDrop-17-TX-Status-Fix-0043/action-tx ./action-tx-0043
chmod 755 ./action-tx-0043
cp /sdcard/Download/XAirDrop-17-TX-Status-Fix-0043/action-public.bin ./action-public-0043.bin
(
  FREQ="$(iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}')"
  [ -n "$FREQ" ] || { echo 'Wi-Fi not connected'; exit 1; }
  ./action-tx-0043 send --dev wlan0 --freq "$FREQ" --frame action-public-0043.bin --rewrite-source --timeout-ms 10000
  echo "send_exit=$?"
) > tx-0043.txt 2>&1
cat tx-0043.txt
cp tx-0043.txt /sdcard/Download/
```

测试报文：广播 DA/BSSID，占位 SA 02:00:00:00:00:01，经显式 rewrite-source 替换；category 4 / Public vendor action 9，实验 OUI 02:00:00，标记 XAIRDROP_PUBLIC_TEST，49 字节。不是 AWDL 协议帧。

预期 submitted 后出现同 cookie 的 tx_status，send_exit=0；广播 acked 字段只反映驱动报告，不证明任何指定接收端收到。仍需实机确认修正有效，必要时用另一设备验证空口。当前包不启用 RAW DATA、不替换原生 WLAN，也不设置固定频道。
