# 0062：WMA → 管理帧分发器 → PE 前段诊断

0061已实测确认注册提交、PE规则插入和owner建立成功，但三轮监听无候选帧。0062保留该修正，只添加39项跨层计数，定位候选帧在何处可见、何处退出。不是收包修复、固件能力确认或互传成功证明。

## 1. 准备

0061回传已确认原厂恢复成功。若后来另开实验，先恢复。ZIP解压到Download，在手机本机root终端执行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-Mgmt-RX-0062 /data/local/tmp/xairdrop-0062
cd /data/local/tmp/xairdrop-0062
chmod 755 action-tx-0062
sha256sum -c SHA256SUMS
```

全部OK后：

```sh
sh popsicle-wlan-trial.sh run-mgmt-rx "$PWD" > trial-0062.txt 2>&1
cat trial-0062.txt
```

看到TRIAL_DRIVER_ACTIVE再继续。否则停止并回传trial日志。只适用于此前popsicle/6.12.69测试机。

## 2. 48信道观察

重新连接原Wi-Fi，检查：

```sh
iw dev wlan0 link
cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_diag
```

应为Connected to、freq 5240或5240.0。先看register_submitted、register_ml_default、pe_inserted、owner_active，再看wma_events、wma_prepared、wma_action、wma_vendor127、wma_apple、txrx_apple、pe_entry_apple；保留全部输出。PE处理异步，瞬时计数可能延迟，不能把提交次数当成固件ACK。

附近Apple打开Wi-Fi/蓝牙、隔空投送所有人10分钟，保持唤醒并打开分享界面。执行：

```sh
sh popsicle-mgmt-diag-0062.sh "$PWD" "$PWD/result-0062-48-01" 5240
```

三轮各最多60秒或1000帧解析成功；正常显示MGMT_DIAG_OBSERVATION_COMPLETE。断线、采样换频、工具失败即停止并保留结果。每2秒检查频道，无法排除采样间隙的短暂离频道活动。若目录已存在，换成result-0062-48-02，不删除旧结果。

## 3. 恢复并导出

等待测试命令退出后，无论成功失败均执行：

```sh
sh popsicle-wlan-trial.sh restore "$PWD" > restore-0062.txt 2>&1
cat restore-0062.txt
```

看到STOCK_RESTORED后：

```sh
mkdir -p /sdcard/Download/result-0062
cp trial-0062.txt restore-0062.txt /sdcard/Download/result-0062/
for d in result-0062-*; do
    [ ! -d "$d" ] || cp -R "$d" /sdcard/Download/result-0062/
done
```

压缩Download/result-0062发回。恢复失败保存输出后重启，不强制卸载。不修改系统分区、原厂模块文件或开机项。

## 判断边界

- 先确认register_submitted、pe_inserted和owner_active，避免把注册回退误当接收过滤。
- wma_events：进入普通WMI管理帧事件回调，不包含所有固件/monitor/重排/元数据事件路径；0不能单独证明固件无接收能力。
- wma_prepared/action/vendor127/apple：原生校验和大小端复制后，有界完整buffer的分类。Apple固定前缀不是身份或TLV认证。over256仅为当层长度证据。
- wma_*fail：事件提取/分配/原生长度校验/下游返回失败；dispatch_ok不证明PE或用户态送达。
- txrx_*：管理帧分发器入口、类型/地址/保护帧长度/未识别帧/模拟钩子/内存/回调/限流相关计数。含apple的字段才针对前缀候选；其他字段可能是无关流量。
- txrx_apple_cb_attempts按入口捕获的前缀标记统计各组件回调尝试，可能一帧多次，也不保证PE收到；不在回调移交buffer之后读取帧。
- pe_entry_apple和既有pe_apple/pe_match_apple区分PE入口、注册匹配入口与匹配成功；pe_*drop计数标出CAC、extscan/epno旁路和无session退出。extscan旁路可能已有专门处理，不等于整个包丢失。
- 调度、重排、模拟钩子和重复回调使跨层数值不能简单逐项相减。WMA之前与所有中间路径尚未逐一覆盖。详细定义见源码docs/POPSICLE-WMA-RX-DIAG-0062.md。
- 计数为本次模块加载后跨接口累计值，各字段原子、整份快照不一致；先看before启动状态，再看每轮差值。owner_active是状态。
- 当前分类仅处理支持长度24..2304、固定24字节管理头的Action前缀，不宣称支持加密/HT-control等所有布局。未改变原有路由检查、回调、buffer所有权或返回值。
- 没有新增换频、AWDL同步、双向数据通道或文件互传。CI编译和模型测试不替代手机实测与完整私有ABI验证。
