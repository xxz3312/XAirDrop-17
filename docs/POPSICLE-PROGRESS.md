## 最新代码阶段 0162（先取消 radio，再等待 MC 排空）

修复 0161 完整 CI 暴露的退出顺序回归：工作引用门禁移到 radio_drain 之后、PE/peer/VDEV 清理之前。排队中的 START 仍须先看到 closing/cancel；零发送尝试的 rate flush 回执发布期间仍不能删除 PE。增强旧 radio 回归及门禁前移变异，提早加入独立 Actions 步骤；保留 0161 的 512/12/4 组合同时复验。100 项本地 Python 回归、语法和源码生成通过；原生执行与完整构建待 CI。未接入新的请求/START 入口，手机无需操作。见 [0162 修复与证据](POPSICLE-RADIO-CANCEL-ORDER-0162.md)。

## 最新代码阶段 0161（准备控制器与原生退出组合验收）

新增 production prestart/session/runtime/rate bridge/owned MC 与 selected native CREATE/context/PE/channel/普通清理/SM 最终释放的单体组合，速率执行与物理原语仍为模型。补齐零发送尝试的 MC 完成发布期间退出门禁：仍有 work_pending/users 时不能提前提交 PE 删除，错误优先保留。100 项本地 Python 回归和组合源码生成通过；512 组组合、12 组发布失败/flush/隔离场景和四项变异已通过 Actions 42618977716 的独立步骤；后续 diagnostic 的原有 radio 退出取消回归失败，完整目标构建未通过；0162 正在修复顺序并复验。0160 八项必选 CI 已全部通过。公开 init/START 关闭，手机无需操作。见 [0161 验证与修复](POPSICLE-PRESTART-NATIVE-0161.md)。

## 最新代码阶段 0160（内部会话接入固定速率准备）

新增内部 prestart controller 和受保护 host 入口，复用已有 CREATE/context/PE/channel 会话阶段，在信道完成后只提交一次 owned rate configure；冻结频率/NSS/速率、验证回执及工作引用归还，成功停在 PLAN，不请求 START-plan/radio，也不开放 managed/public 初始化。raw host session 入口拒绝已选择配置模式的实例。100 项本地 Python 回归和源码/语法检查通过；16 组成功模型、15 组回执保留及六项变异已通过 Actions 42515932856 的 bridge-controller 作业；八项必选 CI 已全部成功，含完整 host 回归和目标编译。0159 八项必选 CI 已全部通过。手机无需操作。见 [0160 实现与边界](POPSICLE-PRESTART-CONFIG-0160.md)。

## 最新代码阶段 0159（peer 已确认、未发送 VDEV DELETE 的 SSR 回收）

新增独立 peer-reset 事务：原始健康 SSR fence 或已验证的 late-peer 来源、MC 排空和原生停机窗口共同约束准入；实际 timer drain 后单独提交 native DP detach，真实 DP final-free 后才释放 WMA/legacy 与 host，最终物理 VDEV free 后退役元数据。VDEV DELETE 标志和普通完成记录不伪造；一次性尝试及错误保留，不重发固件命令。23 项本地变异和 100 项 Python 回归通过；256 组 native 组合、36 组保留场景、四项 native 变异已通过 Actions 42448119773 的独立步骤，含终态不可重新开窗；八项必选 CI 已全部成功，含完整生命周期回归、目标编译、严格链接和布局检查。0158 八项必选 CI 已全部通过。公开 init/START 关闭，手机无需操作。见 [0159 实现与边界](POPSICLE-RATE-PEER-RESET-0159.md)。

## 最新验证阶段 0158（peer 回执后的原生 VDEV timer 合同）

新增隔离 native 组合，核对真实 self-peer ACK 不等于 VDEV timer 释放，并验证现有 prepared timer helper 在 peer 删除后的复用条件、同步 cancel 后重检和二次释放拒绝。64 组组合、20 组拒绝及三个 native 变异已通过 Actions 42416119586 的独立步骤；八项必选 CI 已全部成功，含完整生命周期回归和 WLAN 构建。本地 100 项 Python 回归通过。生产 runtime 未改、peer-only SSR 仍保留剩余资源，尚未接入 timer/DP/上下文回收事务。公开 init/START 关闭，手机无需操作。见 [0158 验收与边界](POPSICLE-RATE-PEER-TIMER-0158.md)。

## 最新代码阶段 0157（原始 SSR 后的真实 self-peer 回执观察）

仅为健康且已成功提交 self-peer DELETE、PE 删除已完成、尚未提交 VDEV DELETE/DP 的配置 owner 在原始 SSR fence 记录 late_peer_armed。精确匹配的真实 native 完成记录 late_peer_reply，保留封锁与错误；hold-request/timer/wake-lock 仍由原生来源清理。本阶段只观察，不放行 VDEV DELETE、DP 或 host 释放；所有剩余资源继续隔离。本地 19 项状态变异检查、100 项 Python 回归通过；64 组 native 观察、24 组保留场景和 3 项原生变异已通过 Actions 42410649117 的独立步骤；0157 八项必选 CI 已全部通过，含原有生命周期回归、完整 WLAN 编译、CNSS 接口、严格链接、BTF 布局及产物检查。0156 八项必选 CI 也已全部通过。公开 init/START 关闭，手机无需操作。见 [0157 实现与边界](POPSICLE-RATE-LATE-PEER-0157.md)。

## 阶段 0156（原始 SSR fence 后的真实 VDEV DELETE 回执）

原始 SSR fence 前只为健康、已确认 PE/peer 删除且 VDEV DELETE 成功提交的配置 owner 记录 late_delete_armed；晚到的真实 native DELETE reply 经身份/状态检查后保存，保持 blocked/错误不变，再复用 0155 DP/上下文回收。未收到回执仍保留，关窗后的真实事实不授予回收资格；匹配异常 peer 通知新增 sticky completion_error。本地 17 项变异、100 项 Python 回归通过；256 组 native 延迟回执组合、10 类保留场景和 3 项原生变异控制已通过 Actions 42408125741 的独立步骤；八项必选 CI 已全部通过，含原有生命周期/父级组合、完整 WLAN 编译、严格链接、BTF 布局和产物检查。0155 八项必选 CI 全通过。公开 init/START 关闭，手机无需操作。见 [0156 实现与限制](POPSICLE-RATE-LATE-DELETE-0156.md)。

## 阶段 0155（普通 DELETE 确认后由 SSR 首次提交 DP detach）

仅对普通 PE/peer/VDEV DELETE 已确认、DP detach 尚未尝试的配置 owner，复用合格 native SSR 窗口和原生 prepared-DP helper 提交一次 DP detach。区分 helper 尝试、成功返回和真实 DP final-free；失败不重试，后续复用 0154 上下文释放/0153 final 记账。缺少删除 reply 的更早阶段仍保留。本地 15 项状态变异检查、100 项 Python 回归通过；256 组 native 组合、18 组故障保留和 3 项原生变异控制已通过 Actions 42405410946 的独立首次 DP SSR 步骤；八项必选 CI 现已全部通过，包括完整目标编译、严格链接、BTF 布局和产物检查。0154 八项必选 CI 全通过。公开 init/START 关闭，手机无需操作。见 [0155 实现与限制](POPSICLE-RATE-SSR-FIRST-DP-0155.md)。

## 阶段 0154（普通 DP 删除尾段衔接 SSR）

只对普通 PE/peer/VDEV 删除均已确认、DP detach 已成功提交的配置 owner，复用原生 SSR 窗口等待原 DP final-free，再一次性释放 WMA/legacy 上下文。记录 tail_attempted/tail_completed，保留普通回执与部分释放事实；无重复 DELETE、DP detach、timer/peer force release。更早的删除中断仍保留。本地 13 项状态变异检查、100 项 Python 回归通过；256 组 native 尾段组合、10 组保留故障及 3 项原生变异控制已通过 Actions 42400068283，原有 ordinary/SSR/final-handoff 回归也通过。八项必选作业全部成功，完整目标编译、严格链接、BTF 布局和产物检查通过。0153 八项必选 CI 全通过。公开 init/START 关闭，手机无需操作。见 [0154 实现与限制](POPSICLE-RATE-SSR-DP-TAIL-0154.md)。

## 阶段 0153（普通清理完成后的 SSR 元数据衔接）

仅对普通 PE/peer/VDEV/DP/context 清理已完成、host 删除已接受、正等待外部 VDEV final-free 的配置 owner，接入既有 SSR final/batch 元数据退休。保留原始回执，继续等待 MC 排空和真实 final-free；不续跑 native 清理，不重发 DELETE/DP detach。部分普通清理遇到 SSR 仍保留。本地 12 项状态变异检查、100 项 Python 回归通过；256 组 native 衔接、22 组保留故障、PE 删除中断拒绝及 3 项原生变异控制已通过 Actions 42391133072 的 stop-admission；普通/SSR 配置清理回归也通过。本轮完整构建仍运行。0152 八项必选 CI 全部通过。公开 init/START 关闭，手机无需操作。见 [0153 实现与限制](POPSICLE-RATE-FINAL-HANDOFF-0153.md)。

## 阶段 0152（配置后、未 START 的普通异步清理）

接入既有普通 PE/peer/VDEV/DP/context/host 清理链。新增 ordinary admission/completion 记录，保留速率原始回执，逐项核对普通 DELETE 及 DP final-free，禁止混合 SSR 路径和公开 START。本地 11 项状态模型变异检查、100 项 Python 回归通过；256 组 native 配置清理组合、24 组失败保留、5 种入口拒绝及 3 项原生变异控制已通过 Actions 42389562888 的 stop-admission，原有配置 SSR 组合也通过；完整目标构建仍在运行。0151 八项必选 CI 全通过。公开 init/START 关闭，手机无需操作。见 [0152 实现与限制](POPSICLE-RATE-ORDINARY-RETIRE-0152.md)。

## 阶段 0151（配置后、未 START 的合格 SSR 回收接入）

只对 owned rate 批次已结束且未请求 START-plan/radio 的 owner，复用既有 native HTC/HIF/WMI reset 窗口和 prepared INIT 清理。新增 reset_admitted/reset_completed 记录，逐项核对 timer/PE/self-peer/DP/WMA/legacy 的实际释放事实，保留原始速率回执；batch、延迟 VDEV final-free 和关窗后 metadata retirement 纳入该路线。普通运行态配置后清理仍关闭。本地状态 C 模型、九项变异检查、100 项 Python 回归通过；16 组配置后 native SSR 组合、六种窗口资格缺失、七种保留故障及三个 native 变异控制已通过 Actions 42380495651 的 stop-admission；0151 的八项必选 CI 均已通过，包括完整目标构建、严格链接及布局检查。公开 init/START 关闭，手机无需操作。见 [0151 实现、验证与限制](POPSICLE-RATE-SSR-RETIRE-0151.md)。

## 最新代码阶段 0150（runtime 固定速率状态与清理准入）

0149 全部八项必选 CI 已通过。实际 runtime registry 新增 one-shot rate 请求、post 返回和完成回执状态；configure 连接 owned MC post，处理 inline 完成、预发布失败、重复/畸形回执，原始错误和部分提交证据保留。普通/SSR/final/batch 清理统一拒绝 pending、integrity 错误和任何已尝试配置的 owner；零尝试只进入原有清理检查，raw START-plan/START 继续封闭。新生产状态桥接/MC C 模型、六项变异检查及 100 项 Python 回归本地通过，完整 runtime 清理断言和目标编译待 CI。尚未实现配置后 qualified teardown 或连接公开 init，手机无需操作。见 [0150 实现与限制](POPSICLE-RUNTIME-RATE-0150.md)。

## 最新代码阶段 0149（owned MC 速率批次和 WMA 直接提交）

0147/0148 全部八项必选 CI 已通过。新增固定速率 post：复制有效参数、取得 VDEV ref/runtime work reservation 后排 MC，执行/flush/封锁结果发布时仍保留所有权，最后归还工作和引用。MC 分支使用精确 WMA/PSOC/VDEV 身份校验及受限参数直接提交，不再嵌套普通 CLI 消息；首次错误、部分提交和 one-shot receipt 保留。384 组速率场景、15 项变异检查、工作所有权 C 模型及 100 项 Python 回归本地通过，Actions 42375590428 全部八项必选作业已通过。尚未连接 runtime 配置状态机/公开 init，未完成全局配置或完整父级租约；手机无需操作。见 [0149 实现与限制](POPSICLE-OWNED-RATE-WORK-0149.md)。

## 最新代码阶段 0148（初始化准备与速率执行共用支持合同）

实际 managed prepare 接入与 0147 执行器相同的纯参数检查，在 native scope、监管查询和元数据保存前拒绝当前不支持的 MCS/GI/legacy/带宽/NSS，明确拒绝 rate adaptation。有效请求仍须每次重新经过原生国家/信道/NSS 检查；未应用参数的 raw step 仍关闭。192 组速率执行器 C 模型、六项执行器变异检查、100 项本地 Python 回归通过；新增 11 项 host 拒绝检查和两个支持合同变异控制待 CI。0147 和本阶段 Actions 42370003141 的全部八项必选 CI 已成功。配置事务和跨调用父级生命周期尚未完成，公开 init/poll 关闭，手机无需操作。见 [0148 支持合同和限制](POPSICLE-RATE-ADMISSION-0148.md)。

## 最新代码阶段 0147（固定速率原生命令执行器）

0146 全部八项必选 CI 已通过。新增内部固定速率执行器，按上游编码和 fixed-rate→GI→带宽顺序提交原生 WMA 命令。逐次记录 attempted/submitted，首个错误立即结束，部分提交不回滚、不重发；全部入队仍不代表固件确认。接入真实目标 Kbuild，暂无 managed/public 调用。限 HT20、最多两流及明确的 HT/VHT/HE/EHT MCS/GI 子集；legacy、宽信道、自适应掩码仍未支持。192 组生产 C 模型、六项变异检查及本地 100 项 Python 回归通过，目标编译待新 CI。公开初始化继续关闭，手机无需操作。见 [0147 实现与限制](POPSICLE-FIXED-RATE-0147.md)。

