# 0101 Native HIF receive and HTC stop ordering

离线验收完成：[CI 41665851697](https://github.com/xxz3312/XAirDrop-17/actions/runs/41665851697)（`fcb336d`）四项作业成功。代码、相关边界用例与 CI 入口集中完成后统一编译验证。

This stage executes five unchanged functions from pinned WLAN sources:
`hif_update_pipe_callback()`, `hif_ce_do_recv()`, the multibus `hif_stop()`
delegate, `htc_stop()` and `reset_endpoint_states()`. Both original
`RX_SG_SUPPORT` branches of HTC stop execute. Native HIF publication replaces
the previous lower callback-copy model, and native CE receive now carries HP
messages to the captured native HTT callback and production unmap consumer.
The fixture selects the source QCN9224 16-pipe bound, not a phone configuration.

The 192 previous composite selections, 64 callback contracts and 303 parser
contracts remain. Forty new contracts comprise 32 stop combinations (SG,
WDI, polled HTT endpoint, message format and alignment) and eight CE length
checks (consumed v2 prefix, short header, zero bytes, oversize, both alignments).
Twelve new mutations extend 82 inherited rejected controls to 94. All counts passed in the accepted CI run. The new job runs alongside all previous independent jobs.

Original stop code flushes endpoint RX/TX queues and stops/frees polling timers
before calling HIF stop. Original multibus dispatch reaches a modeled bus stop
that delivers one final admitted message while HTT context is retained, then
closes model admission. Native lookup-queue policy distinguishes WMI, control,
nonpolled HTT and polled HTT endpoints. The SG branch drains two modeled buffers.
The original endpoint reset runs after this work and resets all selected fields.

Endpoint reset does not revoke captured receive callback/context pointers; this
is explicitly checked. The post-stop producer rejection, lower bus drain and
context-release marker are model assumptions, not real synchronization or HTT
heap release. No production patch is introduced. Actual interrupt/CE-ring/DMA
drain, timer cancellation, tasklet/work synchronization, concurrent producers,
registration reentrancy and late callback safety remain unverified. Queue and
timer primitives and layouts are models. The generic HTT dispatcher remains
consumed-prefix only. Production shutdown coordination remains unfinished.
Backend stays disabled; no phone/RF, SSR or AirDrop certification is claimed.

## 验证记录

新增 32 组停止顺序合同、8 项 CE 长度/所有权检查、192 组既有组合、64 项回调合同、303 项解析合同和 94 项失败控制均通过；九项既有独立组合、53 项 Python 检查、完整 WLAN 编译、CNSS、严格链接、七项选定布局和模块记录检查通过。首次 CI 在新增夹具的 lookup policy 断言处触发 `-Werror=parentheses`，明确括号后正常用例通过，随后省略 HIF stop 的变异留下未用变量；补齐无行为的变量引用后重跑通过。两次问题均在测试夹具，原生函数体未修改。

十份组合生成源码独立重建哈希与 CI 一致；新增组合 SHA-256 为 `6001559183328799a4a98d016fbdaf3ec0c2d949eb7d4a80d63ab79872e1bceb`。五个新接入函数体匹配锁定原始源码，两个 SG 分支各执行同一份原 HTC stop 函数体，来源文件哈希一致；生产 HTT 文件仍与 0099 相同。53 份报告中的生产源码、37 个路径别名、锁定源码清单与四份验证 ZIP digest 均核对。五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖，七项布局候选对应最终链接 WLAN。本地未执行 C 编译。见[完整验收 JSON](research/popsicle-transport-stop-0101-validation.json)。

该结果确认源码中的停止调用顺序与原生 CE/回调传递路径在模型合同下成立；下层 bus stop 的排空与关闭入口仍是串行模型。原生 reset 不清除已保存的接收回调指针，因此不能据此认定真实迟到回调安全。真实总线/中断排空、并发同步、物理 HTT 释放和生产停机协调仍待继续。backend 保持关闭，手机无需操作。
