# 0150：runtime 固定速率状态与清理准入

0149 Actions 42375590428 全部八项必选作业通过，含完整 WLAN 编译、严格链接、布局及 owned rate/WMA 模型。本轮把固定速率 post 接入实际 runtime registry 状态，尚不连接 managed/public 初始化。

## 上游和实现依据

本轮重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（blob `8874b020b4d7eadea41adea787d53dcca08a3c62`）中固定速率配置/失败清理顺序，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`）手动加载边界。上游同步 CLI 返回不能提供本项目异步 owner 的完成/排空证据，故沿用 0149 的 owned MC 路径与本项目已有 runtime registry/work accounting。原厂 CNSS2、设备加载脚本和手机状态不变。

## 状态接入

- `mishare_runtime_rate_configure` 先共享检查实际速率，再以 opaque token 查询真实 registry。准备只接受仍引用的 VDEV、events、active legacy/WMA/self-peer、已完成的 PE/channel，拒绝 quiesce/drain/错误、并行工作、删除或已请求 START-plan/radio 的 owner。
- 原生排队前锁存 `requested` 和五个有效速率字段；`posted/accepted` 单独记录 post 返回，`completed` 和完整 receipt 由 MC callback 发布。同步完成可以早于 post 返回，不丢失结果；post 失败无 callback 时仍锁存终态和原始错误，禁止重放。
- 回调在 runtime work reservation 仍持有、active user 已退出时发布。核对 attempted 与位图、按 0/1/3/7 增长的提交前缀、失败位关系、首错一致性和完成标志。重复结果、无 reservation、回调/投递结果矛盾或畸形回执设置永久 integrity_error，保留原回执，不补造 ACK 或清空状态。
- 未注册 token 不解引用、不更新；configure 与原有 owner-handle API 一样，caller 必须序列化调用并跨 poll 保持 native parent/firmware lifetime。标量回调 hooks 不是外部用户接口。

## 清理与启动边界

普通 NDI drain、host destroy、SSR host/NDI/final retirement、完整 batch 预检查和 recovery candidate/metadata predicates 都增加同一个纯元数据门禁。

- 未返回 post 或未完成回调：EINPROGRESS，保留 owner/module/VDEV。
- 有 integrity_error：EUCLEAN，保留原始状态，不执行 native 清理。
- 已尝试原生速率提交（含成功及部分失败）：EOPNOTSUPP。旧的 pre-configuration 普通/SSR 回收尚未证明配置后 teardown，不能据此释放 timer、PE/DP 或父级。整批在任何 item 副作用之前拒绝这种 owner。
- 预发布拒绝、执行前被封锁或 flush，且实际零尝试：只放行到既有清理检查，不跳过原 native 条件或 owned-work 排空，不等于立即释放成功。
- rate 请求锁存后，旧 raw START-plan/START 入口拒绝，以免绕过其余 BSSID/重试/聚合/过滤/收发配置。新内部 configure 也没有自动 caller。

本轮的保留策略是关闭未完成的清理路线，非已实现配置后回收。未实现请求重置、强制释放或自动重试；需要后续安装 qualified post-configuration teardown，再连接完整配置事务与公开初始化。complete 仍只代表 native 提交完成，不能算固件 ACK、射频或 Apple 完成。手机无需操作。

## 验证

本地 100 项 Python 回归和语法/diff 检查通过。新 fixture 原样提取生产 runtime rate block，并编译执行实际 configure bridge 和 owned MC wrapper；native owner 元数据/引用/工作计数/scheduler/executor 为模型。覆盖前置拒绝、opaque token、四种预发布失败、异步与同步完成、flush/quiesce、提交错误、参数快照、重复配置/回调、七种畸形回执和 post/inline 矛盾。六项变异控制在编译成功后命中行为断言。ASan/UBSan 本地通过；本地 ptrace 下关闭 LSan，Actions 开启。

完整 runtime Actions fixture 新增真实普通 destroy、host/NDI/final/batch retirement 和 raw START 拒绝断言，要求零 native delete 且 handle/批结果保留；零尝试的终态仍经真实 host 清理释放。fixture 为清理合成故障字段会显式恢复模型数据，生产没有对应 reset API。这些完整 runtime 断言、原生类型编译/链接及 0067 Kbuild 接入待本次 CI；本地模型不替代物理 shutdown、完整父级租约或设备验收。
