# 0061：ML-capable STA 默认 link 接收注册修正

0060实测的register_calls=3中，两次非STA跳过，一次ML adapter跳过；register_submitted=0、pe_inserted=0、owner_active=0。因此新增接收路由并未启用。0061允许ML标记的STA默认link进行原生SME注册，仍拒绝附属link adapter。绑定注册时的link指针和vdev ID；切链、缺失vdev、身份变化或原生判定MLO连接时不走新增路由。注销使用注册时保存的vdev ID。不是完整MLO支持，不改固件过滤或频道。

## 1. 准备

0060回传已确认原厂恢复成功。若后来另开实验，先恢复。ZIP解压到Download，在手机本机root终端执行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-Mgmt-RX-0061 /data/local/tmp/xairdrop-0061
cd /data/local/tmp/xairdrop-0061
chmod 755 action-tx-0061
sha256sum -c SHA256SUMS
```

全部OK后：

```sh
sh popsicle-wlan-trial.sh run-mgmt-rx "$PWD" > trial-0061.txt 2>&1
cat trial-0061.txt
```

看到TRIAL_DRIVER_ACTIVE再继续。否则停止并回传trial日志。只适用于此前popsicle/6.12.69测试机。

## 2. 48信道观察

重新连接原Wi-Fi，检查：

```sh
iw dev wlan0 link
cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_diag
```

应为Connected to、freq 5240或5240.0。重点看register_submitted、register_ml_default、pe_inserted、owner_active；保留全部输出。PE处理异步，瞬时计数可能延迟，不能把提交次数当成固件ACK。

附近Apple打开Wi-Fi/蓝牙、隔空投送所有人10分钟，保持唤醒并打开分享界面。执行：

```sh
sh popsicle-mgmt-diag-0061.sh "$PWD" "$PWD/result-0061-48-01" 5240
```

三轮各最多60秒或1000帧解析成功；正常显示MGMT_DIAG_OBSERVATION_COMPLETE。断线、采样换频、工具失败即停止并保留结果。每2秒检查频道，无法排除采样间隙的短暂离频道活动。若目录已存在，换成result-0061-48-02，不删除旧结果。

## 3. 恢复并导出

等待测试命令退出后，无论成功失败均执行：

```sh
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0061.txt 2>&1
cat restore-0061.txt
```

看到STOCK_RESTORED后：

```sh
mkdir -p /sdcard/Download/result-0061
cp trial-0061.txt restore-0061.txt /sdcard/Download/result-0061/
for d in result-0061-*; do
    [ ! -d "$d" ] || cp -R "$d" /sdcard/Download/result-0061/
done
```

压缩Download/result-0061发回。恢复失败保存输出后重启，不强制卸载。不修改系统分区、原厂模块文件或开机项。

## 判断

- register_ml_default>0、register_submitted>0：已允许ML默认link并提交规则；仍需pe_inserted确认处理。
- owner_active=1：读取时路由owner存在，不等于固件接收已启用。
- hdd_stale_identity：默认link或vdev身份变化，等待原生重注册。
- hdd_missing_vdev/hdd_link_switch/hdd_mlo_connection：新增路由被对应检查拒绝。MLO判断沿用原生函数，不据此独立认定AP的MLO状态。
- 所有计数为本次模块加载后的跨接口累计值，逐字段原子但不是一致快照。先检查启动时before，再看增量，owner_active仅是状态。候选前缀计数不认证Apple身份。
- 原有长度、保护/分片、前缀和目的地址检查保留。没有新增跳频、WMA入口诊断、AWDL同步、双向数据通道或文件互传能力。CI和模型通过不替代手机实测、固件验证或完整私有ABI认证。
