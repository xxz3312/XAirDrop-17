# 0059：管理帧接收分段诊断

0058实机通过校验、新WLAN加载、采集前后5240MHz STA联网及原厂恢复；注册ACK成功但HDD routed=0、用户态events/parsed/over_256全0。未验证完整MIF。

0059保持0058默认关闭、单非MLO STA owner、长度/前缀/DA/保护/分片检查和原厂恢复路径；不改变注册/接收策略，不修改固件、频道、P2P或系统分区。新增只读mishare_mgmt_rx_diag：注册调用及各类跳过原因、SME提交、PE队列处理/规则插入、PE匹配、指示回调、HDD入口和拒绝原因。计数不保存帧内容、MAC或SSID。

## 计数边界

- register_submitted只证明SME post成功。pe_add_seen证明PE处理了精确前缀的注册请求；pe_inserted证明当次原生list插入返回成功，不能证明该规则在稍后读取时仍存在。pe_delete_seen是删除请求处理次数，不是删除成功或固件ACK。
- skip_ml_adapter/link_adapter只说明HDD结构被标记；不能据此宣称AP使用MLO。owner_active是读取瞬间的路由owner是否存在，不含地址。
- pe_check_calls只覆盖到达原生已注册帧匹配函数的包，之前的固件/WMA/PE丢弃未覆盖；0不能直接判定固件没收包。
- pe_apple、pe_match_apple、pe_indication_apple、pe_callback_apple、hdd_apple只匹配有界29..2304字节Action及Apple type8前缀，不认证身份和AWDL TLV有效性。hdd_apple在原有40字节下限检查后计数。
- HDD拒绝原因统计所有到达该hook的管理帧，可能包括无关流量；必须结合Apple前缀计数判断。回调计数是调用前观察，不证明下游收到。
- 所有计数为本次模块加载后的累计值，跨接口；前后差值和启动时累计信息均需保留。逐字段原子读取，不是整个链路的一致快照。PE处理异步，瞬时读数不必相等。
- C fixture执行生产helper和计数/边界/getter；SME/HDD/锁/原子/并发为模型。完整原生PE hook由CI实际编译链接，但没有在fixture执行完整PE运行。

## 手机步骤

只适用于此前popsicle/6.12.69测试机。退出旧实验并恢复原厂后，将ZIP解压到Download，逐块执行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-Mgmt-RX-0059 /data/local/tmp/xairdrop-0059
cd /data/local/tmp/xairdrop-0059
sha256sum -c SHA256SUMS
chmod 755 action-tx-0059
sh popsicle-wlan-trial.sh run-mgmt-rx "$PWD" > trial-0059.txt 2>&1
cat trial-0059.txt
```

看到TRIAL_DRIVER_ACTIVE后连接Wi-Fi，再检查iw dev wlan0 link显示Connected to。附近Apple设备打开隔空投送/分享界面，再运行：

```sh
sh popsicle-mgmt-rx-test.sh "$PWD" "$PWD/result-0059-01"
```

约60秒或10帧解析成功后退出。diag-before/after自动记录，不需要手抄sysfs；没有owner仍保留观察用于诊断。注册/驱动/脚本成功都不等于AWDL收包。

```sh
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0059.txt 2>&1
cat restore-0059.txt
```

看到STOCK_RESTORED后导出，恢复联网仍需手动确认：

```sh
cp trial-0059.txt restore-0059.txt result-0059-01/
cp -R result-0059-01 /sdcard/Download/
```

加载失败不继续监听；发trial日志。恢复失败保留日志并重启，不强制卸载。不加载Wonder，不创建monitor，不停P2P，不用填频率。原始日志仅私下反馈。