## 最新代码阶段 0146（当前国家域与 HT20 监管预检）

0145 全部八项必选 CI 已通过。managed prepare 在新 PSOC transition/RTNL scope 内读取原生当前国家码，只允许请求 alpha2 与当前域一致；00 为字面 world domain，不作通配。查询失败、非 2.4/5 GHz、固定/自适应 NSS 超过 caller 提供的对应频段上限、非 ENABLE 的 HT20 信道及 passive 信道均拒绝。重复 prepare 重新查询；失败不覆盖已有请求，不创建接口或下发固件命令。100 项本地 Python 回归及生产监管 helper 独立 ASan/UBSan 模型检查通过；首轮夹具声明顺序问题已修复；Actions 42365788018 的全部八项必选作业通过，含实际 host 监管行为/变异回归、完整目标编译、严格链接和布局检查。仍未下发国家码、速率或过滤配置，未建立跨调用父级/固件租约，公开 init/poll 关闭，手机无需操作。见 [0146 实现与边界](POPSICLE-REGULATORY-PREFLIGHT-0146.md)。

## 最新代码阶段 0145（初始化请求快照与只读上下文准备）

0144 八项必选 CI 已全部通过。新增实际公开参数的形状检查和语义快照，记录全部有效速率/国家码/MAC/BSSID/重试/聚合参数，忽略保留字节及未启用的自适应掩码。内部 prepare 在新 PSOC/RTNL scope 下检查当前 HDD、recovery、mission mode，成功只保存不可变元数据；准备后的请求禁止进入未应用参数的 raw step。公开 init 对畸形请求返回 EINVAL，对有效请求仍返回 EOPNOTSUPP，不分配实例、不发固件命令。100 项本地 Python 回归通过，Actions 42349938676 的 request/bridge/managed/provider/legacy 快速模型已通过，实际 host/prepare 回归也已通过，完整编译、严格链接、布局检查及全部八项必选 CI 均已成功。未实现监管许可、实际国家码/速率应用和跨调用完整父级租约。见 [0145 实现与限制](POPSICLE-INIT-REQUEST-0145.md)。

## 最新代码阶段 0144（managed 停止入口与原生实例退出连接）

0143 八项必选 CI 已全部通过。netdev-stop worker 封闭 managed 入口后推进一次停止；新增可选进程上下文 retire_process，在实例锁外调用原生退出，in-flight 状态阻止并发退役/解绑。HDD 后端停止函数认证私有实例、移交 host、按精确回执推进普通清理，等 host/回执/设备引用/实例实际释放后才清空 handle。公开 init/poll_start 仍 EOPNOTSUPP；内部实例工厂尚无公开创建调用。100 项本地 Python 回归及语法检查通过，Actions 42345877772 的 managed/provider/legacy 等快速 C 模型已通过，host/原生退出回归及完整编译也已通过，八项必选全部 success。未扩大 START/UP SSR 恢复范围，无手机操作。见 [0144 实现与限制](POPSICLE-MANAGED-STOP-0144.md)。

## 最新代码阶段 0143（退出所有权移交与精确完成回执）

0142 八项必选 CI 已全部通过。新增桥接→原生 host registry 的显式移交，关闭启动并丢弃旧 HDD 借用指针；独立模块文本引用和不重复序号保留退出回执。只有对应 host 完成 adapter/runtime/pins/元数据释放后才能完成回执，移交本身仍返回 EINPROGRESS。已移交会话可由现有 ordinary idle/限定 SSR 路径处理，原有恢复范围不扩展，公开 Wonder 回调仍未启用。100 项本地 Python 回归通过；Actions 42341386219 的 bridge 及实际 host/原生退出回归已通过，包括两项回执负向控制；完整目标编译及其余门禁现已通过，八项必选作业全部 success。无新手机包，不重复 apply。见 [0143 实现与限制](POPSICLE-RETIREMENT-RECEIPT-0143.md)。

## 最新代码阶段 0142（接入原生单次调用保护，跨调用生命周期尚未完成）

上一轮 42291190028 的八项必选 CI 已通过。新增 bridge scope：取得设备引用和原生 PSOC transition、排空操作、trylock RTNL 后再解析 HDD；任何进入失败不推进会话，成功/失败均按逆序释放。普通退出沿用 host 自身检查，不因全局健康检查拒绝资源回收。100 项本地 Python 回归通过；Actions 42327840421 的 session/bridge/scope C 模型及 ASan/UBSan 作业已通过；已修复首轮旧 host 夹具的声明顺序问题，host/退出回归及完整目标编译也已通过，八项必选作业全部 success。该保护仅覆盖一次调用，不是异步阶段间的完整父级租约，也不能从已持 RTNL/原生 operation 的公开回调直接调用；Wonder 仍未启用。手机无需操作。见 [0142 实现与限制](POPSICLE-BRIDGE-SCOPE-0142.md)。

## 最新代码阶段 0141（桥接 host 会话控制器已实现，公开回调尚未启用）

按两个上游实现内部 host 分配→runtime 附着→异步 session→退出控制器，固定会话身份，启动失败不重放，退出等待/失败保留权威 host。radio UP 不作为 Wonder 初始化成功；不获取父级生命周期租约，不自动启动。100 项本地 Python 回归通过，Actions 42291190028 的独立 session/bridge ASan/UBSan 模型作业已通过；完整目标编译及全部八项必选 CI 作业现已通过。手机继续保持当前状态，无新安装包，不重复 apply。见 [0141 实现和边界](POPSICLE-WONDER-BRIDGE-0141.md)。

## 最新实机阶段 0140（普通 Wi-Fi 收发与系统连通性短时通过，Wonder 会话仍待接入）

HAL running，5240 MHz STA 网络显示 VALIDATED；采样网口收约 19.4 MB/发约 4.75 MB，errors/dropped 均为 0。新驱动 ready 后约四分钟日志未见明确 panic/Oops/BUG/CFI/未知符号或版本冲突；固件直接查找失败已经 fallback 找到并收到 FW ready。仍有 trace cfg 缺失及 MLO/TWT/P2P、roam/速率统计告警，不能宣称日志全净或长期稳定。已核对上游原生 Wonder ops；当前 managed bridge init 仍返回 EOPNOTSUPP。下一阶段回到源码接入 typed init/poll/retire，不让用户重复 apply，不计 AWDL/Apple 功能完成。见 [0140 审查](POPSICLE-ACTIVE-REVIEW-0140.md)。

## 最新实机阶段 0139（保留原厂 CNSS2 的新 WLAN/provider 加载成功，STA 已恢复关联）

0138 修复后备份通过。实际 apply 按 Wi-Fi off→HAL stop→仅卸载原厂 WLAN→provider/WLAN 插入→HAL/Wi-Fi 恢复顺序完成，退出码 0、phase=active。原厂 CNSS2 note 保持匹配；新 WLAN/provider 为 live 且 note 与已验收原始 ELF 匹配。操作前后 boot-id 一致，没有在本次流程重启。日志确认 STA 重连 5240 MHz 并取得 IPv4；尚未验证互联网可达、长期稳定或卸载回退。下一步审查当前内核与联网状态，再接 Wonder/AWDL；不计 Apple 发现/握手/互传完成，也不能据此断言 0132 重启根因已确定。原始日志不提交公开仓库，仅存 SHA256 与结果索引。见 [0139 实机证据](research/popsicle-stock-cnss-phone-load-0139.json)。

## 最新阶段 0138（修复整份属性表触发外部 printf 参数过长）

0137 手机 archive/check 已通过，但 backup 在 HAL 枚举阶段触发 printf Argument list too long；在快照目录创建、关闭 Wi-Fi 和驱动动作之前停止。按上游流式筛选 getprop，并保留生产者退出码回执，避免外部大参数。45 项回归及实际四文件覆盖模拟通过；只改 IO 的 sc_hals，主控制器/状态机/raw ELF 不变。约 5.3 KB 小修复包，不需重装或重启；CI 42288035806 的 policy/package 已通过，下载小包摘要/内层字节与本地包一致；尚待手机 backup。见 [0138 修复](POPSICLE-HAL-STREAM-FIX-0138.md)。

## 最新阶段 0137（修复 KSU 安装器删除 customize.sh 导致的运行期误阻断）

手机已加载原厂 CNSS2/WLAN，0136 保留文件 SHA 匹配，唯一包校验错误是安装期 customize.sh 被 KSU 正常删除。新增安装/运行期独立清单，保留文件缺失/篡改仍阻断。41 项测试及实际完整安装清理、旧包三文件修复模拟通过；约 1.7 KB 修复包不含驱动/脚本，只更新校验表、说明与版本。两份 raw ELF 和运行脚本不变，无手机驱动操作。CI 42285579522 的 policy/package 已通过；下载的小包外层摘要/内层字节与本地模拟包匹配。尚待手机修复后 check。见 [0137 修复](POPSICLE-KSU-CHECKER-FIX-0137.md)。

## 最新阶段 0136（设备端适配器与 KSU 手动入口已实现，实机未执行）

参考两个上游接入固定目标模块操作、Wi-Fi/HAL 确认及管道捕获框架输出，保留原厂 CNSS2；独立状态/日志、SHA/note/boot/固件门禁、失败不重放，旧 pair 事务明确阻断。KSU 安装和开机不加载，Action 仅手动调用一次 apply。严格打包器固定取用已验收 0133 raw ELF，不含 cnss2.ko，不改二进制；36 项本地测试与 shell 语法通过，实际实验 ZIP 的 16 个条目/15 项摘要复核一致。CI 42280862448 的 policy/package 已通过，CI 内层 ZIP 摘要与本地逐项验收包一致；尚待手机只读 check，不计实机安装或运行通过。见 [0136 设备端和 KSU 包](POPSICLE-STOCK-CNSS-KSU-0136.md)。

## 最新阶段 0135（新 ELF 原厂 CNSS2 导入通过，独立部署核心已实现）

七项必选 CI 成功。完整/精简 ZIP 摘要、64 份 JSON 一致性和五个真实 ELF 复核通过；新 WLAN 含 590 条版本记录，64 项原厂 CNSS2 导入 CRC 匹配，checked_v1/live-arm 均无残留。provider 实际消费者导入 CRC 匹配。新增独立、无 IO 的启动状态机，只允许切换 WLAN/provider，原厂 CNSS2 前后身份持续检查，副作用有 intent/returned/done，失败不重试；12 项故障模型与八项导入测试本地通过。设备端适配器/KSU 包尚未实现，无手机执行或运行认证。见 [0135 验收与边界](POPSICLE-STOCK-CNSS-POLICY-0135.md)。

## 最新阶段 0133（保留原厂 CNSS2 的源码分支可复用，重构建尚待验证）

实测 0130 WLAN ELF 的 62 项原厂 CNSS2 导入 CRC 匹配，但另有两个 checked_v1 强导入和外部 live-unload arm，不能直接配原厂运行。源码已有宏关闭分支，回到原厂 register/unregister 和原生 PCIe callbacks；会失去 checked 注册保留、外部受控热卸载等保证。新增默认 WLAN 链接产物门禁，拒绝 checked/live-arm 残留、旧 CNSS2 CRC 差异和依赖遗漏，八项新回归通过，实际旧 ELF 按预期拒绝。完整构建/新部署合同尚待完成，无新手机包；原 0131 pairctl 不适用于新路线。见 [0133 依赖审查](POPSICLE-STOCK-CNSS-REVIEW-0133.md)。

## 最新实机结果 0132（备份通过，apply 期间重启，运行验收未通过）

Termux 改用管道 tee 后 backup 成功，原厂副本校验和 Wi-Fi/HAL 状态保存通过。随后 apply 中原厂两模块移除返回、provider 插入及 note 验证通过，最后记录 intent:insert:cnss2 后手机重启；缺少 CNSS2 insmod 执行/返回证据，候选 WLAN 未到加载阶段。重启后原厂模块 note 与活动 boot 摘要匹配。pstore 空、DropBox 无上次内核/看门狗记录，厂商历史无本次条目；当前日志不能判定根因。暂停原包 apply/restore 重试，保留事务，先审查卸载生命周期和改进故障前取证。见 [0132 实机重启事件](POPSICLE-RUNTIME-INCIDENT-0132.md)。下面“尚未操作手机”等表述是各历史阶段当时的状态，不代表当前实机结果。

## 最新阶段 0132（手机只读 check 已通过，备份与驱动运行仍待执行）

手机只读状态确认 popsicle / OS4.0.5.0.XPBCNXM，活动 boot SHA 和原厂 CNSS2/WLAN build-id note 均匹配捕获样本；CNSS2 仅由 WLAN 持有，WLAN 引用为零。跟踪定位到检查器在权限 700 上把前导零表达式算成 20，误拒绝了正确目录。修复为文本八进制权限位检查，保持 root 归属、禁止链接及组/其他用户写入的规则；另将完整 uname 与模块 vermagic 字段分开，清单精确匹配已观测的完整运行版本。

92 项回归和 CI 通过，包含全部 512 种三位权限及四种特殊位组合。约 5.5 KB 修复包只替换检查脚本、deployment.tsv 和 SHA256SUMS；在原始 0131 包上模拟更新后全部八项校验一致，驱动、boot 和其他身份字段不变。原三模块未重编译或修改。更新后手机 check 已回传并通过：八项文件校验、完整 uname/boot、原厂已加载 note 与两份磁盘模块 SHA 均匹配，exit 0。尚未观察到备份或驱动替换，不计作运行时 ABI/RF 验收。见 [0132 修复证据](POPSICLE-CHECKER-FIX-0132.md)。

## 最新阶段 0131（部署/回退工具与手动试验包生成通过，尚未操作手机）

