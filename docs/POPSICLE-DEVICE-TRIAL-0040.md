# 首轮手机测试包 0040

这是手动试运行包，不是 Magisk/KernelSU 自动安装模块。首轮不替换原生 WLAN，不自动卸载 mac80211，不自动运行 RAW DATA，也不修改 STA 关联频道。本包包含最新 Wonder、Android arm64 action-tx、会话/RX 脚本、测试帧、许可及对应项目源码。

尚未在手机执行。目标是先确认模块加载、真实收包、Action 原生完成和 token 回写；不能据此期待 Apple 发现或传文件。以项目锁定的 popsicle 内核/stock mac80211 为基线，不同系统版本尚未验证。模块加载若拒绝，保存原始错误和 dmesg，不使用强制加载。

## 1. 准备

在电脑解压后推送整个目录（也可自行复制到手机）：

```sh
adb push XAirDrop-17-Device-Trial-0040 /data/local/tmp/xairdrop-0040
adb shell
su
cd /data/local/tmp/xairdrop-0040
sha256sum -c SHA256SUMS
chmod 755 action-tx
./action-tx --help
command -v iw
command -v ip
uname -a
getprop ro.build.fingerprint
iw dev
iw dev wlan0 info
```

需要 root、`iw`、`ip`、匹配的 stock mac80211。`iw`/`tcpdump` 没有随包提供；缺少 iw 时先停止，不会自动下载工具。维持 WLAN 正常连接，确认 wlan0 是有当前频道的原生接口；如果实际接口名不同，替换后续 wlan0。

若 stock mac80211 尚未加载，先确认手机有匹配文件；常见位置仅作示例：

```sh
[ -d /sys/module/mac80211 ] || insmod /vendor_dlkm/lib/modules/mac80211.ko
```

文件不存在、加载报错或 `iw dev wlan0 info` 没有频道时停止，保留日志。不要卸载正在使用的 WLAN。选择下面 `FREQ` 时，填上一步读到的 MHz，而不是随意指定频道。以 5180 MHz 为例：

```sh
FREQ=5180
```

## 2. 先验证加载与接收

终端 A 保持前台运行：

```sh
sh popsicle-session.sh run --bundle "$PWD" --tx wlan0 --freq "$FREQ" \
  --seconds 60 --max-frames 10 --log "$PWD/rx-session.log"
```

脚本会按需创建 `misharemon0`，启动 Wonder 的 RX-only 桥和 Action 副本监听。默认不产生测试帧。原生驱动若拒绝创建 monitor 或配置频道，保存错误；不要继续执行下一阶段。

在 60 秒内，终端 B 进入相同目录、取得 root：

```sh
cd /data/local/tmp/xairdrop-0040
sh popsicle-rx-start.sh status > rx-status.txt 2>&1
cat rx-status.txt
iw dev > iw-dev.txt
```

成功分两层：`RX bridge ready` 只表示启动完成；`opairshare_wonder_rx` 增长、wonder0 RX 计数或真实抓包才表示收到了帧。若已有 tcpdump，可在会话运行时抓取：

```sh
tcpdump -i wonder0 -c 20 -s 0 -w wonder-rx.pcap
```

60 秒到期会自动清理本次创建的 Wonder/monitor。没有出站 Action 帧时，中继可能以 ENODATA/超时结束；这本身不是 RX 收包失败，结合运行中的 RX 计数判断。Ctrl-C 也会执行清理。借用已有 monitor 时，保留该接口；脚本不会删除它。

## 3. 单独测原生 Action 发送（可选）

先确认前一会话已经结束，FREQ 仍与 wlan0 当前频道一致：

```sh
./action-tx send --dev wlan0 --freq "$FREQ" --frame action-smoke.bin \
  --rewrite-source > native-action.log 2>&1
cat native-action.log
```

