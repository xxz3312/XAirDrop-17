# 0145：初始化请求快照与只读上下文准备

新增完整初始化请求的规范化/语义比较，并让公开 backend init 先检查请求形状。畸形请求返回 EINVAL；合法形状仍返回 EOPNOTSUPP，handle 保持 NULL，不分配 host/实例，不启动固件。

## 上游依据

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：重新核对 channel/rate 枚举、NSS、MAC/BSSID、国家码、重试的原生使用及 init 上下文顺序。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/action.sh`，blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`：保留原厂 CNSS2 和手动加载边界，设备端脚本不变。

保留公开结构体 ABI，私有快照按字段复制/比较，避免 padding 决定请求相等性。与上游同步 init 的差异：当前原生 owned channel 只有 HT20 路径，且尚未应用国家码/速率/过滤/收发，因此不能解析后直接报告初始化成功或静默缩窄请求。

## 请求与准备合同

- 记录信道、固定速率所有有效字段、MAC、BSSID、国家码、管理/数据重试、AMSDU/AMPDU、RA 标志及启用时的 rate mask。保留字段清零；RA 未启用时 mask 不参与有效语义。
- 检查非零频点、单播非零 MAC、枚举上下界（含负值）、非零且不超过公共 NSS 上限的 NSS、终止的两字符大写国家码或 `00`；启用 RA 才验证 mask 的形状。失败不修改输出快照。
- 这不是监管/协议许可：不声明某频点可用，不验证国家数据库/MCS 编码/实际平台 NSS，也不改变全局国家码。频点没有锁定 5745，解析可记录 2412/5240/5745 等请求。
- 内部 managed prepare 额外检查当前实现的 HT20/最多两流范围，以及 caller 提供的 1..2 NSS 数值域。NSS 的原生平台来源仍由 caller 负责，不把数值检查写成硬件能力验证。
- prepare 在取得新的原生 scope 后，验证 HDD context、非 recovering 和 mission mode；没有 CREATE/START、国家码设置、速率设置或接口分配。重复同一请求也重新取得 scope，不能使用上次检查冒充本次父级存活。
- 第一次准备成功后，参数/NSS 不可更改；已尝试 raw host 创建的实例不能补装请求。关闭后的实例拒绝准备。准备失败保留已有元数据和所有权。
- 只存请求不等于已应用请求：准备后的实例禁止调用旧 raw step 捷径，以免只使用 MAC/频点/NSS 而忽略其他初始化语义。公开 init 和 poll_start 仍未启用。

## 验证与边界

100 项本地 Python 回归、Python 语法与 diff 检查通过。[Actions 42349938676](https://github.com/xxz3312/XAirDrop-17/actions/runs/42349938676) 的 bridge-controller 作业 `128335715584` 已成功，含新增 request 和既有 bridge/managed/provider/legacy PASS_ONLY 标志；实际 host/prepare 及原生退出回归作业 `128335715605` 也已通过；完整目标编译仍在运行。Actions-only C fixture 使用真实公开 API 和生产解析器，检查 21 项有效字段变更、17 项畸形输入、失败输出保留、保留字节归一化、inactive mask、输入/输出别名及语义比较。实际 host fixture 继续检查 scope 竞争、失效 context、recovery/非 mission 拒绝、不可变请求和 NSS、raw step 禁止、关闭后拒绝、无 native owner 的元数据退出；原生同步/设备/父级是模型。

下一步仍需验证和应用实际国家码/监管信道/速率/过滤等配置，解决跨调用父级组件/固件生命周期，再连接公开 init/poll。单次只读上下文检查不构成异步阶段间的租约，也不证明 RX/TX、射频或 Apple 互通。本轮无新安装包，手机无需操作，不重复 apply。
