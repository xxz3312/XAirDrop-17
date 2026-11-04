# 0102 Native CE stop and IPCI producer drain

离线验收完成：[CI 41778488794](https://github.com/xxz3312/XAirDrop-17/actions/runs/41778488794)（`99d3f8d`）五项作业成功。代码、相关边界用例与 CI 入口集中完成后统一编译验证。

This stage replaces the selected 0101 lower bus-stop model with the unchanged
`hif_ce_stop()` body. It executes original `hif_disable_isr()` multibus dispatch,
`hif_ipci_disable_isr()`, `hif_destroy_oom_work()` and `hif_buffer_cleanup()`.
The IPCI bus source assignments to CE stop and IPCI ISR disable are checked;
initializing the bus ops table itself remains modeled.

256 new contracts select SG, WDI, 6/16 CE pipes, started/unstarted state,
diagnostic handle, sleep timer, procfs and NSS ownership flags independently.
Message format/alignment follow diagnostic-handle/pipe-count selections.
Each child starts one real host pthread. A model primitive admits that worker,
models interrupt masking, then the modeled CE tasklet-kill primitive lets its
message finish through original callbacks and joins it before native cleanup.
This is a controlled host synchronization contract; actual kernel primitives,
DMA, interrupts and tasklet scheduling are not executed.

Native loops skip a null CE state when destroying OOM work, respect the selected
NSS buffer ownership gate, drain the eligible receive/send endpoints, flush
delayed register work, finalize present CE handles, clear handle/size fields,
apply started/diagnostic/source-entry lock policy, deregister RX buffers and
stop/free an initialized sleep timer. A missing CE handle preserves its prior
buffer-size field, matching the original function's conditional behavior.

Sixteen new behavior mutations extend 94 independent prior controls to 110.
The existing 192 composites, 64 callback contracts, 303 parser contracts,
32 stop-order contracts and eight CE length contracts remain. All counts passed in the accepted CI run. The new job runs alongside all previous jobs.

No production patch is introduced. Residual receive/send cleanup functions,
CE ring teardown, physical HTT storage free, real work/tasklet/interrupt drain
and production parent shutdown coordination remain outside execution. Layouts,
locks, timers, register work and CE-finalize endpoints are models. The real
pthread test is deterministic, runs under ASan/UBSan, and is not TSan or phone
concurrency certification. Callback/context pointers remain retained; stopping
producer admission still depends on modeled primitive behavior. Backend stays
disabled; no active SSR, phone/RF or AirDrop validation is claimed.

## 验证记录

256 组 CE/IPCI 受控线程停止检查、192 组既有组合、64 项回调检查、303 项解析检查、32 组既有停止顺序与 8 项长度/所有权检查、110 项失败控制均通过。十项既有独立组合、53 项 Python 检查、完整 WLAN 编译、CNSS、严格链接、七项选定布局和模块记录检查通过。首次 CI 在夹具中发现 HIF 不透明类型重复定义，复用既有恢复夹具的模型定义后重跑通过；原生函数体未修改。

十一份组合生成源码独立重建哈希与 CI 一致；新增组合 SHA-256 为 `b2a17551eed34aa39d73fe175c4abb57d4d30c7e1bb2f0e91322b3bdd5418712`。五个新接入原生函数匹配锁定原始源码，来源文件哈希一致；生产 HTT 文件仍与 0099 相同。54 份报告中的生产源码、37 个路径别名、锁定源码清单与五份验证 ZIP digest 均核对。五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖，七项布局候选对应最终链接 WLAN。本地未执行 C 编译。见[完整验收 JSON](research/popsicle-ce-stop-0102-validation.json)。

本轮执行原生 CE 停止、IPCI ISR 关闭、OOM 和缓冲区清理循环；主机线程通过模型 tasklet-kill 原语等待消息结束，随后原生流程才清理资源。该结果不证明真实硬件中断、DMA、内核 tasklet/work 排空或迟到回调安全。残留收发缓冲区的完整清理函数、物理 CE/HTT 释放和生产父资源停机协调仍待继续。backend 保持关闭，手机无需操作。
