# 原始队列回包末尾对齐修正（0044）

实机进度：0043 工具直接发送 49-byte Public vendor Action 已收到匹配 cookie 的 tx_status，退出 0。Wonder feedback 模式下，49-byte 帧在 relay_ready 后返回 EBADMSG，未提交原生发送；改为 52-byte 实验帧后，submitted / tx_status / feedback_summary 均成功，completed=1、reported=1、failed=0、rejected=0。广播状态只表示驱动完成报告，不证明指定对端收到或空口抓包通过。

原生 LPC → Wonder → 用户态接收、Wonder 原始 skb/token 队列 → 原生 Public Action → token 完成回传已具备实机证据（后者当前为 52-byte 帧）。AWDL 非 Public Action 发送、独立 NDI 后端、AWDL 频道切换和 Apple 互传仍未通过。

## 原因与改动

Wonder PULL 回复通过 cfg80211_vendor_cmd_alloc_reply_skb 分配，skb_put_data 直接追加 32-byte 队列头和原始无线帧，再由 cfg80211_vendor_cmd_reply 收尾。Linux 的 nla_nest_end / genlmsg_end 记录实际长度，不为这种原始尾部自动追加四字节填充。49-byte 帧导致末尾属性和消息的实际长度不对齐；旧工具要求对齐长度必须全部位于收到的缓冲区中，因此提前返回 EBADMSG。

0044 允许最后一个属性/消息恰好在声明的实际长度结束，末尾可以无填充；多项之间仍按四字节对齐。声明长度超出实收、头部截断、部分填充、重复目标属性仍拒绝。32-byte 队列头的版本、owner、token、保留字段及帧长检查不变。工具不修改、不补零无线帧，也不自动重发。

回归构造 49/50/51/52-byte 队列帧的原始 vendor 回复，覆盖属性与外层 netlink 消息、完整填充/省略填充、实际数据截断和部分填充。C 编译与 ASan/UBSan 回归、Android 编译均在 GitHub Actions 执行。0044 原长度实机验证待完成。

源码：672b5e1b5968de80fd90c0edf78840aec5f56972。只更新工具，复用 0042 Wonder，无内核或 WLAN 替换。

## 原长度实机验证

保留当前 external_tx=Y 的 Wonder 会话，确认上一次中继已结束。解压到 Download，在 root 终端 A：

```sh
cd /data/local/tmp/xairdrop-0040
cp /sdcard/Download/XAirDrop-17-Feedback-Fix-0044/action-tx ./action-tx-0044
chmod 755 ./action-tx-0044
cp /sdcard/Download/XAirDrop-17-Feedback-Fix-0044/action-public.bin ./action-public-0044.bin
(
  FREQ="$(iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}')"
  [ -n "$FREQ" ] || exit 1
  ./action-tx-0044 relay --listen wonder0 --dev wlan0 --freq "$FREQ" --feedback --rewrite-source --max-frames 1 --seconds 120 --timeout-ms 10000 > feedback-0044.log 2>&1
  cat feedback-0044.log
)
```

终端 B root 工作目录中先看日志，出现 relay_ready 后再执行注入一次：

```sh
cd /data/local/tmp/xairdrop-0040
cat feedback-0044.log
```

```sh
wc -c action-public-0044.bin
./action-tx-0044 inject --dev wonder0 --frame action-public-0044.bin --rewrite-source
```

长度应为 49。不是前次补零的 52-byte 测试文件。

预期日志：submitted bytes=49，匹配的 tx_status，feedback_summary completed=1、reported=1、failed=0、rejected=0。注入成功本身不代表原生提交或完成。若失败，保留日志，不重复注入同一会话。

```sh
cp feedback-0044.log /sdcard/Download/
```

实验帧采用 Public category 4 / vendor action 9、OUI 02:00:00、XAIRDROP_PUBLIC_TEST 标记、广播 DA/BSSID、占位 SA（由显式 rewrite-source 替换）。它不是 AWDL 帧。补丁包附原始 49-byte 测试帧、源码及许可。

构建证据：Actions 40840072145 / job 123334017555，success；Android ARM64 工具 SHA256 65c95f543dd77ff2b531b55fd7a1a1127fe0d41e944b998881dccc6f103f0781。