这会明确尝试发送一帧广播 vendor-specific Action，内容是实验标记 `XAIRDROP0040_TEST`，不是 AWDL 报文；SA 从占位值改成原生接口 MAC。`submitted` cookie 只表示提交；还需要 `tx_status` 才有原生完成事件。广播没有对端 ACK 保证，需要另一设备抓包才可确认空口接收。

## 4. 验证原始 skb/token 完成桥

先确认没有其他 Wonder 会话。终端 A：

```sh
sh popsicle-session.sh run --bundle "$PWD" --tx wlan0 --freq "$FREQ" \
  --tx-feedback --rewrite-source --seconds 120 --max-frames 1 \
  --log "$PWD/feedback-session.log"
```

终端 B，确认此次日志出现 `relay_ready`、mode 为 `token_feedback`，再运行：

```sh
cd /data/local/tmp/xairdrop-0040
tail -n 20 feedback-session.log
./action-tx inject --dev wonder0 --frame action-smoke.bin --rewrite-source
```

`inject` 只接受 Action 帧，检查目标是 Wonder PHY 的 UP radiotap 接口；它把带最小 radiotap 的帧交给 Wonder，不直接向原生 monitor 发包。这里使用显式源地址转换来测试链路，不能据此保证 AWDL 身份兼容。

`injected_into_wonder` 只证明向虚拟接口的提交成功，不表示已经进入驱动队列或已发射。终端 A 预期在消费一帧后退出并清理；查看：

```sh
cat feedback-session.log
```

判断顺序：

1. `relay_ready`：用户态已成功领取队列。
2. `submitted` 后有 `tx_status`：收到原生 Action 完成事件。
3. `feedback_summary` 的 `completed=1`、`reported=1` 且无失败：原生完成并且 token 完成请求被内核接受。
4. 这仍是广播完成；不能证明 Apple 收到，更不能证明 AirDrop 已可用。失败/超时要保存完整日志。

若有其他程序同时向 Wonder 发帧，max-frames=1 可能先消费其他帧；首测请保持单一发包源。RAW DATA 本包不启用；它需要额外 patched WLAN 和独立实测，本包未附 WLAN 替换模块。

## 5. 停止与回传日志

优先在终端 A Ctrl-C，等待脚本退出。脚本先停止/等待中继，再关闭 RX，最后删除自己创建的 monitor。若进程已经结束但 Wonder 遗留，先确认无中继进程仍在用它，再执行：

```sh
sh popsicle-rx-start.sh stop
```

该 stop 不删除原生 monitor、不卸载 stock mac80211。只对确定由这次测试创建的原生 monitor 做后续删除，不要删除原有接口。RX stop 失败时脚本会保留 monitor，先收集日志。

```sh
dmesg > device-dmesg.txt
uname -a > device-info.txt
getprop ro.build.fingerprint >> device-info.txt
iw dev >> device-info.txt
ip link show >> device-info.txt
```

请回传 `device-info.txt`、`device-dmesg.txt`、`rx-status.txt`、`rx-session.log`，若做了发送测试再加 `native-action.log`、`feedback-session.log` 和可用的 pcap。没有实际执行的项目标为未测即可。

## 构建来源

Wonder 内核验证：188246a0008a986741379b105fcfde92d64b8d88 / Actions 40768050808。工具及注入入口：0ff3a33c8b25f48d6b8b0918fbd128c6c068648e / Actions 40822824724。

完整 WLAN/Wonder 编译和严格链接、44 项 Python 检查、26 组原生 fixture，以及 16 项会话测试、协议/频道/队列/RAW 模型和 Android 编译通过。这些是离线证据，不构成完整 ABI/KCFI、手机加载或固件运行认证。详细版本与 SHA-256 见 BUILD.json，文件校验见 SHA256SUMS。

`source.tar.gz` 附对应项目源码、补丁和构建流程；外部锁定内核/驱动输入见源码中的 docs/popsicle-source-lock.json。源地址：https://github.com/xxz3312/XAirDrop-17/tree/0ff3a33c8b25f48d6b8b0918fbd128c6c068648e
