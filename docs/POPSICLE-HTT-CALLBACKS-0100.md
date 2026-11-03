# 0100 Native HTC registration and HIF receive callback composite

Implementation prepared; unified Actions compilation/validation pending.

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

All 168 earlier complete selections use captured HTC receive callbacks. Twenty-
four extra selections cover HTC/WDI-on, HIF/WDI-on and HTC/WDI-off delivery, both
unmap formats, both alignments and reference timing/tracing. Sixty-four separate
contracts cover valid endpoint responses 3/6, constructor failure, receive
failure/cancel, null inputs and native send-full KEEP ownership. The 303 parser
contracts remain. Thirteen new mutations and one original wrong-pipe rejection
extend 68 inherited controls to 82. Counts await accepted CI.

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
