# 小米 17 Pro Max AirDrop 移植进度（2026-10-29）

当前完成了用户态兼容载荷构建、驱动资源/上下文生命周期、初始频道参数、owned NDI 启停路径、停机准入栅栏、被跟踪 MC 排空证据、纯 host 及早期 NDI 回收、父资源拆除前窗口撤销及显式 SSR 批量回收（含准入错误优先级及最终记账状态预检）的离线验证，并补齐普通 DP/DELETE 完成事件校验及普通资源已完成后的 NDI host 收尾和普通 host 删除后的最终记账。
实机已确认 MiShare 对临时 XOS 服务的 Binder 元数据访问；还没有实际 AWDL 收发。
“离线通过”指源码、模型测试、编译与链接等检查，不代表手机加载或固件接受。

| 模块 | 状态 | 已完成与剩余边界 |
| --- | --- | --- |
| GitHub Actions 与缓存 | 已完成 | 自动编译、工具链/bindgen 缓存、诊断报告 |
| XOS/Binder 与权限 | 部分实机验证 | MiShare 主进程/UI 元数据访问通过；无线业务未验证 |
| 小米 15 MiShare 兼容逻辑 | 离线构建通过 | 已移植应用补丁、BLE/会话兼容载荷；待上机联调 |
| Wi-Fi 会话协调 | 离线构建通过 | root broker 持有、断连/恢复逻辑；未在手机运行 |
| Wonder/AWDL 参考代码 | 部分完成 | 参考代码已构建；未接通目标 WLAN 收发 |
| Wonder/WLAN 后端接口 | 部分完成 | 类型表、注册和生命周期具备；无线 init/set_freq/filter/rate 等回调仍未实现，capabilities=0 |
| Host VDEV 与引用管理 | 离线验证通过 | 对象创建、引用、最终释放跟踪与失败保留 |
| NDI CREATE/DP/DELETE | 离线验证通过 | 提交结果、真实 DELETE 事件与 DP 回收；新增普通 DP token/顺序校验及完成错误保留；固件未实测 |
| legacy/WMA/self-peer | 离线验证通过 | 上下文、绑定、peer 创建及对称删除路径 |
| PE session | 离线验证通过 | MC 异步创建/删除、完成回执、引用与 flush 回收 |
| 初始频道参数 | 离线验证通过 | 2.4/5GHz HT20、法规/并发/扫描检查及原生参数准备；不发 START |
| START 原生参数准备 | 离线验证通过 | 重查 WMA/self-peer/法规/并发；原生 START 参数构造与摘要，不提交固件命令 |
| START/host-only UP/STOP/DOWN | 离线构建/模型验证通过 | owned controller 接入专用 MLME 回调、真实响应与 PM 清理；accepted DOWN + INIT 后才删资源；完整原生 SM/WMA 运行及固件未实测，默认调用门关闭 |
| 动态换频与并发硬件模式 | 待实现 | AWDL 跳频、硬件模式/DBS、与辅助 monitor 同步 |
| RAW TX | 待实现 | 目标接口已分析；帧发送桥接、队列和完成回收未接入 |
| Monitor/native RAW RX | 待实现 | 接收桥接、过滤、peer/BA 等目标适配 |
| 纯 host 隔离回收 | 离线验证通过 | 限从未发送固件命令的 PAS/INIT 对象；记录被跟踪 MC 排空，等实际 final-free 再释放 owner；NDI/未知发送资源拒绝回收 |
| 早期 NDI 隔离回收 | 离线验证通过 | 限 CREATE/完整 DP attach、尚无 WMA/self-peer/PE/START；资格化 SSR 窗口内释放 timer，等 DP final-free 后删 host；会话中与部分 attach 拒绝回收 |
| 普通 DELETE/DP 完成后收尾 | 离线验证通过 | 限未准备/未 START、普通 host 删除尚未开始的 NDI；合格 SSR 窗口内只删 host 并等最终释放，保留普通完成历史 |
| 普通 host 删除后最终记账 | 离线验证通过 | 删除接受、持有关系解除、MC 排空且无永久错误；等真实 VDEV final-free 后释放 owner，不再调用原生清理 |
| 父资源拆除前窗口撤销 | 离线验证通过 | CDS DP / HDD pdev / dispatcher pdev 关闭前永久撤销回收窗口；仍非父资源 lease 或在途调用屏障 |
| 显式 SSR 批量回收 | 离线验证通过 | 校验完整句柄表；漏列、已记录永久错误及 accepted-delete 记账状态矛盾优先于等待；逐项保留结果，全部清空才成功；父资源仍由调用方保留 |
| SSR/卸载/异常恢复 | 部分完成 | 已实现准入栅栏、被跟踪 MC 排空、早期及普通资源已完成的 NDI 收尾、拆除前窗口撤销及显式批量步骤；会话内 WMA/peer/PE/PM、父资源协调与安全卸载仍待实现 |
| 固件能力与端到端实测 | 待验证 | 驱动加载、NDI/RAW 实际支持、Apple 发现与双向传输、稳定性和安装包 |

最新源提交：`29253f6c843be60305bcb003fecfaa734ec0eebf`。
[Actions 40730487714](https://github.com/xxz3312/XAirDrop-17/actions/runs/40730487714)
已通过 44 项 Python 检查、26 组原生 fixture、完整 WLAN 编译与严格链接；
84 个要求符号存在，574 条版本记录无不匹配、未解决依赖为空，7 项选定布局 MATCH。
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
