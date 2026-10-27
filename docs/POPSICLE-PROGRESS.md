# 小米 17 Pro Max AirDrop 移植进度（2026-10-28）

当前完成了用户态兼容载荷构建、驱动资源/上下文生命周期与初始频道参数的离线验证。
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
| NDI CREATE/DP/DELETE | 离线验证通过 | 提交结果分开记录、DELETE 真实事件路径与 DP 回收；固件未实测 |
| legacy/WMA/self-peer | 离线验证通过 | 上下文、绑定、peer 创建及对称删除路径 |
| PE session | 离线验证通过 | MC 异步创建/删除、完成回执、引用与 flush 回收 |
| 初始频道参数 | 离线验证通过 | 2.4/5GHz HT20、法规/并发/扫描检查及原生参数准备；不发 START |
| START 原生参数准备 | 离线验证通过 | 重查 WMA/self-peer/法规/并发；原生 START 参数构造与摘要，不提交固件命令 |
| START/host-only UP/STOP/DOWN | 部分完成 | 事务和响应来源基础、UP 兼容判断已有；已补强异常响应解码并测试完整 START/STOP handler；原生启停闭环待接通 |
| 动态换频与并发硬件模式 | 待实现 | AWDL 跳频、硬件模式/DBS、与辅助 monitor 同步 |
| RAW TX | 待实现 | 目标接口已分析；帧发送桥接、队列和完成回收未接入 |
| Monitor/native RAW RX | 待实现 | 接收桥接、过滤、peer/BA 等目标适配 |
| SSR/卸载/异常恢复 | 待完善 | 当前异常会保留资源；完整恢复和释放路径尚未实现 |
| 固件能力与端到端实测 | 待验证 | 驱动加载、NDI/RAW 实际支持、Apple 发现与双向传输、稳定性和安装包 |

最新源提交：`d3514465a7f983170b27c09d4d3edac72603878d`。
[Actions 40575306804](https://github.com/xxz3312/XAirDrop-17/actions/runs/40575306804)
已通过 44 项 Python 检查、17 组原生 fixture、完整 WLAN 编译与严格链接；
56 个要求符号存在，574 条版本记录无不匹配、未解决依赖为空，7 项选定布局 MATCH。
以上不构成完整私有 ABI/KCFI、手机加载或 AirDrop 可用认证。

后续顺序：原生启停闭环 → 换频/收发与 Wonder 后端 → 恢复路径、固件与整机联调。
详细证据见 [频道准备报告](research/popsicle-owned-channel-build-pass.json) 和
[启停响应检查报告](research/popsicle-start-stop-response-build-pass.json)，以及
[START 参数准备报告](research/popsicle-owned-start-plan-build-pass.json)。
