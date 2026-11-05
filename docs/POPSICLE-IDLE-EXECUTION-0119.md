# 0119 External execution reference across native IPCI idle callbacks

Ordinary idle shutdown can retire a handed-off private host and release its last allocation reference. Patch 0050 therefore installs the external provider's idle shutdown/restart functions directly in the native ICNSS callback slots. Like the existing SSR entries, they acquire the WLAN module under the provider registry lock, execute the complete native PLD callback without holding that mutex, and release only in provider code after all WLAN frames return. Native callback errno values are propagated unchanged. Closing and module-exit-state refusal apply to all four entries.

The native idle shutdown callback checked `ops->shutdown` but invoked `ops->idle_shutdown`. It now checks the function it actually calls. A missing idle callback returns ENODEV; a missing native context retains the original EINVAL path. This also allows a valid idle callback independently of the unrelated shutdown pointer.

## Private ABI v2

The copied execution descriptor now includes both idle callback pointers. Registration uses the distinct `opairshare_wlan_execution_register_v2` export and does not retain a v1 registration alias. Old three-entry descriptors must never be read as larger tables. Old WLAN binaries cannot resolve v1 registration against the new provider; new WLAN binaries cannot resolve v2 against an old provider. Both modules must be built and distributed from the same source. The linked provider check requires the seven execution function exports and rejects a v1 registration alias. These are symbol/ABI checks, not runtime certification.

## Verification checkpoint

Locally, 53 Python tests, Python syntax, host/external fixture source assembly, complete native IPCI restoration and patch forward/reverse checks passed. [Actions 42008448819](https://github.com/xxz3312/XAirDrop-17/actions/runs/42008448819), source `bb8c8a514cee3a9da9b5403ace6e99021fa04d5d`, passed the production host/runtime/external C fast job with ASan/UBSan and leak detection. All added idle scenarios, three concurrent callback kinds, eight external mutation controls and inherited upper/host/runtime regressions passed. ZIP digest, regenerated three fixtures, provider/shared-header/native-PLD hashes and v2 registration identity match. All seven jobs now pass. The digest-checked compact full artifact matches the host report and production hashes, the provider v2 ELF export gate passes, WLAN has no unresolved symbols, recorded module versions have no mismatches, and selected layouts match. Stage 0119 offline acceptance is complete. The large diagnostic archive was not downloaded. See the [validation checkpoint](research/popsicle-idle-execution-0119-validation.json).

The existing fixture adds full native idle callback execution, final private-reference release and exact EAGAIN/EINPROGRESS propagation, missing native context/callbacks, the corrected unrelated-shutdown-pointer case, module refusal and closed-channel refusal. Real pthread overlap now runs separately for SSR reinit, idle shutdown and idle restart. Three new mutation controls cover premature idle execution put, a native slot bypassing provider, and restoring the incorrect idle callback guard. Five existing external mutations and native upper unload tests remain.

The function-pointer registration descriptor, provider source and shared header are hashed alongside regenerated host/runtime/external fixtures. Kernel loader, native DSC, actual idle power transitions, firmware and ICNSS unregister/error-drain contracts remain models or source assumptions. No real rmmod or phone operation is performed.

## Remaining limits

This covers IPCI SSR and idle WLAN return frames. Remove still runs during native unregister, including module GOING, and needs a separately qualified unregister lifetime rather than a generic get that would fail in that state. Crash shutdown, PM/other native callbacks and managed metadata self-detach remain outside this stage. Physical disappearance, forced unload and active radio interoperability remain unverified. No Apple discovery, handshake or transfer is enabled.
