# 0168 重试零尝试结果的 prepared SSR 回收

## 上游与范围

重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch` 初始化/退出调用链，以及 Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh` 部署和恢复流程。两者没有本项目的异步 receipt/SSR owner 协议；本阶段复用本机已验证的 rate-only prepared SSR 原生回收，不改上游 WMI 重试发送，不伪造 ACK，不替换 CNSS2。

## 本批实现

新增纯 predicate `mishare_runtime_retry_zero_attempt_ssr`，要求 SSR 关闭来源、requested/posted/completed、没有完整性错误、work_pending/users 均为零、work_error 为零、负结果和严格全零的未尝试 receipt。只有这个子集可穿过先前的一律 SSR 保留分支。

这不是新的回收许可或窗口：既有 rate reset eligibility、MC drain、cds_post_disable 的原生 HTC/HIF/WMI 条件、窗口关闭、精确 PE/MLME/WMA/DP 身份及各原生回调门禁均保留。只有成功 fixed-rate 配置后、retry 的 allocation/queue refusal、flush 或关闭拒绝没有执行原生提交，才复用 rate-only prepared reset。记录和错误不清零、不改写为成功。已尝试 retry、pending work、重复/畸形完成、非 SSR 来源仍保留。普通退出、late peer/DELETE 与 ordinary tail 不新增任何放行。

## 验证设计

新 fixture 在原 rate reset fixture 上组合生产 retry begin/posted/complete 和选定原生 prepared SSR、timer/PE/DP/VDEV/free 代码，保留原来的 rate/native window 回归和三个变异控制。

- 32 组合：2 频段 × 4 零尝试来源 × 2 DP 时序 × 2 外部 VDEV ref。
- 12 拒绝场景：完整性、非法掩码、零结果、缺 posted/completed、非 SSR、pending/users/work error、attempted receipt、radio 混入和窗口关闭。
- 2 新变异：忽略 attempted、跳过 receipt 校验；每项须被对应 eligibility/回收断言杀死。
- 关闭时仍有 work 的完成发布必须继续保留；DP/host DELETE 后额外引用等待实际 final-free，关闭恢复窗口后只走已合格的 final bookkeeping。
- retry 和 rate 原始结果在退出各阶段保持不变，禁止固件 DELETE 补发。

零尝试回调来源在新 SSR fixture 内使用模型和实际 runtime work accounting；分配、队列、flush、内联回调本体已有独立 production retry work 和 native prestart 组合覆盖。不是手机/IRQ/固件/父级实测。100 项本地 Python 回归、py_compile、fixture 源码及变异锚点生成通过；不本地编译，集中 CI 待执行。

## 0167 最终状态纠正

Actions [42673697311](https://github.com/xxz3312/XAirDrop-17/actions/runs/42673697311) 最终 conclusion=failure；完整 jobs API 仅七条记录，其中六项必需生命周期/桥接任务 success、optional ICNSS skipped，缺 diagnostic 与 transport-stop 任务。不能继续把两项标记为运行中或通过。原因尚未确认，不把缺失归因于代码。此前 [42673135994](https://github.com/xxz3312/XAirDrop-17/actions/runs/42673135994) 的 diagnostic 确实成功，之后修正的是 fixture 入口，但仍不将不同 run 拼成同一轮全绿。本批集中 CI 同时重新核对完整任务集合。

公开 init/START 保持关闭，已尝试重试的 SSR 回收、自动父级 lease 与手机 Apple 互传未完成；手机无需操作。

## 已观察 CI 结果

首次 [42807927198](https://github.com/xxz3312/XAirDrop-17/actions/runs/42807927198) 在新 fixture 的继承 close guard 遇到 `-Werror=misleading-indentation`，没有执行到回收断言；为该 if 增加括号和独立换行，未关闭 warning 或降低断言。

修正版源码 `c0ba33930e34ac1ed4aaa4efe1beaa198a945879`，Actions [42808171189](https://github.com/xxz3312/XAirDrop-17/actions/runs/42808171189)：

- Zero-attempt retry native prepared SSR 步骤 success：32 回收组合、12 拒绝、原三个加新两个行为变异通过。
- 原 retry work、704 组 prestart/普通退出组合（另七项特殊场景、三个变异）、native retry group/receipt 步骤均 success。
- bridge-controller 整项 success。
- 本轮八项必需任务均存在且已启动，diagnostic、transport-stop 与其余生命周期观察时仍在运行；不能提前写成整轮全绿。

以上仍为生产 C/选定原生代码与模型组合验证，未部署到手机。
