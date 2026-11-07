# 0155：普通 VDEV DELETE 确认后由 SSR 首次提交 DP detach

0154 八项必选 CI 均已通过（Actions 42400068283）。本轮将 SSR 衔接向前扩展到普通 PE、peer、VDEV DELETE 均已确认、DP detach 尚未提交的配置 owner。公开 init/START 继续关闭，手机无需操作。

## 上游与原生依据

本轮重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）中先等待会话 teardown、再 stop/deinit adapter 的顺序；重新读取 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）恢复路径，保持原厂 CNSS2 和现有手动部署边界。

复用锁定 MiCode WLAN `36df473046706a5259942e1bf7222108dbbb860f` 的既有 `mishare_ndi_reset_prepared_dp_detach`。该函数检查精确 VDEV/PSOC/DP cookie、PAS/NDI/INIT、live extension、零物理 peer，再调用普通 native DP detach；不需要重新发送 DELETE 或执行 no-FW peer force detach。本项目的异步 owner 继续持有原引用与 caller 提供的 native parents。

## 行为

- 在保留原有 0154 已提交 DP 路线的同时，`rate_tail_check` 允许尚未尝试 DP、attach/DP cookie/stats 所有权完整的对象成为 native CDS 窗口候选；缺少 PE/peer/VDEV 删除完成通知仍拒绝。
- 仍须原始 SSR fence、MC 排空、有效且未关闭的 native recovery window、无 sticky 错误、精确 host/event/VDEV 关系。进入 native helper 前再次复核窗口和记录，`tail_dp_attempted` 只表示 helper 已尝试，不代表 CDP 已调用或接受。
- 先记录尝试和 dp_detaching，再调用原生 helper，允许 inline DP callback。成功返回后才记录 dp_detach_submitted、归还 stats 所有权；即使 callback 已 inline 完成，本次仍返回 EINPROGRESS，下一次 poll 才能释放上下文。
- 普通 DELETE reply 已由原生 deinit 后的 origin 确认；timer_ready 元数据沿用普通 drain 的消费规则更新，不再次执行 timer deinit。DP 使用原普通回调记录 final-free，不制造 ACK 或 reset-DP 完成标志。
- helper 失败、cookie/物理 peer 不满足或 DP 拒绝会保留未完成资源与尝试记录、写入 sticky recovery_error，不重试。DP 真正完成后沿用 0154 的 WMA/legacy finish、host 删除、外部引用等待以及 0153 的 final metadata retirement。

## 验证

本地实际 runtime scalar block/configure/MC wrapper 的 15 项变异检查、100 项 Python 回归、语法与 diff 检查通过。原生组合源码已从锁定源生成；本地不编译 native composition。

新增独立 Actions 步骤，保留既有普通/native 回归，追加两个频段 × 四种速率提交结果 × 32 种回调组合，共 256 组，direct/batch 随组合交替。覆盖普通 DELETE inline/deferred、physical peer unmap、SSR 第一次 DP submit、DP inline/deferred、外部 VDEV 引用及关窗后 final-free。18 组故障保留覆盖关窗、错误/空 DP cookie、物理 peer 未释放、CDP 拒绝、缺少 DELETE reply、completion 错误、stats 证据缺失和 native reset 资格缺失。三个原生变异控制移除尝试记录、提交后返回屏障或 DP cookie 准入。新增 native C 组合和三个变异控制已通过 Actions 42405410946、stop-admission 作业 128501925667 的独立步骤 Native first DP SSR continuation with sanitizers。该作业的原有生命周期回归和完整目标构建仍在运行，不提前记为全部 CI 通过。

物理 firmware/ACK/DP/peer/ref/lock 原语及速率回执由模型提供；原生函数选择体在该环境执行，不等于实机。父资源仍由 caller/fixture 保留，没有完整自动 parent lease、缺少 PE/peer/VDEV reply 时的恢复、配置后 START/UP 或 Apple 发现/握手/互传认证。无新手机安装包。
