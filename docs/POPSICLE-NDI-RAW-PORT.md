# 小米 17 PAS / NDI / RAW 原生驱动接入分析

本文先记录源码分析起点，再记录 0015 的 WMA 兼容与 0016 的资源创建/删除接入。
固件命令尚未在手机发送。目标源码固定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f`，
分析起点包含 0001–0014 popsicle 补丁；其文件 SHA-256 记录在
[源码快照](research/popsicle-xiaomi15-native-port-source-map.json)。

## 参考来源须分清

Leekin2/XAirDrop 固定提交 `eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76`
提供本轮直接复用的 Java、应用补丁和实际加载参数。
逐项检查其 Git tree 后确认：该提交没有完整 WLAN 驱动源码。
这里的 `kernel/driver/` 是仓库原有 OPAirDrop / SM8750 参考实现；
不能将它表述为“从小米 15 仓库拿到的目标驱动源码”。

小米 15 启动参数选择 NDI type 7、self-peer、host-only UP、WMI RAW 和辅助 monitor。
这支持把相同组合当作 17 的优先移植路线，但不证明 17 固件接受此组合。
SM8750 上 type 9 断言、NDI 可用的记录，也不构成 17 的测试结果。

## 1. NDI 会话必须同时接通创建、响应和销毁

目标 `qcacld-3.0/components/mlme/core/src/wlan_mlme_vdev_mgr_interface.c` 的
`mlme_vdev_uses_self_peer()` 不包含 NDI。目标 `core/wma/src/wma_dev_if.c`
在 `wma_vdev_self_peer_create()`、`wma_vdev_self_peer_delete()`、
`wma_vdev_detach()` 共用该判断。只改 create 会导致删除和同步删除响应不一致。

参考 `kernel/driver/wma_dev_if.c` 的 `opairshare_pas_ndi_peer()` 限定
PAS 主机模式与 NDI 固件类型，`opairshare_uses_self_peer()` 扩展原判断；
创建还检查 `wmi_service_nan_data`。迁入时保留原生 NDI、STA、monitor 行为。

同一文件还在以下函数使用 PAS＋NDI 判断：

| 接口 | 要对齐的行为 |
| --- | --- |
| `wma_vdev_start_resp_handler` | PAS＋NDI 的 START 响应不能落入普通关联/BSSID 分支 |
| `wma_handle_channel_switch_resp` | 频道切换失败清理与 START/RESTART 事件分发 |
| `wma_set_and_update_mac_id` | 固件响应中的 MAC ID 与 DP 路由同步 |
| `wma_post_vdev_start_setup` | NDI 的保护模式与启动后处理 |
| self-peer create/delete、vdev detach | 对称创建、删除、等待真正完成事件 |

目标 `core/mac/src/pe/lim/lim_utils.c` 的 `lim_ap_mlme_vdev_up_send()`
已有 NDI 不发送固件 UP 的分支；`core/wma/src/wma_utils.c` 的
`wma_mon_mlme_vdev_up_send()` 则会调用 `vdev_mgr_up_send()`。
参考 `passthru_ndi_no_up` 的含义是按 PAS＋NDI 条件完成主机 UP，
不能把 monitor 的 UP 函数原样用于这个组合。

当前 popsicle host-only owner 没有 legacy ext 对象，也没有真实固件会话；
START/STOP 入口有相应拒绝条件。现有 mgmt.type=9 是占位。
所以不能只把 9 改成 7 或打开模块参数：下一项驱动修改须为完整会话建立
所需上下文、WMA/DP 绑定、事件路由，并与既有 owner、超时、失败回滚、
DELETE 和 SSR/remove 回收统一。成功条件是收到并关联真实完成响应，
不能用本地主机对象创建成功替代固件成功。

## 2. RAW TX 有现成目标接口，仍须适配所有权

目标速率参数编码器 `wma_update_tx_send_params()` 在
`qcacld-3.0/core/wma/src/wma_data.c`，不是参考文件位置。
目标 `tx_send_params` 已定义 DATA frame_type=1、MGMT=0，以及带宽位；
应调用目标编码器后按参考设置 DATA 和 20 MHz，避免复制旧结构布局。

目标与参考都提供七参数 `wlan_mgmt_txrx_mgmt_frame_tx()`。
目标实现只在该入口检查 802.11 version，没有在这里排除 DATA 帧；
这说明源码接口可以承接参考桥接逻辑，不代表固件一定接收或实际发射。

参考 `wma_opairshare_pas_mgmt.h` 可按函数复用 radiotap 解析、完整帧队列、
probe/action 与 AWDL QoS DATA 分类、self-peer 选择和完成处理。
peer 必须属于本次 PAS vdev，不能依赖普通按目的地址查找的 peer。

目标 `wma_mgmt_unified_cmd_send()` 在 `wmi_service_mgmt_tx_wmi` 缺失时
会回退 `cdp_mgmt_send_ext()`。RAW 路径必须明确检查该服务并拒绝不支持情况，
不能把这个回退当成等价的 RAW 通路。
目标 `wmi_unified_tlv.c` 的 HL 和非 HL 两个 `send_mgmt_cmd_tlv()` 分支
均存在显式发送参数编码；非 HL 分支另负责 DMA map/unmap 和 MLO 参数。
不能由源码包含两个分支推定实际目标启用了哪一个。

移植须逐一对齐提交失败、完成回调和停止时的 skb、nbuf、descriptor、peer、
vdev 引用。目标 mgmt_txrx 在 tx_ops 提交失败时清空 descriptor 的 nbuf 并回收
内部 peer 引用；桥接层不能据此重复释放内部引用，也不能遗漏自己拥有的缓冲。
停止先关新请求并排空 worker/完成事件，再删 peer/vdev。

## 3. RX 不止 monitor 回调

目标 monitor 回调在 `qcacld-3.0/components/dp/core/src/wlan_dp_txrx.c`
的 `dp_mon_rx_packet_cbk()`；context 是 `wlan_dp_link *`。
它遍历 skb 链，释放 QDF debug tracking，处理统计与 mac_header，
并区分最后一个包的 push 类型。接入时须保留这些所有权和批处理约定。

参考辅助 monitor 路由 `wlan_hdd_opairshare_aux_rx.h` 使用 packet_type
接收已上送的 radiotap skb，检查、去重/排序后克隆到 PAS netdev。
因此“直接改 DP monitor 回调”不是唯一方案；优先评估复用这条较少侵入的路由，
确认目标 monitor 帧格式和上送行为后再决定是否增加 DP hook。

参考同时有 `dp_rx.c`、`dp_be_rx.c`、`dp_rx_err.c` 的 native RAW 接纳，
以及目标地址过滤、peer-map、ADDBA/BA 和 RX ring 配置。
复制 monitor 路由只能覆盖其中一部分，不能据此宣称单播数据 RX 已完成。

## 4. 频道与启停需成为同一事务

目标 `wlan_hdd_set_mon_chan()` 在 `core/hdd/src/wlan_hdd_main.c`，
会遍历 link、必要时创建普通 monitor vdev，并执行带宽、信道及硬件模式检查。
它不能直接接收现有的 PAS owner 来完成整个会话。
需复用参考 WonderTap init/set_freq/stop 的组织方式，分别绑定 PAS＋NDI 与
辅助 monitor 的实际上下文，保留目标 regulatory/concurrency 校验，
在两个频道状态和完成响应一致后才报告 set_freq 成功。

## 下一项实际修改的边界

先迁入一个完整的 PAS＋NDI 会话：类型选择、真实固件创建、self-peer、
START/host-only UP、频道响应、STOP/DELETE、失败回滚与回收。
接着在该真实会话上接入 WMI RAW TX 和 monitor/native RX。
构建仍使用 Actions 和工具链缓存。当前仅有应用层复用载荷构建成功；
本分析不构成 WLAN 加载或 AirDrop 可用的结论。

## 实施进展：0015 WMA 兼容接入

`0015-mishare-wma-ndi-compat.patch` 已将上述 WMA 接点按目标源码迁入：

- 同一 `wma_mishare_uses_self_peer()` 用于创建、删除和同步删除响应等待。
- PAS＋NDI 创建 DEFAULT self-peer 前检查 NAN Data capability。
- START/频道失败、MAC ID 和启动后处理识别 PAS＋NDI；普通 NDI 不进入扩展分支。
- monitor UP 接口对准备完成的 PAS＋NDI 返回 host-only UP；验证真实 legacy
  extension、相同 WMA vdev 指针及 NDI 类型，拒绝主机占位对象。
- 未增加可变开关，避免创建和删除之间因切换参数而改变 self-peer 判断。

这是 WMA 兼容代码，不是完整 NDI 会话。现有 host-only 构造、type=9 占位、
专用 MLME 操作表和命令前置检查尚未改变，因此本补丁不会自动发送 CREATE/START，
也没有提供可安装产物。下一处仍是固件会话准备与 owner 的对接。

新增 Actions-only fixture 提取实际目标 WMA 的 peer create/delete/detach 和 UP
函数，测试能力缺失、提交/删除错误、同步删除等待、原生 NDI/STA/monitor 保留、
UP 绑定错误与主机占位拒绝。外部对象访问、传输和回调被替代；它不模拟真实固件。
START/频道/MAC 响应目前依赖完整 WLAN 编译校验，不宣称已通过运行验证。

### 下一阶段创建顺序的进一步核对

目标调用链不是一个原子操作：

1. `vdev_mgr_create_send()` 准备参数和 stats ID。
2. `tgt_vdev_mgr_create_send()` 调用 target-if 提交 CREATE。
3. `target_if_vdev_mgr_create_send()` 先调用 WMI CREATE，再初始化响应 timer；
   timer 初始化失败可覆盖原先的发送成功返回值。
4. target-if 返回成功后，dispatcher 才调用 `cdp_vdev_attach()`；该步骤仍可能失败。
5. 普通 HDD 随后调用 `sme_vdev_post_vdev_create_setup()`，其中包含 WMA、CSR、
   dot11mode 和 self-peer 初始化。

因此一个 CREATE 的通用错误返回不能直接解释为“固件未创建”，也不能据此
释放 vdev ID。owner 需要区分未发送、发送结果不明、传输接受、DP 已挂接、
WMA/CSR/peer 已准备等状态，依据真实 STOP/DELETE 事件及回收结果收尾。
该 CREATE 函数没有等待固件 CREATE 确认的逻辑；不能把 `create_send` 返回成功
写成“固件已确认创建”，也不能等待源码中没有接入的 CREATE 确认来替代 START 验证。
本补丁未更改这些创建流程；上述是下一阶段的实现约束。

## 0015 构建验证结果

[Actions 40493230445](https://github.com/xxz3312/XAirDrop-17/actions/runs/40493230445)
在提交 `894efeac80b62456bf08cc23f2954cf8a9f7e440` 全部通过：44 项 Python 检查、
11 组原生 fixture、完整 WLAN 对象编译与严格模块链接。WLAN 574 条版本记录
无不匹配、没有未解决依赖，28 个要求的主机符号存在，7 项选定结构布局 MATCH。
这些记录与布局检查不等于完整私有 ABI/KCFI 或手机加载认证。

下载的紧凑报告 ZIP SHA-256 已独立核对，fixture 生成源码和四个目标源码文件
哈希也与本地补丁结果一致。结果见
[WMA NDI 构建报告](research/popsicle-wma-ndi-compat-build-pass.json)。
编译工具链与 bindgen 缓存均命中。软件源 403 与 fixture 宏生成错误已在本次
成功构建前修复；依赖安装仅使用正常签名校验的 Ubuntu 源。

本轮没有重新构建应用层，也没有在手机启动新的固件会话。下一阶段是实际
创建与 owner/legacy/DP 的接通，并补齐停止、真实删除和 SSR/remove 回收。

## 实施进展：0016 owner 管理 CREATE / DP / DELETE

新增私有 `mishare_runtime_ndi_create(owner, nss_2g, nss_5g)`。
原有 `mishare_runtime_create()` 仍只创建主机对象。只有显式调用新 API，才会
临时选择 NDI type=7，使用目标原生参数准备器和 WMI 编码器提交 CREATE，
随后调用原生 CDP vdev attach。调用方必须提供经过平台校验的每频段 NSS
（API 仅检查 1–2 范围），并保持 RTNL、父 psoc 排他过渡及相关父资源有效。

新建的内部接口把三个层次的结果写到 owner：timer 已准备、WMI 已尝试/传输
已接受、DP 已尝试/成功、stats ID 仍归本次创建所有。timer 在 WMI CREATE
之前初始化；stats 不会因一个可能已经发出 CREATE 的通用错误而立即回收。
传输接受不等于固件确认，不会把这个结果报告为 START/UP 或无线可用。

普通 DELETE dispatcher 会先拆 DP，再发送 DELETE。owner 采用专用路径调用
原生 target-if DELETE，保留 DP 和主机引用，直到真实 DELETE 响应完成原生
响应 timer、runtime lock 和 wake lock 清理。真实响应与超时在源头分开记录；
这个 owner 没有普通 SME/WMA session 引用，因此只对其匹配的 ID 抑制普通
删除回调，其他 vdev 保持原处理。

`mishare_runtime_destroy()` 现在会先推进这段回收：

1. 最多发送一次 DELETE，等待真实确认；接受提交不代替确认。
2. 确认后调用 CDP detach，等待 DP 的最终释放回调。
3. DP 释放后才允许逻辑删除主机对象，继续等待原有最终释放通知。

早到 DELETE 回复与同步 DP 回调不会让发起调用尚未返回就提前释放 owner。
CREATE 结果不明、删除失败/超时、DP detach 失败等情况保留引用并返回 EUCLEAN。
目标 DP attach 的晚期错误可能已发布部分对象：收到 DELETE 后也不会据此
自动拆除未知状态的 DP 对象；该情况保留父资源，等待后续完整恢复路径。
没有提供强制释放、重置引用或在同一 vdev 上重复发送 CREATE 的接口。

新增 Actions-only fixture 执行真实 owner、跨层 owned helper、完整原生 DELETE
handler 和原生主机最终释放函数；外部平台/WMI/timer/DP 和参数准备边界被替代。
覆盖能力/上下文/准备失败、timer 在 WMI 前初始化、早到回复、响应提取与 timer
拒绝、错误 psoc/ID、DP 延迟/同步回调、剩余对象引用和故障保留。DP 最终释放
回调的位置做源码校验，没有执行完整原生 DP final-free 函数。

当前新 API 尚无运行时 HDD/Wonder 调用方；没有在手机发送 CREATE。
本轮不准备 legacy/CSR/WMA session、不创建 firmware self-peer，不发送 START，
不接通 TX/RX。原有命令前置检查、专用 MLME 拒绝操作和 Wonder init 限制仍保留。
SSR/remove 与部分 DP 初始化失败的完整恢复仍须在启用运行时调用方前完成。
