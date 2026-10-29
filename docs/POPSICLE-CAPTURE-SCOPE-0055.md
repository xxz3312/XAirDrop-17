# 0055：显式请求工作频道采集 OCC

0054 实机观察 7733 包：583 Beacon、7150 DATA、Action=0。来源、radiotap、TX 回显过滤和格式错误均为 0。确认没有被用户态来源过滤，但尚不知道是当前频道没有 Action，还是原生 capture 的上报范围限制。

核查固定小米 WLAN 源码：qca_vendor.h 定义默认 LPC=0（客户端/BSS 流量）和 OCC=1（工作频道）；os_if_dp_local_pkt_capture.c 的非 WLAN_LOCAL_PKT_CAPTURE_SUBFILTER 分支在 OCC 下要求 MGMT/DATA/CTRL 三类全部选中，并配置 MON_FILTER_ALL 和 monitor-other 过滤。此前工具仅 DATA_RX=ALL、MGMT_RX=ALL，缺省 LPC。MGMT_RX=ALL 本身没有漏选 Action，但 LPC 不等于全频道接收。

0055 增加 capture-start --operating-mode occ，发送 RX attr2/4/6=1 和 attr8=1；不请求 TX、不重试、不自动退回 LPC。旧调用继续默认 LPC，GET 状态请求不改变。

重要限制：源码的 SUBFILTER 分支没有读取 operating type，原厂驱动的编译分支及固件行为尚未确认。SET 成功、running=true 只证明请求被接受且 capture 在运行，不能证明 OCC 生效。因此输出 requested_operating_mode=occ、mode_verified=false，不称“全频道已开启”。相邻模式对比、已知外部 Action 发射源或独立空口捕获才可进一步验证。手机本机直发完成不能作为外部 RX 对照。

## 使用

用原厂 WLAN，保持上一轮相同 Wi-Fi 和频道，先不调整路由器。旧 Wonder/monitor 会话应已退出。

解压到 Download 后 root 终端逐块运行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-Capture-Scope-0055 /data/local/tmp/xairdrop-0055
cd /data/local/tmp/xairdrop-0055
sha256sum -c SHA256SUMS
chmod 755 action-tx-0055
```

保存 P2P 状态，暂时停用（测试时不使用 Wi-Fi Direct）：

```sh
P2P_FLAGS=$(cat /sys/class/net/p2p0/flags)
ip link set p2p0 down
```

附近 Apple 设备打开隔空投送接收或分享界面。本轮明确指定 occ，观察约 60 秒：

```sh
cd /data/local/tmp/xairdrop-0055
sh popsicle-awdl-rx-test.sh "$PWD" "$PWD/result-0055-occ-01" occ
```

controller 只运行一次指定模式。请求失败会清理已创建资源并保留 setup.txt，不自动再试 LPC。即便请求成功，依然检查全部统计，不以 RX_OBSERVATION_COMPLETE 当作 AWDL 成功。出现 CLEANUP_FAILED 则保留现场发输出，不强制卸载或切换驱动。

清理成功后，在同一终端恢复 P2P 并复制结果：

```sh
if [ "$((P2P_FLAGS & 1))" != 0 ]; then ip link set p2p0 up; fi
cp -R /data/local/tmp/xairdrop-0055/result-0055-occ-01 /sdcard/Download/
```

上传结果目录压缩包。此包没有新的 WLAN/Wonder，沿用已验证 Wonder；仅用户态工具和 controller 更新。不换频、不建立 peer、不发实验帧，不开启 XOS。AWDL 同步、选举、数据通路和 Apple 文件互传仍未接通。
