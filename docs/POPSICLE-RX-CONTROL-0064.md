# 0064：help兼容与手动重连对照

0063实测：wifi help完整输出含start-scan，但退出255；旧脚本因此跳过扫描。iw disconnect返回Operation not permitted，重连和后续监听均未执行；原厂恢复成功。0064按实际帮助内容识别start-scan，保留返回码；超时帮助不作为支持证明。移除所有自动断开命令，改为系统设置中的手动重连；AWDL监听放在手动步骤之前。驱动、provider和监听工具逐字节复用0062。

## 准备与加载

ZIP解压到Download，在手机本机root终端执行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-RX-Control-0064 /data/local/tmp/xairdrop-0064
cd /data/local/tmp/xairdrop-0064
chmod 755 action-tx-0064
sha256sum -c SHA256SUMS
```

全部OK后：

```sh
sh popsicle-wlan-trial.sh run-mgmt-rx "$PWD" > trial-0064.txt 2>&1
cat trial-0064.txt
```

只在看到TRIAL_DRIVER_ACTIVE后继续。否则回传trial日志。仅适用于此前验证的popsicle/6.12.69；0063回传已确认恢复原厂。通过该Wi-Fi的远程终端不能用于本轮手动断开操作。

## 48信道测试

重新连接原Wi-Fi，检查Connected to与freq 5240或5240.0：

```sh
iw dev wlan0 link
```

附近Apple打开Wi-Fi/蓝牙、隔空投送所有人10分钟，保持亮屏与分享界面。执行：

```sh
sh popsicle-rx-control-0064.sh "$PWD" "$PWD/result-0064-48-01" 5240 --manual-reconnect
```

先等待静置、扫描请求、60秒监听结束，约一分半钟。看到MANUAL_RECONNECT后，再打开系统Wi-Fi设置断开并连接回同一个已保存网络。如果没有断开按钮，可关闭Wi-Fi约5秒，再打开并点回原来的Wi-Fi；不忘记网络，不重新输入密码。保持终端进程运行，脚本最多等待120秒，并要求观察到断开和原BSSID/频率回归，之后留6秒稳定观察。

如果系统因Wi-Fi开关卸载了诊断驱动，或计数减少，手动阶段会标记无效，不计算该阶段增量；前面静置、扫描、监听日志仍保留。若无法手动操作，等待窗口结束即可，结果会标记转变未观察到。脚本自身不执行断开、Wi-Fi开关、改网、忘记网络或修改密码的命令。

不带--manual-reconnect时只采集静置、扫描请求和监听。结果目录已存在时换成result-0064-48-02，不覆盖旧结果。

## 恢复与导出

采集命令退出后，无论手动阶段状态如何都执行：

```sh
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0064.txt 2>&1
cat restore-0064.txt
```

看到STOCK_RESTORED后：

```sh
mkdir -p /sdcard/Download/result-0064
cp trial-0064.txt restore-0064.txt /sdcard/Download/result-0064/
for d in result-0064-*; do
    [ ! -d "$d" ] || cp -R "$d" /sdcard/Download/result-0064/
done
```

压缩Download/result-0064发回。若手动阶段后仍未联网，先手动连接再恢复。恢复失败保留输出并重启，不强制卸载。没有修改系统分区或开机项。

## 结果含义

- exit=0只表示采集程序正常结束；manual_status必须单独看。TRANSITION_OBSERVED_CHECK_DELTA表示观察到断开/回归且计数未减少，仍需查看实际增量。
- INVALID_DRIVER_CHANGED、INVALID_COUNTER_RESET：手动对照无效，不跨重载相减。INCOMPLETE_TRANSITION_NOT_OBSERVED：未观察到完整转变，不据此判断收包能力。
- help_rc保留实际值；帮助明确列出start-scan时，255不再阻止发送一次扫描请求。scan_request_rc仅为该命令退出码，不证明扫描执行；scan_execution_confirmed保持false，扫描列表可能是缓存。
- 扫描交给系统，可能临时探测其他频道；关联频率和单独监听窗口要求回到原AP/频率。扫描窗口不证明流量来自48信道。
- summary与各阶段delta分开记录。WMA_GROWTH_OBSERVED只表示对应窗口WMA计数增长，不认证帧来源、AWDL或AirDrop；有普通背景流量时，不能将所有增长归因于操作。
- 驱动/schema消失和计数减少可发现部分重载，但不是完整模块epoch证明；无法排除未观察到且计数恰巧未减少的重载。
- 沿用0062所有计数边界：跨接口累计、逐字段原子但非一致快照；部分路径尚未覆盖，前缀不认证Apple身份。原始日志含设备和附近AP信息，仅私下回传。
- 本包只更新脚本与测试，未增加固件过滤、AWDL调度或文件互传能力。CI模型不代替手机实测。