新增三模块独立工具和固定产物打包器，复用原样 0130 ELF；旧两模块脚本拒绝 checked 配对。设备端核对固件、当前槽位 boot、原厂/候选 build-id note、文件 SHA 和 holders，先备份原厂模块/用户状态，再以写前 intent 阶段记录每个副作用。restore 仅接受健康 ACTIVE 同 boot-id 事务，先完成 live-unload 才普通删除 WLAN→CNSS2→provider；任何失败/中断立即停止，不强制卸载、不重放未知动作。原厂文件与启动配置不修改；状态/锁隔离并与旧工具互斥。

86 项本地与 CI 回归及 shell 语法通过；CI 成功生成约 171 MB 的手动实验包。外/内 ZIP 摘要、9 个包内文件、全部校验清单、当前脚本、原样三模块和 boot/stock note 记录已核对。新增 status/check 都是只读，backup 只复制数据，apply/restore 必须显式调用。该包不是模块管理器安装器。下一步应先取得手机只读身份/依赖快照，原厂加载器/sysfs/平台卸载重载、private ABI/KCFI、RF/Apple 互传仍需实机验收。见 [0131 流程和限制](POPSICLE-PAIR-DEPLOYMENT-0131.md)。

## 最新阶段 0130（外部一次性卸载控制器、十套 C 验收及真实配对构建通过）

补丁 0064 在成功初始化后为外部 provider 注册 typed 卸载回调并增加独立引用。控制器拒绝 COMING/繁忙请求，准入后关闭 execution 入口，失败保存错误并保留引用，成功在 WLAN 返回且注册表为空后释放最后控制器引用。WLAN 生命周期互斥与一次加载门禁阻止重载/模式切换，实验软加载/卸载路径关闭；正常 module-exit 不重复销毁已经完成的 HDD 图。新增 provider 的显式 0200 请求入口，默认不自动请求。

63 项本地 Python 回归、精确正反和移除包装后整份主文件一致性检查通过。联合测试的 9 个隔离场景、1 个并发请求/6 项错误注入，以及原有九套 C 夹具均通过；十套重新组装源码/生产哈希与下载产物一致。真实三模块已严格配对链接：原厂 CNSS2 81/81 导出记录及前置字匹配；provider 旧 20 项记录不变、增加两个 live 接口；导入 15/364/602 项匹配。WLAN 强导入 arm，typed callback 入口前置字与 provider int(void) 函数匹配，provider 控制参数权限 0200、owner/ops/setter 重定位已核对，load_error 仍为 0444。完整/紧凑产物、ELF/type-inputs 摘要已核对；默认完整诊断另行运行。默认消费者关闭，手机未操作；正常原厂加载器/sysfs/文件排空和实机 RF 尚未验收，部署替换/回退仍待实现。见 [0130 控制器与边界](POPSICLE-LIVE-UNLOAD-0130.md)。

## 最新阶段 0129（完整 HDD 卸载结果、九套 C 验收及配对构建通过）

补丁 0063 为整个 HDD 卸载函数补齐结果输出：四处提前返回传播实际错误，仅完整清理尾部结束才报告成功。checked transition 错误不再先触发 QDF_BUG；底层注销及后续同步失败保留剩余组件/同步资源，并进入已有隔离状态，阻止软卸载失败后重新加载。新增内部 typed entry，未导出或安装自动调用入口，也未释放最后模块引用。

63 项本地 Python 回归、原生还原、独立补丁正反检查通过。新增 18 个完整卸载场景/5 项错误注入及原有八套 C 夹具全部通过；九套夹具、生产文件和原生片段哈希重新组装核对一致。真实 CNSS2/provider/WLAN 已严格配对链接，原厂 81/81 导出记录及前置字匹配，13/364/601 项导入记录匹配。新增 checked 卸载函数存在于实际 WLAN ELF，未导出，load_error 参数仍为 0444。完整/紧凑产物、模块及 type-inputs 摘要已核对；默认完整诊断工作流仍另行运行。下一步仍需外部控制器串行化、成功后的 module-exit 分流与外部返回后的引用释放，再接部署回退。默认实验开关关闭，手机未操作。见 [0129 实现范围](POPSICLE-UNLOAD-RESULT-0129.md)。

## 最新阶段 0128（注册失败回滚、八套 C 验收与真实配对构建通过）

补丁 0062 为注册返回增加明确的回调发布回执；干净失败可重试，可能发布回调的失败保留整个加载图。PLD 后续总线失败先执行 checked PCIe 注销，拒绝时停止其他清理；HDD 注册和晚期加载失败均传播拒绝。针对模块初始化负返回会释放代码的问题，保留态由只读 mishare_load_error 报告失败并驻留，成功加载持续持有引用；受控正常卸载仍待实现。

63 项本地 Python 回归、固定源码完整补丁应用/七文件正反检查通过。新增 19 个注册/完整 HDD 加载场景和 6 项错误注入，以及原有七套 C 夹具均在 Actions 通过；八套产物哈希重新组装核对一致。真实 CNSS2/provider/WLAN 已严格配对链接：原厂 81/81 导出记录与入口前置字匹配，仅两个显式 checked 扩展，导入 13/364/601 项匹配；实际 WLAN 同时强导入 checked 注册/注销、无旧生命周期导入，错误状态参数权限 0444。完整产物、ELF 与 type-inputs 摘要已核对。默认完整诊断工作流仍另行运行；默认实验消费者关闭，手机未操作。见 [0128 实现与限制](POPSICLE-REGISTRATION-0128.md)。

## 最新阶段 0127（原厂 81/81 记录匹配，真实 checked WLAN 配对与 C 验收通过）

固定 Qualcomm 原始 WLAN 提交中找到完整 TSF/SMMU/Wonder 实现和 Direct Refill 能力项；原厂反汇编确认能力编号 5 读取位 7。补丁 0061 原样移植完整函数并接入 GPIO/MMIO/IRQ、component probe/remove、SMMU 与六项能力枚举，移除多余旧 GPIO 导出，不使用空壳函数或 CRC 改写。来源 Git blob/SHA256 与 13 个函数体已核对。

62 项本地回归、独立补丁正反、11 个平台文件还原与七套 C 夹具验收通过。真实 CNSS2/provider/checked WLAN 已编译并严格链接：原厂 81/81 导出记录精确匹配，仅新增 checked 接口；三模块导入记录 13/364/601 匹配，WLAN 强导入新接口、无旧注销导入/未解析符号，实际回调槽位直达外部 provider。完整产物摘要、三份 ELF、type-inputs、81 个旧导出及四个 PCIe 回调前置数据字已核对。手机未操作，默认实验开关与无线后端仍关闭；注册失败展开、安全卸载与实机部署仍需验收。见 [0127 移植与限制](POPSICLE-CNSS2-UPSTREAM-0127.md)。

## 最新阶段 0126（实际 CNSS2 已编译链接，原厂接口门禁阻断）

新增独立的 CNSS2/provider/WLAN 严格配对工作流。恢复九个真实原厂早期提供者的 141 项导出，51 个原厂 CNSS2 导入 CRC 与实际导出全部匹配，固定核心与 29 个提供者覆盖原厂 CNSS2 的全部导入。构建选用固定 SoC MHI 头文件和目标配置，要求原有 81 个 CNSS2 导出记录不变，才允许继续 checked WLAN 配对，不修改或放宽 CRC。

