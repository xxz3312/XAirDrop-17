# 0057：256 字节接收限制的源码定位

## 本轮结果

这是源码定位和审计工具阶段，没有新的手机测试包，没有修改 WLAN/Wonder/解析器，也没有修复完整 MIF 接收。不要重跑 0056 来验证一个尚未修改的接收通路。

0056 实机首次有一帧 PSF 通过 AWDL头与完整TLV边界检查（247字节、7个TLV）。208候选落在tlv_overrun。首个MIF样本256字节，TLV12起点227，声明内容47字节而只剩26字节；至少需要帧长277。仅记录首个样本，不能据此证明208帧长度都相同。格式匹配不是身份认证、AWDL同步或文件互传证明。

## 已找到的限制

检查的 MiCode WLAN 工作树基于36df473046706a5259942e1bf7222108dbbb860f，含此前popsicle适配补丁；本轮审计文件中wlan_hdd_cfg80211.c为已修改文件，其余三个DP文件未改。报告记录当前文件哈希，结论限定于这些内容：

1. os_if_dp_local_pkt_capture.c 把LPC/OCC设置交给 cdp_start_local_pkt_capture。
2. dp_mon_filter.c 的 dp_mon_start_local_pkt_capture 调用 dp_mon_set_local_pkt_capture_rx_filter。
3. 此函数明确启用 packet_header=1、rx_hdr_length=RX_HDR_DMA_LENGTH_256B。OCC更改PASS/OTHER范围，未更改这个长度。
4. dp_mon_filter.h 的 header DMA枚举只有64/128/256字节，256编码为3。不能发明512编码，也不能把2.0完整数据DMA里的DEFAULT_DMA_LENGTH=7套到这个字段。
5. dp_rx_mon.c 的 HAL_TLV_STATUS_HEADER 分支从header TLV克隆并按payload_len保留数据，随后拼接/送至monitor。仅把skb长度加大不能补回未DMA的数据。

以上定位与256字节样本吻合，但不构成原厂二进制逐字节一致证明，也没有排除其它接收路径或固件限制。

## 已排查的上层

当前Wonder外部monitor桥接函数只校验/转发已收到skb，没有256裁剪调用。用户态监听缓冲为8192，recvfrom使用MSG_TRUNC；样本也未触发packet_truncated。故没有证据表明把用户态缓冲或tcpdump snaplen调大能恢复当前已被上游裁剪的MIF。

新增 tools/kernel/audit_capture_limit.py，对上述调用点、枚举与header-copy路径进行限定检查，输出源码哈希和结论边界。源码变化时拒绝套用旧结论，新增更大枚举时分开报告“可声明长度”和“当前配置长度”。它是静态审计，不认证固件。

```sh
python3 tools/kernel/audit_capture_limit.py \
  --wlan-source /path/to/pinned-wlan-source \
  --project "$PWD" \
  --out capture-limit.json
```

## 完整帧接收需要处理的两条路径

优先评估完整管理帧indication，因为当前先需要完整PSF/MIF：

- 主动在固件/SME注册Apple vendor Action匹配，并对称注销。只做用户态NL80211 REGISTER_FRAME不够；审计的update_mgmt_frame_registrations回调只做上下文检查和日志，没有调用SME去注册该匹配。
- 原生hdd_indicate_mgmt_frame还有广播/多播目标adapter路由限制，不能假设注册后就会把所有AWDL广播交给wlan0。
- 保留真实frm_len，并建立明确有归属的RX目标、失败处理和注销/卸载顺序。未接通前不启用默认功能。
- 后续可复用已有AWDL解析器，独立标记新接收来源；先验证完整MIF，再接同步/选举。

另一条是完整monitor packet DMA/RX ring路径；它与当前header TLV截取不同，需要目标硬件/固件、并发资源和生命周期验证。将来RAW DATA通路仍需要单独实现，管理帧indication不能代替数据接收后端。

本阶段仅把截断来源及改造要求落到可核对的源码；full_frame_rx_implemented=false，不能称完整帧修复完成。

## 验证记录

审计脚本已对实际目标工作树运行。CI 40923724035 的5项Python fixture通过，包括枚举变化、较大枚举出现、接收路径变化及SME调用/bridge裁剪识别。CI执行的是合成源码fixture，不等于再次验证目标固件或运行完整WLAN。源码定位提交：dc2bb2e215ae27111649a43af289bea5f790a489。本轮没有新的C/内核编译或手机测试。
