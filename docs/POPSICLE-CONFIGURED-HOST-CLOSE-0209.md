# 0209 — host close calls configured STOP before resource teardown

0208 target compilation, strict module linking, selected layouts and offline module records succeeded in job132477308922 of Actions43604892297. The obsolete initial fixture assertion kept that overall run failed; focused source cfefff822ef8c42cf290d9c1dd595b16fd11ae02 / Actions43605506637 passed the configured512-cycle composite and all stop regressions with identical production source. That is software acceptance, not new ELF installation or phone/RF qualification.

## Reference and scope

Rechecked unchanged XAirDrop585e850e3e026bf9eae90f654dafd01746bc5ec9 module/action.sh and OPAirDrop28a3a1dbc9f515fa5705417a3973616e5ae6180d module/bin/control.sh plus kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch. Follow native STOP/completion before interface destruction; retain original CNSS2 and local managed parent/ownership checks instead of copying upstream passthru flags or synchronous shutdown.

## Integration

Host VDEV destroy and full host destroy now mark the session closing, call runtime_configured_drain, and only then call the existing runtime_destroy. Any pending/error result returns with the exact host/runtime/adapter/sync/parent ownership retained. No unregister, adapter close or unpin is reached until the prefix and all normal runtime callbacks/final references finish. Parent identity and running/open/session checks still precede the close flag and native control. Closing remains monotonic between polls.

The prefix authenticates non-null runtime tokens before dereference. NULL/pristine unconfigured records add no radio operation; malformed cold records refuse cleanup. Configured attempts route through the existing208 STOP/DOWN path. A valid stopped receipt needs no new native operation, even while final VDEV free is pending; all checks on that branch are scalar, and runtime_destroy still checks PE/peer/DELETE/DP and final-free evidence. Zero from the prefix does not mean resources were released. No registry lock is held across STOP, no owner slot is cleared early and no state/receipt/phase is reset.

Public Wonder initialization and active configured SSR/remove recovery stay closed. The caller still retains/serializes the complete native parent and firmware lifetime. A fresh per-call scope/device ref alone is not that asynchronous lease. No new module ID, installation package, boot action, driver CRC rewrite or phone command.

## Verification and CI policy

Local110 Python tooling regressions, Python syntax and diff checks pass. New composite executes the exact production host VDEV-close body (only model type/primitive names are mapped by preprocessing) through actual208 runtime/radio/native SM and ordinary cleanup. Matrix512 covers two bands, four retry pairs, early/delayed callbacks and32 cleanup variants. Six parent/adapter/cold-record/recovery refusals and six cleanup failures retain ownership. Three native mutations remove the host prefix, parent check or cold-record guard. Full host model adds both close entries with pending/hard/shutdown outcomes and two prefix-omission mutations. Existing configured runtime and raw factory/native lifecycle are also regressed.

Host object, RTNL/parent primitives and adapter flags remain explicit models in the new native composite; full adapter/sync/parent release has separate existing/model coverage, not one configured end-to-end native factory proof. Firmware delivery/WMI execution, primitive references/locks/unmap and physical timing remain unqualified. No AWDL receive/send or Apple claim follows.

The dedicated branch workflow first runs these native checks and host regressions; only success starts one complete target build. This avoids building a full driver for a failed test harness. Per user preference return the CI link immediately, leave CI running and inspect it only when asked to continue. Main stays at accepted208 until209 validation is reviewed.

## Initial CI failure and fixture-only correction

Source cc5d6f8ecd8a32042397c359f704f4894591b6f5 / Actions43612381222 passed110 Python regressions but failed compiling the new native composite: its model declared link_flags as a scalar although the extracted production host body passes it as a bitmap pointer to test_bit. Correct the model to a one-element unsigned-long array and set its first word for the session-open guard. No production source or guard is changed. The native matrix and downstream regressions have not passed yet; the complete target job was skipped. Re-run the dedicated branch workflow with unchanged production bytes, and keep all native/target checks pending until the next review.
