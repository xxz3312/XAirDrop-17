# 0056：Apple OUI 候选帧拒绝定位

0055 OCC 请求成功后，实机收到 16045 包，包含 609 Action；591 帧通过 category127/Apple OUI 检查，但均落入 bad_awdl。另有18帧其他 Action。前后频道均5240MHz，来源/radiotap错误=0，正常退出和清理。相比0054 Action=0，观察范围明显扩大；没有完整全频道覆盖证明，也没有有效AWDL/Apple接收认证。

0056 保留原校验条件和返回值，只把内部拒绝细分。awdl_candidate_reasons 包含 oversize、frame_flags、fragment、short_header、other_type、other_version、other_subtype、short_tlv_header、tlv_overrun、parsed；not_candidate 应为0（接收入口已检查OUI）。总和应等于上层 observed+bad_awdl+unsupported_awdl。bad_awdl 是解析器拒绝，不等同于空口帧损坏。

每类只保留首个 awdl_candidate_sample：帧字节数、frame_control、分片号、协议 type/version/subtype、失败TLV起点/剩余字节/声明长度/类型和已完整遍历TLV数。protocol_fields_present、tlv_type_present、tlv_length_present 控制字段是否有效；false 时不要解读相应数值。TLV偏移以去掉radiotap的802.11帧起点计数，候选AWDL头按现有假设从24开始，TLV从40开始。诊断不保存MAC/SSID/时间戳/载荷，不认证设备身份；parsed 样本的TLV失败字段不作错误解释。

我们不会尝试其他偏移、忽略FCS或跳过坏TLV以获得成功计数；实际兼容调整要等新证据。

## 手机操作

用原厂WLAN、保持本轮Wi-Fi/频道条件，旧会话已结束。下载解压到Download后，root终端逐块运行：

```sh
su
cp -R /sdcard/Download/XAirDrop-17-AWDL-Parse-0056 /data/local/tmp/xairdrop-0056
cd /data/local/tmp/xairdrop-0056
sha256sum -c SHA256SUMS
chmod 755 action-tx-0056
```

```sh
P2P_FLAGS=$(cat /sys/class/net/p2p0/flags)
ip link set p2p0 down
```

附近Apple设备打开隔空投送接收或分享界面；显式请求OCC，约60秒，只接收：

```sh
cd /data/local/tmp/xairdrop-0056
sh popsicle-awdl-rx-test.sh "$PWD" "$PWD/result-0056-occ-01" occ
```

正常清理后，在同一终端恢复原P2P状态并复制日志：

```sh
if [ "$((P2P_FLAGS & 1))" != 0 ]; then ip link set p2p0 up; fi
cp -R /data/local/tmp/xairdrop-0056/result-0056-occ-01 /sdcard/Download/
```

若 CLEANUP_FAILED，先保留现场发输出，不强制卸载或切换驱动。目录必须为新目录；重复用02。重点反馈 awdl-rx.log，也请上传完整日志目录压缩包。

本轮不改WLAN/Wonder，不发送帧，不换频道，不实现AWDL同步/选举/文件互传。requested_operating_mode=occ、mode_verified=false 继续如实表示请求意图与模式读回缺失。
