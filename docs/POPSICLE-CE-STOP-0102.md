# 0102 Native CE stop and IPCI producer drain

Implementation prepared; unified Actions compilation/validation pending.

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
32 stop-order contracts and eight CE length contracts remain. Counts await
accepted CI. The new job runs alongside all previous jobs.

No production patch is introduced. Residual receive/send cleanup functions,
CE ring teardown, physical HTT storage free, real work/tasklet/interrupt drain
and production parent shutdown coordination remain outside execution. Layouts,
locks, timers, register work and CE-finalize endpoints are models. The real
pthread test is deterministic, runs under ASan/UBSan, and is not TSan or phone
concurrency certification. Callback/context pointers remain retained; stopping
producer admission still depends on modeled primitive behavior. Backend stays
disabled; no active SSR, phone/RF or AirDrop validation is claimed.
