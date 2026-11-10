# 0169 已提交重试配置的 prepared SSR 回收

## 上游与边界

重新核对 Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` 的 `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`（初始化、retry SME 调用及退出链），Leekin2/XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` 的 `module/action.sh`（部署、原厂驱动恢复）。两者未提供本项目的异步 SSR receipt 协议；本阶段复用 pinned 本机 native prepared-reset，保留原厂 CNSS2，不改 WMI 命令，不合成 ACK。

本批一并增加 frozen VDEV ID、prepared retry SSR 纯资格判断、实际 MC work/registry 与原生回收组合测试。目标仅是 never-START、fixed-rate 成功后的 retry 提交完成（含部分失败）配置，不能沿用 ordinary tail/peer-reset/mixed-origin 回收。

## 生产合同

runtime retry begin 保存精确 VDEV ID；completion 同时核对当前 exact VDEV 的 ID 与冻结值。receipt 的普通退出和 SSR 复核使用冻结 ID，不再以 receipt 自己报告的 ID 作为比较标准。该字节在物理 VDEV 释放后继续保留，不为校验访问已释放指针。

新增 `mishare_runtime_retry_prepared_ssr`，要求 requested/posted/accepted/completed、无 integrity/work 错误、实际 attempted receipt 严格匹配参数/ID/组掩码/结果、SSR 来源及 MC drained，且 pending/users 均零。原 fixed-rate 必须全部成功；存在 ordinary/late-peer/late-delete/peer-reset/tail 或 START-plan/radio 历史均不允许此分支。

资格通过仍不等于可以回收。原有 native CDS→HTC/HIF/WMI 恢复窗口、窗口关闭、精确 native PE/MLME/WMA/DP 身份、timer/PE/context/DP 完成来源、真实 final-free 门禁均保留。使用原 rate.reset_admitted/reset_completed 记录同一 prepared reset 的阶段，不增加第二套可重放回收状态。WMI 部分失败不重发、不回滚，负结果及 receipt 保留到 owner 退休。无固件 DELETE 补发。

0168 的严格零尝试分支保持独立。完成发布时 reservation/ref 仍持有，即使发生 SSR fence 也不能提前回收；关闭后的工作要先释放，再由 native MC stop 和 qualified window 允许推进。已进入 ordinary 退出的 retry 不属于本阶段。

## 测试范围

新 fixture 将实际 retry MC work/configure/registry 与 rate prepared-SSR 的选定原生代码组合；WMI retry executor 用模型，具体 SME/WMA 组循环和 receipt 由现有独立 fixture 验证。保留原 rate reset 和 0168 zero-attempt 所有回归。

352 组合：五组零/非零/255 参数，成功和有效的两组部分失败（共 11 种）× 32 种时序/环境（频段、内联完成、完成发布中关闭、额外 VDEV ref、DP 内联）。16 拒绝场景覆盖 frozen ID/掩码/完整性、缺 posted/accepted/completed、非 SSR、work pending/users/error、MC 未 drain、rate 失败、ordinary 混入、START-plan、恢复窗口关闭、PE 频率漂移。增加三项行为变异（绕过 MC drain、跳过 frozen receipt 校验、忽略 ordinary 混入），加原有 rate 三项及 zero-attempt 两项共八项。

测试必须证明定时器/PE/DP 仅一次退出、零固件 DELETE、记录不改写、额外引用等待实际 final-free，窗口关闭后仅做已完成 native cleanup 的 final bookkeeping。以上为测试设计；本地只运行 100 项 Python 回归、py_compile、源码/变异锚点生成与 diff 检查，原生执行和目标编译统一在 Actions。

0168 Actions [42808171189](https://github.com/xxz3312/XAirDrop-17/actions/runs/42808171189) 八项必需任务已全部 success，包含完整 diagnostic 和 transport-stop。

公开 init/START 仍关闭；automatic parent lease、ordinary-tail/peer-reset 的 retry 扩展和手机 Apple 发现/握手/双向传输未完成。手机无需操作。

## 已观察验证结果

Actions [42837056822](https://github.com/xxz3312/XAirDrop-17/actions/runs/42837056822)，源码 `1fb5ba911e55384817a944ed84d7b3d1a40a4cd8`：

- Submitted retry native prepared SSR 步骤 success：352 组合、16 拒绝、原 rate/zero 回归及总八项 native 行为变异通过。
- 独立 Zero-attempt retry native prepared SSR 步骤 success，保持 32 组合和 12 拒绝。
- retry work 步骤与 bridge-controller 整项 success。
- 普通 704 组组合（另七项特殊场景和三项变异）与 native retry group 步骤也 success；后续退出回归和完整 diagnostic 仍在运行。不能提前标记整轮全绿。

未部署到手机；上述成功不等于固件 ACK、射频或 Apple 互传成功。
