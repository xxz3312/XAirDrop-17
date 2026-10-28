# 原生频道跟随首版（0038）

`action-tx` 的中继模式新增 `--follow-channel --monitor NAME`，持续读取原生 STA/P2P client 当前 home channel，把借用的原生 monitor 与下一次发送的频率同步过去。默认仍为固定频道。

统一会话启动示例（沿用已有收发 bundle）：

```sh
su
sh /data/local/tmp/xairdrop/popsicle-session.sh run \
  --bundle /data/local/tmp/xairdrop --tx wlan0 --freq 5180 \
  --follow-channel --seconds 300
```

`--freq` 仍是启动时检查值。启动后跟随 `wlan0` 的实际频道；脚本创建的 monitor 自动纳入跟随。若使用已经存在的 monitor，必须同时指定 `--configure-monitor`，表示允许整个会话修改该接口的频道；退出后保留借用接口及最后频道。需要 RAW DATA 时再加 `--raw`，驱动要求见 [RAW TX 说明](POPSICLE-RAW-TX-BRINGUP.md)。

直接启动工具：

```sh
./action-tx relay-all --listen wonder0 --dev wlan0 --freq 5180 \
  --follow-channel --monitor misharemon0 --seconds 300 --max-frames 10000
```

频道读取使用 nl80211 GET_INTERFACE，要求发送端是 STA/P2P client，接收端确为同一 PHY 的 monitor。每次循环检查频道，空闲时约每秒检查一次，发送前再次检查。检测到变化后，通过 SET_WIPHY 对 monitor 请求 HT20，再重读 STA，只有频道一致才发布新的发送频率。换频与 Action/RAW 提交在同一线程串行执行；帧数和时长限制跨换频累计。

换频后丢弃捕获队列中的旧帧，避免把排队帧继续发往新频道；单次最多清理 1024 帧，队列仍持续拥塞时停止。发送前发现换频时，也丢弃手中这帧。接口消失、类型/PHY 改变、STA 断连或频道未知、超出 2.4/5GHz 支持范围、设置拒绝，以及设置后 STA 再次换频，均停止本次中继并返回错误。统一会话脚本随后执行原有资源清理，不自动重发。

日志 `channel_synced` 的证据等级是 `command_accepted_sta_readback`：SET_WIPHY 收到本请求成功 ACK，且随后 STA 读回一致。目标驱动 monitor 没有完整 get_channel，因此不能据此宣称 monitor 固件频道或射频已经验证。`channel_summary` 记录同步次数、旧队列丢弃数和失败状态；`changes` 统计首次之后的同步操作，也包含发现 monitor 读回偏离后的重新同步。

本功能没有改变 STA 关联频道，也没有 AWDL 时间槽/序列调度、DBS/并发硬件模式预留或原子频道 lease。其他主体仍可能在最后检查之后换频；RAW 原生入口还会再次核对 home channel。工具等待一次 TX 完成期间不会响应频道变化；这是跟随现有 WLAN 的首版，不能作为微秒级 AWDL 跳频实现。固定频道模式保持原有行为。

功能提交：`2f95a88a8a2affd2dabe987fbfd39c2cb2e827d5`；测试时序修正及最终验证提交：`b32354789133462815de0d16fc1a6241301a9e2a`。离线构建和模型证据见 [验证报告](research/popsicle-channel-follow-build-pass.json)。手机运行与实际收发待验证。
