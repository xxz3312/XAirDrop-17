# 0104 Production idle and mode-change stop admission

Implementation prepared; unified Actions validation pending.

Production `mishare_runtime_psoc_busy()` observes every exact-PSOC runtime owner under its registry lock, including construction before a VDEV exists, asynchronous drain, freed-but-not-retired metadata and quarantine. `mishare_wonder_host_stop_ready_locked()` combines the host and runtime registries without nesting their locks; invalid parent identity returns EINVAL and any owned object returns EBUSY.

Patch 0038 routes the existing native idle gate through this combined predicate and adds gates before module stop in both mode-change callbacks. Regular idle maps refusal to EAGAIN; mode-change returns the actual refusal without clearing the inner mode-change flag. Empty registries preserve native module-stop results. No firmware command or forced cleanup is added. The caller must retain the existing exclusive parent/driver transition through observation and stop; these are snapshots, not references or leases.

The actual production host/runtime files and three patched native entry functions run in Actions fixtures. Runtime tests cover standalone/pending/draining/quarantined owners and foreign PSOC exclusion. Host tests cover runtime-only, host-only, invalid context, mode flag retention, native error propagation and ordinary idle behavior. Five targeted mutation controls remove either registry check or each of the three call-site gates. A fast independent Actions job runs these tests alongside all previous jobs; final module symbol checks require both new production helpers.

This is stop admission for idle/mode change, not a complete automatic shutdown coordinator. Some native remove/SSR callers ignore lower stop failures, so those paths are not made safe by returning an error here and are unchanged. Global owner-handle transfer, native parent component lifetime, real IRQ/DMA/callback drain and physical HTT free remain outstanding. No new radio init, backend activation or phone test is enabled.
