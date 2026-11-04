# 0108 Protect owned host adapters from generic SSR reset

## Production change

Patch 0040 adds one bounded guard at the start of each `hdd_reset_all_adapters()` iterator body, before any per-link reset. An adapter still held by the private host registry is skipped after returning the iterator's current netdev reference. The iterator retains control of the already-held next adapter reference and advances normally. Ordinary STA/P2P/SAP and unregistered PAS adapters keep the original reset body.

`mishare_wonder_host_adapter_owned()` compares the exact non-NULL adapter pointer under the host registry lock. It does not inspect a device name, mode, MAC, HDD or adapter contents, adopt ownership, allocate, or clean up. Caller-owned, draining, handed-off and error-retained hosts remain protected until registry retirement. NULL queries must not match a host still being constructed before an adapter exists.

Host creation now publishes its successfully opened adapter under this same registry lock. PSOC serialization still protects the local create/reset/retire decision, but the global lookup must not race an unlocked pointer publication in another PSOC. The caller must hold its native iterator/netdev reference and serialize the parent transition across the reset decision. This lookup is an ownership observation, not a reference lease or SSR qualification.

## Validation

Implementation complete; production C and full Actions validation pending. 53 Python checks passed. The production-host fixture executes the entire patched native reset function, comparing its bounded reversal byte-for-byte with the pinned original function. The existing whole-HDD origin audit still reconstructs its prior source hash exactly.

The reset fixture has 62 controlled cases: 48 combinations of four private-owner states, first/middle/last position, SAP internal-restart selection and VDEV presence; 12 all-unowned combinations; one retained-error child; and one empty adapter list. It verifies current/next iterator reference balance and original generic queue/WMM/scan/stop boundaries, including unowned PAS with the same MAC as the private host. Five new mutation controls remove the NULL-query guard, ownership match, native skip, skipped iterator put or over-broaden skipping to all PAS adapters. All previous 32 mutation controls and 36 parent-identity refusals remain. Full WLAN object/module checks require the new ownership API symbol.

The iterator holds, one active link per adapter, queue/scan/WMM/TWT/TDLS/stop bodies, VDEV references, runtime retirement and locks are model boundaries in this fixture. Actual production lookup/host code and the complete native reset body execute with sanitizers. This does not certify real native iterator concurrency, MLO link coverage, reset timing or physical parent teardown.

## Remaining integration

This protects the early generic adapter-reset traversal. It does not insert automatic qualified SSR retirement later in the CDS window, propagate all upper teardown errors, schedule asynchronous retries, protect every generic remove/close path or retain HDD/native components automatically. Those remaining parent/entry/exit paths must be coordinated before radio backend activation. No default backend handoff or phone action is added. Apple discovery, handshake and two-way files remain pending.