62 项本地回归、脚本/YAML、0059/0060 补丁正反及八个平台源文件还原检查通过。最新 stop-admission 的六套 C 夹具通过，产物摘要、重组夹具/生产/原生哈希与真实构建 type-inputs 已核对。三项编译错误已按固定源码修复。[Actions 42215079411](https://github.com/xxz3312/XAirDrop-17/actions/runs/42215079411) 已完整编译并严格链接实际 CNSS2：provider/CNSS2 的 13/362 项导入记录匹配，共有 77 个导出入口前置数据字一致；旧导出记录 76/81 精确匹配，四项缺失、一项 CRC 不同，另多出一个 GPIO 导出，故严格门禁拒绝继续 WLAN 配对。四个缺失定义不在当前固定开源树中，下一步需定位目标 TSF/SMMU/Wonder 实现和 cnss_get_fw_cap 类型差异，不能添加空壳接口或改写 CRC。默认开关关闭，手机未操作，无线后端未开启。见 [0126 配对门禁](POPSICLE-CNSS2-PAIR-0126.md)。

## 最新阶段 0125（PCIe / CNSS2 checked 注销源码，联合 C 验收通过）

补丁 0057 为实际 PEACH PCIe/CNSS2 增加独立 checked 注销：原生同步事件显式传递回执，remove 错误在清 PROBED/ops 和断电前返回；投递/准入/执行失败进入 terminal 状态，旧入口不能重放。补丁 0058 提供 opt-in 原生 PCIe 消费者，直接使用 v3 provider 槽位、PSOC transition 内的 remove preflight 与回执，以及 PCIe→PLD→HDD 拒绝传播。电源尾部失败保留剩余状态，不承诺撤销此前完成的硬件/WLAN 操作。

新增真实平台/消费者联合 C 夹具，57 项本地 Python 回归、源码组装及独立补丁正反检查通过。[Actions 42201870635](https://github.com/xxz3312/XAirDrop-17/actions/runs/42201870635) 的 stop-admission 作业通过：两组成功、九组失败、七组准入拒绝及六项错误注入通过 ASan/UBSan/leak detection；原有五套回归通过。ZIP 摘要与六套重新组装夹具、原生片段及生产哈希核对一致。完整诊断构建仍未验收。默认实验开关仍关闭，平台二进制/配对 ABI 未验收，手机未操作。见 [0125 边界与限制](POPSICLE-CNSS-CHECKED-0125.md)。

## 最新阶段 0124（PCIe 类型化边界与原生回调修复，默认模块构建与 C 验收通过）

已按实际 PCIe/CNSS2 签名新增独立 v3 描述符与四个外部入口，保留设备 ID，沿用共享 owner/引用/关闭保护；v2 布局不变，错总线拒绝。补丁 0056 修复四个原生回调的空 context/ops 访问及 idle_shutdown 指针检查错误。新增真实 provider + 四个原生 PCIe 回调 C 夹具、四类并发关闭和六项错误注入，接入默认 CI，真实 provider 导出门禁扩展为 17 项。

57 项本地 Python 回归、源码组装与独立补丁正反检查通过。[Actions 42198546212](https://github.com/xxz3312/XAirDrop-17/actions/runs/42198546212) 的 stop-admission 作业通过，新增四类 PCIe 并发关闭与六项错误注入、原有 host/runtime/IPCI/ICNSS 参考夹具均通过 ASan/UBSan/leak detection。产物 ZIP 摘要及五套重新组装夹具/生产哈希已核对；七项默认作业均通过；完整紧凑产物摘要、五个模块记录检查、选定布局和 provider 的 17 项实际导出已核对。生产 PCIe 注册槽位尚未切换，CNSS2 checked 注销/清空/断电返回链尚未接入；本阶段不计作实机入口保护完成。手机未操作，无线后端仍关闭。详见 [0124 边界与限制](POPSICLE-PCIE-BOUNDARY-0124.md)。

## 最新阶段 0123（ICNSS 参考 CRC 已修复，实际目标总线已纠正）

定位到独立构建缺少 gendwarfksyms 稳定模式：沿用内核原有 KABI 注解，设置 KBUILD_GENDWARFKSYMS_STABLE=1 后，60 个旧导出记录全部与原厂匹配，53 处 CRC 差异归零。非稳定/稳定构建的 .text、.init.text、.exit.text 字节哈希一致，60 个旧导出入口数据字一致；provider 与 ICNSS 的记录范围内版本检查通过，没有增加 KABI 规则或放宽 CRC 检查。实际类型流、配置和原有 declonly 规则已保存并核对。

重要纠正：原厂 qca_cld3_peach_v2.ko 实际导入 cnss_wlan_register_driver / cnss_wlan_unregister_driver，依赖 cnss2；固定配置开启 PCIe CNSS、未开启 IPCI ICNSS。因此此前把 ICNSS 作为本机主线不准确。0118–0122 中 IPCI 专用入口的源码/C 验证属于旁支参考，不能作为本机入口已接通的证据；通用主机/runtime 层也仍需核对实际 PCIe 接入。

新增源码配置与实际原厂导入的总线准入检查及四项回归，57 项 Python 检查通过。默认 CI 不再要求错误总线的配对；ICNSS 仅保留为显式手动触发的 reference-only 构建。严格配对入口遇到 PCIe 目标会拒绝，不会强开 IPCI 或声称目标配对完成。下一步主线是 pld_pcie.c 与 platform/cnss2/pci.c，尚未完成该接入。手机未操作，无线后端仍关闭。见 [0123 说明](POPSICLE-CRC-TYPES-0123.md)。

## 阶段 0122（实验版 WLAN 消费者验证通过，平台 ABI 配对阻断）

补丁 0053 通过独立编译开关让完整原生 WLAN checked 注销函数调用平台新接口，并直接使用外部 provider 回执查询；不使用目标 GKI 未导出的 symbol_get，也不在失败后回退旧接口。默认构建保留原调用路径，无线后端仍关闭。

新增独立 checked-platform CI 作业，从固定 canoe_gki ICNSS 配置构建真实平台模块和 provider，移除本次替换模块的原厂 symvers 条目，再用真实生成的导出表链接实验 WLAN。要求原有 ICNSS 导出齐全且 CRC 不变、新接口真实导出、WLAN 确实导入新接口且不导入旧注销接口、依赖及版本记录通过；不放宽 modpost，不改写版本。新增两组消费者成功、两组失败保留及旧接口回退错误注入。53 项 Python 检查、脚本语法、八作业 YAML、源码组装及补丁正反检查通过；[Actions 42188446777](https://github.com/xxz3312/XAirDrop-17/actions/runs/42188446777) 的四套生产 C 复验通过：包括真实 opt-in 消费者的两组成功/两组失败、九项平台错误注入及原有回归；紧凑摘要与四套重新组装夹具/生产源码哈希已核对。真实 ICNSS 已完整编译并严格 modpost 链接，新增接口实际导出，但 60 个旧导出中有 53 个 CRC 与原厂不同，故未继续实验 WLAN 配对链接，0122 尚未完整离线验收。

已从原厂补充包 vendor_boot.img 恢复 socinfo、pdr_interface、pinctrl-msm 三个真实提供者的 29 项导出，六个缺失符号均与原厂 ICNSS 导入 CRC 匹配。候选 device 大小 912 字节、59 个直接成员偏移/位宽与原厂 BTF 一致，但不能解释或消除传递类型 CRC 差异。下一步定位 genksyms 类型与构建配置差异；不放宽 CRC 检查。

配对构建产物仅作诊断，不自动打包进安装模块、不替换手机平台驱动。手机加载、平台配置/私有 ABI/KCFI、卸载替换顺序、固件与无线实测仍需验收。见 [0122 说明](POPSICLE-CHECKED-PAIR-0122.md)。

## 最新阶段 0121（可选 ICNSS 注销扩展源码，完整离线验收通过）

补丁 0052 为锁定平台源码增加独立 `icnss_unregister_driver_checked_v1`，不扩展原生 ops 结构体。同步、不可中断事件携带本次归属和外部回执查询；remove 返回后先检查结果，失败保留 ops/PROBED/UNLOADING/关机阻塞，设置终止状态位并拒绝后续 checked/legacy 注销重放。无 probe 的 checked 清理暂时拒绝，未提供强制恢复接口。

provider 增加只读、按设备身份检查的 remove 回执查询，未开始/未完成/失败不返回成功，不释放模块引用。新增联合夹具执行真实 provider、完整原生 PLD remove、平台 handler/新旧注销入口，以真实 pthread 模拟同步事件投递，并要求八项错误注入被拒绝。53 项 Python 检查、源码组装、三份平台源码完整还原及补丁正反检查通过，最新 [Actions 42105131303](https://github.com/xxz3312/XAirDrop-17/actions/runs/42105131303) 生产 C 快速作业通过：两组成功、12 组隔离 remove 失败、7 组准入拒绝、旧接口限制用例及八项错误注入通过，原有主机/runtime/外部执行回归通过（ASan/UBSan 与 leak detection）。紧凑 ZIP 摘要、重新组装的四套夹具和生产/原生哈希已核对。七项作业全部通过；紧凑完整产物摘要、生产哈希、主机报告、模块版本/符号与选定布局已核对，0121 完整离线验收完成。平台二进制不属于该阶段构建。

这是可选平台接口的实现和离线验证阶段：当前目标构建仍沿用原厂 ICNSS，WLAN 的现有注销调用方尚未改用新接口。平台二进制未构建/安装，新保护尚未作用于手机。需要完成平台构建/ABI/部署方案和消费者接入后，才能称作目标路径修复。其他电源/恢复入口与 module-exit 失败仍未协调；无线后端保持关闭。见 [0121 说明](POPSICLE-ICNSS-CHECKED-0121.md)。

## 最新阶段 0120（IPCI 注销回执与错误传播，完整离线验收通过）

补丁 0051 在 ICNSS 注销前建立 provider 作用域。正常运行另取模块引用；GOING 时只记录调用方持有的 module-exit 执行资格。remove 的失败和未完成回执阻止作用域释放，live 失败引用保留且不提供重置接口。

ICNSS 自身的事件投递错误也计入回执，拒绝重放。锁定平台源码仍会在 void remove 返回后清空自身状态并断电；本阶段尚不能阻止该平台尾部。

checked IPCI→PLD→HDD 返回链在其他总线注销、清空 PLD 状态及组件拆除前传播拒绝，主卸载路径检查返回值。公共 void 兼容接口仍存在，忽略结果的旧调用方不获认证。新增完整原生 remove/checked 函数场景与六项错误注入。53 项 Python 检查、源码组装、还原及补丁正反检查通过，最新 [Actions 42102327073](https://github.com/xxz3312/XAirDrop-17/actions/runs/42102327073) 生产 C 快速作业通过：12 组注销回执场景、14 项外部错误注入（6 项新增）、原有主机/runtime 与 SSR/idle 并发回归通过，使用 ASan/UBSan 与 leak detection。紧凑 ZIP 摘要、重新组装的三套夹具及生产/原生源码哈希已核对；七项作业全部通过；紧凑完整产物摘要、生产哈希、主机报告一致性、模块版本/符号与选定布局已核对，0120 完整离线验收完成。

真实 ICNSS 排空、模块加载器、失败 module-exit、物理热拔插与其他回调仍未验收。无线后端关闭，手机无需操作。见 [0120 说明](POPSICLE-UNREGISTER-RECEIPTS-0120.md)。

## 阶段 0119（IPCI idle 回调外部执行引用，完整离线验收通过）

补丁 0050 将 idle shutdown/restart 直接接到外部 provider，覆盖空闲回收释放最后主机引用后仍需返回 WLAN 调用栈的窗口。原生 idle shutdown 的指针检查从无关的 `shutdown` 修正为实际调用的 `idle_shutdown`；保留上下文缺失、回调缺失及原生 errno 传播。

回调表扩展为 v2，使用独立登记导出名，不提供 v1 别名；provider/WLAN 需要同源配对构建。新增目标 provider 导出检查，要求七个执行接口并拒绝旧登记别名。53 项 Python 检查、源码组装、完整原生源码还原和补丁正反向检查通过；[Actions 42008448819](https://github.com/xxz3312/XAirDrop-17/actions/runs/42008448819) 生产 C 快速作业通过：idle 最后私有引用/错误码/回调 guard/缺失路径、三类真实 pthread 回调与关闭重叠、八项外部错误注入（含三项新增）及既有主机/runtime/上层回归全部成功（ASan/UBSan 与 leak detection）。紧凑 ZIP 摘要、三套重新组装夹具、provider/shared header/原生 IPCI 哈希及 v2 登记协议已核对。七项作业全部成功；紧凑完整产物摘要、生产哈希、主机报告一致性、目标 ELF v2 导出、模块版本/未解析符号与选定布局均通过，0119 完整离线验收完成。见 [0119 说明](POPSICLE-IDLE-EXECUTION-0119.md)。

remove 的模块注销期资格、其他原生回调和 metadata 自身解绑仍待协调。无线后端保持关闭，手机无需操作。

## 阶段 0118（IPCI SSR 的外部执行/返回边界，完整离线验收通过）

补丁 0049 将 ICNSS 的 SSR shutdown/reinit 槽直接指向独立 provider。provider 在进入完整 WLAN/PLD 回调前取得模块引用，全部 WLAN 调用栈返回后才释放，再返回外部 ICNSS。上层显式卸载在拆除前关闭入口；仍有执行中的回调时返回 busy 并保留登记，后续可重试。没有永久登记引用，也没有新增自动重试/强制清理接口。

新增执行边界夹具覆盖真实 pthread 回调/关闭重叠、最后私有引用释放、取引用失败、重复/外部归属、登记回滚及五项外部错误注入；另有两组真实上层卸载前缀场景和一项 busy 传播错误注入。53 项 Python 检查、主机/外部夹具组装、完整原生 IPCI 源码还原及补丁正反向检查通过；[Actions 41994547385](https://github.com/xxz3312/XAirDrop-17/actions/runs/41994547385) 生产 C 快速作业通过：主机/runtime 既有回归、两组上层 busy 场景、一项上层错误传播变异、外部真实 pthread 重叠场景及五项外部错误注入全部成功（ASan/UBSan 与 leak detection）。紧凑 ZIP 摘要、重新组装的三套夹具、生产/原生 IPCI/provider/shared header 哈希已核对。七项作业全部成功；完整目标模块链接、选定布局、记录范围内的加载器与符号检查通过。完整/快速主机报告一致，紧凑诊断包摘要及准确源码哈希已核对，0118 完整离线验收完成。大型诊断归档未下载。见 [0118 说明](POPSICLE-EXTERNAL-EXECUTION-0118.md)。

只覆盖 IPCI SSR shutdown/reinit 的 WLAN 返回栈；物理 remove、其他原生回调、metadata 自身解绑及真实 ICNSS 排空/模块加载器契约仍待验收。无线后端保持关闭，手机无需操作。

## 阶段 0117（停机记录与上层电源的独立模块引用，完整离线验收通过）

停机 journal 在记录私有状态前独立取得模块引用；等待、身份错误与永久错误继续持有，只有原生模块关闭成功后才在解锁后释放。补丁 0048 为上层电源保护另取一份引用，覆盖“对象已退役、模块 journal 已清空，但电源尾部未完成”的窗口；仅原生完成尾部返回后释放。上层取引用失败时，void shutdown 回调在拆除动作前停止，reinit 拒绝缺失引用。

53 项 Python 检查、源码组装、继承原生源码还原及补丁正反向检查通过。[Actions 41990018323](https://github.com/xxz3312/XAirDrop-17/actions/runs/41990018323) 生产 C 主机/runtime 快速作业通过：四组新增场景、六项新增错误注入及既有回归成功（ASan/UBSan 与 leak detection）。紧凑 ZIP 摘要、生产/原生源码及重新组装夹具哈希已核对。七项作业全部成功；完整 WLAN 链接、选定布局、记录范围内的加载器与符号检查通过。紧凑诊断包摘要、准确源码及完整/快速主机报告一致性已核对，0117 完整离线验收完成。大型诊断归档未下载。测试计数器会在继承场景之间丢弃模拟的保留状态，这不是生产清理/重置 API。见 [0117 说明](POPSICLE-STOP-MODULE-LEASES-0117.md)。

仍需原生调用方维持最终 put 到返回期间的执行与父资源同步；实际模块加载器、强制卸载、物理消失及活动无线流程未验收。手机无需操作。

## 阶段 0116（主机与运行时模块引用，完整离线验收通过）

主机对象与独立 runtime owner 各自在分配/发布前通过 `try_module_get(THIS_MODULE)` 取得一份 WLAN 模块引用。模块已进入退出态时拒绝新建；分配失败、父引用失败、重复/隔离准入失败等回滚路径释放引用。异步删除、隔离保留、物理 VDEV 已释放但 owner 尚未退役时继续持有；仅最终登记移除与存储释放后 `module_put()`。host/runtime 可分别存活，不能互相替代引用。

[Actions 41986954101](https://github.com/xxz3312/XAirDrop-17/actions/runs/41986954101) 生产 C 主机/runtime 快速作业通过：五项主机模块引用场景、主机与 runtime 各三项新增错误注入及既有场景通过（ASan/UBSan 与 leak detection）。紧凑 ZIP 摘要、生产源码及重新组装的主机/runtime 夹具哈希已核对。53 项 Python 检查通过；七项作业全部成功；完整 WLAN 链接、选定布局、记录范围内的加载器及符号检查通过。完整诊断主机报告与快速报告一致，紧凑产物摘要和准确源码哈希已核对，最终 bookkeeping 夹具的模块引用边界断言也已实际通过，0116 完整离线验收完成。大型诊断归档未下载。首次运行的缺少 get 变异在回滚 module_put 平衡断言处提前捕获，现修正预期标记，生产代码未改。见 [0116 说明](POPSICLE-OWNER-MODULE-REFS-0116.md)。

独立停机记录与上层电源保护在对象退役后仍可能存活，本阶段尚未为它们持有模块引用；整个 kernel module exit 协调尚未闭合。调用方继续负责原生执行与父资源同步，强制卸载和物理消失未获认证。无线后端保持关闭，手机无需操作。

## 阶段 0115（上层显式卸载准入，完整离线验收通过）

补丁 0047 在 `hdd_driver_unload()` 获得 driver transition 后，先排空操作并检查全局主机/运行时归属、模块停机记录和上层电源保护。有私有对象、跨 PSOC 归属、失败/等待/残留记录时，在修改 loaded/unloading 标志、注销总线、拆除组件之前返回，并释放本次取得的 driver transition。该检查不依赖当前 HDD 查找，不能用空 HDD 或切换父身份绕过。

保留公开 void 接口，并通过逐次调用的拒绝结果恢复软卸载调用方预先设置的 `g_soft_unload`，避免拒绝后误报“已禁用”。[Actions 41984362810](https://github.com/xxz3312/XAirDrop-17/actions/runs/41984362810) 生产 C 快速作业通过：新增 17 组上层卸载场景、4 组真实软卸载调用场景、9 项新增及 90 项继承错误注入检查成功（ASan/UBSan 与 leak detection）。53 项 Python 检查、源码组装、完整原生卸载体/软卸载调用方还原、干净前置源码正向补丁链及反向检查通过；紧凑 ZIP 摘要、生产源码、重新组装夹具及原生卸载体/前缀哈希已核对。七项作业已全部成功，完整 WLAN 链接、选定布局、记录范围内的加载器/符号检查通过；紧凑诊断包摘要及完整主机报告与快速报告一致，0115 完整离线验收完成。大型诊断归档未下载。见 [0115 说明](POPSICLE-DRIVER-UNLOAD-0115.md)。

这是可返回的显式 driver unload 路径保护。内核 module_exit 返回无法取消模块移除；模块代码引用、外部物理卸载、既有 SSR transition 等待及完整卸载后半段仍未验收。radio 后端保持关闭，手机无需操作。

## 阶段 0114（IPCI remove 注销前保护，完整离线验收通过）

补丁 0046 在 `pld_ipci_remove()` 注销 PSOC sync 查找之前，先排空已有操作，再检查私有停机记录、主机/运行时归属及后端注销结果。有等待、错误、身份不匹配或仍持有私有对象时，保留原查找与独占 transition，不进入原生 remove/父资源删除；空私有状态保留原生清理路径。这是拒绝不安全注销的保护，尚未实现物理热拔插或完整 module exit 协调。

[Actions 41977591491](https://github.com/xxz3312/XAirDrop-17/actions/runs/41977591491) 七项作业全部成功；新增 17 组 remove 场景、10 项错误注入及既有 80 项错误注入通过。53 项 Python 检查通过；完整 WLAN 链接、选定布局、记录范围内的加载器与符号检查通过。七个紧凑产物摘要已验证，完整诊断与快速主机报告一致，生产源码、重新组装夹具、原生 remove 函数及既有全文件还原审计通过。大型诊断归档未下载。本地管理帧 C 夹具受 LeakSanitizer/ptrace 环境限制；C sanitizer 验收以本次 CI 为准。

下一步：补齐卸载/物理 remove 调用方如何保留或交还生命周期的协调，再推进活动 START/UP 与真实无线后端。当前无需手机操作，Apple 发现、握手和双向互传仍未验证。见 [0114 说明](POPSICLE-IPCI-REMOVE-0114.md) 与 [验收记录](research/popsicle-ipci-remove-0114-validation.json)。

## 阶段 0113（完整离线验收通过）

补丁 0045 将原生 reinit 回调接到 0112 模块续执行，并复用原电源停机完成尾部。准确 HDD/回调设备匹配且模块停机及 LPASS/SMMU 尾部完成后，才清除 SoC 保护并进入原生 reinit；等待或永久错误保留保护和原独占 transition，报告当前 errno。模块空记录、单独模块完成及 owner 消失不能替代电源完成确认。这里的确认指原有尾部函数执行结束，不代表单独验证了硬件/固件 ACK。

53 项 Python 检查、源码组装、完整原生 power 文件及既有源文件还原、补丁反向检查通过。[Actions 41930505140](https://github.com/xxz3312/XAirDrop-17/actions/runs/41930505140) 生产 C 快速作业通过：16 组新增上层场景、十项新增及 70 项既有变异控制通过；ZIP 摘要、生产/原生源码、重建夹具、原生入口/完成/模块续执行/电源 helper 与未改 OSIF resume 哈希已核对。七项 CI 已全部通过；完整 WLAN 链接、选定布局、记录范围内的加载器检查及主机符号检查通过。完整诊断报告与快速报告一致，紧凑产物摘要及对应源码/夹具哈希已重新核对。首次 CI 的正常生产 C 场景通过，既有模式变异改由上层更早捕获；断言及电源完成顺序检查已同步，生产代码未改。

每次原生 reinit 回调只尝试一次，未安装独立 worker、定时器或平台重试策略；仍需调用方维持原生父生命周期。物理 remove/exit 协调、自动 owner 交还、活动 START/UP 支持和真实无线后端仍待完成，手机无需操作。0111 已完成七项 CI 和完整离线验收。见 [0113 说明](POPSICLE-SSR-POWER-ACK-0113.md)。

## 阶段 0112（快速验证通过，完整构建运行中）

补丁 0044 复用原生模块停机体，新增显式续执行包装器；仅准确 HDD/device/PSOC/PDEV、原 driver_status、恢复态及 mission 模式下的 POST_DISABLED 异步等待可以被领取一次。从 CDS 停用后的边界重新进入限定回收并继续原生父关闭，重复等待可再次暂停；不重放模块停机前缀或 CDS。首次永久错误、前缀失败、父关闭失败及空记录均拒绝续执行。

53 项 Python 检查、源码组装、继承 parent 夹具组装、原生全文件还原及补丁反向检查通过。[Actions 41928166595](https://github.com/xxz3312/XAirDrop-17/actions/runs/41928166595) 生产 C 快速作业通过：17 组新增续执行场景、十项新增及 60 项既有变异控制通过。ZIP 摘要、生产/原生源码、重新生成夹具和实际原生入口/完成/续执行包装器哈希已核对；完整构建及其余回归仍在运行。首次运行正常生产 C 场景通过；身份变异在后续完成断言才被发现，现加强到拒绝当下检查等待状态未被消耗，生产代码未改。

这是显式模块层入口；没有自动 worker、上层调用、电源尾部完成确认或 SoC gate 清除，物理 remove 与无线后端也未接通。调用方必须保留原独占 transition 和完整原生父生命周期，借用身份记录不提供引用租约。见 [0112 说明](POPSICLE-SSR-RESUME-0112.md)。

## 阶段 0111（离线验收完成）

补丁 0043 在原生模块停机的首个副作用前记录私有恢复停机，并跟踪 CDS 停用成功、进入父关闭和本次完整结束三个边界。即使 owner 已回收或恢复标志清除，保留记录仍拒绝再次进入；父身份变化拒绝执行。原生 DP/PDEV 错误在返回值被后续成功覆盖前保留，只有同次完整成功且原生模块已关闭才清除记录；SoC 上层失败保护独立保留。

53 项 Python 检查、源码组装、原生全文件还原、有界补丁反向检查通过。[Actions 41925977115](https://github.com/xxz3312/XAirDrop-17/actions/runs/41925977115) 生产 C 快速作业首次通过：八组新增阶段场景、八项新增及 52 项既有变异控制通过；ZIP 摘要、生产/原生源码、重建夹具及实际入口/完成片段哈希已核对。七项作业现已全部成功，含完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录；七份 ZIP 摘要、57 份生产源码报告、快速/完整报告一致性、重新生成夹具及最终模块符号已核对。记录仅保存借用身份，不构成 HDD/组件引用；本轮没有异步续执行、重试或强制清除接口，也不覆盖物理 remove。无线后端继续关闭。见 [0111 说明](POPSICLE-SSR-JOURNAL-0111.md)。

## 阶段 0110（离线验收完成）

补丁 0042 将限定回收接到原生 CDS 停用成功后的入口。新增包装器对已显式交还、父身份匹配的 host 使用 RTNL trylock 进入现有限定 SSR 回收桥；同步完成后可继续停机，等待/错误保留 owner、更新后的 token 与父资源。失败仍受 0109 的重复停机/重初始化保护约束。

53 项 Python 检查通过，[Actions 41917643897](https://github.com/xxz3312/XAirDrop-17/actions/runs/41917643897)（`6f80bff`）生产 C 快速作业通过：18 个直接包装器场景、七项新增和 45 项既有变异控制通过。七项作业全部成功，含完整 WLAN 编译、CNSS、严格链接、七项布局和模块记录。七份精简 ZIP 摘要、57 份生产源码报告、快速/完整报告一致性、重建夹具、原生源码、包装器、有界补丁及最终模块符号已核对。测试中的 CDS 桩已移除模拟回收调用，由实际原生入口调用生产代码；资格与底层完成仍是模型。0109 已完成七项 CI 和完整离线验收；CI 按提交分别验证以保留其结果。异步停机恢复、完成确认、自动交还及物理 remove 协调仍待接入，backend 关闭。见 [0110 说明](POPSICLE-SSR-PREPARE-0110.md)。

## 阶段 0109（离线验收完成）

补丁 0041 在原生 SSR 的 CDS 停用边界拒绝未回收 owner 继续关闭后续父资源，并把私有会话停止错误传给电源停机上层。原生 SoC SSR 入口记录未完成状态，失败后拒绝重复部分停机与原生重初始化，并向等待方报告错误；owner 元数据消失不能清除未完成状态。无私有 owner 的既有行为保留。

[Actions 41913522724](https://github.com/xxz3312/XAirDrop-17/actions/runs/41913522724)（`aefa112`）七项作业全部通过：53 项 Python 检查、15 组 SSR 场景、45 项变异控制、既有原生组合、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。快速/完整构建报告一致，57 份含生产源码的报告、七份精简 ZIP 摘要、五个原生体和重建夹具/原生源码哈希、旧审计及原生电源停机最终模块符号已核对。 限定回收调用、异步恢复继续执行与物理 remove/close 路径仍待接入；失败状态没有强制清除接口，backend 保持关闭。见 [0109 说明](POPSICLE-SSR-STOP-0109.md)。

## 阶段 0108（离线验收完成）

补丁 0040 在原生 SSR 的适配器重置遍历中跳过登记表仍持有的私有 host，并归还当前迭代引用；普通 STA/P2P/SAP 和未登记 PAS 保留原处理。新增准确适配器指针归属查询，并使 host 的适配器发布与全局查询使用同一登记表锁，避免跨 PSOC 查询与发布并发。

[Actions 41901539216](https://github.com/xxz3312/XAirDrop-17/actions/runs/41901539216)（`ae65ac4`）七项作业全部通过：53 项 Python 检查、62 组原生重置合同、37 项变异控制、既有 host/runtime 及原生组合、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。快速/完整构建报告一致，生产源码与重新生成夹具哈希、原生函数/全文件还原、七份精简 ZIP 摘要和归属 API 最终模块符号已核对。 后续限定 SSR 回收调用、上层错误传播、异步重试与物理 remove/close 协调仍待接入，backend 保持关闭。见 [0108 说明](POPSICLE-ADAPTER-RESET-0108.md)。

## 阶段 0107（离线验收完成）

新增已交还 host 的显式 SSR 回收入口：不需要旧调用方槽位，沿用现有严格 SSR 回收桥推进 registry owner；覆盖不完整、等待、隔离错误和 sync 失败均保留 owner/更新后的 runtime token。修复同一 HDD 更换 PSOC 后可能被准确 PSOC 扫描漏掉的情况，普通 idle 与模式停机准入均拒绝父身份变化。

[Actions 41875529467](https://github.com/xxz3312/XAirDrop-17/actions/runs/41875529467)（`0e57e50`）七项作业全部通过：53 项 Python 检查、生产 host/runtime 快速夹具、32 项变异控制、36 次父身份拒绝及 SSR 序列、完整 WLAN 编译、CNSS、严格链接、七项布局与模块记录检查通过。快速/完整构建报告一致，57 份含生产源码的报告、七份精简 ZIP 摘要和新增 SSR API 的最终模块符号已核对。 完整原生 SSR/remove 上层调用、异步重试和父组件保留仍待接入；backend 保持关闭。见 [0107 说明](POPSICLE-HANDOFF-SSR-0107.md)。

## 阶段 0106（离线验收完成）

新增显式 host 所有权交还：关闭会话准入后将唯一 owner 留在登记表，并清空调用方槽位。补丁 0039 接入原生普通 idle 入口，只回收准确匹配且已交还的 host；RTNL 只尝试加锁，竞争、异步等待、隔离错误和 sync 异常均推迟停机并保留引用。回收后仍检查独立 runtime，原生接口打开检查和停止返回值保留。

[Actions 41857539940](https://github.com/xxz3312/XAirDrop-17/actions/runs/41857539940)（`688330f`）七项作业全部通过：53 项 Python 检查、生产 host/runtime 快速夹具、26 项变异控制、36 次父身份拒绝、完整 WLAN 编译、CNSS、严格链接、七项布局与模块记录检查通过。快速/完整构建报告一致，57 份含生产源码的报告、七份精简 ZIP 摘要和两项新增 API 的最终模块符号已核对。 完整 SSR/remove 协调、调用方自动交还及 idle 调度尚未接入，backend 继续关闭。见 [0106 说明](POPSICLE-IDLE-RETIRE-0106.md)。

## 阶段 0105（离线验收完成）

host 创建时持有 device、PSOC 和 PDEV 的分配引用，检查 PDEV 属于准确的 PSOC；失败逆序回滚。异步等待、回收拒绝和 sync 注销失败保留引用，完整 adapter/sync 关闭后才逆序释放。后续五个 host 入口拒绝 HDD 中已被替换的父对象，避免继续使用另一组父资源。

引用不保留 HDD、原生组件或固件；完整 remove/SSR 协调、独立 runtime 的父生命周期和真实无线后端仍待接入。[CI 41851852074](https://github.com/xxz3312/XAirDrop-17/actions/runs/41851852074)（`b09a4a9`）七项作业通过：生产 host 的引用回滚与保留、30 次父身份拒绝、七项新增及六项既有变异控制、53 项 Python 检查、既有组合、完整 WLAN 编译、CNSS、严格链接、七项选定布局及模块记录检查通过。快速作业与完整构建中的 host/runtime 报告一致，七份精简验证 ZIP 摘要和报告中的生产源码哈希已核对。 这不代表实机或 Apple 互通通过。见 [0105 说明](POPSICLE-PARENT-PINS-0105.md)。

## 阶段 0104（离线验收完成）

生产补丁 0038 将原有 idle 保护扩展为 host/runtime 两个登记表联合检查，并接入两条模式切换停机回调；模式切换总入口在停止适配器之前也拒绝存活 owner。独立 runtime、构造中、等待释放、已 final-free 但尚未退登记以及隔离错误对象均保持阻止停机。普通 idle 返回 EAGAIN；模式切换直接返回拒绝错误，内层标志在拒绝时保持原值。登记表为空时保留原生停止返回值。

[CI 41796505527](https://github.com/xxz3312/XAirDrop-17/actions/runs/41796505527)（`b55d01c`）七项作业成功。生产 host/runtime 准入检查、四个原生准入入口及六项变异控制、53 项 Python 检查、全部既有组合、完整 WLAN 编译、CNSS、严格链接、七项布局和模块记录检查通过。十二份组合源码、两个生产 helper、四个停机入口、55 份报告中的生产源码、37 个路径别名及七份验证 ZIP 摘要均核对；快速作业两份报告与完整构建对应报告一致。0038 独立重放与有界原生改动还原检查通过。

这些检查依赖调用方保持既有独占 driver/psoc transition，既不持有父引用，也不自动回收对象。部分 remove/SSR 上层忽略停止返回值，本轮未接入这些路径，不能认定完整 remove/SSR 已安全。真实 IRQ/DMA/迟到回调、物理 HTT 释放及完整父资源停机协调仍待继续。backend 保持关闭，手机无需操作。

见[0104 说明](POPSICLE-STOP-ADMISSION-0104.md)。

## 阶段 0103（离线验收完成）

0103 已完成离线验收：[CI 41782619036](https://github.com/xxz3312/XAirDrop-17/actions/runs/41782619036)（`af57774`）六项作业成功。88 项残留缓冲区检查（72 项独立、16 项停止链集成）、116 项失败控制及全部旧组合通过；53 项 Python 检查、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。十二份组合源码、两个原生清理函数、55 份报告中的生产源码、37 个路径别名及六份验证 ZIP 摘要均已核对。

原生 RX/TX 清理函数通过模型 CE 撤销/取消队列执行；DMA unmap、direct-link pages 和 TX completion 仍为模型。HTT/无回调缓冲区按原路径保留归属，断言完成后由模型所有者清理。HTT 控制包在真实流程中可能已由其他路径释放；夹具使用活体宿主缓冲区记录归属，未重放此前释放历史。真实环/DMA、原生 HTT TX completion、物理 HTT free 和生产父资源停机协调仍待继续。backend 保持关闭，手机无需操作。

见[0103 说明](POPSICLE-CE-BUFFERS-0103.md)。

## 阶段 0102（离线验收完成）

在既有 HTC stop → multibus HIF stop 路径中接入原生 `hif_ce_stop()`、`hif_disable_isr()`、`hif_ipci_disable_isr()`、`hif_destroy_oom_work()` 和 `hif_buffer_cleanup()`。原生 IPCI 顺序为 exec kill、屏蔽中断、CE tasklet kill、总中断 tasklet kill、计数清零，再进入 OOM 工作与 CE 资源清理。模型 CE tasklet-kill 原语放行并 join 一条真实主机线程，消息通过原生回调和生产解析器结束后才允许清理；这仍是模型同步合同。

[CI 41778488794](https://github.com/xxz3312/XAirDrop-17/actions/runs/41778488794)（`99d3f8d`）五项作业成功：256 组受控线程停止检查、192 组组合、64 项回调检查、303 项解析检查、32 组停止顺序和 8 项 CE 长度检查、110 项失败控制、十项既有独立组合、53 项 Python 检查、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。十一份组合源码和五个新增原生函数、54 份报告中的生产源码、37 个路径别名及五份 ZIP digest 均独立核对。首次夹具 HIF 类型重复定义已修正并记录；未新增生产补丁。见[0102 说明](POPSICLE-CE-STOP-0102.md)及[验收记录](research/popsicle-ce-stop-0102-validation.json)。

256 项独立选择 SG、WDI、6/16 pipes、started、diagnostic handle、sleep timer、procfs 和 NSS；消息格式/对齐随其中两个维度选择，不代表手机实际配置。原生循环覆盖空 CE state、NSS buffer gate、有/无 CE handle、source-entry lock、句柄/大小清零与 timer 条件。中断、tasklet、work、残留收发清理、CE fini、锁和 timer 底层仍为模型；受控 pthread 不代表真实内核并发或 DMA 排空。回调指针仍保留，物理 HTT free、生产父资源停机及整机验证继续待办。backend 保持关闭，手机无需操作。

## 阶段 0101（离线验收完成）

接入原生 HIF `hif_update_pipe_callback()` 回调保存、`hif_ce_do_recv()` 长度设置/超长释放、multibus `hif_stop()` 转发、`htc_stop()` 两个 SG 分支和 `reset_endpoint_states()`。原生 CE 收包通过保存的 HP 回调进入 HTT 适配、生产解析器及既有释放链。停止函数先清理 endpoint RX/TX 和 polling timer，再调用下层 HIF，随后按 WMI/control/非轮询 HTT 策略清理 lookup queue、排空 SG 并重置 endpoint。

[CI 41665851697](https://github.com/xxz3312/XAirDrop-17/actions/runs/41665851697)（`fcb336d`）四项作业成功：32 组停止合同、8 项 CE 长度/所有权合同、192 组组合、64 项回调合同、303 项解析合同、94 项失败控制、九项既有独立组合、53 项 Python 检查、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。十份组合源码和五个新增原生函数、53 份报告中的生产源码、37 个路径别名及四份 ZIP digest 均独立核对。两次夹具编译警告（断言括号和变异未用变量）已修正并记录；未新增生产补丁。见[0101 说明](POPSICLE-TRANSPORT-STOP-0101.md)及[验收记录](research/popsicle-transport-stop-0101-validation.json)。

本轮也确认：endpoint reset 不清除已保存的接收回调指针；排空并阻断迟到消息必须依赖下层停止同步。bus stop 中最后一条已接纳消息、停止后入口关闭及 context release 均为模型合同，未证明真实并发/中断/DMA 排空或物理 HTT free。CE 采用源码 16-pipe 分支，SG 两分支覆盖不代表手机配置。queue/timer/layout 仍为模型，生产父资源停机协调、真实总线与整机验证继续待办。backend 保持关闭，手机无需操作。

## 阶段 0100（离线验收完成）

执行原生 `htt_soc_initialize()`、`htt_htc_soc_attach()`、`dp_htt_hif_t2h_hp_callback()`、`dp_htt_h2t_full()` 和两个 `dp_hif_update_pipe_callback()` 源码分支。模型下层 HTC/HIF 端点保存原生注册的回调/上下文，再通过保存的指针送入消息；原生 HP 适配检查 pipe 5、清零包、填写成功状态和 nbuf，进入原接收函数的 unmap 消费前缀及 0099 生产解析器，再衔接既有 DP 释放链。WDI-disabled 原分支保持 no-op，普通 HTC 接收仍可用；连接失败不发布模型端点。

代码和相关用例集中完成后统一验证，[CI 41625241354](https://github.com/xxz3312/XAirDrop-17/actions/runs/41625241354)（`d09f2bf`）三项作业成功：192 组组合、64 项回调合同、303 项继承解析合同、82 项失败控制、0099/0098/0097/0096/0095/0094/0093/0092 八项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。九份组合源码、四个 HTT 原生函数、两个 HIF 源码分支、接收消费前缀及 52 份报告中的生产源码、37 个路径别名和三份 ZIP digest 均独立核对。生产 HTT 与 0099 一致。见[0100 说明](POPSICLE-HTT-CALLBACKS-0100.md)及[验收记录](research/popsicle-htt-callbacks-0100-validation.json)。

下层 service/connect、endpoint 保存、logging、HIF 回调存储、构造存储/句柄与数据布局仍为模型；未证明真实总线/DMA/中断/固件消息、注册重入、注销和迟到回调安全。generic dispatcher 非消费尾部是中止桩，并未执行；只对该前缀的未用局部变量作窄范围警告豁免。WDI 两分支测试不代表手机当前配置选择。既有 DP 构造/引用、peer-gone/platform/清理端点、生产父资源停机及活动 SSR/完整 AWDL/整机验证仍待继续。backend 保持关闭，手机无需操作。

## 阶段 0099（离线验收完成）

生产补丁 0037 在 `dp_htt_t2h_msg_handler()` 读取 packet context/header 前调用新的 unmap consumer。它处理传输错误/取消、缺失 context/nbuf/data、短 header；成功非 unmap 消息保留原 generic dispatcher 所有权。V1 至少四字节，V2 至少包含 WDS-free-count 的二十字节消费前缀，额外尾部兼容；有界复制到对齐局部 words 后使用原始 wire GET 和 MAC deswizzle，再调用原生 DP unmap，并在返回后恰好释放一次 nbuf。旧两个 unmap switch 分支移除，其他分支与原注册指向保持。

相关代码和用例集中写齐后统一验证，[CI 41515796705](https://github.com/xxz3312/XAirDrop-17/actions/runs/41515796705)（`bbe95ed`）两项作业成功：168 组释放组合、303 项解析合同、68 项失败控制、0098/0097/0096/0095/0094/0093/0092 七项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局和模块记录检查通过。先后修正夹具 MAC-size 宏作用域，以及完整 WLAN 编译发现的 qdf_size_t 日志格式问题；夹具加入类型/格式检查，本次完整重跑成功。八份组合源码、补丁独立重放、generic dispatcher 受限改动和原始 deswizzle/wire 来源及 51 份报告中的生产源码、37 个路径别名和两份 ZIP digest 均核对。见[0099 说明](POPSICLE-HTT-UNMAP-0099.md)及[验收记录](research/popsicle-htt-unmap-0099-validation.json)。

生产 parser helper 已在主机模型中执行，完整 generic dispatcher、HTC/HIF 注册和真实固件事件输送只经源码/编译检查；没有主机模型运行或实机事件证明。BIG_ENDIAN_HOST 为字节表示转换后的原源码分支探针，非真实大端平台认证。初始资源/引用、peer-gone gate 和平台/清理端点仍为模型；真实并发、生产父资源停机、活动 START/UP SSR、完整 AWDL 收包与整机验证仍待继续。backend 保持关闭，手机无需操作。

## 阶段 0098（离线验收完成）

0097 组合接入原生 `dp_rx_peer_unmap_handler()`、`dp_peer_get_ref()`、`__dp_peer_get_ref_by_id()` 和 `dp_peer_find_id_to_obj_remove()`，保留原生 peer/VDEV 最终函数体。lookup 通过非零总引用取得临时 HTT pin；map remove 在模型 map lock 内清除 peer/txrx ID 和 slot，归还独立 map CONFIG；unmap 继续执行 Qref/事件/状态/通知及 HTT、生命周期 CONFIG 归还，最终进入 peer/VDEV host heap free 和既有生产运行时完成回调。覆盖未知/边界/重复 ID、零引用 lookup、WDS skip 和两种 AST 返回、offload/IPA/txrx/可选回调与外部引用释放时机。

相关代码和用例集中完成后统一验证，[CI 41497778660](https://github.com/xxz3312/XAirDrop-17/actions/runs/41497778660)（`80f9194`）两项作业成功：152 组组合、56 项失败控制、0097/0096/0095/0094/0093/0092 六项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。继承 46 项控制保持此前模型 unmap，十项新控制针对本轮原生路径。七份组合源码、六个原生函数和三个原始来源 Git blob 及 50 份报告中的生产源码、37 个路径别名和两个 ZIP digest 已独立核对。见[0098 说明](POPSICLE-NATIVE-DP-UNMAP-0098.md)及[验证记录](research/popsicle-native-dp-unmap-0098-validation.json)。

本轮为夹具调用原生 handler，未执行固件 HTT 解析/事件注册/真实输送；初始构造/map/生命周期引用、map 数组与平台原语、事件/AST/Qref/flow/统计/回调端点、peer-gone gate 和释放调度仍为模型。STA 和多 SOC/MLO 路径未选定；DP/ObjMgr peer 仍没有经过验证的生产衔接。真实组件、生产停机协调、真实并发、活动 START/UP SSR、完整 AWDL 收包和整机验证仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0097（离线验收完成）

0096 组合接入未改写的原生 `dp_peer_unref_delete()`。DP peer 使用独立 host heap，原生函数执行模块引用递减、最终引用和 peer-ID/AST 检查、inactive 列表移除、清理与锁销毁调用、实际 peer heap free，随后归还 DP VDEV CHILD 引用并进入原生 VDEV finalizer；VDEV heap free 后经既有 checking trampoline 调用生产运行时完成回调。额外 TX/RX 引用尚存时保留 peer 与 CHILD；覆盖 RX 模块计数绕过规则。

相关代码和用例集中完成后统一验证，[CI 41488890858](https://github.com/xxz3312/XAirDrop-17/actions/runs/41488890858)（`c4926c2`）两项作业成功：120 组组合、46 项失败控制、0096/0095/0094/0093/0092 五项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。六份生成组合源码、两个 DP 原生函数/Git blob/enum 与 HTT 常量来源及 49 份报告中的生产源码、37 个路径别名和两个 ZIP digest 已独立核对。见[0097 说明](POPSICLE-NATIVE-DP-PEER-FREE-0097.md)及[验证记录](research/popsicle-native-dp-peer-free-0097-validation.json)。

DP peer/VDEV 构造、初始引用、peer-ID map 失效、peer-gone gate、释放调度及清理端点/列表/锁/原子操作仍为模型；没有执行固件 `dp_rx_peer_unmap_handler()`。DP peer 与 ObjMgr peer 为不同对象，未声称其间已有生产引用桥。真实组件、生产停机协调、真实并发、活动 START/UP SSR、完整 AWDL 收包及整机验证仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0096（离线验收完成）

0095 组合接入未改写的原生 `dp_vdev_unref_delete()`，选定 passthru 路径执行模块引用递减、最后引用判断、清理调用、inactive 列表移除、可选删除通知、实际 DP VDEV host heap free，再经检查 trampoline 把原始令牌交给既有生产运行时完成回调。额外 HTT 引用尚存时必须保留存储；模型 peer 清理失败时保留 DP 资源，禁止完成。

相关代码和用例集中写齐后统一验证，[CI 41441718233](https://github.com/xxz3312/XAirDrop-17/actions/runs/41441718233)（`07f0c79`）两项作业成功：104 组组合、34 项负对照、0095/0094/0093/0092 独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项布局及模块记录检查通过。首次运行的最后一个错误令牌负对照有测试变体花括号问题，修正后全部重跑成功，原生函数体未改。五份生成组合源码、DP 原生函数/Git blob/enum 来源及 48 份报告中的生产源码、37 个路径别名和两个 ZIP digest 已独立核对。见[0096 说明](POPSICLE-NATIVE-DP-VDEV-FREE-0096.md)及[验证记录](research/popsicle-native-dp-vdev-free-0096-validation.json)。

DP 分配、attach/detach 设置、初始引用取得、peer-gone gate、迟到 HTT put、清理端点、列表/锁/原子操作仍为模型；未执行真实 DP peer unmap/ref-delete，也不声明 DP 与 ObjMgr 间存在已验证的直接引用释放桥。继承的父资源构造/真实组件、生产停机协调、真实并发、活动 START/UP SSR、完整 AWDL 收包和整机验证仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0095（离线验收完成）

选定序列的 PSOC 改为 host heap，原生 object_status、component_detach、最终 dispatcher、peer_list_deinit 和最终 free 五个函数体接入；此前六个 PSOC 引用/map/逻辑删除及 10 个 PDEV 原生函数体保持执行。原生 PSOC dispatcher 正序调用两个模型组件处理器，成功后原生 free 依次执行模型全局 detach、原生 peer-list deinit 的 64 个空模型桶和锁清理、最终 PSOC 锁销毁及实际 host heap free。异步组件经原生 completion 恢复 free；失败保留未完成部分。

相关实现、失败处理、边界用例和 CI 入口集中完成后统一验证。[CI 41436339138](https://github.com/xxz3312/XAirDrop-17/actions/runs/41436339138)（`cc815e1`）两项作业均成功：88 个组合序列、26 项负对照、0094/0093/0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局及模块记录检查均通过。完整新/旧组合源码、11 个 PSOC 和 10 个 PDEV 原生函数体、PSOC 文件/Git blob 身份及 47 份报告中的生产源码已核对，37 个路径别名、源码清单及两份 ZIP digest 匹配。见[0095 说明](POPSICLE-NATIVE-PSOC-FREE-0095.md)及[验证记录](research/popsicle-native-psoc-free-0095-validation.json)。

全局 PSOC 注册/detach、分配初始化、registry/sentinel handler、空哈希桶和平台原语仍是模型；未执行原生 PSOC/PDEV create、原生 peer-list init、真实 PSOC peer/VDEV 引用图或真实组件。只验证私有父资源整体停机合同；真实 DP unmap/完成图、并发迟到生产者、生产父资源协调、活动 START/UP SSR 恢复及完整 AWDL 收包仍待继续。生产内核未修改，backend 保持关闭，手机无需操作。

## 阶段 0094（离线验收完成）

将六个原生 PSOC 引用、PDEV attach/detach 和逻辑删除函数体接入 0093 的堆 PDEV 组合。原生 attach 维护 ID/map/count 并取得 PSOC attachment 引用；原生 PDEV free 调用原生 PSOC detach 后，fixture caller 仍持有 PSOC HDD 引用，直到 PDEV 队列关闭及 host heap free 完成才归还。原有 56 个序列迁移到该合同，另有 16 个 PSOC OSIF 引用与归还顺序组合，共 72 个序列、17 项负对照；单槽合同检查满表与无效已脱离 ID。

[CI 41424409521](https://github.com/xxz3312/XAirDrop-17/actions/runs/41424409521)（`1d8aec3`）两项作业均成功：新增组合、0093/0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局及模块记录检查均通过。完整新/旧组合源码、六个 PSOC 和 10 个 PDEV 原生函数体、PSOC 原始文件/Git blob 身份及 46 份报告中的生产源码已核对，37 个路径别名、源码清单与两份 ZIP digest 匹配。见[0094 说明](POPSICLE-NATIVE-PSOC-LEASE-0094.md)及[验证记录](research/popsicle-native-psoc-lease-0094-validation.json)。

PSOC 最终 destroy/free 及存储仍是静态模型端点，未执行真实 PSOC 组件、PSOC peer/VDEV attachment 引用或 PSOC heap free。移除 caller pin 的负对照在原生最后引用分支进入模型端点时检测到 PDEV 仍存活，不构成实际内核 UAF 复现。容量 1 为 Kbuild 默认选择；原生 attach 的逻辑删除准入及 detach 的有效槽位 owner 检查没有修改，仅选取私有、串行化、已核对归属的映射合同。真实 DP 完成图、PSOC 最终析构、迟到生产者、自动停机协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0093（离线验收完成）

将 0092 的选定父对象改为 host heap PDEV，执行原生 PDEV object_status、component_detach、最终 dispatcher 和最终 free 四个函数体，并保留此前六个原生引用/attachment 函数体。成功路径由原生最终 free 依次执行 PSOC detach、父锁销毁、原生延迟 peer queue deinit/QDF cancel、队列锁销毁及实际 host heap free，fixture 调用方不提前 deinit。0092 的 40 个序列迁移到堆父对象，另外 16 个覆盖父组件异步、组件失败、PSOC detach 失败及错误异步 token；共 56 个序列、11 项负对照。

[CI 41416403715](https://github.com/xxz3312/XAirDrop-17/actions/runs/41416403715)（`61d86cb`）两项作业均成功：新增组合、0092 独立组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局及模块记录检查均通过。独立重建的新/旧组合源码、10 个原生 PDEV 函数体、原始文件与 Git blob 身份均匹配；45 份报告中的生产源码、37 个路径别名和固定源码清单已核对，两份 ZIP digest 匹配。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖。见[0093 说明](POPSICLE-NATIVE-PDEV-FREE-0093.md)及[验证记录](research/popsicle-native-pdev-free-0093-validation.json)。

PDEV 分配/初始化、组件 registry/sentinel handler、PSOC detach、锁/列表及 Linux workqueue 仍为模型；QDF_BUG 为受控捕获端点，异步完成由 fixture 选择进程上下文。原生 PDEV create、真实组件/DP unmap 生产者与完成图、PSOC 生命周期、并发迟到生产者、自动停机协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待继续。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0092（离线验收完成）

将六个原生 PDEV 引用、VDEV attach/detach 和逻辑删除函数体接入选定的 0090 peer/VDEV/native SM 析构组合。VDEV 分配端点取得原生 PDEV attachment pin；原生 VDEV 最终 free 调用原生 PDEV detach 归还它。显式调用方持有 HDD 引用，等 peer/VDEV 存储清理和队列 deinit 完成后再归还；可选 OSIF 引用继续推迟父对象最终减零端点。新增 32 个成功序列和八项失败保留序列，覆盖两种 VDEV trace，另有五项负对照；0090 baseline 保留。

[CI 41408965293](https://github.com/xxz3312/XAirDrop-17/actions/runs/41408965293)（`69e6d0f`）两项作业均成功：新增组合、53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、CNSS 检查、严格链接、七项布局和模块记录检查均通过。独立重建的完整测试源码及六个原生 PDEV 函数体哈希与 CI 一致；新组合与 43 份 diagnostic 模型报告所列生产源码均匹配，37 个路径别名及固定源码清单已核对，两份验证 ZIP digest 匹配。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖。见[0092 说明](POPSICLE-PARENT-PEER-COMPOSITE-0092.md)及[验证记录](research/popsicle-parent-peer-composite-0092-validation.json)。

PDEV/PSOC 存储仍为静态模型，父对象最终组件分发/free 是受控标记端点；没有执行组合中的原生 PDEV free，也没有父 heap 释放认证。VDEV 创建、DP unmap 生产者/完成门、工作队列及平台原语保留既有模型边界。真实 DP 回调、迟到生产者、PDEV/PSOC 最终析构、自动停机协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0091（离线验收完成）

独立 parent/queue fixture 执行七个原生 PDEV 引用、attach/detach、逻辑删除和最终 free 函数体，以及十四个原生 peer queue/QDF work 函数体。50 个序列及八项负对照验证：调用方保留 PDEV 引用，worker 内 VDEV detach 后父存储仍存活，关闭生产者并在进程上下文显式排空后归还最后引用；原生 free 按序关闭队列并释放 host heap。

[CI 41348908513](https://github.com/xxz3312/XAirDrop-17/actions/runs/41348908513)（`10eaf90`）通过 53 项 Python 检查、0091/0090 及旧回归、完整 WLAN 编译、严格链接、七项布局和模块记录检查。独立核对四份原生文件、21 个函数体、引用枚举和完整 fixture 哈希；43 份生产源码报告及 37 个路径别名均匹配仓库，报告 ZIP 校验通过，布局候选对应链接 WLAN，五个模块无版本记录不匹配或缺版本依赖。见[0091 说明](POPSICLE-NATIVE-PDEV-QUEUE-0091.md)及[验证记录](research/popsicle-native-pdev-queue-0091-validation.json)。

本阶段是独立引用合同验证，并未把实际 peer/VDEV/DP 析构图接入父对象回收；组件分发、PSOC detach 和平台原语仍有模型端点。持有引用仅保留父存储，不能阻止组件关闭。真实 DP 回调、全局迟到生产者、自动停机协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待实现。生产内核未修改，backend 关闭，手机无需操作。

## 阶段 0090（离线验收完成）

在 0089 组合上执行原生 peer 延迟工作队列五个函数体与九个 QDF work 适配函数体。排队期间检查 peer heap、VDEV peer pin、DP VDEV 和 native SM 保留；worker 解开列表锁后才调用原生 peer 析构。新增 36 个队列/组件/引用组合，普通与 trace VDEV 配置分别重跑完整 0089 套件，累计 35 项负对照。

CI [41338423652](https://github.com/xxz3312/XAirDrop-17/actions/runs/41338423652)（`e444e3d`）已全部通过：53 项 Python 检查、原生 peer 延迟队列模型及 36 个新增组合、累计 35 项负对照、0089 至 0082 独立模型与旧 C 回归、完整编译、CNSS 检查、严格链接、七项选定布局及模块记录检查。43 份模型报告的生产源码哈希均已核对，其中 37 份与本模型共享主生产文件；37 个路径别名与 Git blob/SHA-256 一致。14 个新增原生函数体及四份固定输入的 Git blob 身份已独立匹配，完整生成源码重建哈希与 CI 一致，0089 生成源码也保持一致；本地未执行 C 编译。报告 ZIP 校验通过，布局候选对应最终链接 WLAN，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。离线验收完成，见[验证记录](research/popsicle-native-peer-queue-0090-validation.json)。

本阶段验证的是父对象仍存活、私有 peer 生产者已结束后，显式 flush 至工作空闲且列表空，再调用原生 deinit 的 fixture 调用方合同。原生 qdf_destroy_work 同步取消工作，不能代替排空。合并调度后的 active_work_cnt 残留、运行期间重入队需再次 flush、列表满时 enqueue 忽略 insert 失败均已在模型中观察；没有修改这些生产行为，也不以计数授权停机。

Linux workqueue/锁/链表和若干 DP/对象管理器端点仍为模型。父对象最终引用在 worker 内释放、全局迟到生产者、真实 DP 回调图、native shutdown 自动协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0090](POPSICLE-NATIVE-PEER-QUEUE-0090.md)。

## 阶段 0089（离线验收完成）

12 个原生函数体进入 self-peer 回收组合：非 trace peer 引用 API 与 debug-ID 检查、逻辑删除、正序组件分发/状态汇总/异步 detach、非延迟销毁入口、peer 最终 free，以及 VDEV peer detach。unmap 端点释放真实执行的 native peer DP 引用，由原生计数减零触发析构。原生 peer free 临时持有 VDEV，移除 VDEV/PSOC 归属并释放 peer 存储，最后归还临时 VDEV 引用。

CI [41332655703](https://github.com/xxz3312/XAirDrop-17/actions/runs/41332655703)（`b1de1f3`）已全部通过：53 项 Python 检查、新原生 self-peer 回收模型、24 个新增组件/引用用例、累计 29 项负对照、0088/0087/0086/0085/0084/0083/0082 独立模型与旧 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。42 份模型报告所列生产源码哈希均已与仓库源码核对，其中 36 份与本模型共享主生产文件；37 个路径别名均与相应 Git blob 及 SHA-256 一致。12 个函数体从固定源码独立匹配，peer type 枚举及三份原始 native 输入的 Git blob 身份也已核对。完整生成源码已从固定快照与既有补丁重建，SHA-256 与 CI 一致；本地未执行 C 编译。报告 ZIP 校验值、实际链接 WLAN 模块和布局候选哈希已核对；WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-peer-destructor-0089-validation.json)。

新增 24 个组件异步/失败、列表/PSOC detach 失败、错误完成参数与额外 peer 引用用例，分别经过提前/延迟 unmap 和两种 VDEV trace 配置；BSS 指针与 unmap 共用测试位，不宣称独立全组合。失败保留已经发生的部分效果，不伪造回滚。peer 创建/注册/组件处理器、QDF atomic/锁、DP 生产者、PSOC/链表与 PDEV 计数端点仍为模型；peer trace 数据库及延迟销毁队列尚未覆盖。完整真实 DP 回调图、native shutdown 自动协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0089](POPSICLE-NATIVE-PEER-DESTRUCTOR-0089.md)。

## 阶段 0088（离线验收完成）

普通/trace 两套原生 get_ref、try_get_ref、release_ref 与完整 obj_delete 已进入组合执行，保留原生 109 个引用 ID。原生逻辑删除先关闭准入再释放 OBJMGR 引用，原生 aggregate 减零才进入 0087 析构分发器；旧 refs 仅是被核对的镜像，不独立触发销毁。两种版本各重跑完整套件，并各覆盖三个额外引用的六种释放顺序、带/不带外持引用，共 24 个新增完整序列。新增九项负对照，总计 24 项。

CI [41328315517](https://github.com/xxz3312/XAirDrop-17/actions/runs/41328315517)（`16f4599`）已全部通过：53 项 Python 检查、普通与 trace 两个版本各自完整执行 0087 套件、24 个新增多引用释放序列、累计 24 项负对照、0087/0086/0085/0084/0083/0082 独立模型及既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局和最终模块记录检查。41 份报告所列生产源码哈希均已与仓库源码核对，其中 35 份与本模型共享主生产文件；37 个路径别名均与相应 Git blob 和 SHA-256 一致。七个函数体和完整引用 ID 枚举独立匹配固定源码。完整生成源码已从固定快照与既有补丁重建，SHA-256 与 CI 一致；本地未执行 C 编译。报告 ZIP 校验值、实际链接 WLAN 模块与布局候选哈希已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-reference-release-0088-validation.json)。

保持原生差异：raw get_ref 本身没有状态准入门槛，try_get_ref 才会拒绝八种非 CREATED 状态；受控 QDF_ASSERT/BUG 仅为隔离契约。紧凑调用方标签映射到原生 HDD/OSIF/WMA/MAC ID，不能认证全部真实调用方。atomic/锁、trace 数据库、创建与组件注册仍为平台模型；真实 DP/peer 析构图、自动父资源协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0088](POPSICLE-NATIVE-REFERENCE-RELEASE-0088.md)。

## 阶段 0087（离线验收完成）

0086 的零引用清理继续进入原生 VDEV 析构分发器、组件状态汇总、component detach 和完整 MLME destroy handler。保留原生 54 个组件槽位与对象状态枚举，MLME 为原生处理器体，另外两个槽为逆序检查的测试处理器。新增 12 个带/不带外持引用用例，覆盖异步成功、组件失败、MLO detach 拒绝、错误逻辑状态、MLME detach 不匹配和错误异步完成参数。

CI [41284004867](https://github.com/xxz3312/XAirDrop-17/actions/runs/41284004867)（`e6d68ca`）已全部通过：53 项 Python 检查、新原生析构模型、12 个新增组件/外持引用用例、15 项负对照、0086/0085/0084/0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。40 份模型报告所列生产源码哈希均已与仓库源码核对，其中 34 份与本模型共享 runtime/radio 等主文件；不同路径别名也已对照相应 Git blob 验证。四个原生函数体与两组枚举独立匹配固定版本，四份 native 输入的原始 Git blob 身份一致。完整生成源码在实现时从固定快照与既有补丁重建，SHA-256 与 CI 匹配；本地未执行 C 编译。报告 ZIP 校验值、实际链接模块与布局候选哈希均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-object-destructor-0087-validation.json)。

原生 MLME 处理器忽略 detach 错误时，生产 final-free 的 attached-pointer veto 仍挡住 VDEV/父资源释放；已释放的 SM/MLME 不伪造回滚。实际引用获取/释放、计数和处理器注册/创建仍为平台模型，真实 release_ref/debug 与 registration init 尚未编入；DP/peer 真实析构图、自动父资源协调、活动 START/UP SSR 恢复和完整 AWDL 收包仍待继续。backend 关闭，手机无需操作。见[0087](POPSICLE-NATIVE-OBJECT-DESTRUCTOR-0087.md)。

## 阶段 0086（离线验收完成）

普通 DOWN/INIT 后，0085 完整 WMA/SM 主流程继续经过原生 PE 析构、普通 WMA peer 删除、固件 peer/VDEV DELETE 响应来源、DP 完成、WMA/legacy 释放、原生 SM 销毁与 VDEV 最终释放。新增 32 种串行回调/引用组合、六类失败保留和两个生产等待门槛负对照；外持引用与 flush-service 共用测试位，不能宣称六个独立维度的全部组合。

CI [41275178699](https://github.com/xxz3312/XAirDrop-17/actions/runs/41275178699)（`388b029`）已全部通过：53 项 Python 检查、16 种 WMA 主流程与三次 ratemask 流程接续完整清理、32 种新增回调/引用组合、六类新增失败保留、既有八类 WMA 失败保留、11 项负对照、0085/0084/0083/0082 独立模型与旧 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。39 份模型报告的公共生产源码哈希一致，五个生产文件已独立核对；两个普通 WMA 删除函数与固定源码独立匹配，owned peer 删除入口与 0017 补丁一致。完整生成源码在本地从固定快照与既有补丁重建，SHA-256 与 CI 匹配；本地未执行 C 编译。报告 ZIP 校验值及实际链接模块/布局候选均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。本阶段离线验收完成，见[验证记录](research/popsicle-native-cleanup-0086-validation.json)。

peer 引用/逻辑删除/unmap、DP 完成、component destructor 调用方和父列表仍为平台模型；模型明确将 DP VDEV 完成延迟至 peer unmap/逻辑删除完成，不认证真实 DP/peer 析构图或硬件并发顺序。真实对象管理器析构调用方、父资源停机自动协调、活动 START/UP SSR 恢复与完整 AWDL 收包仍待后续工作。backend 关闭，手机无需操作。见[0086](POPSICLE-NATIVE-CLEANUP-0086.md)。

## 阶段 0085（离线验收完成）

完整原生 WMA START 响应函数及 MAC/DP 更新、频道响应、ratemask 转换三个助手已进入 PAS/NDI 复合模型。覆盖频道复制、TX streams、MAC/功率和原生指针长度事件参数；检查早期失败、部分字段已更新、UP 后失败及 SM 拒绝事件时 controller 封锁并保留资源。原生 ratemask 发送失败仅记录继续、越界配置跳过的行为保持原样。

CI [41273213537](https://github.com/xxz3312/XAirDrop-17/actions/runs/41273213537)（`82baf02`）已全部通过：53 项 Python 检查、新完整 WMA 响应模型、16 种主流程、3 次额外 ratemask 流程、6 项类型映射契约、8 类失败保留、九项负对照、0084/0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。38 份报告的公共生产源码哈希一致，五个生产文件已独立核对；四个函数体从固定源码加 0015 补丁重建后匹配，ratemask 类型、回调/PAS 表与独立模型哈希一致。完整生成源码也已在本地从固定源码快照与补丁重建，与 CI 生成源码哈希一致；本地未执行 C 编译。报告 ZIP 校验值及实际链接模块/布局候选均已核对，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 见[0085](POPSICLE-NATIVE-WMA-START-0085.md)与[验证记录](research/popsicle-native-wma-start-0085-validation.json)。

DP/policy/ratemask transport、上下文/config 等端点仍是平台模型；非 PAS 分支和 AP MCC 条件配置未由本阶段认证。delivery bridge 的观察/拒绝探针明确记录，不将源函数体覆盖写成全部传递调用或实际固件执行。物理 PE/peer 完整清理、原生 object-manager 调用方、父资源停机自动协调、活动 START/UP SSR 恢复及完整 AWDL 收包仍需后续实现/验证。backend 关闭，手机无需操作。

## 阶段 0084（离线验收完成）

原生 12 个 inline 回调、完整 ops 类型及 32 槽 PAS 表已进入模型执行。每个 adapter 覆盖 NULL ops/slot 默认 SUCCESS、参数和三类返回值传播；完整绑定检查及两个新增负对照避免把缺回调的默认成功当作动作完成。八种主流程与既有五项负对照保留，validation/down 两个竞态测试探针明确记录。

CI [41270857085](https://github.com/xxz3312/XAirDrop-17/actions/runs/41270857085)（`01b6203`）已全部通过：53 项 Python 检查、新原生回调模型、12 个 adapter 的 60 项空槽/参数/返回值契约检查、完整 32 槽绑定、八种主流程、七项负对照、0083/0082 独立模型与既有 C 回归、完整编译、CNSS 名称检查、严格链接、七项选定布局和最终模块记录检查。37 份模型报告的公共生产源码哈希一致，五个生产文件已独立核对；12 个函数与原生 ops 类型哈希匹配，PAS 表从 0011/0022 补丁独立重建后匹配。整个 ops 头文件与原始固定源码的差异来自既有 0007 补丁的 PASSTHRU 类型宏/注释，重建后的整文件哈希也匹配，ops 声明没有差异。报告 ZIP 校验值与实际链接模块/布局候选记录均已复核，WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 见[0084](POPSICLE-NATIVE-CALLBACKS-0084.md)及[验证记录](research/popsicle-native-callbacks-0084-validation.json)。

完整 WMA 后处理、真实 object-manager 调用方、物理 PE/peer 生命周期、实际 START/UP SSR 恢复、父资源自动协调与完整 AWDL 收包仍需后续工作。平台字段/锁/minidump/transport 仍有模型；backend 关闭，手机无需操作。

## 阶段 0083（离线验收完成）

新增模型实际执行原生 `mlme_vdev_sm_create/destroy`，覆盖创建分配失败、VM-id 名称/初始状态、minidump 与锁建立/释放顺序、三次成功配对释放，并包围八种主流程和拒绝用例。CI [41247250279](https://github.com/xxz3312/XAirDrop-17/actions/runs/41247250279)（`22cd90f`）已全部通过：53 项 Python 检查、新原生创建/销毁模型、八种启动组合、五项负对照、0082 独立引擎模型、既有 C 回归、完整 WLAN/Wonder/provider 编译、CNSS 名称检查、严格链接、七项选定布局及最终模块记录检查。36 份模型报告的公共生产源码哈希一致；两个原生 wrapper 函数哈希与固定源码独立匹配，五个生产文件哈希、报告 ZIP 校验值及实际链接模块/布局候选记录均已核对。WLAN 无未解决依赖，五个模块均无版本记录不匹配或缺版本依赖。 见[0083](POPSICLE-NATIVE-SM-OWNER-0083.md)与[验证记录](research/popsicle-native-sm-owner-0083-validation.json)。

锁/minidump 仍是平台模型，真实 object-manager 调用方、MLME callback adapter、完整 WMA 后处理和物理 PE/peer 生命周期仍未覆盖。实际 START/UP 的 SSR 恢复、父资源/停机自动协调及完整 AWDL 收包仍未完成；backend 关闭，无新手机操作。

## 阶段 0082（验收完成）

原生通用状态机引擎、完整原始状态/事件表及真实枚举已进入模型执行，原生 transition/deliver 桥接替代层级适配器。首次 START 允许匹配的 INIT/0 或 INIT/IDLE，初始子状态漂移拒绝；新建 INIT/0 遇 SSR 保留资源。CI [41244837690](https://github.com/xxz3312/XAirDrop-17/actions/runs/41244837690)（`005ee1b`）已全部通过：53 项 Python 检查、原生引擎八种启动组合、三项负对照、既有 C 回归、完整 WLAN/Wonder/provider 编译、CNSS 名称检查、严格模块链接、七项选定结构布局及最终模块记录检查。35 份模型报告的公共生产源码哈希已交叉匹配，五个生产文件与已验证源码独立核对；WLAN 未解决依赖为空，五个模块均无版本记录不匹配或缺版本依赖。报告 ZIP 的 SHA-256 已核对，布局候选模块哈希与实际链接 WLAN 模块一致。 详见[0082](POPSICLE-NATIVE-ENGINE-0082.md)和[验证记录](research/popsicle-native-engine-0082-validation.json)。

本阶段的离线验收已完成。实际 START/UP 的 SSR 恢复、父资源自动协调、真实 MLME create/destroy/callback adapter 与完整 monitor/AWDL 收包仍需后续实现和验证，backend 关闭，手机无需操作。

## 阶段 0081

START/STOP 发送现在同时要求精确原生子状态，INIT 校验要求 INIT/IDLE。新增模型编入 23 段原生 entry/event 函数及原生 INIT/API，普通主流程经过其中 20 段，贯通 START→UP→DOWN→STOP→INIT、双频与提前响应，检查原生 handled=true 掩盖回调失败时 controller 仍隔离资源。两个负对照移除 START/STOP 子状态门槛，必须均被识别。CI [41208058251](https://github.com/xxz3312/XAirDrop-17/actions/runs/41208058251) 已通过 53 项 Python 检查、新原生主流程模型及两个子状态负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；11 组模型公共生产哈希、23 段原生函数哈希、9 个 native 文件哈希、实际链接符号和模块记录已复核。通用状态机引擎/层级分派/transition 仍有模型，实机和固件未验证；不扩大 SSR 回收范围，backend 关闭，手机无需操作。见[0081](POPSICLE-NATIVE-LIFECYCLE-0081.md)。

## 阶段 0080

新增原生 INIT START 校验被原始 SSR 拒绝后的显式回收：必须依次确认 validation 拒绝、down 通知被拒绝、原生分支 origin、成功返回且 SM 已解锁，并保持 INIT/IDLE、空事务及零 pending/users。保留 BLOCKED/ESHUTDOWN 和入口历史，不冒充 DOWN；七项原生计划在 timer drain 前后重检。新增原生 API wrapper 执行、双频与异常来源/状态/回调顺序检查，以及缺失原生 origin、缺失 SM unlock 两个负对照。CI [41200864386](https://github.com/xxz3312/XAirDrop-17/actions/runs/41200864386) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；十组模型生产哈希、九个 native 文件哈希、九项 START 回收入口实际链接及模块记录已复核。真正进入 START 状态/发送 START/等待响应/UP 的回收、自动父资源协调及完整接收路径仍未完成，backend 关闭，手机无需操作。见[0080](POPSICLE-NATIVE-INIT-RESET-0080.md)。

## 阶段 0079

新增 START SM 意图提交与原生入口间的共享锁门槛，原始 SSR 封锁先到则不调用 native dispatch，保存独立 SM-entry-abort 来源并沿用计划重检/显式回收；入口标记先到则继续保留资源。模型实际执行固定版本 INIT START handler，覆盖 PAS 校验失败 handled=true、额外 down-complete 通知且仍不回收的行为。新增双频、20 类拒绝、七项计划/当前参数与 timer 漂移、入口后拒绝、两个负对照。CI [41197736928](https://github.com/xxz3312/XAirDrop-17/actions/runs/41197736928) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接及七项布局检查；生产/native 哈希、新 origin 实际链接和模块记录已复核。真正进入 SM/START/UP 后的回收、自动父资源协调和完整接收路径仍未完成，backend 关闭，手机无需操作。见[0079](POPSICLE-SM-ENTRY-RESET-0079.md)。

## 阶段 0078

新增 START 准备成功、七项原生编码器摘要与原计划完全匹配、尚未提交任何 SM 的 SSR 回收。计划按值拷贝，不借用 caller 存储；准备、SM 提交、SSR 封锁使用明确的记录。回收预检与 timer drain 后重新构建并比较当前原生摘要，漂移则保留 controller/PE/DP。新增双准备边界、20 类拒绝、全部七项参数/当前参数漂移、caller 拷贝、SM 已提交但仍 INIT 的拒绝及两个负对照。CI [41193377121](https://github.com/xxz3312/XAirDrop-17/actions/runs/41193377121) 已通过 53 项 Python 检查、新模型及两个负对照、既有全部 C 模型、完整编译、严格链接和七项布局检查；生产/native 哈希、新 origin 实际链接及模块记录已复核。失败/部分准备、SM/START/UP、自动父资源协调和完整接收路径仍未完成，backend 关闭，手机无需操作。见[0078](POPSICLE-COMPLETED-PREPARE-RESET-0078.md)。

## 阶段 0077

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
