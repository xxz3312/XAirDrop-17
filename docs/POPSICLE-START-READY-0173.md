# 0173 完整请求的 pre-START 就绪观察

## 基线和参考

0172 修正版 `fe399fb74bd6bde3fd17331f0945378ee84f7e86` 的 Actions [43195729713](https://github.com/xxz3312/XAirDrop-17/actions/runs/43195729713) 八项必需任务全部 success，含完整 WLAN 编译/严格链接。

核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`。上游同步 init/全局上下文和驱动恢复没有本项目的异步 rate/retry receipt、work 排空、request/instance 账本。复用现有真实准备和回执接口，新增单一快照观察而非直接套用上游同步成功返回。

## 当前约束

生产 `mishare_runtime_ndi_start_plan` 和 `mishare_runtime_ndi_start` 对 `rate.requested` 显式返回 EOPNOTSUPP；rate/retry 回收规则也限定 never-STARTed origin。本批保留这些约束。配置后的 START-plan/START 仍须完成相应退出/SSR 资格再接入；本批不发送 START，不将配置就绪解释为公开 init、固件 ACK 或 radio UP。

## 一批接线

- `mishare_start_ready_check`：只读一个 coherent runtime snapshot 和对应 session/prestart/完整请求。核对参数支持、关闭/SSR、错误和 mixed cleanup origins、PE/channel/CREATE/DP 前置条件、BSSID host-MLME 回读、固定速率字段及全部提交掩码、重试参数和完整 receipt validator、最后一个 pending/user work。配置未完成或工作未退出返回 EINPROGRESS；矛盾状态、参数漂移、退出/恢复历史拒绝。相同请求与零值重试遵循既有语义，不写回状态。
- `mishare_wonder_host_start_ready_locked`：实际 owned host 父级身份、DOWN adapter、context/SSR 和 runtime 检查后只获取一次快照并执行同一观察。
- `mishare_request_bridge_ready_locked`：不分配 host、不调用 prepare、不重放配置。重查完整冻结请求、raw/typed 投影和当前 native policy，再观察真实 host。未绑定/未 attach 的实例只返回等待。
- `mishare_wonder_managed_start_ready`：内部进程上下文入口，instance claim → fresh native scope → 父级身份 → request/host 观察 → scope/claim 释放。不缓存 ready 标记，不发布新父级登记。关闭实例拒绝调用。
- target source staging 显式复制新头文件；新测试加入 bridge-controller 同一轮 CI。公开 backend init/poll、runtime START 门禁、KSU 安装流程、原厂 CNSS2、init_boot 均不改变。

返回 0 仅表示当前 scope 内配置证据完整；不是跨轮询可持有的启动凭证。后续 START 入口必须在自己的保护上下文重新验证，并满足 configured START 的退出合同。

## 验证范围

新增纯观察 fixture：16 种 rate/NSS/零重试组合、56 项等待/漂移/SSR/混合退出边界、九项行为变异；检查输入快照不变和不产生 START。该 fixture 的完成事实是模型，既有实际 production prestart/session 回归仍执行。

完整 host fixture 增加实际 instance/request/host/scope/引用路径：无请求、prepare 后不分配、完整快照成功、pending work、快照漂移、当前 policy 拒绝、busy、scope 竞争、父级替换、关闭与最终退休。runtime snapshot producer 在此是模型；rate/retry 实际原生生产者继续由原有组合回归验证，不把两类测试冒充同一条实机流水线。五项生产行为变异覆盖准备门禁、scope 释放、claim 释放、观察接线及 predicate 返回结果。

request bridge fixture 增加无创建副作用、每轮新结果以及 policy 拒绝不读取 host 的检查。100 项本地 Python 回归、py_compile、diff 以及 14 项变异构造检查通过；原生 sanitizer 和完整目标构建集中交给本轮 Actions，提交时待结果。

没有本批手机或射频测试。公开 init/START、过滤/数据面与 Apple 发现/握手/双向文件传输仍待完成。手机无需操作。
