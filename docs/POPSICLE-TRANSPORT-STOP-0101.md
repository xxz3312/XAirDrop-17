# 0101 Native HIF receive and HTC stop ordering

Implementation prepared; unified Actions compilation/validation pending.

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
Twelve new mutations extend 82 inherited rejected controls to 94. All counts
await CI acceptance. The new job runs alongside all previous independent jobs.

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
