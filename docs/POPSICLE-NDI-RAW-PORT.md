# 小米 17 PAS / NDI / RAW 原生驱动接入分析

本文先记录源码分析起点，再记录 0015–0021 的 WMA、资源、self-peer、PE 会话与启动前准备。
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

## 0016 构建验证结果

[Actions 40498357106](https://github.com/xxz3312/XAirDrop-17/actions/runs/40498357106)
在提交 `6a1d8475b580014431c0d9800fb3c969ed67c057` 全部通过：44 项 Python 检查、
12 组原生 fixture、完整 WLAN 对象编译和严格模块链接。37 个要求的主机符号
存在，WLAN 574 条版本记录无不匹配，没有未解决依赖；7 项选定结构布局 MATCH。
clang/rust 工具链和 bindgen 缓存均命中。

紧凑报告 ZIP、生成 fixture、五个原生文件及三个 owner 文件哈希已独立核对。
WLAN SHA-256 为 `704d5162639d3dc4432ce9caeb9b66b4d7db5434d93cdf22f0d822eed60134f0`。
完整记录见 [owned NDI 资源构建报告](research/popsicle-owned-ndi-resource-build-pass.json)。
这些结果不构成完整 ABI/KCFI、模块加载或固件接受的证明。

本轮已将资源 CREATE/DP/DELETE/最终释放接进私有 owner API，但没有运行时调用方，
未在手机发送固件命令。下一阶段需准备 legacy/WMA 上下文与固件 self-peer，
同时扩展对应回收，再接 START/频道和 RAW 收发；SSR/remove 仍须在启用前完成。

## 实施进展：0017 legacy / WMA / self-peer 接入

新增私有 `mishare_runtime_ndi_prepare(owner)`，仅接受已完成资源 CREATE 和 DP
挂接、尚未开始删除的 owner。它检查并分配 native legacy 扩展，初始化 rate/
connect 默认值、wait-key timer、两个 wake lock 与三个 runtime lock；每一步
检查失败并逆序只释放已初始化部分。保留原 NSS，不调用 SME/CSR，不再次 CREATE。
正常释放执行原生完整 legacy destructor。PAS 不申请 STA roam stats/FILS。

WMA 使用独立绑定函数，检查相同 psoc/vdev、空闲 slot 与引用获取结果后，保存
NDI 类型、STOPPED 状态及额外 WMA 引用。不调用普通 post-create 的全局配置、
普通数据回调注册或会隐式 detach DP 的 `wma_cleanup_vdev()`。
这是最小 WMA 绑定，不代表普通会话配置已经完成。

self-peer 直接复用目标 `wma_create_peer(DEFAULT)`，拒绝已存在的 MAC，检查原生
返回和 peer count。一次尝试后的通用错误不能证明没有发送命令，因此保留所有
资源并隔离，不在同一 owner 重试。成功仅表示原生 API 成功，未等待固件创建确认。

删除采用新的内部 request type `0x12`（原 0x01–0x11 不变），复用 WMA hold
queue、timer 与 `wma_remove_peer()`。完整的 hold request 必须先建立，再调用
删除。userdata 是保持存活的 owner token，不能进入普通 SME 删除参数转换。
真实响应在原生 timer/wake/CDP/request 清理后通知 owner；超时单独标记为失败，
清理 request 后才通知 owner 并保留原恢复策略。匹配还要求 token、psoc、vdev ID
和 MAC 一致。WMI event ID 在转换成 uint8 队列键之前检查范围。

owner 的回收顺序扩展为 self-peer DELETE 确认 → VDEV DELETE 确认 → DP 最终
释放 → WMA 解绑/引用释放 → native legacy destructor → 主机对象删除。
早到回复仍需等待提交函数返回。创建结果不明、hold-request 分配/发送错误或
超时均不释放父资源、不发送后续 VDEV DELETE。未增加强制释放/引用重置接口。

新增 Actions-only fixture 执行真实 owner、legacy 初始化及完整 destructor、
WMA 绑定/解绑和 peer helper，以及原生响应/超时的限定插入片段。外部 QDF 资源、
WMA 队列/timer、原生 wma_create_peer/wma_remove_peer 与固件/DP 传输被模型替代；
未执行完整 WMA handler、真实 peer 最终释放或 IRQ/list 竞争。全文件去掉命名
新增片段后哈希须与 0016 前的固定文件相同，防止改动普通路径。

新 API 尚无运行时调用方。没有 CSR/PE session、普通 post-create 参数准备、
START/频道或 TX/RX；专用 MLME 拒绝操作仍保留。SSR/remove 与失败隔离后的恢复
仍须在手机启用前接通。目前未在手机运行新命令。

## 0017 构建验证结果

[Actions 40548389136](https://github.com/xxz3312/XAirDrop-17/actions/runs/40548389136)
在提交 `ad2e31badc3aad73611a6ae322361e580c0357d1` 全部通过：44 项 Python 检查、
13 组原生 fixture、完整 WLAN 对象编译及严格链接。45 个要求的主机符号存在；
WLAN 574 条版本记录无不匹配，没有未解决依赖；7 项选定结构布局 MATCH。
工具链与 bindgen 缓存命中。

下载的紧凑报告 ZIP、生成 fixture、三个原生文件与三个 owner 文件哈希已独立
核对。WLAN SHA-256 为 `a4f3bb7b1ec8f7ef11fc1d52f3577197721b89d14f05c055b99b9313017c66d7`。
完整记录见 [context/self-peer 构建报告](research/popsicle-owned-context-peer-build-pass.json)。
这些结果不构成完整 ABI/KCFI、模块加载、固件接受或真实 peer 最终释放认证。

本轮完成私有 owner 的 legacy/最小 WMA/self-peer 接入与对称回收，尚未增加运行时
调用方或在手机执行。下一阶段为 PE/session 参数、START/STOP 和频道切换，随后
接 RAW 收发；启用前仍需补齐 SSR/remove 与失败隔离后的完整恢复。

### Owned PE session lifecycle (0018)

The Xiaomi 15/SM8750 reference adds its own `sme_create_pe_session` and PAS
PE role; neither API nor role exists in the pinned SM8850 source. Queue
acceptance in that reference also does not confirm actual PE creation.
This port therefore uses an owned native MC-thread request and explicit
completion before admitting a future START implementation.

`mishare_runtime_ndi_session` requires an already prepared owned NDI context
and self-peer. It is one-shot: the owner records pending state before posting,
then retains actual completion separately from successful queue submission.
Every request pins the exact VDEV with `WLAN_LEGACY_MAC_ID`; its native scheduler
flush callback releases that reference and reports cancellation. The callback
queue is TARGET_IF on the same native MC thread as PE, because PE's legacy
queue does not dispatch arbitrary function pointers. No request waits while
holding RTNL or executes native session-table work on the requesting thread.

A new private host BSS/PE role is appended; existing enum values are unchanged.
The native `pe_create_session` still owns its DPH table, index pool and MAC VDEV
reference. Bounded owned additions initialize the role/self MAC and release the
MAC reference on an owned post-lookup constructor failure. The PE session keeps
a stable owner identity. Ordinary native source files match their recorded
pre-0018 hashes after removing the additions. `struct pe_session` is rebuilt
with a private owner field; this is not a promise of compatibility with a stock
binary that accesses that internal structure.

Destroy first waits for any pending create, then queues PE deletion and waits
for its real MC callback. Deletion requires the same owner, exact VDEV, native
session address, private BSS/PE roles and self MAC; an occupied foreign session
is never adopted or deleted. Native `pe_delete_session` releases the PE-owned
MAC reference before completion is published. Only then may existing self-peer,
VDEV and DP teardown proceed. Failure to queue/execute/flush a delete, unexpected
matching replies or ambiguous session identity quarantines all remaining
resources. No fake DOWN event is used for a session that has never started.

The new Actions fixture executes the production owner and actual extracted
request/post/callback/flush helpers plus bounded native constructor insertions
under ASan/UBSan. Scheduler primitives and the full PE allocator/destructor
remain modeled; this does not exercise real MC queue races, firmware or radio.
The existing fixtures retain explicit aborts for accidental PE transport calls.
Full WLAN compilation and strict linking remain required. No runtime caller,
channel validation/preparation, START/STOP/DOWN, TX/RX or SSR/remove recovery is
added in this lifecycle unit; the dedicated PAS MLME table still rejects radio
operations. No new phone installation or test package is produced.

### 0018 构建验证结果

[Actions 40560249082](https://github.com/xxz3312/XAirDrop-17/actions/runs/40560249082)
在源提交 `1db4af3cacf615f2e1229f61b7703a814341faa1` 全部通过：44 项 Python
检查、14 组原生 fixture、完整 WLAN 对象编译、严格模块链接和 7 项选定结构
布局检查。48 个要求的主机符号存在，WLAN 574 条版本记录无不匹配，未解决依赖为空。
工具链和 bindgen 缓存均命中。新增 fixture 在 Actions 中通过 ASan/UBSan；
完整原生 PE allocator/destructor 与真实 MC 竞争仍属于其明确列出的模型边界。

已独立下载紧凑报告 ZIP 并核对大小和 SHA-256，重新生成的 fixture 源码 SHA、
五个目标原生文件及三个 owner 文件哈希全部一致。完整诊断大包仅记录 GitHub
报告的哈希，未独立下载，也不可安装。结果见
[PE 会话构建报告](research/popsicle-owned-pe-session-build-pass.json)。

本轮没有在手机调用新 PE API，没有启用 START/STOP/频道或 TX/RX。
下一项是频道原生参数、regulatory/concurrency 校验与专用 PAS MLME 的
START/STOP/DOWN 及真实响应闭环，须一起更新已启动会话的停止与回收顺序。

## 0019：owned MC 频道参数准备

新增一次性的 `mishare_runtime_ndi_channel(owner, freq)`，前提是 owned NDI、
legacy/WMA/self-peer 和 PE session 均已完成准备。频道请求独立持有 MAC VDEV
引用，由与 PE 相同的 MC 调度线程执行，带 flush 回调；destroy 等待请求实际完成
后才可以排队删除 PE。排队成功与参数准备成功分别记录。

本阶段只准备 HT20 的 2.4/5 GHz 频道。先确认同一个 PE 指针、owner、VDEV、
角色和 self MAC，要求原生 MLME 仍为 INIT。目标 regulatory API 拒绝无效、
passive/disabled、DFS 及不匹配的 20 MHz bonding；拒绝 6 GHz。再检查没有活动
连接、没有扫描，使用已验证的每频段 NSS 和法规功率，调用目标原生
`lim_pre_vdev_start`，并核对最终 desired channel 的频率、20 MHz 宽度和中心频率。
输入/法规/并发拒绝发生在参数修改之前。原生参数准备错误或输出不一致可能留下
部分主机字段，owner 会保留资源并进入 quarantine，不会当成可重试成功。

这些检查只是当时的状态，不是给后续 START 的法规或并发租约。START 必须再次
验证并完成政策/硬件模式与 WMA 的启动前处理；本阶段没有提交 WMI、改变原生
MLME 状态或实现频道跳转。`channel_prepared` 仅代表这次主机频道参数准备完成，
不代表完整 START 参数、UP 或无线可用。

源码核对还确认不能直接转接普通 monitor 流程：其 start_continue 会改 pdev
全局统计，stop/down helper 的一些发送错误路径仍会发送 MLME 完成事件，
`lim_send_switch_chnl_params` 也会改变全局 deferred-message 状态并在内部发 WMI。
后续 PAS 启停须独立关联真实提交、响应、PM 锁与 STOP/DOWN 结果，不能直接以
这些 helper 返回成功为固件成功。专用 PAS MLME 表与 START type=9 拒绝门仍保留。

新增 Actions-only fixture 执行实际 owner 与新增 channel/post/flush helper，
覆盖 preflight 拒绝、请求分配/引用/排队失败、早到回调、取消、按频段选 NSS、
输出不符与部分准备失败、错误身份/重复完成以及 pending 时禁止提前 teardown。
原生 regulatory/scan/policy 和完整 `lim_pre_vdev_start` 是明确的模型边界；
后者会随完整 WLAN 编译，但这组 fixture 不执行其完整实现。不新增上机调用者。

## 0020：START/STOP 响应解码与会话匹配补强

接入 START 前检查发现，目标 WMI START 解码器把 32 位固件 vdev ID 直接写入
公开的 8 位字段；未知响应类型仅打印日志，随后仍返回成功，零初始化的类型
可能被解释为 START。STOP 解码器还直接解引用 fixed_param，且其 32 位输出
在后续 timer / owner 接口会缩窄。上述情况可能误触另一个 ID 的等待事务。

新增补丁在 START 缩窄前拒绝超过 255 的 wire ID，未知 START/RESTART 类型
明确返回错误；STOP 检查 fixed_param、输出指针和 wire ID，并在原生 STOP
handler 的 timer 查询之前再次检查范围。合法响应保留原有回调路径，公开结构
布局不变。这里的 255 是字段可表示上限；实际 vdev 是否存在仍由原生 timer /
对象管理器判断，不把所有 0–255 ID 当成有效会话。

新增 Actions-only 回归直接执行完整原生 START/STOP TLV 解码函数、完整原生
响应 handler、真实 registry 和 transaction 代码，覆盖 263→7 截断别名、未知
类型、空 fixed_param、timer 错误、RESTART 隔离、普通模式回调与 PM 清理。
TLV envelope / wire 字段、对象管理器、timer、PM 与 RX ops 使用主机模型；
不测试真实二进制 TLV 校验、IRQ/MC 竞争或固件。原有 origin fixture 继续验证
除明确新增的 STOP 范围检查外，原生响应文件仅含已记录的 bounded insertions。

本项不增加运行时调用方，不发送 START/STOP，不开放专用 PAS MLME 操作表。
完整启停、DOWN、SSR/remove 和 TX/RX 接线仍待完成。构建结果须以本次 Actions
实际产出为准，不能沿用 0019 的成功记录。


### 0020 构建验证结果

[Actions 40569344422](https://github.com/xxz3312/XAirDrop-17/actions/runs/40569344422)
在源提交 `dde8d940599f9eb207950c0ce6f2a8da16d5cede` 全部通过：44 项 Python
检查、16 组原生 fixture、完整 WLAN 编译、严格链接与 7 项选定结构布局检查。
51 个要求符号存在，WLAN 574 条版本记录无不匹配，未解决依赖为空。
工具链/bindgen 缓存均命中。新增完整响应 fixture 通过 ASan/UBSan。

紧凑报告 ZIP 已独立下载并核对大小、SHA-256；本地重新生成的完整响应 fixture、
原有 origin fixture C 哈希以及三个相关原生文件哈希均与报告相同。完整诊断大包
仅记录 GitHub 报告的哈希，未独立下载，也不可安装。详见
[响应检查构建报告](research/popsicle-start-stop-response-build-pass.json)。

后续仅修正 origin 报告中的范围标签：应为“origin 插入及 STOP ID guard”，
而非旧的“仅 origin 插入”；生成的 C 和被编译的原生代码未变化。
本轮未在手机发送新命令。START/STOP 的完整 owner/MLME/WMA 调用闭环仍未实现；
尤其 STOP 回应不代表 DOWN 与 PM/runtime lock 已清理，不可据此直接释放会话。

## 0021：owned START 原生参数准备

启动前的源码核对确认，普通 `wma_pre_vdev_start_setup()` 会再次创建 DEFAULT
peer，不能直接用于已有 owned self-peer 的 PAS 会话。新增私有
`mishare_runtime_ndi_start_plan(owner)`，在已完成 channel 准备后，由一次性的
MC request 重新检查 PE/owner 身份、INIT、法规、扫描、活动连接及 WMA slot。
WMA 检查要求已存在的 self-peer 属于同一个 VDEV 且类型为 SELF；不创建第二个 peer。

随后调用目标完整原生 `vdev_mgr_start_param_update()`，核对 HT20、频率/中心频率、
每频段 NSS、phy mode、法规功率和非 MLO 参数，仅复制不含指针的参数摘要。
不保存可直接发送的 WMI 参数。后续 START 必须在实际提交前重新检查并重建。
原生构造函数在非 MOBILE_DFS_SUPPORT 配置下，AP 模式判断会退化为 true，可能
改全局 DFS 状态；本 helper 对该配置明确返回不支持，不把它当成主机参数准备。

owner 分开记录 request/submitted/completed/ready 和实际错误，destroy 必须先等
pending request 完成；request 自带 VDEV 引用及 scheduler flush 回调。异常身份、
部分参数准备失败或原生输出不一致保留资源并 quarantine。队列失败或 flush 不会
被当成参数准备成功。原有类型 9 命令门、专用 PAS MLME 拒绝表及所有无线门保持关闭。

新增 Actions-only fixture 执行真实 owner、owned WMA checker、MC/flush helpers 和
完整原生 START 参数构造函数。外部对象/法规/调度、lim_pre_vdev_start、MLO/11be
子 helper 与完整 PE allocator/destructor 仍为模型边界。该实现属于完整启停接入
的启动前子阶段；没有发送 START/STOP/DOWN、修改原生 MLME 状态或增加上机入口。
完整 MLME/WMA 启停、PM 锁释放、SSR/remove 与 RAW 收发仍待接通。


### 0021 构建验证结果

[Actions 40575306804](https://github.com/xxz3312/XAirDrop-17/actions/runs/40575306804)
在源提交 `d3514465a7f983170b27c09d4d3edac72603878d` 全部通过：44 项 Python
检查、17 组原生 fixture、完整 WLAN 编译、严格链接和 7 项选定结构布局检查。
56 个要求符号存在，WLAN 574 条版本记录无不匹配，未解决依赖为空。
工具链/bindgen 缓存均命中，新增 fixture 通过 ASan/UBSan。

紧凑报告 ZIP 已独立下载并核对大小与 SHA-256，重新生成的 fixture、三个原生
文件及三个 owner 文件哈希均与报告一致；原生 START 参数构造函数与固定目标
原文完全相同。完整诊断大包只记录 GitHub 提供的哈希，未独立下载，也不可安装。
详见 [START 参数准备报告](research/popsicle-owned-start-plan-build-pass.json)。

MLME 保存的是已转换的 WMI PHY mode，校验使用 WMI_HOST_MODE 的 HT20 常量，
而非 WLAN 主机枚举。WMA 检查在读取 service bitmap 前拒绝空 WMI handle 或
interfaces；对应失败用例会保留完整 owner。没有启用 START/STOP/DOWN 的发送、
专用 PAS MLME 回调或上机调用方；完整启停闭环仍是下一处待实现内容。

## 0022：owned NDI 原生 MLME 启停控制

新增显式 `mishare_runtime_ndi_start(owner)`，只接受已完成资源、上下文、PE、
频道与 START plan 的 owner。没有新增默认 HDD/Wonder 调用方。radio controller
单独持有 VDEV 引用；其 MC 请求及正在执行的回调全部退出后，才允许移除 registry
和释放引用。runtime destroy 在原有 PE/peer/VDEV/DP 删除之前先驱动 radio drain。

专用 PAS 表的启停回调仅在匹配的 radio controller 存在时工作；未绑定时仍拒绝。
原有 STA/AP/monitor 表不变。调用原生 START 前，在 MC 上重新验证并构造参数，
随后从原生 MLME START 事件进入 `vdev_mgr_start_send`。真实 target-if START/STOP
来源继续由原有 transaction registry 区分固件响应和超时；通用发送错误进入隔离。
完整 START 响应复制到 MC 请求，避免保留原生事件缓冲指针。NDI host-only UP 验证
相同 WMA/legacy/self-peer，复用原生兼容判断，不发送 WMI UP，随后清理 START PM 锁。

关闭时由原生 MLME DOWN 路线进入 STOP。PAS 不在 disconnect callback 删除
self-peer，而是在真实 STOP 响应之后执行 DOWN。DOWN 没有固件 ACK：状态中的
`down_accepted` 只表示原生提交成功并执行 PM 清理。只有此后真正返回 native INIT，
才能继续旧的 PE、自有 peer、VDEV DELETE 和 DP 最终释放。DOWN 错误不发布
DOWN_COMPLETE；START/STOP 超时、未知发送结果、响应队列失败/flush 及上下文
异常保留全部父资源。嵌套 MLME 回调使用不重新加锁的 `_sync` 事件接口；入口请求
使用带锁接口。普通 monitor 的全局统计、SME stop 通知和无条件完成路径不复用。

新增 Actions-only fixture 执行生产 owner/radio/registry、完整原生 target-if
START/STOP/DOWN 发送、START/STOP 响应处理、owned WMA wrapper、NDI UP 兼容函数
和 PM helper。完整 native SM、WMA START 后处理、core send wrapper、调度/IRQ、
对象/法规/DP 和二进制 TLV 提取仍为明确的模型边界；完整 native SM 随 WLAN 编译。
尚未进行手机加载、固件接受、硬件模式/并发租约、TX 队列、SSR/remove 或收发验证。
默认可用性和 Wonder init 门保持关闭，不制作安装包。


### 0022 构建验证结果

[Actions 40582653523](https://github.com/xxz3312/XAirDrop-17/actions/runs/40582653523)
在源提交 `fa02b5dfb7d4e394b48b22e389b0c6fbcd206b70` 全部通过：44 项 Python
检查、18 组原生 fixture、完整 WLAN 编译与严格链接。65 个要求符号存在，
WLAN 574 条版本记录无不匹配、未解决依赖为空，7 项选定结构布局 MATCH。
工具链/bindgen 缓存命中；新增 radio 回归在 ASan/UBSan 下通过。Kbuild 已明确
编入 `wlan_hdd_mishare_radio.o`，生产对象及最终模块均通过符号存在性检查。

紧凑报告 ZIP 已独立下载并核对大小与 SHA-256；本地重新生成的 fixture、六个
原生文件和八个生产文件哈希均与报告一致。完整原生 SM 源文件与固定目标版本
逐字节相同，其 SHA-256 为
`81ed7e217c9e8ba849c2cd13b6f95f708acd0b8e1abc1dc52454a6959f504649`。
完整诊断大包只记录 GitHub 提供的哈希，未独立下载，也不可安装。
详见 [启停生命周期报告](research/popsicle-owned-radio-lifecycle-build-pass.json)。

这些证据证明 owned 启停代码和真实原生传输函数的离线接入；不证明完整原生
SM/WMA 已运行、固件接受 START 或无线可用。默认调用门仍关闭，手机未加载。
启用前优先补 SSR/remove/隔离恢复与并发/硬件模式资源预留；RAW TX/RX、Wonder
回调和 Apple 端到端传输仍待实现与实测。

## 0023：SSR/remove/module-stop 的旧 owner 准入栅栏

HDD 原生 SSR notifier、remove 和实际模块停止前分别标记匹配 psoc 的全部 owned
owner。首次原因保留，重复通知不会重置它；runtime/NDI 标记 blocked，radio 标记
BLOCKED/closing，事务标记 QUARANTINED 并保留 pending、serial、submitted/replied
证据。不发送 STOP/DOWN/DELETE，不清 PM 锁，也不释放引用或发布完成事件。

显式创建先验证实际 HDD 上下文、psoc 身份、ENABLED 状态与 recovery/unload/bad/
module-stop 标记。PE、频道、START 参数准备和 radio MC 请求在执行前再次验证
引用中的 VDEV 与不透明 owner token；被栅栏阻止的请求只退还自身队列资源及
引用，不能访问 PE/WMA 准备上下文或提交新启停命令。回调和事件 registry 同样
保持隔离；重初始化、迟到 free 通知和相同 psoc 的另一个 MAC 都不能复活旧 owner。

这是非阻塞的“关闭准入”，不是已执行任务、IRQ、timer、native scheduler 或固件
的静止屏障。读检查与实际执行之间仍需原生停机同步；完整在途工作屏障、父资源
最终回收、替换 psoc/地址重用、活动 owner 下安全卸载与模块文本寿命仍未完成。
因此默认 HDD/Wonder 调用门继续关闭，也不以此声明 SSR 恢复完成。

新增 Actions-only 回归将执行生产 owner/radio/event registry、原生健康判断和精确
停机调用插入，覆盖 28 组阶段/flush 组合、同 psoc 新 MAC 拒绝、错误 psoc/owner、
重复停机/重初始化、迟到响应与线程锁竞争。完整 HDD shutdown、native SM/WMA
后处理、scheduler/IRQ/对象/DP 同步仍是模型边界。编译与实机验证结果另行记录。


### 0023 构建验证结果

[Actions 40619757403](https://github.com/xxz3312/XAirDrop-17/actions/runs/40619757403)
在源提交 `541f91ce8328a10af27cbdcc0ed3594f0676a02d` 全部通过：44 项 Python
检查、19 组原生 fixture、完整 WLAN 编译与严格链接。70 个要求符号存在，
WLAN 574 条版本记录无不匹配，未解决依赖为空，7 项选定结构布局 MATCH。
工具链/bindgen 缓存命中，新增停机回归在 ASan/UBSan 下通过。频道测试提取器
保留并执行实际新增准入检查；另外以剥离明确新增块后的原文哈希审计普通路径。

紧凑报告 ZIP 已独立下载并核对大小与 SHA-256；重新生成的 fixture、三个原生
文件和七个生产文件哈希与报告一致。三个原生文件移除本阶段明确插入后与上一
阶段逐字节一致；完整原生 SM 源文件与固定目标版本一致。完整诊断大包仅记录
GitHub 提供的哈希，未独立下载，也不可安装。
详见 [停机准入栅栏报告](research/popsicle-shutdown-admission-build-pass.json)。

这些检查没有执行完整 HDD 原生 shutdown 或证明在途任务/IRQ/timer 已排空，
没有释放隔离 owner，也没有验证活动 owner 下卸载、模块文本寿命或 psoc 地址
重用。默认调用门继续关闭；安全回收、并发预留、RAW/Wonder 和实机联调仍待补齐。

## 0024：owned MC 任务排空证据与 never-wired host 回收

PE、频道、START plan 和 radio 消息在发布前持有 owner 任务 reservation；worker
在进入原生执行前另记 active，完成发布之后才归还 reservation 与请求的 VDEV 引用。
停机准入与 get/enter 使用同一 registry 锁：停机后不能获得新 reservation 或进入
新的执行。已进入的任务允许退回 active/reservation，不清计数、不假造回调。
计数下溢、溢出或 active/reservation 不一致会留下永久 work_error。

在固定目标 `cds_post_disable()` 的原生 `scheduler_disable()` 成功返回后记录
`mc_stop_seen`。只有已隔离 owner 的 active 和 reservation 均为零、且没有计数
错误，才记录 `mc_drained`。原生 already-disabled 返回而仍有排队任务时不满足
这个条件。这只是已跟踪 owned MC 工作的证据，不是 IRQ/timer/固件排空证明。

新增显式 `mishare_runtime_reclaim_host()`，仅在上述 MC 证据成立后，允许回收
从未接触过固件命令、DP、WMA、legacy extension、peer、PE 或 radio 的纯 host
对象。还需核对 PAS/INIT、对象 cookie、事务 serial=0 和没有扩展对象，复用真实
object-manager 删除、event unbind 与最终 free 通知。存在额外对象引用时保留
owner 并返回 EINPROGRESS；只有实际 final-free 才允许释放 owner。删除失败或
残留组件留下终止错误，不重复删除或清除 quarantine。原停机原因始终保留。

该回收不覆盖已创建 NDI、未知固件发送结果、PM/timer、PE/peer/DP 和 radio
隔离资源；也不授权活动 owner 下卸载、父 psoc 地址复用或模块文本释放。默认
无线调用门保持关闭。native scheduler_disable、单队列与全队列 flush 函数由
新增 Actions-only 回归完整执行；QDF wait/thread/queue 原语和完整 native MC
线程仍为模型，另用 pthread 暂停真实 owned PE callback 验证等待与完成顺序。


### 0024 构建验证结果

[Actions 40642419522](https://github.com/xxz3312/XAirDrop-17/actions/runs/40642419522)
在源提交 `c026f2048a12bfb7ae2d1ffc3a71b77ce783c700` 全部通过：44 项 Python
检查、20 组原生 fixture、完整 WLAN 编译与严格链接。76 个要求符号存在，
WLAN 574 条版本记录无不匹配，未解决依赖为空，7 项选定结构布局 MATCH。
工具链/bindgen 缓存命中，新增排空/回收回归在 ASan/UBSan 下通过。

回归还验证了 radio 请求发布时发生停机：在第二次健康读取时关闭 owner，
不得发送 START，也不得把已隔离状态改写成普通 CANCELLED。排空前的 active/
reservation、already-disabled 分支、延迟 final-free、计数错误、事务历史、
组件残留和删除失败都不能授权提前回收。NDI 资源始终拒绝进入纯 host 回收路径。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成 fixture、四个原生文件与
四个生产文件哈希均匹配。两个修改的原生文件可精确恢复到上一阶段原文，两个
scheduler 文件和完整 native SM 源码与固定目标版本逐字节一致。完整诊断大包
只记录 GitHub 的哈希，未独立下载，也不可安装。
详见 [MC 排空与纯 host 回收报告](research/popsicle-owned-mc-drain-reclaim-build-pass.json)。

该证据不等于真实内核线程/IRQ/timer/固件已验证，也不覆盖 NDI 的 WMA、PE、
peer、DP 与未知发送隔离资源回收。默认无线调用门继续关闭，尚未上机加载。

## 0025：pre-context NDI 的 SSR 回收

新增只覆盖“CREATE/DP attach 完成，但从未准备 legacy/WMA/self-peer/PE、频道、
START plan 或 radio”的显式 `mishare_runtime_reclaim_ndi()`。部分 attach、CREATE
发送未知、DELETE/事务历史、已进入会话的 owner 继续隔离。没有默认恢复调用方。

原生 `cds_post_disable()` 完成 MC、HIF/ISR、HTC、RX 停止后，只有 SSR 标记、
HIF TARGET_STATUS_RESET、有效且 blocked 的 WMI、已排空 owned MC 和精确候选
owner 同时成立，才额外执行原生 WMA/WMI 工作队列清理并开放窗口。没有候选
owner 时不增加 WMI flush。窗口在原生 `cds_close()` 进入时永久关闭，不能重开。
这是驱动记录的复位/停机条件，不是固件物理复位或 DELETE ACK 的独立证明。

回收先核对 PAS/NDI/INIT、空 extension、事务 serial=0，再同步取消无 pending
response、无 runtime PM 锁的准确原生 timer，并执行原生 deinit。timer 状态漂移
或错误会永久保留资源。CREATE 时记录 DP soc cookie；detach 前必须匹配当前父
实例，提交失败不能当作“没有 DP”。统计 ID 的释放来自原生 detach，实际 DP
final-free 回调到达后才能转回 host 类型并进入 object-manager 删除。不会发布
伪造 STOP/DOWN/DELETE 完成，不写普通 delete_replied/dp_freed，不清原始发送历史。

window 关闭后的迟到 DP 回调只记录事实，不授权新的 native 删除；已经进入纯
host 最终删除的 owner 仅能等待真实 final-free 并释放 bookkeeping。调用方必须
保留准确 psoc/DP/timer 父资源及 RTNL/独占父事务，阻止 CDS 继续销毁父上下文，
直到轮询完成；此协调、活动 owner 下安全卸载、模块文本寿命与 psoc 地址复用
尚未实现，因此默认无线入口继续关闭。

新增 Actions-only 回归执行完整原生 CDS post-disable、WMI stop/blocked/work close/
remove-work、timer deinit、owned DP wrapper 和真实 object-manager final-free。
HIF/HTC、QDF scheduler/IRQ/timer/workqueue、完整 DP detach/storage free 和组件
析构仍是模型；DP callback 在 native storage free 之后的来源顺序另行源码审计。
完整 WMA/self-peer/PE/STARTed NDI/PM 恢复回收及手机固件行为仍未完成验证。


### 0025 构建验证结果

[Actions 40667786202](https://github.com/xxz3312/XAirDrop-17/actions/runs/40667786202)
在源提交 `b896edfb376938c5c27be5d801c193cb0e95a896` 全部通过：44 项 Python
检查、21 组原生 fixture、完整 WLAN 编译与严格链接。82 个要求符号存在，
WLAN 574 条版本记录无不匹配，未解决依赖为空，7 项选定结构布局 MATCH。
工具链/bindgen 缓存命中，新增早期 NDI 回归在 ASan/UBSan 下通过。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成 fixture、六个原生文件
与三个生产文件哈希均匹配。三个修改的原生文件移除新增块后与上一阶段原文
逐字节一致；WMI、WMA main、DP 和完整 native SM 与固定目标版本一致。
完整诊断大包仅记录 GitHub 哈希，未独立下载，也不可安装。
详见 [早期 NDI SSR 回收报告](research/popsicle-early-ndi-reset-reclaim-build-pass.json)。

回归覆盖 native WMI 两条独立事件队列在 window 打开前排空、timer 身份/状态/
取消后漂移、DP cookie/缺失实例/提交失败、inline/延迟/重复 DP 回调、延迟 host
final-free、window 关闭后不得重开及会话/部分 attach 拒绝。原始 CREATE 历史和
quarantine 保留，普通 DELETE ACK 标记不变。父资源协调与自动恢复调用方尚未
接入，已准备或 STARTed 会话仍保留；默认无线入口关闭，没有上机加载或传输验证。

### 0026 父资源拆除前撤销回收窗口

复核原生 HDD 调用链后发现：正常停机在 `cds_close()` 前已调用 `cds_dp_close()`、
关闭并删除 pdev；启动失败回退则先 `dispatcher_pdev_close()` / pdev 删除，再
DP close。因此只在 CDS close 撤销窗口，不能覆盖较早的父资源拆除。

0026 在完整原生 `cds_dp_close()` 的 interrupt detach / timer / DP deinit 前，
以及 `hdd_component_pdev_close()`、`dispatcher_pdev_close()` 的首个组件 close
前，按准确 psoc 永久关闭现有 owner 的恢复窗口。保留 CDS close 的后备关闭。
此变更不改变原生拆除顺序、返回值或 owner 的 quarantine/CREATE 历史。

窗口关闭后，未开始、待 DP 回调、inline DP 已回调但尚未进入 host 删除的 owner
均不能继续访问 timer/DP/MLME 或开始 host 删除；迟到回调不恢复资格。已经完成
host 逻辑删除、仅等最终 free 的路径仍可完成 bookkeeping。无 owner 的原生清理
照常执行，外来 psoc 不能关闭当前 owner 的窗口。

这是关闭后续准入的修正，不是父资源 lease，也不能等待或中止已进入的 reclaim
调用。调用方仍须串行化父资源拆除与所有轮询，并在异步回调期间保留准确父实例；
完整协调器、自动恢复调用方和活动 owner 下安全卸载尚未接入。默认入口关闭。
新增回归执行完整原生 CDS DP close、HDD/dispatcher pdev close；它们调用的实际
DP、IRQ、timer 和组件析构仍为模型，完整 HDD 停机/错误回退路径只做源码审计。

协调器接入约束：正常 HDD stop 在 `cds_post_disable()` 返回错误后仍继续后续
拆除（记录错误并触发断言）；启动失败回退调用点直接忽略该返回值。因此不能
仅让 CDS 返回失败就视为父资源被保留，也不能仅在 `cds_close()` 拦截。未来实现
必须在外层 HDD 拆除流程中明确保留父实例并处理异步完成、失败及上层继续拆除。


### 0026 构建验证结果

[Actions 40675754483](https://github.com/xxz3312/XAirDrop-17/actions/runs/40675754483)
在源提交 `04b809efed826c69dc4914a4c296b18e41beecc4` 全部通过：44 项 Python
检查、22 组原生 fixture、完整 WLAN 编译及严格链接。82 个要求符号存在，
574 条版本记录无不匹配、未解决依赖为空，7 项选定结构布局 MATCH。
工具链与 bindgen 缓存命中；新增回归在 ASan/UBSan 下通过。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成的新增 fixture、三个原生
文件和两个生产文件哈希匹配 CI。三个原生文件移除有界新增块后，均与 0025
原文逐字节一致；生产 runtime C 保持原样。完整诊断大包仅记录 GitHub 哈希，
未独立下载且不可安装。详见 [父资源拆除窗口报告](research/popsicle-parent-teardown-window-build-pass.json)。

原生回归覆盖三个拆除入口、尚未开始/待 DP 回调/inline 已回调但未删 host、
迟到 DP 回调、不可重开窗口、已进入 host final-free 的 bookkeeping、外来 psoc
和无 owner 路径。完整父资源协调器与自动调用方仍待实现，已准备/STARTed 会话
继续隔离；默认无线入口关闭，未在手机加载或验证固件与传输。

### 0027 显式 SSR 批量回收步骤

新增 `mishare_runtime_reclaim_batch()`，供未来外层父资源协调器显式调用；它没有
接入 HDD 自动恢复，也不持有父资源引用。调用方传入权威 owner 句柄表，并在
全部轮询期间保留准确父实例、独占 psoc 事务、串行化创建/删除/回收/父资源拆除。
该表是句柄存储本身，成功项会清空 owner；不得另存可继续使用的别名。

每次进入前，在 registry 锁下按不透明指针匹配，验证准确 psoc、无重复/失效/
外来句柄，并要求列全该 psoc 的所有 owner，包括只等物理 final-free 的 owner。
每个 owner 都必须保持第一停机原因为 SSR、被跟踪 MC 已排空且没有永久计数/
回收错误。不满足准入时整张表不变，不运行任何原生回收。表大小上限 64 是此
helper 的有界扫描限制，不表示硬件支持 64 个 VDEV。

准入后逐项复用原有纯 host 或早期 NDI 回收，不放宽 WMA/peer/PE/START 等
资格限制。每项独立记录结果，已完成项清空句柄，等待项和错误项保留句柄；一次
步骤可以部分完成，先前错误不能被后面的成功覆盖。只有整张表及准确 psoc 的
registry 均为空才返回 0；EINPROGRESS 等真实回调，其他错误须保留父资源诊断。
空 registry 是串行化时点的观察，不是父资源 lease、固件 ACK 或安全卸载证明。

新增回归使用不同 VDEV ID/MAC 的多对象模型，覆盖漏列/重复/外来/失效句柄、
MC reservation、延迟 host final-free、host+早期 NDI 混合表及顺序变化、inline/
延迟 DP 回调、已准备会话保留、错误后成功不得掩盖、父窗口关闭后拒绝推进。
对象分配/ID、QDF、DP storage free 与组件析构仍为模型，完整 HDD 异步暂停、
父实例寿命协调、已准备/STARTed 恢复与实机行为尚未实现或验证。默认入口关闭。


### 0027 构建验证结果

[Actions 40679560456](https://github.com/xxz3312/XAirDrop-17/actions/runs/40679560456)
在源提交 `ceef28434d341d3ea088d349b5942fd1b72ebae8` 全部通过：44 项 Python
检查、23 组原生 fixture、完整 WLAN 编译及严格链接。83 个要求符号存在，
574 条版本记录无不匹配、未解决依赖为空，7 项选定结构布局 MATCH。
工具链与 bindgen 缓存命中；新增多 owner 回归在 ASan/UBSan 下通过。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成的 batch fixture、三个原生
文件和两个生产文件哈希匹配 CI。三个选定原生文件与上一阶段完全一致；移除
新增批量函数后，原 runtime C 与 0026 逐字节一致。完整诊断大包仅记录 GitHub
哈希，未独立下载且不可安装。详见 [显式 SSR 批量回收报告](research/popsicle-ssr-batch-reclaim-build-pass.json)。

回归执行生产批量步骤与现有单 owner 控制器，验证多对象身份、全表覆盖、MC
准入、混合异步推进、延迟 final-free、逐项错误与部分完成；不会把未支持会话
当作已恢复。完整外层父资源协调和自动调用方尚未接入，默认无线入口关闭，
手机加载、固件接受和 Apple 传输仍未验证。

### 0028 批量准入错误优先级修正

复核批量准入时发现：原循环遇到首个 MC 尚未排空的 owner 就立即返回
EINPROGRESS，会掩盖 registry 后面 owner 的永久计数/回收错误、错误停机原因，
甚至尚未列入权威表的 owner。结果取决于 registry 链表顺序，可能使未来协调器
错误地继续等待一个已经不能推进的批次。

现在先独立验证准确 psoc 的完整表覆盖，再扫描全部 owner 的准入状态；MC 等待
只记为候选结果，继续查找永久错误或非 SSR 原因。漏列先报 EBUSY，永久错误报
EUCLEAN、非 SSR 报 ESHUTDOWN；只有没有这些错误时才返回 EINPROGRESS。
所有拒绝均保持句柄、逐项结果、原生回收资源和待处理 reservation 不变。

新增十组双 owner 场景覆盖两种 registry 顺序、真实 work_put 下溢、永久 reclaim/
recovery 错误、错误首停原因和漏列 owner。Actions-only 负对照把 runtime 精确
恢复为上一阶段源码，要求同一新增期望结果断言失败；编译失败或其他失败不能
当作负对照通过。原生 C 不在本地编译。

此变更修正现有显式接口的返回语义，不增加自动恢复、父资源引用、HDD 拆除暂停
或已准备/STARTed 会话支持。完整父资源协调与实机验证仍待完成，默认入口关闭。


### 0028 构建验证结果

[Actions 40687248667](https://github.com/xxz3312/XAirDrop-17/actions/runs/40687248667)
在源提交 `c0616a7bad3565b893e51774508b3d74889e4fa1` 全部通过：44 项 Python
检查、23 组原生 fixture（扩展既有批量回归）、完整 WLAN 编译及严格链接。
83 个要求符号存在，574 条版本记录无不匹配、未解决依赖为空，7 项选定结构
布局 MATCH。工具链与 bindgen 缓存命中。

新增十个顺序/错误场景在 ASan/UBSan 下通过，拒绝时句柄表、逐项结果和原生回收
计数不变。负对照实际编译并执行精确恢复的 0027 runtime C；它被新增期望结果
断言拒绝，验证此回归能够捕获旧实现中的等待掩盖错误问题。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成的 fixture、三个原生文件
与两个生产文件哈希匹配 CI。选定原生源码保持原样；移除批量函数后，其余
runtime C 与 0026 逐字节一致。完整诊断大包仅记录 GitHub 哈希，未独立下载且
不可安装。详见 [批量准入错误优先级报告](research/popsicle-batch-preflight-priority-build-pass.json)。

这仍是离线源码/模型/编译验证。完整 HDD 父资源协调、自动恢复调用方、已准备/
STARTed 会话恢复及实机验证尚未完成，默认无线入口关闭。

### 0029 普通 NDI 完成事件身份与顺序校验

准备态恢复还需要 peer/WMA/legacy 与父资源协调，不能仅凭 blocked 标志解除
隔离。复核时先发现普通 DP final-free 回调直接解引用 owner token，且不区分
重复、过早或错误回收路由；SSR DP 回调此前已具有 registry 身份校验。

普通回调现在先在锁下匹配 live registry 中的不透明 token，未知/已释放 token
不解引用。只有 NDI active、普通 detach 已启动、DELETE 已提交且真实回执已到、
此前尚未收到普通 DP 完成，才记录 dp_freed。发布后不再访问 owner。正常 inline/
延迟回调和停机栅栏后的有效回调仍可记录实际释放事实，不重新开放清理准入。

过早、重复或跨 SSR/普通路由的 DP 回调，以及重复/非固件 DELETE 通知，记录
永久 completion_error 并保留历史。普通销毁、纯 host 回收、SSR NDI 回收、候选
窗口资格及批量准入均不能绕过该错误；不会伪造 DELETE ACK 或 DP final-free。

新增 Actions-only 回归覆盖有效 inline/延迟完成、停机后有效发布、未知与释放后
重复 token、过早/重复/错误路由、DELETE 重复/超时通知及各回收入口保留资源。
使用生产 owner 控制器与原生 DELETE response/DP wrapper/object-manager free；
完整 DP storage free、QDF/timer、组件析构仍为模型。指针 registry 比较不能证明
地址复用/ABA 或模块回调文本寿命，完整父资源协调、准备态/STARTed 恢复和实机
验证仍待完成，默认入口关闭。

既有批量优先级负对照改为精确恢复 0027 的批量函数，并独立核对历史函数哈希，
其余新完成事件校验保持当前实现。这样仍验证旧批量错误被新增断言捕获，同时
避免后续独立修正被整份旧 runtime 覆盖；0028 的整份 runtime 对照证据保持原样。


### 0029 构建验证结果

[Actions 40691954631](https://github.com/xxz3312/XAirDrop-17/actions/runs/40691954631)
在源提交 `0629027538c5303945a47483ec9338e6b8d88207` 全部通过：44 项 Python
检查、24 组原生 fixture、完整 WLAN 编译及严格链接。83 个要求符号存在，
574 条版本记录无不匹配、未解决依赖为空，7 项选定结构布局 MATCH。
工具链与 bindgen 缓存命中，新增完成事件回归在 ASan/UBSan 下通过。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成的 completion/batch fixture、
三个选定原生文件与三个生产文件哈希匹配 CI。选定原生源码保持原样。批量函数
负对照的历史函数哈希已独立与 0027 源码核对，并在 CI 被既有顺序断言拒绝。
完整诊断大包仅记录 GitHub 哈希，未独立下载且不可安装。
详见 [普通 NDI 完成事件报告](research/popsicle-ndi-completion-integrity-build-pass.json)。

回归验证正常完成路径仍能释放、未知/释放后 token 不被解引用、错误回调记录
永久错误、合法栅栏后完成仅发布事实；错误状态下各显式入口保留资源。完整
父资源协调、准备态/STARTed 恢复、地址复用、模块回调文本寿命和实机验证仍待
完成，默认无线入口关闭。

### 0030 普通 DELETE/DP 已完成后的 NDI host 收尾

显式 `mishare_runtime_reclaim_ndi()` 新增普通 host 逻辑删除尚未开始、传输资源
已完成的窄分支：普通 DELETE
已提交且真实回执已记录，普通 DP detach 已成功提交且真实 final-free 已记录，
timer_ready/stats_owned 已由普通流程清除；同时必须从未准备 WMA/legacy/self-peer/
PE/频道/START 参数或 radio，且无 completion/work/reclaim/recovery 永久错误。

这些 owner 与原早期候选一起，经过既有 CDS 的 HIF/HTC/RX 停止、blocked WMI
和独立 WMI 队列排空资格化后才开放 SSR 窗口。不能仅因 DELETE/DP 已完成就
省略窗口；如果 DP 回调在资格化帧过去后才到，本分支只等待，不自动补开窗口。
窗口在父资源拆除前仍永久关闭。默认路径没有 owner 时不增加 WMI flush。

窗口内再次验证准确 PAS/NDI/INIT、空 extension、零事务历史与完整候选事实后，
只退回 host 类型、启动对象管理器删除并等真实物理 final-free，不再发送 DELETE、
清理 response timer、detach DP 或释放统计 ID。保留普通 CREATE/DELETE/DP 历史，
新增 ndi_completed_reclaim 标识来源，不写 SSR timer/DP 尝试或完成标记。
已进入 host 逻辑删除的 owner 仍可在窗口关闭后仅完成最终释放 bookkeeping。

共享 host 删除在原生操作前后都检查 completion_error；若删除期间出现错误回调，
保留诊断 owner 与已发生的物理释放事实，不再把本次步骤报告为成功。不能回滚
已经发生的 native free，也不能依赖此检查代替父资源/并发执行屏障。

新增回归覆盖普通 inline/延迟 DP 完成、批量推进、延迟 VDEV final-free、原始
历史保留、未完成/晚到 proof、窗口关闭、native/事务漂移、对象删除失败、删除中
错误回调和已准备 peer 上下文拒绝。完整 DP/QDF/HIF/组件析构仍为模型；父实例
协调、自动恢复、准备态/STARTed 回收、地址复用与手机固件验证继续保留为未完成。

普通 detach 新增独立 dp_detach_submitted 标记，只在原生 wrapper 成功返回后设置。
它与 dp_detaching 尝试标记、dp_freed 回调事实分别记录；即使 inline 回调先到，
也不能把随后失败的提交返回当作成功。新增回归包含“inline free 后返回失败”，
该 owner 保持隔离，不进入已完成收尾分支。


### 0030 构建验证结果

[Actions 40708768545](https://github.com/xxz3312/XAirDrop-17/actions/runs/40708768545)
在源提交 `34ab0f87546255bbcf67ecdf34026f72d5d8cce6` 全部通过：44 项 Python
检查、25 组原生 fixture、完整 WLAN 编译及严格链接。83 个要求符号存在，
574 条版本记录无不匹配、未解决依赖为空，7 项选定结构布局 MATCH。
工具链与 bindgen 缓存命中，新增收尾回归在 ASan/UBSan 下通过。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成的 completed fixture、
三个选定原生文件与三个生产文件哈希匹配 CI。选定原生源码保持原样，历史
批量函数负对照仍被既有顺序断言拒绝。完整诊断大包仅记录 GitHub 哈希，未
独立下载且不可安装。详见 [普通资源已完成 NDI 收尾报告](research/popsicle-completed-ndi-host-reclaim-build-pass.json)。

新增回归验证 qualified 窗口内的单 owner/批量收尾、真实 final-free 等待、普通
完成历史保留、无新增 DELETE/DP/timer 操作；inline free 后提交失败、缺失/晚到
完成、已准备上下文、窗口关闭和状态漂移继续隔离。host 删除中出现错误时保留
诊断 owner，即便 native VDEV 已经实际释放也不报告成功或撤销 free。

原普通 host 删除已经开始的隔离对象仍未由此分支接管。完整父资源协调、自动
资格重查/恢复、准备态与 STARTed 会话、地址复用、模块回调文本寿命和手机验证
仍待完成，默认无线入口关闭。

### 0031 普通 host 删除已接受后的最终记账

新增 host_delete_accepted 来源标记：仅在原生逻辑删除成功、事件解绑完成、自持
VDEV 引用及句柄已交出后记录，在最后的自持引用释放前发布。组件最终释放拒绝
也会记录永久 reclaim_error，不能让 SSR 将它当作仅需等待的正常状态。

显式 mishare_runtime_reclaim_final() 先在 registry 匹配不透明 owner token，再核对
第一停机原因为 SSR、被跟踪 MC 已排空、没有永久错误、host 删除接受标记存在，
且 vdev/ref/events/radio/PE cookie、NDI active/legacy/WMA/timer/stats 所有当前持有
关系均已解除。未收到真实 final-free 时返回 EINPROGRESS；只有准确的 free 通知
到达才解除 registry 并释放 owner。函数不调用任何原生删除、组件 getter、DP、
WMI 或 timer，也不重开窗口。批量回收优先分派到这个纯记账分支。

这可以完成普通 host 删除先开始、随后 SSR 保留的 owner，也允许正常清理完成
后的 prepared 历史；它不执行 prepared/STARTed 恢复。窗口关闭之后仍须由调用方
保留父实例直到真实物理释放，不能把窗口关闭或仅有逻辑删除当作父资源可销毁。
构造 NULL 路径缺少接受来源、仍有 native handle、组件 veto、完成/计数/恢复错误
及非 SSR 首停原因均拒绝。未知/已释放 token 不解引用；地址复用/ABA 未认证。

新增 Actions-only 回归覆盖纯 host、普通 NDI 与已正常清理 prepared 上下文，
直接/批量等待、窗口关闭后记账、未知/释放后 token 与永久错误拒绝。对象分配、
QDF/DP/timer、组件析构及父引用寿命仍为模型，完整父资源协调与实机仍未验证。
历史批量函数负对照改为不可变源码常量（同一已核对 SHA），便于独立扩展分派，
仍要求旧优先级实现在既有期望结果断言失败。


### 0031 构建验证结果

[Actions 40724040219](https://github.com/xxz3312/XAirDrop-17/actions/runs/40724040219)
在源提交 `f2be7bdf6bf2c444c8eac7896521b134d0a056d3` 全部通过：44 项 Python
检查、26 组原生 fixture、完整 WLAN 编译及严格链接。84 个要求符号存在，
574 条版本记录无不匹配、未解决依赖为空，7 项选定结构布局 MATCH。
工具链与 bindgen 缓存命中，新增最终记账回归在 ASan/UBSan 下通过。

紧凑 ZIP 已独立下载并核对大小与 SHA-256；重新生成的 final fixture、三个选定
原生文件与三个生产文件哈希匹配 CI。选定原生源码保持原样，历史批量函数的
不可变源码常量哈希一致，负对照仍被既有期望结果断言拒绝。完整诊断大包仅
记录 GitHub 哈希，未独立下载且不可安装。
详见 [host 最终记账报告](research/popsicle-host-final-bookkeeping-build-pass.json)。

正常 host、普通 NDI 与已正常清理 prepared 上下文，均在真实 final-free 后才
释放 owner；直接和批量分派没有再次触发 native 删除/DP/WMI/timer。组件 veto、
缺失接受来源、当前持有关系、错误原因和永久错误保留。它不执行 prepared/
STARTed 恢复，也未实现父资源协调、自动恢复、安全活动卸载、地址复用或手机
验证；默认无线入口保持关闭。

### 0032 批量最终记账状态预检

0031 的批量分派在逐项操作时才核对 accepted host-delete 的最终记账状态。
因此某项虽记录删除接受，但仍带 native handle 或其他矛盾字段时，健康项可能
先执行清理，随后才报告该项 EUCLEAN；等待中的 MC 项也可能先遮住这个错误。

提取 registry 锁内的纯元数据校验函数，由直接 final 入口与批量整表预检共用。
accepted host-delete 项必须已 draining/allocated，且 vdev/ref/events/radio/PE
cookie 与 NDI active/legacy/WMA/timer/stats 当前持有关系为空。完整覆盖与首停
原因、永久错误检查仍先执行；形状错误优先于 MC 等待，拒绝时所有 item/result
及 native 资源不变。预检不解引用这些 native 字段、不访问父组件或执行清理。

正常但仍等实际 VDEV final-free 的项保持逐项 EINPROGRESS，其他健康项仍可在
准入后完成。缺少 accepted 标记的 owner 仍按既有 host/NDI 路由判断，不能据此
推断已接受删除。预检不保证所有 native 状态都可回收，也不创建父引用或屏障。

扩展原批量 Actions-only 回归：12 种矛盾字段 × 两种 registry 顺序 × 两种 MC
等待状态，共 48 个拒绝组合；另有 4 个有效 deferred-free 对照。所有拒绝均核对
句柄表和结果不变、健康 owner 未开始删除，native delete/DP 次数不变。新增仅
移除本阶段整表校验的负对照，必须在表未改变断言失败；历史优先级负对照保留。


### 0032 构建验证结果

[Actions 40730487714](https://github.com/xxz3312/XAirDrop-17/actions/runs/40730487714)
在源提交 `29253f6c843be60305bcb003fecfaa734ec0eebf` 全部通过：44 项 Python
检查、26 组原生 fixture、完整 WLAN 编译、CNSS 接口及严格链接。84 个要求符号
存在，574 条版本记录无不匹配、未解决依赖为空，7 项选定布局 MATCH；工具链与
bindgen 缓存命中。批量回归及两个负对照均在 Actions 内执行。

紧凑 ZIP 已独立下载并核对大小和 SHA-256；本地生成的 batch/final fixture、
三个选定原生文件及三个生产文件哈希与报告一致。选定原生文件相对 0031 未变。
完整诊断大包仅记录 GitHub 哈希，未独立下载且不可安装。
详见 [批量最终记账预检报告](research/popsicle-batch-final-preflight-build-pass.json)。

首轮测试错误地在注入伪造 radio 句柄后调用快照，UBSan 将其拒绝；测试改为
直接读取模型状态字段后，重新执行本轮完整验证通过，生产实现未因此修改。
离线验证不代表完整私有 ABI/KCFI、实机加载或固件接受；父资源协调、准备态
恢复、安全卸载、地址复用和无线收发仍待完成，默认无线入口关闭。
