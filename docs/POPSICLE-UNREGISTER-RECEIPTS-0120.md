# 0120 IPCI unregister receipts and checked teardown

Native remove is void: ICNSS unregister returning does not prove private cleanup succeeded. Patch 0051 records remove begin/end in an external provider scope. Checked IPCI, PLD and HDD functions propagate failure; main unload honors it before global component deinitialization. PLD unregisters IPCI first, retaining other buses and ops/state on refusal. Public void wrappers remain compatible; callers ignoring results remain outside certification.

Live scopes acquire a WLAN module reference, release it only after successful provider-side registration removal, and rely on the native caller's execution contract through return. GOING scopes validate the mode and borrow module-exit's existing execution lifetime without a new get. ICNSS must synchronously drain remove callbacks before unregister returns. Neither assumption is real-kernel tested here.

Transition failure, private cleanup refusal and missing context are recorded. Outstanding receipts return EINPROGRESS; mismatched completion and overlapping remove latch errors. Legacy unregister cannot clear a scope. Errors retain live module references and registration with no production reset API. Fixture failure children retain them until process exit, which is not recovery. Module-exit returning early cannot veto actual loader removal; borrowed-exit failure remains unresolved. Physical remove outside native unregister retains its prior contract.

The v2 descriptor layout is unchanged; four additive receipt/scope exports bring the required execution exports to eleven. Matched provider/WLAN builds remain required.

Local 53 Python tests, fixture assembly, restoration and patch checks pass. Pending Actions validation executes provider C, full native remove/checked functions and the extracted late unload guard with modeled synchronization, module API, ICNSS and vendor callbacks. New scenarios cover success, borrowed mode, failures, no replay, pending/mismatched/overlapping receipts. Six mutation controls cover swallowed cleanup error, premature completion, leaked live reference, PLD ignored refusal and late unload bypass; inherited host/runtime and concurrent SSR/idle regressions remain required.

No real ICNSS drain, failed-init teardown, module loader, firmware, physical disappearance or forced-unload certification. No phone operation, Apple discovery, handshake or transfer is enabled.

ICNSS unregister errno is recorded before scope completion; an event-post failure retains registration and the live reference without attempting a replay.
