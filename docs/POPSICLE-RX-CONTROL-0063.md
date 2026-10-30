# 0063：主动操作与 WMA 活性对照

0062 三分钟内全部管理帧计数无增量；17个WMA事件和4个Action帧都来自监听前累计。0063沿用0062驱动和监听工具，只更新控制脚本，把静置、系统扫描请求、一次断开重连、重连后的AWDL监听分阶段记录，避免继续只比较零计数。

只适用于此前验证的popsicle/6.12.69设备。0062回传已确认原厂恢复。新包的驱动和工具逐字节复用0062；源码中原有kernel/native文件在打包时逐一比较。没有新的驱动编译或接收策略修改。

## 操作

ZIP解压到Download，在手机本机root终端执行，不能通过依赖该Wi-Fi的远程终端操作：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-RX-Control-0063 /data/local/tmp/xairdrop-0063
cd /data/local/tmp/xairdrop-0063
chmod 755 action-tx-0063
sha256sum -c SHA256SUMS
```

全部OK后加载：

```sh
sh popsicle-wlan-trial.sh run-mgmt-rx "$PWD" > trial-0063.txt 2>&1
cat trial-0063.txt
```

看到TRIAL_DRIVER_ACTIVE后连接原来的48信道Wi-Fi，确认Connected to与freq 5240或5240.0：

```sh
iw dev wlan0 link
```

附近Apple保持Wi-Fi/蓝牙开启，隔空投送所有人10分钟，亮屏并打开分享界面。启动完整对照：

```sh
sh popsicle-rx-control-0063.sh "$PWD" "$PWD/result-0063-48-01" 5240 --reconnect
```

前约20多秒采集静置和扫描请求。看到RECONNECT_CONTROL后，脚本会对本机wlan0发出一次断开请求；立即打开手机Wi-Fi列表，点回同一个已保存的Wi-Fi，保持Wi-Fi总开关开启。不忘记网络、不重输密码、不改路由器。脚本最多等待90秒，并要求观察到断开及回到原BSSID/频率，随后自动再监听60秒。不要关闭终端进程，保持手机唤醒。若Android自动重连，也可让脚本继续；若未观察到断开转变，会保存日志并报告控制不完整。

不带--reconnect仅进行静置、扫描请求与监听，不会主动断开连接。首次建议使用上面的完整命令。目录已存在时改用result-0063-48-02，不删除旧结果。

扫描请求交给Android扫描流程，可能临时探测其他频道；关联频率仍要求5240，扫描阶段不证明收到的帧来自48信道。重连后监听窗口单独检查原AP和频率。

## 恢复与导出

命令结束后，无论成功失败都恢复：

```sh
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0063.txt 2>&1
cat restore-0063.txt
```

看到STOCK_RESTORED后：

```sh
mkdir -p /sdcard/Download/result-0063
cp trial-0063.txt restore-0063.txt /sdcard/Download/result-0063/
for d in result-0063-*; do
    [ ! -d "$d" ] || cp -R "$d" /sdcard/Download/result-0063/
done
```

压缩Download/result-0063发回。如果重连超时，先手动连接网络，再执行恢复。恢复失败保存输出并重启，不强制卸载。加载失败仅回传trial-0063.txt。

## 如何理解结果

- 每个阶段分别保存diag前后快照与delta；summary中的WMA_GROWTH_OBSERVED只说明该阶段WMA计数增加，不认证特定发送者、帧类型、AWDL或AirDrop。
- 静置也可能收到管理流量。扫描/重连期间的增量仅是时间相关观察，不能把所有增长归因于该操作；前缀专属计数需另看。
- Android原生start-scan命令调用startScan后直接返回0，忽略该API的返回值。因此scan_request_rc=0不证明执行成功。list-scan-results可能是缓存。脚本始终写scan_execution_confirmed=false，且不更改扫描限流或其他系统设置。
- 扫描无增长也可能来自固件扫描卸载；重连无增长仍不能直接判定固件不支持AWDL。重连只用于尝试制造可观察的管理帧活动，不承诺必然经过该WMA入口。
- 重连要求记录到断开和原BSSID/频率回归，不只是命令返回0。只发一次断开请求，无重试，无密码、配置或Wi-Fi总开关改动。
- 若驱动诊断消失或累计计数减少，脚本停止，不能跨重载比较。单调检查不是完整模块epoch证明，无法排除未观察到且计数恰巧未减小的重载。
- 保留0062全部计数边界：跨接口累计、逐字段原子但非一致快照；部分路径未覆盖。原始日志含设备和附近AP信息，仅私下回传。
- 不生成伪造帧或伪造计数；没有增加跳频调度、固件过滤、AWDL同步或文件互传。

命令依据：Android Open Source Project，WifiShellCommand.java（本次核对blob fe23f18d12def390ec3e801fe8b9fb3441b435e2）：https://android.googlesource.com/platform/packages/modules/Wifi/+/refs/heads/main/service/java/com/android/server/wifi/WifiShellCommand.java 。手机侧仍先检查实际help是否支持start-scan，OEM实现可能不同。
