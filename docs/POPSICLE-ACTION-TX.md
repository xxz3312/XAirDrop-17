# Action 帧原生发送首版

这一版补上可运行的管理帧发送路径：Android arm64 工具 `action-tx` 使用标准
`NL80211_CMD_FRAME`，由当前原生 WLAN 驱动发送。无需替换 WLAN 内核模块，
不需要 Python 或额外运行库。原生接口必须已经 UP，并与指定频率处于同一频道。
驱动仍执行监管、接口状态及并发检查；本版不申请离频道发送或自动重试。

支持两种使用方式：

- `send`：发送一个已有的原始 802.11 Action 帧文件，可选移除 radiotap/FCS。
- `relay`：监听 `wonder0` 的 `PACKET_OUTGOING`，将其中 Action 帧交给原生接口。
  接收帧、数据帧和其他管理帧不转发。首版串行发送，一次只等一个 cookie。

只支持普通 24 字节 MAC 头、未保护、未分片的 Action 帧，总长最多 2304 字节。
真实 RAW 数据帧发送及完整 AWDL 会话仍待接入。

## 手机上使用

从试运行包取出 `action-tx`，放到 `/data/local/tmp/` 并赋予执行权限：

```sh
su
chmod 755 /data/local/tmp/action-tx
/data/local/tmp/action-tx --help
```

先让原生 `wlan0` 或 P2P 接口处于 UP 状态，确认它当前的工作频道。以下 `5180`
只是命令参数示例，必须替换为原生接口实际使用且设备允许的频率。

直接发送已有的 Action 帧文件（文件不含 radiotap）：

```sh
/data/local/tmp/action-tx send --dev wlan0 --freq 5180 \
    --frame /data/local/tmp/action-frame.bin
```

若文件含 radiotap，增加 `--radiotap`。帧的源地址默认必须等于原生接口 MAC。
默认不自动改写地址。显式传 `--rewrite-source` 才会替换 802.11 源地址；这会改变
协议身份，帧体中的地址/签名等不会自动更新，不应据此判断 AWDL 协议兼容。

使用上一版接收桥后，可以启动出站 Action 帧中继：

```sh
sh /data/local/tmp/popsicle-rx-start.sh start /data/local/tmp/wonder.ko mon0
/data/local/tmp/action-tx relay --listen wonder0 --dev wlan0 --freq 5180 \
    --max-frames 1 --seconds 30
```

随后由现有发送端向 `wonder0` 注入正确的 radiotap + Action 帧。中继只读出站包，
不生成测试帧、不重放收到的帧。Wonder 内核接收模式仍会丢弃原始 TX；中继另走
原生管理帧通道，因此不依赖 monitor 驱动提供 RAW TX。
如果两个接口源 MAC 不同，中继会记录 `source_mismatch`；只有明确接受上述身份
变化时再加 `--rewrite-source`。本模式没有向 mac80211 回写 TX status，真实结果
从工具输出观察，暂不能作为 mac80211 原生发送后端的替代。

首版默认只处理一次合格发送，适合确认路径；可按需增加 `--max-frames` 和
`--seconds`。Ctrl-C 停止中继，接收桥按原说明停止，原生 WLAN 接口保持原样。

## 结果含义

输出为 JSON 行：

- `submitted`：原生 nl80211 返回请求 cookie，仅表示提交，不是发射成功。
- `tx_status`：收到匹配原生接口、完整帧和 cookie 的真实完成事件。
  `acked=true` 表示驱动报告收到 ACK；`acked=false` 的单播按失败返回。
  广播/组播没有对端 ACK 保证，完成事件也不能证明 Apple 设备收到了帧。
- `tx_error` 或超时：保留 errno，不自动重发。驱动仅返回成功而未发出完成事件
  时会超时，不会被判为 TX 成功。
- `relay_summary`：完成、失败、忽略和源地址不匹配的数量。

主机测试检查属性编码、帧类型/源地址、radiotap/FCS、畸形消息，以及 ACK 不能
当完成、完成早于 cookie、错误 cookie/帧/接口不能匹配等协议行为。Android
构建检查只能确认可执行文件生成；手机执行、固件接受及实际发射尚待实测。


## 本轮构建

源提交 `7e53a21a5af27c22ebe6c91eab4ef956b3420116`。
[Actions 40749179035](https://github.com/xxz3312/XAirDrop-17/actions/runs/40749179035)
已通过主机协议测试（ASan/UBSan）和固定 NDK 27.2.12479018 的 Android API 31
arm64 构建。可执行文件 15456 字节，SHA-256：
`dbfa772b05bc4ae580bfb41a755e3e212b8eaa2f2fef9c443dd09da2a935ac50`。
产物 ZIP 已独立下载并核对大小/哈希，ELF 架构和可执行文件哈希匹配报告。
本轮未重编内核，接收模块按原校验和复用 0034。
详见 [构建证据](research/popsicle-native-action-tx-build-pass.json)。
