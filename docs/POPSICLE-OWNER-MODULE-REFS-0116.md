# 0116 Module references for host and runtime allocations

A void module exit callback cannot veto module removal. Each private host and runtime allocation now takes an independent `try_module_get(THIS_MODULE)` reference before allocation/publication. Failure to obtain the reference returns ESHUTDOWN without publishing an owner. A built-in kernel uses the module API's existing NULL-module semantics.

Host allocation failures, parent pin failures and sync/adapter construction rollback release the reference. Successful host retirement releases it after adapter/sync teardown, parent unpinning, registry removal, storage release and caller-slot clearance. Busy, pending, identity-error and sync-error paths retain it. A host handoff transfers ownership without dropping its reference.

A runtime takes its own reference even if a host exists. Duplicate MAC and quarantined-PSOC refusal release the temporary reference. Ordinary destruction and qualified final bookkeeping release only after actual owner registry removal and allocation release. Partial constructor retention, asynchronous object free, quarantine, unconsumed final-free evidence and outstanding callbacks keep the owner and its reference. Physical VDEV free alone does not retire its owner. No new force-clear or recovery interface is introduced.

## Verification checkpoint

Local verification passed 53 Python tests, Python syntax, source assembly for host/runtime/radio/work/recovery/batch/completed/final fixtures and existing native source restoration audits. Native C execution remains Actions-only and is not claimed yet. The host fixture adds module-exit-state refusal, live/busy/pending/retired owner assertions and three mutations for omitted get, omitted puts and premature put. The runtime fixture adds API refusal, acquire/release balance, pending/physical-free retention and three mutations. The final bookkeeping fixture checks that an actual completed VDEV still holds the runtime reference until qualified owner retirement.

Fixture module API operations are counters with an unload-state refusal model; they do not execute the Linux module loader. Existing native synchronization, firmware and teardown limitations remain. Kernel/module headers are stubbed explicitly in inherited fixtures; production sources use the real Linux module API and require the full kernel link/import gates.

## Remaining lifetime work

This closes host/runtime allocation references only. The standalone module-stop journal and upper power gate can outlive these allocations; their references are not installed by this change. A complete module unload contract remains blocked on that independent lifetime and final execution barriers. The last put relies on the caller retaining native execution/parent synchronization through return; a self-reference does not by itself prove return-to-caller safety. No physical hot-unplug, forced unload, built-in runtime experiment, actual rmmod, Apple discovery, handshake or bidirectional transfer is certified. Radio remains disabled and no phone action is required.
