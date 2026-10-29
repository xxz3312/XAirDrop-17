# 独立原生 vendor Action 发送入口（0045）

## 起点

0044 实机验证：49-byte Public Action 经 Wonder 原始队列、原生 STA 发送和 token 完成回传，completed=1、reported=1、failed=0、rejected=0。原生 LPC → Wonder → 用户态 RX 也已通过抓包确认。以上不证明指定对端收到或 Apple 互传。

AWDL 使用的 vendor-specific Action category 127 不能直接复用普通 STA 的标准管理帧广播发送条件。0045 实现独立、默认关闭的原生 vendor 请求入口，将此类帧交给目标 WLAN 的 WMI MGMT 发送路径并等待原生完成回调。这是当前已连接 STA 同频道下的最小原生入口，不是独立 NDI/AWDL 后端的完成认证。

## 实现

- 新工具命令 `vendor-action-send --dev wlan0 --freq MHz --frame FILE [--radiotap] [--rewrite-source]`，不自动回退、不自动重发、不改变频道。普通 send/relay/relay-all 仍保留原传输选择，不自动转入此路径。
- 复用私有 OUI 0x001a11 / subcmd 0x1701 / version 1 / 16-byte 头。请求偏移 12 的 u32 现在是 kind：0 仍为原 RAW DATA，1 为 vendor Action，其他值拒绝。旧驱动会拒绝 kind=1，工具不能凭空提供驱动能力。
- 新驱动只读加载参数 `mishare_action_tx` 默认 false，独立于 `mishare_raw_tx`。开启 RAW DATA 不会开启 Action；开启 Action 也不会开启 RAW DATA。
- 仅接收至少含 category 和三字节 OUI 的 category 127 Action（28..2304 bytes），无 DS、分片、Protected 或 HTC 标志。地址与报文体不自动转换；只有显式 rewrite-source 才改 SA。
- 保留 CAP_NET_ADMIN、HDD/vdev 同步、上下文有效性、非 MLO STA、vdev active、当前频道 2400..5900 MHz 与 SA 匹配检查。只使用已有同 vdev 的 DA peer 或 self peer，不创建 peer、不配置 NDI、不切换硬件模式。
- WMI tx_send_params 使用 MGMT=0（RAW DATA 保留 DATA=1），6 Mbps / 20 MHz / retry_limit=1。由 wlan_mgmt_txrx_mgmt_frame_tx 持有原生发送资源，使用既有完成回调；同步等待 1 秒，超时后等待者释放自身引用，原生回调仍持有其引用，禁止超时后主动释放原生 packet 或重发。
- 只在实际收到完成回调后返回 native_status。工具输出 vendor_action_tx_status，status=0 表示原生完成报告，不能当作单播 ACK、指定 Apple 接收端收到或 RF 认证。

## 验证范围

源码提交：d8365331d8920786fcdb345a31679347d7903273。
快速工具构建：40841130477，成功；生产 WMA 代码的 host 模型覆盖独立开关、MGMT 类型、错误类别、截断、分片/保护帧、源地址/频道/MLO 检查和超时后的延迟完成释放。保留原 RAW DATA 模型与 Action/反馈协议回归。
完整 WLAN 构建：40841130362 / job 123337497774，成功。新增严格符号检查要求 mishare_action_tx_sync 确实存在于链接后的目标 WLAN。

现有手机只安装了 stock WLAN 和 0042 Wonder；新工具不能在这个环境中启用新后端。没有在手机替换或卸载 WLAN，也没有执行 vendor Action 无线发送。完整构建成功仍不代表已通过加载、固件接受、完整 ABI/KCFI 或 AWDL 实测。

## 下一步实机准备

下一步先定位当前 WLAN 模块文件、启动加载配置、依赖和启动槽，再准备可回退的启动测试方案。不要在使用中的系统直接 rmmod qca_cld3_peach_v2，不使用强制加载，不覆盖系统模块，也不要将诊断包中的整套内核模块直接安装。

在准备好并实际加载带 mishare_action_tx=1 的匹配驱动后，才运行一次以下实验命令（这是后续步骤，当前 stock 驱动不适用）：

```sh
./action-tx vendor-action-send --dev wlan0 --freq CURRENT_MHZ --frame action-smoke.bin --rewrite-source
```

action-smoke.bin 是实验 category 127 帧，不是 AWDL 协议帧。AWDL 本体、双向 DATA、独立地址/接口、频道时间槽和 Apple 发现/文件互传仍需后续接入验证。

## 构建证据与预检

最终 WLAN 的 86 个必需符号均存在（含 mishare_action_tx_sync），575 条导入版本记录没有已记录不匹配/缺失；选取的 7 个结构布局检查 MATCH。报告记录 WLAN SHA256 为 1c998d320351a37f54fca2e0b93808db7b8d73ea05c108df8b93b046936a0567。Wonder SHA256 与 0042 相同，不需要为本入口重建 Wonder。这些是构建报告，不是完整 ABI 或实机加载认证。

只读预检脚本位于 tools/device/popsicle-wlan-preflight.sh。下载到手机 Download 后执行：

```sh
su
sh /sdcard/Download/popsicle-wlan-preflight.sh > /sdcard/Download/wlan-preflight-0045.txt 2>&1
```

回传 wlan-preflight-0045.txt 后再确定可回退的驱动加载方案。脚本不卸载/安装模块，不更改 Wi-Fi、频道、分区或系统设置。
