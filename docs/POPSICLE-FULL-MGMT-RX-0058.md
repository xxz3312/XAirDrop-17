# 0058：独立完整管理帧接收试运行

新 WLAN 新增默认关闭的 mishare_mgmt_rx 参数。它在 native register_frames 末尾为单个非MLO STA提交Apple vendor Action前缀的SME/PE主机匹配规则，失败沿原注册回退路径清理；重复注册会重提，覆盖SSR重放。PE按type+prefix全局替换、并不按session隔离，因此只允许一个STA owner。注销先关闭新路由再提交主机规则删除；提交失败或MAC上下文已消失时永久关闭该helper；后者不会向SME传NULL。上述异常均要求正常卸载/重载，不能强制卸载。

在原生HDD vdev同步保护内，仅对已提交owner的默认link、受支持大小、未保护/未分片的Apple type8候选帧，允许组播DA或owner本机单播DA进入该STA的原生cfg80211管理帧上报，保留真实frm_len。不使用monitor/LPC，不把256字节header片段补零或拼成完整帧。原生cfg80211_rx_info同时显式清零。

重要边界：进一步核对发现 sme_register_mgmt_frame 仅向PE队列提交主机匹配规则，不是固件RX过滤命令；提交成功并不证明PE最终分配成功、固件会接收外部AWDL，或完整MIF已经到达。这是新的可验证接收路径，实机尚未验证。新增C owner helper的host fixture执行生产helper，但SME、HDD、锁/原子与并发均为模型；完整WLAN由CI编译与严格链接，不认证固件和完整私有ABI。

## 前提

只适用于此前验证的popsicle/6.12.69测试设备，保持原Wi-Fi。退出旧监听/Wonder/monitor会话。新包包含WLAN、必需provider、工具和两份脚本；这轮不加载Wonder、不创建monitor、不用LPC/OCC，也不需要停用P2P。采用手动RAM切换，不修改系统模块文件/分区/开机脚本。

## 1. 准备与切换

解压到Download后root终端逐块执行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-Mgmt-RX-0058 /data/local/tmp/xairdrop-0058
cd /data/local/tmp/xairdrop-0058
sha256sum -c SHA256SUMS
chmod 755 action-tx-0058
```

```sh
cd /data/local/tmp/xairdrop-0058
sh popsicle-wlan-trial.sh run-mgmt-rx "$PWD" > trial-0058.txt 2>&1
cat trial-0058.txt
```

看到TRIAL_DRIVER_ACTIVE后连接Wi-Fi，再单独检查：

```sh
iw dev wlan0 link
```

没有Connected to时不开始监听。run-mgmt-rx才显式传入mishare_mgmt_rx=1；原run保持旧参数。已有实验driver/state时先用对应旧脚本restore，不覆盖旧会话。驱动切换失败会按已有流程恢复，RESTORE_FAILED则按输出恢复/重启。

## 2. 监听

附近Apple设备打开隔空投送或分享界面：

```sh
cd /data/local/tmp/xairdrop-0058
sh popsicle-mgmt-rx-test.sh "$PWD" "$PWD/result-0058-01"
```

约60秒或解析10帧后结束。工具在wlan0上用标准nl80211 REGISTER_FRAME注册精确前缀，采用6.12传统单socket模式；驱动未声明multicast registrations扩展，故不发送该扩展flag。冲突/不支持时报错，不抢占、不退回monitor。关闭socket移除它自己的cfg80211注册；PE主机规则保留到WLAN正常停机注销。

检查 awdl_mgmt_rx_summary：events表示收到匹配管理帧事件，over_256/max_frame_bytes是完整长度证据，parsed是头与TLV边界通过数量。ready只证明cfg80211接受注册；0帧不算发现成功。mishare_mgmt_rx_routed只统计HDD路由候选，不证明送达socket/解析/Apple身份。有效观察也不代表AWDL同步或互传。

## 3. 恢复原厂 WLAN 和导出

确认观察脚本已退出，再运行：

```sh
cd /data/local/tmp/xairdrop-0058
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0058.txt 2>&1
cat restore-0058.txt
```

看到STOCK_RESTORED后，复制：

```sh
cd /data/local/tmp/xairdrop-0058
cp trial-0058.txt restore-0058.txt result-0058-01/
cp -R result-0058-01 /sdcard/Download/
```

如果监听前失败，没有结果目录则把trial-0058.txt发来。恢复失败不强制卸载；保留输出，重启会走系统原驱动。日志可能包含设备信息，仅私下反馈。
