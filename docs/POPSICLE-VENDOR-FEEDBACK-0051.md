# 0051：Wonder → vendor Action → token 完成回写

新增显式 `vendor-action-relay --feedback` 模式，仅接受 category 127 vendor Action。使用与 0050 直发相同的原生接口，收到 native_status=0 后回写 WONDER_FB_NOACK=1；错误、超时和无效帧回写 FAILED。不会根据广播完成推断对端 ACK，不自动重发或切换到其他发送路径。旧 send/relay/relay-all 的选择保持原样。仅支持当前 STA 频道，未实现完整 AWDL 跳频或 Apple 互传。

CI 40890855957 已通过 ASan/UBSan 协议回归、原生 RAW 模型与 Android arm64 构建。新回归覆盖 vendor 路由、Public/DATA/保护/分片帧拒绝、来源重写、超时/错误回写和 token NOACK 编码。完整真实内核/固件闭环仍待本轮手机测试。

本包包含新工具、RX helper、Wonder、实验广播帧和源码许可；沿用已实机启动通过的 0049 WLAN，不需重新下载 WLAN。Wonder SHA256 为 8e1d629cfe2a32f552d0190dac09912fb68c4756268ab53f18d0b3bb3f6532ea，与 0042 实机验证的模块一致，从 0049 CI 40861769292 提取。

## 1. 准备并启动 0049 WLAN（root 本地终端）

解压本包到 Download，然后：

```sh
cp -R /sdcard/Download/XAirDrop-17-Vendor-Feedback-0051 /data/local/tmp/xairdrop-0051
cd /data/local/tmp/xairdrop-0051
sha256sum -c SHA256SUMS
chmod 755 action-tx-0051
cd /data/local/tmp/xairdrop-0049
sh popsicle-wlan-trial.sh run "$PWD" > /data/local/tmp/xairdrop-0051/trial-0051.txt 2>&1
cat /data/local/tmp/xairdrop-0051/trial-0051.txt
```

先确认 TRIAL_DRIVER_ACTIVE 且 Wi-Fi 已连接。若实验 WLAN 已启动，不重复 run；可用 0049 的 status 与 iw dev wlan0 link 检查。若 run 失败或 RESTORE_FAILED，按输出恢复/重启，不继续。

## 2. 终端一：准备 Wonder 并等待一帧

此轮验证发送 token 闭环，monitor 用于 Wonder 绑定。以下只创建本次测试的 misharemon0；若已有同名接口或 Wonder 会话，先结束原会话，不接管未知接口。

```sh
cd /data/local/tmp/xairdrop-0051
(
  set -e
  [ "$(cat /sys/module/qca_cld3_peach_v2/parameters/mishare_action_tx)" = Y ]
  [ ! -d /sys/module/wonder ]
  [ ! -e /sys/class/net/misharemon0 ]
  FREQ="$(iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}')"
  [ -n "$FREQ" ]
  PHY="phy$(iw dev wlan0 info | awk '$1=="wiphy"{print $2; exit}')"
  [ "$PHY" != phy ]
  if [ -e /sys/class/net/p2p0 ]; then ip link set p2p0 down; fi
  iw phy "$PHY" interface add misharemon0 type monitor
  ip link set misharemon0 up
  sh popsicle-rx-start.sh start "$PWD/wonder.ko" misharemon0 tx-feedback
) > setup-0051.txt 2>&1
cat setup-0051.txt
```

只有出现 RX bridge ready 才继续。若创建 monitor 后启动失败，按第 4 步清理本次已创建的资源。

```sh
FREQ="$(iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}')"
./action-tx-0051 vendor-action-relay --listen wonder0 --dev wlan0 --freq "$FREQ" \
  --feedback --rewrite-source --max-frames 1 --seconds 120 --timeout-ms 10000 \
  > feedback-0051.log 2>&1
cat feedback-0051.log
```

上面命令会等待。终端二可先用 cat feedback-0051.log 查看；确认 relay_ready 且 transport=vendor_action 后再注入。

## 3. 终端二：注入一次实验帧

```sh
cd /data/local/tmp/xairdrop-0051
cat feedback-0051.log
./action-tx-0051 inject --dev wonder0 --frame action-vendor.bin --rewrite-source > inject-0051.txt 2>&1
cat inject-0051.txt
```

帧为广播 category 127 / OUI 02:00:00 / XAIRDROP0051_TEST，不是 Apple AWDL。两处 rewrite-source 均显式开启，仅为实验桥接；正式协议身份仍需后续接入。等待终端一结束，再查看 feedback-0051.log。

预期 vendor_action_tx_status 的 native_status=0、feedback_complete 的 outcome=1，以及 feedback_summary completed=1、reported=1、failed=0。outcome=1 是 NOACK，不是对端 ACK。独立空口/Apple 收包尚未验证。若没有注入或发生错误，等待有界退出或在终端一 Ctrl+C 后再清理，不重复注入同一轮。

## 4. 清理和恢复原驱动

先确认终端一已经退出；若第 2 步成功加载 Wonder，执行 stop。只删除本次测试创建的 misharemon0。

```sh
cd /data/local/tmp/xairdrop-0051
sh popsicle-rx-start.sh stop > stop-0051.txt 2>&1
cat stop-0051.txt
ip link set misharemon0 down && iw dev misharemon0 del
cd /data/local/tmp/xairdrop-0049
sh popsicle-wlan-trial.sh restore "$PWD" > /data/local/tmp/xairdrop-0051/restore-0051.txt 2>&1
cat /data/local/tmp/xairdrop-0051/restore-0051.txt
cd /data/local/tmp/xairdrop-0051
dmesg > dmesg-0051.txt
cp trial-0051.txt setup-0051.txt feedback-0051.log inject-0051.txt stop-0051.txt restore-0051.txt dmesg-0051.txt /sdcard/Download/
```

restore 失败时重启恢复原厂驱动；不强制卸载，不覆盖系统模块。
