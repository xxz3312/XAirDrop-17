# LPC 捕获请求格式修正（0041）

实机已确认 0040 的 Wonder 能加载、注册 PHY 并绑定原生 monitor RX handler，但没有收到帧。已观察到两类不同问题：

- `iw dev misharemon0 set freq ... HT20` 在 STA 活动时返回 EBUSY。标准 cfg80211 monitor 换频入口要求当前只有 monitor；不应把它误判成单纯 160MHz 不支持，也不应在本阶段强制换频。
- 显式 QCA 捕获配置返回 `kernel reports: expected nested data`。此时 SET 请求被 nl80211 参数校验拒绝，尚未进入驱动捕获配置。`iw vendor send` 的 raw 数据缺少外层 VENDOR_DATA 的 NLA_F_NESTED 标志，在二进制文件里面再套一层属性不能替代这个外层标志。

0041 只更新 Android 工具，不更换 Wonder/WLAN/mac80211，也不改系统策略。新增：

```sh
./action-tx capture-status --dev wlan0
./action-tx capture-start --dev misharemon0
./action-tx capture-status --dev wlan0 --require-running
```

`capture-start` 检查目标已 UP、类型为 monitor，先查询是否已有捕获；已有捕获时返回 EALREADY，不覆盖配置。配置使用 QCA OUI 0x001374 / 子命令 202，外层 VENDOR_DATA 正确标记 NLA_F_NESTED，内部仅包含 DATA_RX_FRAME_TYPE_ALL=1 和 MGMT_RX_FRAME_TYPE_ALL=1，使用默认 LPC 类型。它不发送无线帧、不设置频道。默认 LPC 关注当前客户端/BSS 的本地捕获，不等于全频道监听或 AWDL 接收。驱动仍会执行其并发/模式/固件检查，不能保证一定接受。

GET 使用子命令 225，按 RAW_DATA 策略保持未嵌套；解析属性 1 的 u32 状态 0/1。默认 capture-status 查询成功即返回 0，配合 --require-running 则要求状态为 1。capture-start 仅在配置 ACK 和随后 running=true 均成功时返回 0；这仍不是实际收包证明。

## 更新工具

将 XAirDrop-17-LPC-Fix-0041.zip 解压到 Download，保持旧 0040 工作目录。在 root 终端：

```sh
cp /sdcard/Download/XAirDrop-17-LPC-Fix-0041/action-tx /data/local/tmp/xairdrop-0040/action-tx-lpc
chmod 755 /data/local/tmp/xairdrop-0040/action-tx-lpc
cd /data/local/tmp/xairdrop-0040
./action-tx-lpc --help
```

采用新文件名，不覆盖原 0040 工具，因此原 SHA256SUMS 中旧文件校验仍有效。补丁包自身提供 SHA256SUMS。

## 复用当前测试 monitor

先确认 `iw dev misharemon0 info` 能找到原生 monitor；不要重复创建同名接口。若已删除它，先停止本段测试并告知接口状态。保持 Wi-Fi 连接，本段不调用标准 set freq。

```sh
(
  set -e
  echo ENABLE_CAPTURE
  ./action-tx-lpc capture-start --dev misharemon0
  echo CHECK_CAPTURE
  ./action-tx-lpc capture-status --dev wlan0 --require-running
  echo START_WONDER
  sh popsicle-rx-start.sh start "$PWD/wonder.ko" misharemon0
  echo BEFORE
  sh popsicle-rx-start.sh status
  sleep 20
  echo AFTER
  ip -s link show misharemon0
  sh popsicle-rx-start.sh status
) > lpc-fixed-test.txt 2>&1

dmesg > lpc-fixed-dmesg.txt
cat lpc-fixed-test.txt
cp lpc-fixed-test.txt lpc-fixed-dmesg.txt /sdcard/Download/
```

仅在没有其他 Wonder 会话时执行。等待期间可打开网页产生正常 Wi-Fi 流量。出错时后续步骤停止，保留日志即可，不自动重试、不卸载原生 WLAN、不删除 NAN/P2P。

若 capture_config_accepted 之后 running=true，说明驱动报告本地捕获正在运行；仍需 RX 计数增长或抓包验证。若出现权限、并发或不支持错误，这次请求已跨过嵌套格式校验，应根据新驱动日志继续定位，不能声称捕获或 AWDL 已可用。

## 停止

如果 Wonder 已成功启动，先运行：

```sh
sh popsicle-rx-start.sh stop
```

随后对本次测试创建的 misharemon0 执行：

```sh
ip link set misharemon0 down && iw dev misharemon0 del
```

目标驱动在 monitor 停机路径中停止 LPC。若 stop 失败先保留日志，不强制卸载依赖。本工具没有虚构单独的 QCA stop 子命令。

## 源码与验证范围

源码提交：6700e2b418e2e39dbc3eb1b8044a51117bdd4900。对应目标源码 QCA SET/GET monitor mode 定义及 nl80211 策略检查已核对。主机回归检查嵌套标志位、RX 属性和值、GET 的非嵌套格式、状态 0/1 以及畸形响应；Android 构建由 GitHub Actions 完成。此修正未在手机执行，尚不构成固件接受或实际收包认证。
