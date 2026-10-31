## 最新阶段 0077

新增已获准 START 在准备入口前遇到 SSR 的显式回收：共享 radio 锁保护 preparation-entry 与封锁观察，work_exit、reservation 和 pending 释放后才发布独立 body-abort origin。已进入准备函数的情况继续保留资源；准备返回后的复核若发现已封锁，不会覆盖 BLOCKED 或继续进入 SM。新增双边界零准备/SM 计数、18 类拒绝、准备中/准备后 fence、混合来源及私有事实负对照。CI [41190764518](https://github.com/xxz3312/XAirDrop-17/actions/runs/41190764518) 已通过 53 项 Python 检查、新模型与私有 abort 负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希、新 origin 实际链接和模块记录已复核。实际准备已执行/START/UP 的 reset 回收、自动父资源协调和完整接收路径仍未完成，backend 关闭，手机无需操作。见[0077](POPSICLE-ABORTED-START-RESET-0077.md)。

## 阶段 0076

新增 SSR 先封锁已排队 START、回调后进入但 work_enter 在 radio_execute 前拒绝 ESHUTDOWN 时的显式回收。私有拒绝事实、原始 SSR、单独 runtime origin、INIT/空事务/零 users/pending 共同核对；保留 BLOCKED/ESHUTDOWN 和请求历史，不冒充 flush、队列失败或 DOWN。新增准备/SM 边界计数、16 类拒绝、封锁时序与私有事实负对照。CI [41187930152](https://github.com/xxz3312/XAirDrop-17/actions/runs/41187930152) 已通过 53 项 Python 检查、新模型与私有 refusal 负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希、新 origin 实际链接及模块记录已复核。START 回调内准备/SM 已执行及 START/UP 的 reset 回收、自动父资源协调和完整 monitor 仍未完成，backend 关闭，手机无需操作。见[0076](POPSICLE-REFUSED-START-RESET-0076.md)。

## 阶段 0075

新增 START 被原生 scheduler 明确拒绝、未入队未执行后的显式 SSR 回收。私有 pre-insertion 拒绝事实、原错误、runtime 提交历史、INIT/空事务共同核对，保留 radio_requested 和原始错误；不制造 MC flush、DOWN 或 ACK。新增 native scheduler post 分支模型、失败回收模型及私有错误匹配负对照，CI [41184172003](https://github.com/xxz3312/XAirDrop-17/actions/runs/41184172003) 已通过 53 项 Python 检查、新回收模型及私有错误负对照、原生 scheduler post 模型、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希和模块记录已复核。实际 START/UP、自动父资源协调和完整 monitor 仍未完成，backend 关闭，手机无需操作。见[0075](POPSICLE-REJECTED-START-RESET-0075.md)。

## 阶段 0074

新增 queue-accepted START 被原生 MC 停机 flush、回调从未执行时的 SSR controller 回收。实际 flush origin、私有 controller 事实、INIT/零事务/零 callback users 双重核对；先 unlink/ref release，再接续 PE/peer/DP/WMA/对象清理。保留 radio_requested 和 BLOCKED/ESHUTDOWN，仅记录启动前撤销，不造 DOWN/ACK。新增原生队列 flush C 模型、13 类拒绝及私有事实负对照；CI [41175604451](https://github.com/xxz3312/XAirDrop-17/actions/runs/41175604451) 已通过 53 项 Python 检查、新模型及私有 flush 负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；生产/native 哈希、三个新增入口实际链接与模块记录已复核。实际 START/UP、自动父资源协调和完整 monitor 仍未完成，无线 init 关闭，手机无需操作。见[0074](POPSICLE-QUEUED-START-RESET-0074.md)。

## 阶段 0073

显式 SSR 回收扩展到 channel 与可选 START plan 已完成、从未请求 radio START 的 INIT。捕获并复核 PE/desired HT20 几何后，沿用原生 PE 析构及分阶段资源释放；保留准备历史，不重跑准备或伪造 ACK；重复通知以独立 completion_error 保留，不能被 SSR 封锁标记掩盖。新增 2.4 GHz/5240 MHz、9 类原生拒绝、20 类失败/矛盾/重复通知历史及频率检查负对照，并保留 0072 回归；CI 41173256945 已通过 53 项 Python 检查、新模型及负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；native/生产源码哈希、helper 实际链接和模块记录已复核。radio START/UP 回收、自动父资源协调和完整 monitor 尚未完成，无线 init 关闭，手机无需操作。见[0073](POPSICLE-PRE-RADIO-RESET-0073.md)。

## 阶段 0072

扩展显式 SSR 回收到 PE 已成功、尚未请求 channel/START 的 INIT：严格原生会话身份/IDLE/确认定时器预检 → 同步关闭 NDI 响应定时器 → 原生完整 PE 析构 → 0070 分阶段 peer/DP/WMA/legacy/对象回收。保留创建事实，不伪造普通 PE DELETE ACK。新增原生 C 模型、22 类拒绝与 SAE 负对照；CI 41155181814 已通过 53 项 Python 检查、新 PE reset/原生析构模型及负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；两项新 helper 的实际链接、生产与 native 哈希已复核。尚无自动父资源协调、channel/START/UP 回收或完整 monitor，无线 init 保持关闭，手机无需操作。见[0072](POPSICLE-PRE-CHANNEL-PE-RESET-0072.md)。

## 阶段 0071

修复私有 PAS 的 PE 删除错误触及共享 SAE 认证定时器：仅私有类型跳过普通 SAE cleanup，其他类型保留原生行为。新增执行原生完整 PE 析构的 Actions 模型：生产 owner/MC 请求回归复用真实 `pe_delete_session`，检查全部可选分配、DPH 借用数组、确认定时器、MAC VDEV 引用释放顺序，并以漏掉引用释放、撤销 SAE 隔离的两个负对照验证。CI 41123670326 已通过 53 项 Python 检查、原生 PE 析构模型及两个负对照、既有 C 模型、完整编译、严格链接和七项布局检查；生产与 native 哈希已复核。本轮补齐验证，不扩大 SSR 准入；手机无需操作。见[0071](POPSICLE-NATIVE-PE-DESTRUCTOR-0071.md)。

## 阶段 0070

新增 pre-PE prepared NDI reset 回收：能力/归属预检 → 同步关闭响应定时器 → 原生 no-FW force peer detach/object-peer 组件析构 → 实际 DP final-free → WMA/legacy 释放 → 对象实际 final-free。完整 prepare 成功、从未请求 PE/START 的 INIT 才可进入；PE/UP 状态仍不支持。CI 41118167241 已通过 53 项 Python 检查、native WMA 分支/两阶段回收 C 模型与 no_fw=false 负对照、完整 WLAN/Wonder/provider 编译、严格链接及 7 项选定布局。5 个新增入口实际链接与生产源码/native 源码哈希已复核。见[0070](POPSICLE-PREPARED-RESET-0070.md)。

native shutdown 自动协调与父资源租约、PE/UP 回收和完整 monitor 仍未完成；无线 init 保持关闭，无新手机测试。

## 阶段 0069

新增显式 SSR host 回收入口：完整 registry coverage、owned MC、合法恢复策略和实际 final-free 由既有 runtime batch 执行，成功后才关闭 adapter/sync；每次返回恢复最新 runtime 句柄，等待与错误均保留 host 和 idle inhibition。CI 41110041682 已通过 53 项 Python 检查、host 与既有 runtime C 模型、完整 WLAN/Wonder/provider 编译、严格链接及 7 项选定布局；新增入口实际链接、生产源码和重建 C 模型输入哈希已复核。见[0069](POPSICLE-HOST-SSR-RETIRE-0069.md)。

这尚无自动 native shutdown caller，不构成 SSR/remove 父资源租约，也未新增 prepared/UP 回收。无线 init 和完整 monitor 仍未启用，无新手机测试。

## 阶段 0068

原生空闲关机增加专用 DOWN host 生命周期检查：在独占 psoc transition 和 operations 排空后，有 host 即返回 EAGAIN，不进入 module stop。登记覆盖 runtime 创建前、异步清理以及 adapter/sync 最终释放；创建失败撤销登记。完整生产 host + 原生 idle 函数 C 模型已扩展；53 项 Python 检查和精确源审计通过。CI 41101029685 已成功，C 模型、完整编译、严格链接及 7 项选定布局检查通过。见[0068](POPSICLE-IDLE-HOST-GUARD-0068.md)。

这仅保护普通 idle shutdown，不代表 SSR/remove 父资源租约完成。prepared/UP SSR 回收、完整 monitor 和实际无线初始化仍未启用，无新手机测试。

## 阶段 0067

默认关闭的HDD元数据绑定通过私有provider传递managed companion，component master实际安装/解除绑定。发布ops前关闭准入，CLAIM成功后开放；清除前quiesce，有归属时保留component/descriptor/claim，显式retire后才解绑，最终free拒绝仍有归属的实例。公开ops/priv ABI不变。CI 41089242566已通过完整编译、严格链接、3个provider导出、6个Wonder入口和7项选定布局检查；私有/通用两模式C模型通过。

HDD init仍返回EOPNOTSUPP，不创建固件会话。目标remove是void，native caller尚不能以EBUSY阻止父资源拆除；创建/启动接线仍须等父资源租约和prepared/UP SSR恢复完成。完整monitor未接通，无新手机测试。见[0067](POPSICLE-MANAGED-BINDING-0067.md)。

## 阶段 0066

Wonder入口新增显式managed生命周期：启动一次后poll，部分失败保留句柄，retire实际完成才DOWN，错误/虚假成功隔离，待完成阶段冻结配置；绑定/实例分别保持回调模块/Wonder模块引用。上游ops/priv ABI和默认同步路径不变。CI 41065931217的53项Python检查、生产入口C模型、完整编译/严格链接和7项选定布局检查通过。

尚未安装managed绑定调用方，host glue、父资源/SSR/remove/实例释放与完整monitor仍未接通，无新手机入口或AWDL成功证明。见[0066](POPSICLE-WONDER-LIFECYCLE-0066.md)。

## 阶段 0065

0064普通管理帧路径活跃：静置WMA +2，扫描窗口WMA/分发 +34、PE入口 +15；AWDL事件0。监听时断网，手动阶段未进入，已恢复原厂。无需重跑。

0065新增生产专用会话controller和host显式入口，将已有NDI创建、准备、PE、频道、START计划、radio启动按实际完成状态推进。固定配置、单次提交、错误保留及销毁后禁止重启。Wonder入口、完整monitor、地址过滤与native RAW仍未接通，无手机入口、无AirDrop成功证明。详见[0065](POPSICLE-UPSTREAM-SESSION-0065.md)。

## 历史阶段 0058

新增默认关闭的单STA完整管理帧实验路径、标准nl80211接收工具和一键60秒观察脚本，不依赖monitor/LPC。仅显式run-mgmt-rx启用；加入MAC上下文消失时关闭路由且不调用SME的停机保护。修正版内核[40926997789](https://github.com/xxz3312/XAirDrop-17/actions/runs/40926997789)、工具[40927043957](https://github.com/xxz3312/XAirDrop-17/actions/runs/40927043957)、打包[40927044125](https://github.com/xxz3312/XAirDrop-17/actions/runs/40927044125)均通过。53项内核host Python检查、生产owner helper模型、15项切换脚本与4项观察脚本测试通过，严格链接无未解决依赖，7项选定布局匹配；这些不认证完整私有ABI或固件。

已生成并校验0058测试包（7,488,393字节）。完整MIF接收、超过256字节的有效AWDL帧、AWDL同步/选举与文件互传仍待实机验证。SME注册仅为PE主机队列提交，不是固件过滤命令。见[0058步骤](POPSICLE-FULL-MGMT-RX-0058.md)与[构建证据](research/popsicle-full-mgmt-rx-0058-build-pass.json)。只对既有popsicle/6.12.69测试环境提供实验包，不能推广为小米17 Pro适配认证。

## 最新阶段 0057

0056实机首次完整解析1帧PSF（247字节、7个TLV）；208候选TLV越界，首个MIF样本256字节但至少需277字节。0057已在固定WLAN源定位header DMA固定256字节设置和header-copy路径；新增可重复静态审计和推断边界回归。尚未修改/修复完整MIF接收，无新手机包、不需重跑旧测试。后续要探索原生完整管理帧指示和广播RX路由，或完整monitor packet DMA；SME/PE注册仅为主机队列提交，不能称作固件过滤命令；不能直接增大不存在的枚举。见 [0057源码定位](POPSICLE-CAPTURE-LIMIT-0057.md)。

## 最新阶段 0056

0055 实机 OCC 请求接受后收到609 Action（591 Apple OUI候选，全部bad_awdl），监听共16045包，无来源/radiotap错误、正常清理。0056保持全部校验，新增候选拒绝原因细分与每类首个有界数值样本，不保存身份/载荷。尚未收到通过解析的AWDL，不认证Apple接收或全频道范围。见 [0056测试步骤](POPSICLE-AWDL-PARSE-0056.md)。

## 最新阶段 0055

0054 实机：7733 包全部通过来源/格式检查，其中 583 Beacon、7150 DATA，Action=0。源码审计确认默认 LPC 是客户端/BSS 采集，新增显式 OCC 工作频道采集请求（RX 三类+operating_type=1），不自动回退。SET/GET 无模式读回，且 SUBFILTER 分支可能忽略模式属性，故始终 mode_verified=false；OCC 实际范围待验证。见 [0055 测试步骤](POPSICLE-CAPTURE-SCOPE-0055.md)。

## 最新阶段 0054

0053 实机运行约 60 秒：Wonder RX=1043、invalid=0，监听 packets=1043、observed=0、ignored=1043，无解析/运行错误且正常清理。由于旧 ignored 合并了来源过滤和帧类型过滤，不能据此认定频道上没有 AWDL。0054 新增 16 类互斥过滤结果、帧类型/Action 分类与首包非身份元数据，并记录测试前后 STA 频道；仍只读、不换频、不认证 Apple 身份。见 [0054 测试说明](POPSICLE-AWDL-RX-0054.md)。

## 最新阶段 0053

新增只读 AWDL Action 接收识别与离线解析、单终端 LPC/Wonder 采集控制器；识别 Apple OUI、PSF/MIF 和有界 TLV 链。不是 AWDL 同步/选举或 Apple 互传；本阶段 CI/实机证据分别记录。见 [0053 使用步骤](POPSICLE-AWDL-RX-0053.md)。

# 小米 17 Pro Max AirDrop 移植进度（2026-10-29）

当前完成了用户态兼容载荷构建、驱动资源/上下文生命周期、初始频道参数、owned NDI 启停路径、停机准入栅栏、被跟踪 MC 排空证据、纯 host 及早期 NDI 回收、父资源拆除前窗口撤销及显式 SSR 批量回收（含准入错误优先级及最终记账状态预检）的离线验证，并补齐普通 DP/DELETE 与 SSR DP 完成事件校验及普通资源已完成后的 NDI host 收尾和普通 host 删除后的最终记账。
实机已确认 MiShare 对临时 XOS 服务的 Binder 元数据访问、LPC/OCC接收和1帧AWDL PSF结构解析；完整AWDL同步与文件互传尚未实现。
“离线通过”指源码、模型测试、编译与链接等检查，不代表手机加载或固件接受。

最新实机结果：0049 自编译 WLAN 已完成加载、/dev/wlan 注册、HAL 开启、AP 连接和 DHCP。0050 工具沿用同一驱动完成一次 45 字节实验广播 vendor Action：native_status=0、send_exit=0，随后 STOCK_RESTORED。此前一次 errno 110 本次未复现，尚不能据此确定旧超时成因。此结果只证明收到原生完成回调，不证明独立空口捕获、对端接收、Apple AWDL 或长期稳定。0051 已新增显式 vendor-action-relay --feedback，原生成功按 token 回写 NOACK，错误/超时回写 FAILED，禁止升级为 peer ACK；CI 40890855957 通过，0052 手机已确认完整 token 闭环：native_status=0，NOACK=1，completed/reported=1，failed/rejected=0，Wonder 已卸载且 STOCK_RESTORED；monitor 删除出现一条 DP peer 状态警告，待跟踪。详见 [0051 测试步骤](POPSICLE-VENDOR-FEEDBACK-0051.md)。

| 模块 | 状态 | 已完成与剩余边界 |
| --- | --- | --- |
| GitHub Actions 与缓存 | 已完成 | 自动编译、工具链/bindgen 缓存、诊断报告 |
| XOS/Binder 与权限 | 部分实机验证 | MiShare 主进程/UI 元数据访问通过；无线业务未验证 |
| 小米 15 MiShare 兼容逻辑 | 离线构建通过 | 已移植应用补丁、BLE/会话兼容载荷；待上机联调 |
| Wi-Fi 会话协调 | 离线构建通过 | root broker 持有、断连/恢复逻辑；未在手机运行 |
| Wonder/AWDL 参考代码 | 部分完成 | 参考代码已构建；未接通目标 WLAN 收发 |
| Wonder/WLAN 后端接口 | 部分完成 | 类型表、注册和生命周期具备；完整 NDI 无线 init/set_freq/rate 等回调仍未接通，默认后端 capabilities=0；另有可独立启动的原生 monitor 接收模式 |
| Host VDEV 与引用管理 | 离线验证通过 | 对象创建、引用、最终释放跟踪与失败保留 |
| NDI CREATE/DP/DELETE | 离线验证通过 | 提交结果、真实 DELETE 事件与 DP 回收；新增普通 DP token/顺序校验及完成错误保留；固件未实测 |
| legacy/WMA/self-peer | 离线验证通过 | 上下文、绑定、peer 创建及对称删除路径 |
| PE session | 离线验证通过 | MC 异步创建/删除、完成回执、引用与 flush 回收 |
| 初始频道参数 | 离线验证通过 | 2.4/5GHz HT20、法规/并发/扫描检查及原生参数准备；不发 START |
| START 原生参数准备 | 离线验证通过 | 重查 WMA/self-peer/法规/并发；原生 START 参数构造与摘要，不提交固件命令 |
| START/host-only UP/STOP/DOWN | 离线构建/模型验证通过 | owned controller 接入专用 MLME 回调、真实响应与 PM 清理；accepted DOWN + INIT 后才删资源；完整原生 SM/WMA 运行及固件未实测，默认调用门关闭 |
| 动态换频与并发硬件模式 | 原生频道跟随首版已实现 | 新增 opt-in STA home channel 跟随、同 PHY monitor 同步与旧帧排空；AWDL 时间槽跳频、硬件模式/DBS 和原子频道预留仍待实现 |
| RAW TX / vendor Action TX | vendor Action 一次原生完成实机通过；DATA 待固件 | 0050/0049 返回 native_status=0（45 字节广播实验帧），独立空口/对端接收未验证；Action 帧工具已具备；新增 opt-in WMI RAW DATA vendor 入口与 raw-send/raw-relay，限同频道非 MLO STA、已有 peer、6Mbps/20MHz；新增 opt-in 原始 skb/token 完成桥；独立 NDI 待接入 |
| Monitor/native RAW RX | 原生 LPC → Wonder → 用户态已实机通过 | 0041 修正嵌套请求并确认接口并发限制，0042 修正 RX 协议值门槛；Wonder RX 增加 1277，invalid=0，wonder0 pcap 帧头可解析；0055显式OCC收到Action，0056解析1帧247字节PSF。默认LPC仍为当前BSS捕获；MIF受256字节header限制，完整管理帧路径待实机验证 |
| 统一收发会话入口 | 首版已实现，待实机 | relay-all 单进程分派 Action/RAW；前台会话按需创建 monitor、核对频道、统一启动/清理；新增 --tx-feedback 选择原始帧完成桥；独立 NDI 初始化仍待接通 |
| mac80211 发送状态回写 | 外部 monitor 路径首版已实现，待实机 | 原始 skb 有界队列、owner/token 匹配、完成/超时/退出处理；Action 明确 ACK 才回写 ACK，RAW 不推断单播 ACK；默认 full backend 旧路径未改 |
| 纯 host 隔离回收 | 离线验证通过 | 限从未发送固件命令的 PAS/INIT 对象；记录被跟踪 MC 排空，等实际 final-free 再释放 owner；NDI/未知发送资源拒绝回收 |
| 早期 NDI 隔离回收 | 离线验证通过 | 限 CREATE/完整 DP attach、尚无 WMA/self-peer/PE/START；资格化 SSR 窗口内释放 timer，等 DP final-free 后删 host；会话中与部分 attach 拒绝回收 |
| 普通 DELETE/DP 完成后收尾 | 离线验证通过 | 限未准备/未 START、普通 host 删除尚未开始的 NDI；合格 SSR 窗口内只删 host 并等最终释放，保留普通完成历史 |
| 普通 host 删除后最终记账 | 离线验证通过 | 删除接受、持有关系解除、MC 排空且无永久错误；等真实 VDEV final-free 后释放 owner，不再调用原生清理 |
| 父资源拆除前窗口撤销 | 离线验证通过 | CDS DP / HDD pdev / dispatcher pdev 关闭前永久撤销回收窗口；仍非父资源 lease 或在途调用屏障 |
| 显式 SSR 批量回收 | 离线验证通过 | 校验完整句柄表；漏列、已记录永久错误及 accepted-delete 记账状态矛盾优先于等待；逐项保留结果，全部清空才成功；父资源仍由调用方保留 |
| SSR/卸载/异常恢复 | 部分完成 | 已实现准入栅栏、被跟踪 MC 排空、早期及普通资源已完成的 NDI 收尾、拆除前窗口撤销及显式批量步骤；会话内 WMA/peer/PE/PM、父资源协调与安全卸载仍待实现 |
| 固件能力与端到端实测 | 待验证 | 驱动加载、NDI/RAW 实际支持、Apple 发现与双向传输、稳定性和安装包 |

最近内核构建源提交：`188246a0008a986741379b105fcfde92d64b8d88`。
[Actions 40768050808](https://github.com/xxz3312/XAirDrop-17/actions/runs/40768050808)
已通过 44 项 Python 检查、26 组原生 fixture、完整 WLAN 编译与严格链接；
85 个要求符号存在，575 条版本记录无不匹配、未解决依赖为空，7 项选定布局 MATCH。
以上不构成完整私有 ABI/KCFI、手机加载或 AirDrop 可用认证。

已补齐纯 host 与早期 NDI 的显式回收、拆除前窗口撤销和批量步骤。启用调用方前，仍需已准备/STARTed 会话的 WMA/peer/PE/PM 恢复、跨轮询父资源协调、活动 owner 卸载、psoc 复用和并发/硬件模式资源预留；随后接通换频、收发与 Wonder 后端，再做固件与整机联调。
新增回归执行原生 target-if 启停发送/响应、owned WMA wrapper 和 PM helper；完整原生 SM 与 WMA START 后处理在回归中仍为模型。
新增 MC 回归执行原生 scheduler_disable/queue flush 和 owned PE callback；QDF 线程/事件/队列原语、完整 native MC 线程及组件析构仍为模型。
早期 NDI 回归还执行 CDS post-disable、WMI 工作清理和原生 timer deinit；HIF/HTC/QDF 与完整 DP detach/free 仍为模型，真实内核与固件未验证。
父资源撤销回归还执行完整原生 CDS DP / HDD / dispatcher pdev close；其调用的 DP、IRQ、timer 和组件拆除为模型，完整 HDD 停机/回退仅做源码审计。
批量回归使用不同 MAC/VDEV ID 的多对象模型；准入检查不修改表，准入后的步骤可部分完成，错误项仍保留。批量接口没有持有父引用或自动接入 HDD。批量优先级回归覆盖十组双 owner 顺序/错误组合；历史批量函数负对照被既有断言拒绝。
普通完成事件回归覆盖有效 inline/延迟/栅栏后 DP 完成、未知及释放后 token、过早/重复/错误路由和 DELETE 异常；完整 DP/QDF/组件拆除仍为模型，地址复用与模块回调文本寿命未认证。
新收尾分支要求普通 DELETE 回执、DP detach 成功返回和 DP final-free 都已观察；inline free 后提交返回失败仍拒绝。它保留普通历史，不写 SSR timer/DP 执行标记。普通 host 删除已接受且持有关系已解除时，新增显式最终记账入口；无接受来源、永久错误及窗口后的晚到完成仍不自动接管。
最终记账回归覆盖纯 host、普通 NDI 和已正常清理 prepared 上下文；允许窗口关闭后等待实际 free，但父实例仍须保留到通知到达，不执行准备态恢复。
窗口撤销不能中止已进入的 reclaim；父资源仍须由调用方保留并串行化。CDS 返回错误也不会让现有 HDD 调用点统一停止拆除。
DOWN 没有固件 ACK，accepted DOWN 只表示原生提交成功及 PM 清理，不能称为固件确认。
详细证据见 [频道准备报告](research/popsicle-owned-channel-build-pass.json) 和
[启停响应检查报告](research/popsicle-start-stop-response-build-pass.json)，以及
[START 参数准备报告](research/popsicle-owned-start-plan-build-pass.json) 和
[启停生命周期报告](research/popsicle-owned-radio-lifecycle-build-pass.json) 和
[停机准入栅栏报告](research/popsicle-shutdown-admission-build-pass.json) 和
[MC 排空与纯 host 回收报告](research/popsicle-owned-mc-drain-reclaim-build-pass.json) 和
[早期 NDI SSR 回收报告](research/popsicle-early-ndi-reset-reclaim-build-pass.json) 和
[父资源拆除窗口报告](research/popsicle-parent-teardown-window-build-pass.json) 和
[显式 SSR 批量回收报告](research/popsicle-ssr-batch-reclaim-build-pass.json) 和
[批量准入错误优先级报告](research/popsicle-batch-preflight-priority-build-pass.json) 和
[普通 NDI 完成事件报告](research/popsicle-ndi-completion-integrity-build-pass.json) 和
[普通资源已完成 NDI 收尾报告](research/popsicle-completed-ndi-host-reclaim-build-pass.json) 和
[host 最终记账报告](research/popsicle-host-final-bookkeeping-build-pass.json)。

最新批量回归新增 48 个最终记账异常组合与 4 个有效等待对照；直接 final 与批量预检共用纯元数据校验。矛盾状态在任何逐项操作前拒绝，正常 final-free 等待仍保留逐项语义。移除新校验的负对照被表未改变断言拒绝。证据见 [批量最终记账预检报告](research/popsicle-batch-final-preflight-build-pass.json)。

SSR DP 回调现已校验已知 token 的恢复来源与普通路径混用；15 种异常保留永久错误，直接 host/NDI/final 与批量入口均拒绝继续回收。合法晚到 free 保留已有错误和窗口关闭状态，未知/释放后 token 忽略。旧回调负对照在新错误断言失败。证据见 [SSR 完成事件校验报告](research/popsicle-recovery-completion-integrity-build-pass.json)。

开发重点已转向功能打通：新增原生 monitor 接收模式及手动试运行包，先验证模块启动和真实收包，再接 RAW TX、频道控制及 NDI 会话。见 [接收模式运行说明](POPSICLE-RX-BRINGUP.md) 和 [编译证据](research/popsicle-external-monitor-rx-build-pass.json)。新模式尚未在手机执行；已有 26 组原生回归不等于新模式运行认证。

管理帧工具阶段提交：`7e53a21a5af27c22ebe6c91eab4ef956b3420116`。新增 Android arm64 `action-tx`，支持单帧发送和 Wonder 出站 Action 帧中继，复用原生 nl80211，不替换 WLAN。 [Actions 40749179035](https://github.com/xxz3312/XAirDrop-17/actions/runs/40749179035) 已通过主机协议测试及 Android 编译；本轮未改内核源码，接收模块沿用上述内核构建。见 [Action TX 使用说明](POPSICLE-ACTION-TX.md) 与 [构建证据](research/popsicle-native-action-tx-build-pass.json)。实际发射、RAW 数据帧、mac80211 完成状态回写与完整 AWDL 待实现/验证。

RAW DATA 阶段提交：`57184ea2203dfa05ab33c3c7171a2ade31675e2d`。RAW DATA 驱动入口与 Android 工具已接通编译链，完整 WLAN 编译/严格链接和两个工具/模型测试均通过；native_status 只由真实原生完成回调产生。需要新驱动显式启用 mishare_raw_tx=1，旧接收包/stock WLAN 不具备入口。手机加载、WMI DATA 接受和实际发射待验证。见 [RAW TX 首版说明](POPSICLE-RAW-TX-BRINGUP.md) 与 [构建证据](research/popsicle-native-raw-tx-build-pass.json)。

统一会话阶段提交：`8f4a8afa609a687f48c79746329507afe094fbe3`。统一收发会话入口与 Action/RAW 单进程分派已实现。[Actions 40757236509](https://github.com/xxz3312/XAirDrop-17/actions/runs/40757236509) 通过 13 项会话命令模型测试、协议/RAW 提交模型和 Android arm64 编译。本轮未改内核，完整 WLAN 证据仍为 0036。见 [统一会话说明](POPSICLE-SESSION-BRINGUP.md) 与 [构建证据](research/popsicle-unified-session-build-pass.json)。独立 NDI 初始化、动态换频、mac80211 状态回写及手机互通仍待完成。

频道跟随阶段：功能提交 `2f95a88a8a2affd2dabe987fbfd39c2cb2e827d5`，最终验证提交 `b32354789133462815de0d16fc1a6241301a9e2a`。新增 `--follow-channel`，持续跟随原生 STA/P2P client 当前频道并同步 monitor，换频与发送串行执行；掉线、同步失败和设置后再次换频停止会话。此为 home channel 跟随，不含 AWDL 时间槽调度。[Actions 40763644465](https://github.com/xxz3312/XAirDrop-17/actions/runs/40763644465) 已通过 15 项会话命令测试、频道跟随/Action/RAW 模型与 Android arm64 编译。见 [使用说明](POPSICLE-CHANNEL-FOLLOW.md) 与 [验证报告](research/popsicle-channel-follow-build-pass.json)。本轮未改内核，完整 WLAN 构建证据仍沿用 0036；手机收发未验证。

发送状态回写阶段提交：`218a67c2e451172268acc9657b6b141f4fb8c769`。新增 `external_tx=1`、工具 `--feedback` 与会话 `--tx-feedback`，原始 skb 按 owner/token 关联到原生完成；默认外部 monitor 仍只接收。16 项会话命令测试、队列所有权/ACK 证据模型、频道/协议/RAW 模型及 Android arm64 编译通过。见 [使用说明](POPSICLE-TX-FEEDBACK.md) 与 [构建证据](research/popsicle-tx-feedback-build-pass.json)。独立 NDI、AWDL 时间槽跳频和手机实际收发仍待完成。

0039 完整内核验证已完成：[Actions 40768050808](https://github.com/xxz3312/XAirDrop-17/actions/runs/40768050808) 通过 44 项 Python、26 组原生 fixture、WLAN/Wonder 编译与严格链接；Wonder 107 条版本记录、WLAN 575 条记录无不匹配/无缺版本依赖，85 个要求符号存在、7 项选定布局 MATCH。0039 工具最终验证源为 `1a1166b8816b151f36a4f6a7b464e70e1a43dc53`，与内核分别记录，不代表手机加载或固件认证。

0040 已整理首轮手动实机包 `XAirDrop-17-Device-Trial-0040.zip`（2,656,084 字节），SHA-256 `fb1888dcf8fd5db4f36d5a5a779e863fb09d55e0dd2040e6a1c6ffcde7c4b008`。复用 0039 新 Wonder，新增仅限 Wonder PHY 的 Action 注入入口和实验广播测试帧；[Actions 40822824724](https://github.com/xxz3312/XAirDrop-17/actions/runs/40822824724) 通过 16 项会话模型、协议/频道/队列/RAW 模型和 Android 编译。包内无 WLAN 替换驱动、无自动安装，尚未上机；按加载/收包、原生 Action、token 回写分步测试。见 [首轮测试说明](POPSICLE-DEVICE-TRIAL-0040.md) 和 [打包证据](research/popsicle-device-trial-0040.json)。

0040 首轮手机反馈：Wonder 成功加载、注册 PHY 并绑定原生 monitor RX handler；两次 RX 计数均为 0，尚未验证收包。STA 活动时标准 monitor 换频返回 EBUSY。QCA GET_MONITOR_MODE 已可查询，返回当时未运行；显式 SET 进一步出现 expected nested data，定位为 nl80211 外层嵌套格式拒绝，不是固件接收失败的证明。原始上传日志未提交到公共仓库。

0041 提交 `6700e2b418e2e39dbc3eb1b8044a51117bdd4900`，新增 capture-start/status，修正 QCA SET 的 NLA_F_NESTED 标志，GET 保持 RAW；不再让用户用 iw raw 数据发送结构化 SET。[Actions 40827521911](https://github.com/xxz3312/XAirDrop-17/actions/runs/40827521911) 通过 16 项会话、协议/频道/队列/RAW 模型及 Android 编译。补丁仅含工具和源码，沿用 0040 Wonder，不替换 WLAN，不改频道；修正版实机效果待反馈。见 [使用说明](POPSICLE-LPC-FIX-0041.md) 与 [验证报告](research/popsicle-lpc-nested-fix-build-pass.json)。

## 0052 单终端测试控制器

新增单终端 vendor Action token 测试：就绪后单次注入、频道复查、NOACK 证据检查和有归属的逆序清理；复用 0049/0051 二进制。CI 40898427028 已通过；0052 实机单帧发送和 token NOACK 回写、资源清理及原厂驱动恢复已通过。见 [0052 操作说明](POPSICLE-VENDOR-FEEDBACK-0052.md)。

## 0042 原生 RX 与桥接修正

原生 LPC 已采集到 Beacon 和 QoS 数据帧；20 秒内原生 RX 增加 1813 包而 Wonder RX/invalid 仍为 0。外部 monitor 的 skb 协议值门槛已修正，构建 40832922219 成功；模块实机验证尚未完成。详见 [0042 测试步骤](POPSICLE-RX-FIX-0042.md)。此进展不代表 AWDL 或 Apple 文件互传已通过。

## 0043 原生 Action 完成事件

Public Action 实机提交返回 cookie=256，iw 观察到 cookie 0x100 的 acked 状态；旧工具逐字节帧匹配导致超时。原生驱动会填写 12-bit 序列号；0043 只放宽这 12 位，继续严格校验其余帧内容、接口和 cookie。Actions 40836954137 编译回归通过，工具实机待测。广播状态不证明 Apple 收到；非 Public AWDL 帧仍受 STA 入口限制。详见 [0043](POPSICLE-TX-STATUS-FIX-0043.md)。

## 0044 完成回传闭环与回包解析

0043 原生 49-byte Public Action 发送已实机匹配状态并退出 0；52-byte 测试帧经 Wonder token 队列 → 原生发送 → token 完成回传，completed=1、reported=1、failed=0、rejected=0。49-byte 队列回复此前触发 EBADMSG，0044 修正最终 netlink 消息/属性可省略末尾填充的解析；49/50/51/52-byte、截断和部分填充回归与 Android 编译通过（Actions 40840072145）。0044 原长度闭环仍待实机验证。详见 [0044](POPSICLE-FEEDBACK-FIX-0044.md)。广播完成不证明对端收到，AWDL 与 Apple 互传仍未验证。

## 0045 独立原生 vendor Action 入口

0044 原始 49-byte 帧的完整 token 回路已实机通过：completed=1、reported=1、failed=0、rejected=0。0045 新增显式 vendor-action-send 和默认关闭、独立加载参数 mishare_action_tx；通过原生 WMI MGMT 发送 category 127，限非 MLO STA 当前频道并保留源地址/peer 检查。用户态回归/Android 构建 40841130477 与完整 WLAN 构建 40841130362 均成功；86 必需符号、575 WLAN 导入记录与所选布局检查通过。原生 WLAN 替换、固件接受、空口接收、NDI/AWDL 时槽/身份和 Apple 互传仍待验证。下一步先运行只读 WLAN 加载预检，详见 [0045](POPSICLE-VENDOR-ACTION-0045.md)。

## 0046 参考小米 15 的运行时切换流程

重新核对 Leekin2/XAirDrop 当前 main（eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76）的 action/service/customize 实现。按其 Wi-Fi/HAL 停止、RAM 中正常切换驱动、失败恢复流程适配 17；初次测试仅手动触发，不启用上游 boot_completed 后自动调用。原系统模块/启动文件不修改，重启仍走系统原驱动。controller 6f1e2bff9c75c6564879c98213c8ad2b26f38be9，10 个实际 shell 模拟路径通过；打包构建 40844885387 成功，原生 WLAN 仍来自 0045 已通过的构建。只在 CI 移除调试信息，模块约 21.5 MB，测试 ZIP 约 7.4 MB。实机驱动切换、固件 Action、PAS/NDI 与 Apple 互传仍未验证。详见 [0046 手动测试与恢复](POPSICLE-WLAN-TRIAL-0046.md)。
