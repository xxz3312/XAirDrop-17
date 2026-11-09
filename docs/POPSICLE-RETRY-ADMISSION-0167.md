# 0167 SSR 等待优先级与初始化参数支持范围

## 0166 结果和修正

Actions [42657490299](https://github.com/xxz3312/XAirDrop-17/actions/runs/42657490299) 的七项必需任务成功，包含 diagnostic 完整 WLAN 编译、严格链接和布局记录。独立 retry work、request bridge 通过，但 stop-admission 的 retry native composite 在 `EXPECTED_RETRY_NATIVE_RETAIN_DURING_PUBLISH` 断言失败。其后步骤 skipped，不宣称该批全部通过。

旧分支对已选定 retry 先判断 pending/posted，再判断 SSR，导致 SSR 完成回调仍持有 reservation 时返回普通 EINPROGRESS，而测试要求明确 EUCLEAN 隔离。改为 requested retry 遇 quiesced 优先 EUCLEAN。并未解除 reservation 或放开 SSR 回收；普通未关闭路径仍等待 work drain。新增失败诊断输出记录参数、故障、时序和返回码。704 组合与七项特殊场景在集中 CI 重验；未用降低断言要求来绕过失败。

## 上游参考和聚合约束

重新读取 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`：`qdf_mem_zero(features, ...)` 后仅设置 dynamic frequency/rate、frame filter、custom retries 和可选 coexist，A-MPDU/A-MSDU capability 保持 0；初始化没有消费 `ampdu_enable` / `amsdu_enable`。Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh` 未提供独立聚合应用协议。本机 GEN TX_AMPDU/TX_AMSDU 是大小配置路径，不能仅凭名称视为 Wonder boolean 的等价实现。本阶段不复制一个未经验证的固件命令序列。

增加纯 `mishare_init_aggregation_check`，在 managed prepare、native request preflight、内部 request bridge 三个入口拒绝任一聚合 enable。bridge 首次拒绝不分配、不绑定、不推进 native；已绑定请求的改值仍先返回 EBUSY。语法解析仍可记录这些有效字段，不把语法有效误当支持。零值表示未申请 enable，不证明固件聚合关闭；返回 0 仍只代表已有 prestart 子集。

## 同批测试

- 三个非零聚合组合分别覆盖纯支持检查、完整 managed prepare、实际 native preflight 和 request bridge 无副作用拒绝；零值保留现有正常路径。
- 原八组 request bridge 成功场景改为 retry 零值/非零与 HT/HE 组合，不再将不支持的聚合 enable 当作成功场景。
- native policy 案例从 13 增至 16，新增绕过聚合支持检查的行为变异。
- retry 原生 SME/WMA fixture 同时执行实际 receipt validator；每个提交/失败位置覆盖 busy、complete、attempted、ID、两项参数、三类掩码及 first_error 共十项篡改拒绝。
- 100 项本地 Python 回归、py_compile、native fixture 源码生成和 diff 检查通过；不在本地编译。全部相关修改集中为一批 CI。

公开 init/START 仍关闭，保留原厂 CNSS2；没有手机或 Apple/RF 成功声明，无需手机操作。重试后的 SSR 合格回收、aggregation 原生应用、完整父级跨轮询 lease 仍待完成。

## 首轮复验与测试入口修正

Actions [42673135994](https://github.com/xxz3312/XAirDrop-17/actions/runs/42673135994) 的 request bridge 与 retry work 通过，retry composite 初始主程序完整返回成功（704 组合和七项特殊场景），随后第一项 negative control 未被杀死而失败。原因是 engine.audit 调用 extra_audit 前留下 drift-only main，新 fixture 未显式切换到 retry 入口；变异代码没有执行。现为三个控制分别指定普通、重复完成、SSR retry 基线，先验证未变异基线成功，再验证变异以 SIGABRT 和 EXPECTED_RETRY_NATIVE 标记被拒绝。不得将该轮写成所有变异通过。

## 修正后的已观察结果

Actions [42673697311](https://github.com/xxz3312/XAirDrop-17/actions/runs/42673697311)，源码 `a5c62c23e09797c35c1d0a56d9b5c8009c4423f0`：

- bridge-controller 整项 success，包含 16 项 native policy、四项 policy 变异和新增聚合拒绝场景。
- Owned retry queue and completion ownership 步骤 success。
- Retry prestart and native retirement composite 步骤 success：704 组合、七项特殊场景及三项各自先运行基线的行为变异通过。
- Native retry group submission 步骤 success，含原生 SME/WMA 循环及实际 receipt validator 的十类篡改拒绝。

观察时后续 BSSID/退出回归仍在运行，完整目标构建尚待调度/完成，不能据此声称整轮全部通过。上述结果仍是原生代码和模型组合验证，不是手机或固件 ACK 证明。
