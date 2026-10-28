# 原生 WMI RAW DATA 发送首版

本阶段新增真正的 RAW 数据帧驱动入口与 `raw-send` / `raw-relay` 工具模式。
目标 DP 的 bank 配置要求封装类型与 VDEV 一致，不能给普通 STA 临时覆盖 RAW
metadata。本实现复用原生 mgmt_txrx/WMI descriptor 通道，明确选择 DATA=1，
不改普通 STA 的 DP 封装、不修改其 peer、不创建新的固件会话。

## 实现范围

- 已运行的非 MLO STA VDEV，同频道发送，源地址必须等于该 VDEV MAC。
- 借用已有目的 peer，或同 VDEV 的 self peer；不存在则返回 ENOTCONN，不创建或
  接管其他接口 peer。
- 原始 Data / QoS Data，DS=0 或 ToDS；未保护、未分片，普通 24/26 字节头。
  QoS 限 TID 0..7；不支持 A-MSDU、其他 ACK policy 或 HTC。总长最多 2304 字节。
- 固定 6 Mbps、20 MHz、retry_limit=1，使用原生 rate encoder 与 WMI DATA 参数。
- 原生框架拥有成功提交的 descriptor、peer 引用和包；等待者与回调分别持有
  context 引用。1 秒内未完成返回超时，包仍由原生框架保留到回调，不重发或强制释放。
- 只有实际原生完成回调到达后，vendor 请求才返回 `native_status`。

这接通了 RAW 提交/完成路径，不代表 Apple 已接收、AWDL 身份/加密/数据协议
兼容，也不表示普通 STA 已成为可任意跳频的 AWDL VDEV。完整 NDI 初始化、
频道/DBS 协调和 mac80211 TX status 回写仍待完成。

## 启用条件

**上一版接收试运行包里的 stock WLAN 不具备本入口。** 需要本轮补丁后的 WLAN
驱动，并在该驱动加载时设置只读参数 `mishare_raw_tx=1`。默认 false；旧驱动或
未启用参数返回 EOPNOTSUPP。本轮不提供自动替换 WLAN 的安装脚本。

私有 vendor 请求使用 ID `0x001a11`、subcmd `0x1701`，仅作为本移植的实验协议，
不是标准 RAW 注入 API。命令需要 NET_ADMIN，原生接口必须已经 UP；HDD 保持
vdev sync operation 和对象引用，WMA 重查同实例、UP、非 MLO、源地址与当前频率。

现有 Android `action-tx` 增加两个模式：

```sh
# raw-data.bin 为正确的原始 802.11 数据帧；含 radiotap 时另加 --radiotap
/data/local/tmp/action-tx raw-send --dev wlan0 --freq 5180 \
    --frame /data/local/tmp/raw-data.bin

# 只中继从 Wonder 注入的出站数据帧；Action 帧仍由 relay 模式处理
/data/local/tmp/action-tx raw-relay --listen wonder0 --dev wlan0 --freq 5180 \
    --max-frames 1 --seconds 30
```

5180 必须替换为原生 STA 当前实际使用的频率。默认不改写源地址；显式
`--rewrite-source` 只改 MAC 头，不更新帧体中的 AWDL 地址/身份，不构成协议兼容。
工具不会把数据帧送到 NL80211_CMD_FRAME，也不会回退成普通 Ethernet 发送。

`raw_tx_status` 表示观察到原生完成，`native_status` 原样保留；非零按失败返回。
超时、没有 peer、MLO/频道/地址不匹配或驱动不支持都会返回错误，没有成功回执。
主机模型验证不运行真实 WMI/FW；手机驱动加载、WMI DATA 接受、实际发射及对端
解析仍需后续实测。原生 SSR/drain 和卸载寿命按原生框架合同使用，未认证实机稳定性。


## 本轮验证

源提交 `57184ea2203dfa05ab33c3c7171a2ade31675e2d`。
[完整 WLAN Actions 40752944098](https://github.com/xxz3312/XAirDrop-17/actions/runs/40752944098)
通过 44 项 Python 检查、26 组既有原生 fixture、完整编译、CNSS 接口、严格链接
及 7 项选定布局；85 个要求符号（含 mishare_raw_tx_sync）存在，575 条版本记录
无不匹配、无缺失版本符号、未解决依赖为空。
[工具 Actions 40752944311](https://github.com/xxz3312/XAirDrop-17/actions/runs/40752944311)
通过 Action/RAW 协议检查、生产 WMA wrapper 模型（ASan/UBSan）和 Android arm64
编译。WMI 传输、peer、分配与完成原语在新测试中为模型，未执行真实固件路径。

紧凑报告 ZIP 与工具 ZIP 均已独立核对大小和哈希，Android 工具二进制 16992 字节，
SHA-256 `e46a3664676d5019fe695c32709ee9ed468c98fa7a3037aed4ffbf1954429b39`。
完整诊断大包未独立下载，仅记录 GitHub 哈希，未认证为可安装驱动。
详见 [构建证据](research/popsicle-native-raw-tx-build-pass.json)。
