# 0148：统一初始化准备与固定速率执行的支持合同

把 0147 的纯参数检查提取为共享 `mishare_rate_check`，接入实际 managed prepare。输入支持检查发生在实例 claim、native scope、监管查询及元数据保存之前；执行器仍在原生编码前重复调用同一检查，不依赖早期检查作为未来执行许可。

## 上游依据

本轮重新读取以下固定版本：

- Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`，`kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`，blob `8874b020b4d7eadea41adea787d53dcca08a3c62`：核对 preamble、NSS 减一、GI/带宽命令和初始化先创建再配置的顺序；其 adaptive mask setter 仍返回错误。
- Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`，`module/action.sh`，blob `024cd17fb19c50c10f204552f8a2cd6fffc5d30a`：核对手动加载、原厂 CNSS2 及设备支持边界。本轮不改设备端脚本。

与上游的差异延续 0147 的保守支持子集，并在任何 native 准备前拒绝不能执行的请求，避免把单纯可解析的参数当成当前支持。国家码/信道仍用 0146 的每次实际查询；共享速率检查不替代监管检查或平台能力来源。

## 行为和限制

- 共享检查不分配、读父级、调用编码器或下发命令，只验证 HT20、最多两流和 0147 的 HT/VHT/HE/EHT MCS/GI 子集。形状错误返回 EINVAL，不支持组合返回 EOPNOTSUPP。
- managed prepare 明确拒绝启用的 rate adaptation，包括形状有效的 mask，防止在固定速率路径静默忽略自适应请求。旧的不可到达 native RA NSS 分支移除，固定 NSS 的对应频段上限检查保留。
- 速率支持检查成功后仍需实际 scope、HDD/recovery/mode 和当前国家/信道/NSS 检查。仅这些检查全部成功才保存完整不可变请求；失败不覆盖已有元数据。
- 原请求快照仍包含所有参数，保留字节及 inactive mask 继续归一化。支持检查没有缩窄或改写输入。已准备实例仍禁止 raw step，公开 init/poll/速率接口保持关闭。
- 这是准备合同接入，不是完整配置事务完成。BSSID、重试、聚合、过滤和收发的实际应用、WMA 队列排空以及跨调用父级/组件/固件生命周期协调仍未接通，不能据此启动 START 或宣称射频/Apple 完成。

## 验证

192 组实际速率执行器 C 模型、六项执行器变异检查、100 项本地 Python 回归及 Python 语法/diff 检查通过。速率报告新增共享头及公共 ABI 头摘要，避免仅对 C 文件取摘要遗漏已移动的验证代码。

Actions-only host fixture 新增 11 项实际 managed prepare 拒绝检查，覆盖 legacy、四种 PHY 的 MCS 越界、不匹配 GI、宽带宽、NSS 超限、有效 RA mask 和畸形 GI，要求无监管读取、无 scope/host/runtime 副作用、无已准备元数据。保留原生国家/信道漂移重查和固定 NSS 验证；有效准备基线改为显式 HE。

新增两个 host 变异控制：吞掉共享速率检查结果，以及移除 RA 拒绝，均须编译后命中行为断言；六项仍有效的原生监管变异控制保留。完整 host 行为/变异回归和目标编译待本次 CI。0147 的六项必选 CI 已成功，其完整构建和 parent-peer-composite 在本轮开始时仍运行，不提前记录全通过。无新安装包，手机无需操作。
