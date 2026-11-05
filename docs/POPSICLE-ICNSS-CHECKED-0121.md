# 0121 Optional checked ICNSS unregister contract

Patch 0052 adds `icnss_unregister_driver_checked_v1(ops, remove_status)` to the pinned platform source. It preserves the existing public unregister entry and native ops structure layout. The new entry submits an uninterruptible synchronous event carrying the exact ops pointer and a read-only receipt callback. The worker rechecks ownership before native removal. A stack guard is valid only across this synchronous contract; caller must retain callback code/data until return.

After void remove returns, the worker queries the external provider before clearing platform ops/state or powering off. Refusal retains ops, PROBED, UNLOADING and shutdown blocking, sets an appended terminal state bit, and returns the error. Both new checked and legacy unregister events then refuse replay. There is no retry/reset API. A checked no-probe path refuses ENODEV pending separate proof of empty private ownership; wrong/missing platform/ops and event-post failures return before removal.

The provider exports `opairshare_wlan_execution_remove_status(dev)`. It checks the active unregister scope, first error, outstanding execution/remove, successful completion and exact device identity; it never releases the scope/reference or invokes WLAN. A completed receipt is cleared when a new remove starts. The linked provider gate now requires twelve execution exports.

## Delivery boundary

This stage supplies optional platform source and host C validation. Current target setup patches platform source but builds WLAN/provider against the stock platform exports; it does not build or replace ICNSS. The shipped PLD consumer still uses the old unregister API. Therefore phone unregister still has the 0120 platform limitation. A matched platform build/deployment and consumer integration are required before enabling this path. No automatic platform replacement, private kernel symbol hooking or device operation is installed.

The original first-use legacy path remains unchanged, including powering off after a refused void remove. A dedicated test demonstrates this limitation rather than treating the new interface as deployed. The new terminal flag gates unregister entry points only: other shutdown, SSR, reset and module-loader paths remain uncoordinated. A blocked failure intentionally has no recovery policy; this is not a complete error recovery solution and a borrowed module-exit failure still cannot veto loader removal.

## Validation checkpoint

Local 53 Python tests, source assembly, complete restoration of three platform files to the locked commit and patch forward/reverse checks pass. A new Actions-only fixture executes actual provider C, complete native PLD remove, ICNSS handler and checked/legacy functions. It models module API, synchronization, vendor removal, platform power and event posting; the modeled synchronous event posts to a real pthread and joins before the caller returns. It covers live/GOING success, twelve isolated remove failures, seven admission failures and a legacy compatibility case. Eight mutations target swallowed receipt errors, power-off after refusal, legacy replay, worker identity check, synchronous posting and missing/mismatched/error receipts.

Native event scheduling/completion, full platform target compilation, ABI/CRC/KCFI, real module loader, firmware, phone discovery/handshake/file transfer and stable recovery are not certified. Failed child universes retain resources until process exit, not a production reset. Production C and full target regressions are pending CI.
