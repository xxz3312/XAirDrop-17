# 统一收发会话首版

本轮把已有接收桥、Action 帧和 RAW DATA 发送串成前台会话入口，减少分别启动
多个中继和手动清理接口的步骤。它复用原生接口，不创建独立 NDI 固件会话；
Wonder 完整 NDI 后端初始化仍待接通。

## 新增功能

- `action-tx relay-all`：一个进程监听 Wonder 出站包。Action 帧进入 nl80211
  管理帧通道，Data/QoS Data 进入私有 RAW vendor 通道；每帧只选一个通道。
  接收帧、其他管理帧和不合格数据帧仍忽略。
- `popsicle-session.sh run`：检查原生 TX 频道、按需创建临时 monitor、启动
  Wonder RX，再运行中继。结束或中断时先停止中继，再释放本次创建的 RX 和
  monitor。原生 STA、stock mac80211 和原生 WLAN 驱动保持原状。
- `status`：显示会话记录、接收计数和最近的中继日志。Action/RAW 完成与失败
  分别计数；`completed` 是驱动完成结果，不是对端收到或 AirDrop 传输成功。

## 使用方式

目录中放置 `action-tx`、`wonder.ko`、`popsicle-rx-start.sh` 和
`popsicle-session.sh`。需要 root、iw/ip、匹配的 stock mac80211 已加载，原生
TX 接口已 UP 并工作在指定频道。默认只启用 Action TX；下面的 5180 仅为示例。

```sh
su
chmod 755 /data/local/tmp/xairdrop/action-tx
sh /data/local/tmp/xairdrop/popsicle-session.sh run \
  --bundle /data/local/tmp/xairdrop --tx wlan0 --freq 5180
```

默认 monitor 名为 `misharemon0`。不存在时，在 TX 接口所属原生 PHY 上创建，
开启并请求 HT20 频道。驱动若拒绝 monitor/并发/频道设置则返回原始错误，不
覆盖原生策略。退出时删除本次创建的 monitor。

可通过 `--monitor mon0` 借用已有 monitor。默认不改写它的频道；若驱动可回读
频道，必须与请求频率一致。需要显式配置已有 monitor 时加 `--configure-monitor`，
该设置在结束后保留，接口也保留。

目标驱动的 get_channel 只实现 STA/SAP 等模式，monitor 可能没有频道回读。
新建或显式配置的 monitor 可以依据 set-frequency 命令成功继续启动；日志以
`rx_channel_evidence=command_accepted` 标注，不能称作实际射频频道验证。有回读
结果时记录 `readback` 并核对频率；原生 STA 的 TX 频道始终要求回读匹配。

启用 Action + RAW DATA 统一中继：

```sh
sh /data/local/tmp/xairdrop/popsicle-session.sh run \
  --bundle /data/local/tmp/xairdrop --tx wlan0 --freq 5180 --raw
```

`--raw` 要求补丁后的 WLAN 已加载且 `mishare_raw_tx=1`，脚本在修改接口前检查。
默认模块名 `qca_cld3_peach_v2`，可用 `--wlan-module` 指定。该检查只确认开关，
不确认固件能力、peer 或帧能否发送。RAW 的非 MLO STA、同频道、已有 peer、
6 Mbps/20 MHz 等限制继续适用。

默认运行上限 300 秒、10000 次合格发送，可用 `--seconds` / `--max-frames` 调整。
Ctrl-C 停止前台会话并清理。若 RX 停止失败，保留 monitor 并报错，不强删父接口。
默认日志追加到目录中的 `session.log`，`--log` 可指定路径；`--lock` 可指定锁目录。

```sh
sh /data/local/tmp/xairdrop/popsicle-session.sh status \
  --bundle /data/local/tmp/xairdrop
```

`SESSION_START` 表示启动流程已发起；工具的 `relay_ready` 才表示监听器就绪。
当前不会自动产生帧，仍由已有发送端向 Wonder 注入正确帧。源地址默认要求与
原生 TX 接口一致，显式 `--rewrite-source` 才会改写，协议身份限制不变。

## 验证边界

主机命令模型覆盖临时/借用接口、RAW 准入、配置 monitor、启动失败清理、中断
停止顺序、RX 关闭失败保留父接口及会话锁。它没有执行手机上的 iw、驱动或
模块加载；实际启动、并发 monitor 支持、射频收发及稳定性仍待实测。
新 C 分派测试复用原 Action/RAW 验证规则。底层内核代码未改动，完整 WLAN
构建证据仍沿用 0036；本轮单独验证工具、模型、shell 语法和 Android 编译。


## 本轮构建

源提交 `8f4a8afa609a687f48c79746329507afe094fbe3`。
[Actions 40757236509](https://github.com/xxz3312/XAirDrop-17/actions/runs/40757236509)
已通过 13 项会话命令模型测试、统一帧分派/协议测试、既有 RAW 提交模型测试
及固定 NDK 的 Android API 31 arm64 编译；C 测试使用 ASan/UBSan。
产物包含新版 action-tx、两个启动脚本与构建记录，不包含 WLAN 或 Wonder .ko。
产物 ZIP 已独立校验大小、哈希，工具 ELF/二进制哈希及两个脚本与源码一致。
详见 [构建证据](research/popsicle-unified-session-build-pass.json)。

0038 新增可选 `--follow-channel`：运行中跟随原生 STA/P2P client 的 home channel，同步同 PHY monitor 和下一帧发送频率。借用 monitor 时须同时提供 `--configure-monitor`。默认固定频道不变；具体行为、限制和验证见 [频道跟随说明](POPSICLE-CHANNEL-FOLLOW.md)。
