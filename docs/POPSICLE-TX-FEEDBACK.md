# 原始帧 TX 完成回写（0039）

新增可选的 Wonder → 用户态 → 原生 TX → mac80211 完成桥。Wonder 在 `.tx` 中保存原始 skb，用户态通过独立 token 取帧；原生发送完成后，工具把结果回写到对应 token，内核只对该原始 skb 报告一次完成。旧 PF_PACKET 中继仍可用，默认接收模式保持 RX-only。

启动方式（使用本阶段新 Wonder 模块和新工具，沿用统一会话 bundle 布局）：

```sh
su
sh /data/local/tmp/xairdrop/popsicle-session.sh run \
  --bundle /data/local/tmp/xairdrop --tx wlan0 --freq 5180 \
  --tx-feedback --seconds 300
```

可加 `--raw` 使用 Action/RAW DATA 统一分派；RAW 仍需 patched WLAN 已加载 `mishare_raw_tx=1`。可同时加 `--follow-channel`，跟随当前 home channel。创建的 monitor 由本次会话清理；借用 monitor 时跟随频道仍需 `--configure-monitor`。

手动接收桥入口新增可选第四个参数：

```sh
sh popsicle-rx-start.sh start ./wonder.ko misharemon0 tx-feedback
./action-tx relay-all --listen wonder0 --dev wlan0 --freq 5180 \
  --feedback --seconds 300 --max-frames 10000
```

`tx-feedback` 对应 `insmod wonder.ko external_monitor=1 external_tx=1 ...`。`external_tx` 默认为 false，且只能用于 external monitor 模式。旧 0034/0035 试运行包内的 Wonder 模块没有该入口，不能只替换工具后使用本功能。本阶段没有自动更换或卸载手机原生 WLAN。

源地址策略沿用现有工具：802.11 SA 必须等于原生发送接口 MAC，否则计入 rejected 并按失败完成。需要转换时可显式加 `--rewrite-source`；它改变协议身份，且不会重写帧体内地址，不能据此保证 AWDL 互通。

## 完成证据

| 原生结果 | mac80211 回写 |
| --- | --- |
| Action 完成事件，确切 cookie/接口/帧匹配且带 ACK | 单播且原始帧未要求 NO_ACK 时设置 ACK |
| Action 组播完成、RAW native_status=0 | 仅原始组播/NO_ACK 帧设置 NOACK_TRANSMITTED；不推断单播 peer ACK |
| 拒绝的帧、源地址不匹配、提交失败、完成超时、非零原生状态 | 不设置成功标记，按失败完成 |
| 队列满、没有中继 owner、队列超时、停机或 owner 退出 | 按失败释放原始 skb |

不会伪造信号强度、重试次数或速率。RAW 单播即使 native_status=0，也缺少明确 peer ACK 证据，因此原始单播 skb 不会被标记 ACK；工具的 `completed` 统计表示原生完成，不能解读为对端确认收到。

## 队列和资源

队列最多 64 帧，每帧最多 2304 字节，待发及已交付帧总超时为 15 秒，周期检查约 250ms。用户态一次只提交一帧原生 TX；内核完成桥不主动重试。取帧回复失败或丢失也不会自动重新交付，避免重复发送。

PULL 首次绑定一个随机 owner，其他 owner 返回 busy；空队列轮询也更新心跳。owner 30 秒无心跳后由周期工作撤销，并按失败清理残留。正常退出发送 RELEASE；统一会话先停止/等待中继，再关闭 RX 和删除自己创建的 monitor。硬件 stop、原生 monitor detach 和模块退出也会停止队列，释放 skb，并在释放私有内存前取消周期工作。此可选模式的 RX 与 TX status 都通过 mac80211 IRQ-safe tasklet 处理；默认 RX-only 和 full backend 路径不变。

token 在模块实例内递增，接口 down/up 不重置；计数耗尽后拒绝新帧，避免复用。起始 token 与用户态 owner 使用随机数，跨模块重载依赖随机隔离，不是形式化的跨重载持久身份。完成必须同时匹配当前 owner、已交付的 token；过早、重复、未知、已超时或其他 owner 的完成被拒绝。

工具先通过 PULL 验证 Wonder 端点并领取 owner，再设置 Wonder 自身的软件频道；同一频道变化还会同步该软件频道，避免虚拟 mac80211 仍以旧频道处理注入。设置失败停止中继，不宣称固件频道已验证。

频道跟随检测到变化时，把未完成的队列按失败清空后重新领取；发送前检测到变化时，当前已取帧也按失败完成。`feedback_summary` 记录原生完成、失败、验证拒绝、已回写数量和频道清队列次数。帧数上限在本模式按已消费的完成/失败/拒绝累计。

## 范围与限制

该模式接通实验性外部 monitor 收发路径的真实完成关联，未接通独立 NDI 后端初始化。默认 full backend 的旧 synthetic TX status 路径没有在本阶段更改。

队列失败不表示帧一定未上空口：超时或设备 down 时，原生发送可能已经在途；本桥不取消已提交的原生固件命令。频道检查也不构成原子频道 lease、AWDL 时间槽调度或 DBS 资源预留。需要手机验证 monitor 注入是否进入 `.tx`、实际射频、固件 RAW 接受、ACK 与 Apple 互通。

内核功能提交：`218a67c2e451172268acc9657b6b141f4fb8c769`；工具频道同步修正提交：`3ad9761afc5f8287c7f0fa6b3f09a3840a3cb594`；最终内核验证提交：`188246a0008a986741379b105fcfde92d64b8d88`；最终工具验证提交：`1a1166b8816b151f36a4f6a7b464e70e1a43dc53`。验证报告见 [构建与模型证据](research/popsicle-tx-feedback-build-pass.json)。
