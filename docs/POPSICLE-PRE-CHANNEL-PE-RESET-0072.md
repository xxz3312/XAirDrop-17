# 0072：尚未请求信道的 PE 会话显式 SSR 回收

在 0070 prepared INIT 回收和 0071 私有 PAS 析构隔离之上，新增已观察到 PE 创建成功、尚未请求 channel/START 的显式 SSR 回收。pending/失败 PE、任何 channel/START-plan/radio 历史仍不支持；无线 backend 保持关闭，不创建手机测试包。

准入依旧要求原始 psoc 的 SSR fence、已排空的 owned MC、原生停止 HIF/HTC/RX 和阻断/排空 WMI 的窗口，以及调用者始终保留并串行保护原始 MAC/DP/pdev/adapter 父资源。不是自动 shutdown coordinator 或父资源租约。

新原生 PE check/release helper 严格核对 cookie、owner、psoc、vdev、MAC、session table 槽位、私有 BSS/role/opmode、原生 INIT/IDLE、空信道/认证超时/关联请求、DPH 归属形状和确认定时器。匹配 sessionId 的确认定时器若仍在运行，则拒绝操作，不能据此取消归属不明的定时器。

先完成所有预检，再同步关闭 NDI 响应定时器；重新核对 PE 原生身份后，直接执行 0071 修正后的完整 `pe_delete_session()`，由它释放 MAC VDEV 引用。确认 session invalid、vdev/mac_ctx 清空且查询不再命中后，才记录 recovery_pe_released，并清除活动 PE cookie/ready。原始 PE 创建事实保留，普通 PE DELETE 请求/响应旗标不改写，也不向已停止的 MC 再发请求。其后复用 0070 的 peer → 实际 DP final-free → WMA/legacy → 对象实际 final-free 顺序。

预检/部分失败设置 sticky recovery_error，保留剩余上下文，不重试删除。PE 已释放而后续 peer 清理失败时保留已完成 PE 事实，不重复执行析构。最终 owner 清理再次检查 reset PE 的完整事实。

新增 Actions C 模型执行生产 runtime、新原生 PE helper、完整原生 PE 析构及 no-FW WMA peer 分支。覆盖同步/异步 DP、batch、额外 final-free 引用、22 类预检失败、定时器 cancel 时的身份漂移、后续 peer 失败和不支持的状态；撤销私有 PAS 的 SAE guard 必须在实际 SAE helper 路径触发共享认证定时器断言。旧模型缺少真实 PE reset helper 时保留 fail-closed stub。

本地 53 项 Python 检查、补丁应用与原生 API 基线还原已通过。C 模型、完整编译、严格链接和选定布局检查待 CI。

PE 分配、其余 cleanup primitives、实际内核锁/定时器/调度器、DP force detach、peer 组件物理析构与父对象仍为模型。没有认证目标固件、实机并发、无线收发或 AirDrop。后续仍需 channel/START/UP 恢复、原生自动 shutdown/父资源协调，以及完整 monitor。
