# 0100 Native HTC registration and HIF receive callback composite

离线验收完成：[CI 41625241354](https://github.com/xxz3312/XAirDrop-17/actions/runs/41625241354)（`d09f2bf`）三项作业成功。代码、边界/失败检查和 CI 入口集中完成后统一编译验证。

This stage executes the unchanged `htt_soc_initialize()`, `htt_htc_soc_attach()`,
`dp_htt_hif_t2h_hp_callback()` and `dp_htt_h2t_full()` bodies. Both original
`dp_hif_update_pipe_callback()` variants are included explicitly: the WDI-enabled
variant publishes the HP callback to a modeled lower HIF endpoint; the disabled
variant is an original no-op and preserves ordinary HTC receive delivery.

The lower connect endpoint captures the original constructor's callback/context
pairs. Messages are delivered through those captured pointers, not by calling
the parser directly. The native high-priority adapter asserts pipe 5, zeroes its
packet, supplies successful status and the nbuf context, then enters the
unchanged consumed-message prefix of `dp_htt_t2h_msg_handler()`. That prefix
returns through the production parser added in 0099. Generic unconsumed-message
tail code is an abort stub; it is not counted as executed. Unused-local warnings
are suppressed only around this extracted prefix because its locals belong to
the unselected tail. The full production dispatcher remains compiled normally.

The 168 earlier composite selections route through captured HTC callbacks when cleanup reaches unmap; retention/failure selections preserve their stopped paths. Twenty-
four extra selections cover HTC/WDI-on, HIF/WDI-on and HTC/WDI-off delivery, both
unmap formats, both alignments and reference timing/tracing. Sixty-four separate
contracts cover valid endpoint responses 3/6, constructor failure, receive
failure/cancel, null inputs and native send-full KEEP ownership. The 303 parser
contracts remain. Thirteen new mutations and one original wrong-pipe rejection
extend 68 inherited controls to 82. All checks passed in the accepted run.

The new callback job runs alongside the unchanged independent regression and
full build jobs, retaining all previous checks without serially stacking the
new compilation work. No new production patch is added this stage.

Constructor storage, handles, HTC connect, endpoint save, logging initialization,
HIF callback storage and layouts are models. Only the original consumed prefix
runs; unrelated generic dispatcher paths and TX completion are not executed.
Both WDI source variants are tested, not proof of the phone's active feature
selection. No real bus/DMA/interrupt/firmware service, attach-time reentrancy,
deregistration, late producer race or parent shutdown is certified. Inherited
DP object/reference, peer-gone, platform and cleanup endpoints remain models.
Backend remains disabled; no phone/RF, active SSR or AirDrop validation is claimed.

## 验证记录

192 组释放组合、64 项构造/注册/回调合同、继承的 303 项解析合同、82 项失败控制（68 项继承、13 项新增变异及 1 项未改写原生 wrong-pipe 拒绝），0099/0098/0097/0096/0095/0094/0093/0092 八项独立组合、53 项 Python 检查、旧回归、完整 WLAN 编译、CNSS、严格链接、七项选定布局及模块记录检查均通过。新增回调作业、原独立回归和完整构建并行，保留此前全部验证。

九份组合生成源码独立重建哈希均与 CI 一致，本轮 SHA-256 为 `36dda8a177c9efe942fd71be425bce6784c9e818cc3324c64774c7cb9e2032fb`。四个 HTT 原生函数体和两个 HIF 注册函数体匹配锁定原始源码；实际消费入口前缀和来源头文件哈希一致。生产 HTT 文件与 0099 相同，本轮未新增生产补丁。52 份报告中的生产源码、37 个路径别名、锁定源码清单以及三份验证 ZIP digest 均核对。布局候选对应最终链接 WLAN，五个模块无版本记录不匹配或缺版本依赖，WLAN 无未解决依赖。本地未执行 C 编译。见[完整验收 JSON](research/popsicle-htt-callbacks-0100-validation.json)。

本轮执行的是原生构造/注册、高优先级适配和接收函数的消费前缀，消息通过模型下层保存的原生回调指针送达。它不是实际 HTC/HIF 总线、DMA、中断或固件消息证明；未覆盖注册重入、注销/停机与迟到生产者竞态。完整 generic dispatcher 尾部仍不在主机运行范围。backend 保持关闭，手机无需操作。
