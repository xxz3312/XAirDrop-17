# 原生 monitor 接收模式

本阶段优先让 Wonder 从“有模块但 init 不支持”进入可启动、可真实收包的状态。
新增 `external_monitor=1`：借用已经由原生 WLAN 驱动启动的 radiotap monitor，
创建 Wonder monitor 接口，将真实 RX 转发给抓包程序。此模式不依赖 Wonder
provider，也不创建新的 PAS/NDI 固件会话。原生驱动负责频道与监管限制。

实现了启动/停止、原生接口停机时解除 RX 绑定、软件 type/subtype 帧过滤、
RX 计数和启动脚本。该模式只支持 monitor，发送包会丢弃并计数，不报告发送成功。
动态频率、固定速率与速率 mask 命令返回不支持；请在原生 monitor 上配置频道。
默认模式及完整 WLAN 后端不变。

## 手机上运行

需要 root、`ip`、`iw`、与当前内核匹配的 stock `mac80211.ko` 和本轮构建的
`wonder.ko`。当前会话无法直接操作手机；以下步骤尚待实机执行。
保留原生 WLAN 驱动，先加载匹配的 stock mac80211（已加载则跳过）：

```sh
su
insmod /vendor_dlkm/lib/modules/mac80211.ko
```

先用原生 WLAN 的 PHY 创建 monitor。下面的 `phy0` 必须替换为 `iw dev` 显示
的原生 PHY；不要选 Wonder PHY。驱动若拒绝 monitor/并发，保存原始错误，
本模式不会绕过驱动策略。

```sh
iw dev
iw phy phy0 interface add mon0 type monitor
ip link set mon0 up
iw dev mon0 set freq 5180 HT20
```

频率按所在地法规和设备支持调整；也可以直接使用已经可收包的原生 monitor。
先确认原生 RX，再启动桥接：

```sh
tcpdump -i mon0 -c 10 -s 0
sh /data/local/tmp/popsicle-rx-start.sh start /data/local/tmp/wonder.ko mon0
sh /data/local/tmp/popsicle-rx-start.sh status
tcpdump -i wonder0 -s 0 -w /data/local/tmp/wonder-rx.pcap
```

`RX bridge ready` 表示接口成功启动，不表示已有帧到达。观察
`opairshare_wonder_rx` 增长及 pcap 中的真实 radiotap/802.11 帧。
脚本不会加载替换 WLAN 模块，不会卸载 stock mac80211，也不修改借用的 monitor。

停止时先结束抓包，再关闭桥接，然后按需删除本次自己创建的原生 monitor：

```sh
sh /data/local/tmp/popsicle-rx-start.sh stop
ip link set mon0 down
iw dev mon0 del
```

原生 monitor 被关闭/删除时，桥接会解除 RX 绑定并释放引用；原生 RX 恢复后需
把 Wonder 接口 down/up 重启。不能把接收模式当作 AWDL 发现、RAW TX 或双向传输
已经实现；下一项功能是接通实际发送，再接频道控制与会话联调。


## 本轮构建

源提交：`dd85ef8fa566aea4998c57f01f7f80e20e8047ba`。
[Actions 40743774260](https://github.com/xxz3312/XAirDrop-17/actions/runs/40743774260)
已通过 44 项 Python 检查、26 组既有原生回归、完整编译、CNSS 接口、严格链接
及选定布局检查。新接收模式完成编译链接，尚未在原生 fixture 或手机执行。

手动试运行包 `XAirDrop-17-RX-only-0034.zip` 只包含 `wonder.ko`、启动脚本、
README、构建信息和 SHA256SUMS。模块 SHA-256：
`8cd248a74c707fbca8a36bbb714bb9404654710056475073040392ce7bb9866b`。
包 SHA-256：`dd577f28b05ad8e708bb4148effc16f1a64ae5deacbf8fa561b956299f9ce29b`。
模块由诊断构建提取，仅供手动试运行；不是自动安装包。原始诊断 ZIP 和紧凑
报告均已独立下载并核对大小与哈希，提取的模块哈希匹配 CI 报告。
Wonder 的 88 条版本记录无不匹配、无缺失版本符号；它们不能替代手机加载与
收包验证。首轮控制帧常量拼写错误已修正后重新完成本轮验证。
详见 [构建证据](research/popsicle-external-monitor-rx-build-pass.json)。
