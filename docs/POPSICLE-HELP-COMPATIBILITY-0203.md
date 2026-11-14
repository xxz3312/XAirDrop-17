# 0203 — validate help semantics; preserve pre-effect diagnostics

## Observed phone blocker

0202 receipt SHA256 `e32db54b794399d5592ff76eabb89ce1aab9b1ab1fe31889a6a48f2c20ac86a9` verifies the exact delivered201 bundle. Stock CNSS2/WLAN/provider-absence/holder/firmware/backup/history checks pass. No active transaction or preparing directory exists at capture. Current primary Wi-Fi is associated with an IP and Android VALIDATED; direct and timeout-bound status both return zero, timeout exists, HAL is running. The only observed failing predicate is capabilities: help returns255 with the normal header and explicit list-scan-results/start-scan command lines. The old predicate exits before trying the independent list query. This reproduces a pre-effect rejection, not a candidate HAL or native-load test result.

The framework BasicShellCommandHandler default-command implementation invokes onHelp for help/-h and returns -1. Shell-visible255 with valid help is therefore consistent with this default path. Source reviewed: https://android.googlesource.com/platform/frameworks/libs/modules-utils/+/refs/heads/main/java/com/android/modules/utils/BasicShellCommandHandler.java (blob32e6f792ad886aa348d4902c5fd402b3580d0007). Do not treat all255 responses as successful: errors and unknown commands may share that status. The phone receipt and exact command/body semantics qualify this narrow fix.

Rechecked XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Retained original-CNSS2 architecture and per-step ownership/native boundaries are unchanged. Neither path requires general relaxation of command failures. All native ELF bytes/parameters, CRC/vermagic, firmware and boot behavior remain unchanged.

## Narrow compatibility and diagnostics changes

Stable ID `xairdrop17_cycle0195`, name XAirDrop-17, versionCode203. Reuse the qualified candidate HAL/ordinary Wi-Fi lifecycle and exact completed199 archive requirement. There is no201 active-state migration or deletion. Any unexpected active/preparing state still blocks installation/cycle and is preserved. Existing archive-0199 remains verification-only when the exact directory already exists.

Help accepts only status0 or255, with the expected first header and exact standalone required command lines. Exception/security/permission/unknown-command text, incomplete help and other exit statuses remain failures. A real read-only list-scan-results query must independently return0 before any snapshot/control. Setters, scan requests, ordinary queries and loaders receive no255 exception. Cached results and scan request return codes still do not certify a new scan.

Before SC_LOG exists, sc_log writes to the caller's redirected stderr; after publication it retains private journal behavior. Preflight and snapshot failures are labelled, including stock/history/residue/framework/connection/capability gates. The dispatcher tracks effect-request intent only immediately before an adapter effect. If none was requested, it preserves state, skips framework recovery and reports `PRE_EFFECT_ABORT_PRESERVE_STATE_NO_WIFI_OR_DRIVER_CONTROL_THIS_RUN`. It makes no claim that unrelated prior hardware state is healthy. Snapshot/journal residue still blocks replay; a log/publish failure never authorizes deletion.

Once effects have been requested, existing conservative identity-gated cleanup/reboot messaging remains. Ordinary observation gaps after a complete stock restoration retain result3. Candidate HAL faults, busy modules, signals and native errors still block further loaders; no forced unload, blind native rollback or automatic retry. Primary connected/IP parsing, normal shutdown and ten candidate-HAL-stopped samples remain unchanged. No Apple service.

## Validation and phone handoff

Focused local tests exercise valid-help255 with a complete real-controller lifecycle, bad/truncated/exception help and rejected error statuses, independent list-query errors, snapshot residue and published-journal failure before effects. CI reuses the complete201 lifecycle/failure/signal/recovery fixtures with203 adapters under sh/mksh, plus both valid-help statuses and all new rejection/message cases, then audits immutable native files and reproduces the ZIP. Record actual counts and package hash after completion; no native rebuild.

After CI acceptance, cover-install203 using KernelSU and reboot as prompted. Start with Wi-Fi normally connected and hotspot off. Execute check, archive-0199 (verification only if already preserved), then cycle once; do not touch Wi-Fi until terminal completion. Upload the new log regardless of exit code. Keep historical logs/archives/backups. All candidate HAL/connection/scan-freshness and Apple outcomes remain phone-pending.

## CI acceptance

CI [43581297930](https://github.com/xxz3312/XAirDrop-17/actions/runs/43581297930), source `fb01a8a07a1259ef06f6ca2208235311cff9ccf4`, passed 15 sh controller/policy tests, 14 mksh controller tests and 110 kernel-tool tests: total139, no skips. Both syntax groups and final immutable-ELF audit/package job passed. Local ZIP CRC/version/help-adapter checks passed, and streamed native byte hashes equal the original accepted modules. No native rebuild.

CI/local ZIP SHA256: `50dcc801f111482003e1f3f52d3dae22d6477167b711ab2f134e7a2d8d86d982`, 168,807,334 bytes. The phone's existing199 archive was verified by0202; the next handoff can use check then cycle directly. Cycle still revalidates exact archived history and absence of active/preparing paths; omitting the idempotent archive command does not bypass any gate. Do not delete or replay any new record if this attempt fails. Candidate HAL/connection and scan freshness remain phone-pending.

## Phone receipt: candidate HAL/ordinary connection round trip passed

The 65,576-byte receipt SHA256 is `b3c43499c4c660d7c6305621f90dab18394b74cee3cc4091c6434a81cd400205`. Help255 validates, independent list query returns0 and preflight/snapshot pass. Both original and candidate stopped-HAL windows contain samples0–9. All19 reported commands return0, including the six native commands in their intended order, explicit candidate HAL start/stop, candidate Wi-Fi on/off and original setting restoration. No labelled gate blocks; phase restored, RESULT0 and scan-review-pending success marker are present.

Under candidate ownership, HAL PID27137 runs, primary supplicant reaches COMPLETED with an assigned IP on5240MHz and negotiated Tx/Rx2401Mbps. Packet counters show14 successful transmit and9 receive packets; this is not a throughput test. The candidate NetworkCapabilities has INTERNET but not VALIDATED at this immediate observation, so do not certify Internet validation. The HAL was stopped and ten ownership/quiet/stopped samples passed before normal removal and stock restoration. Raw kernel evidence for this new trial has not yet been independently reviewed.

The post-request list contains12 rows on5220/5240/5785/5805MHz, ages1.081–1.243seconds. Observation starts at uptime136.14 and ends136.48 (0.34seconds). Since every age exceeds even this whole interval, the returned observations predate the explicit start-scan request; they are compatible with automatic connection scanning, not proof that this request completed. Keep explicit scan completion uncertified. No2.4GHz result or full-band scan acceptance is established by this post-request list.

At final stock capture Wi-Fi/scan are enabled and HAL is running, but Wi-Fi is not yet associated. Do not transfer the user's earlier0199 automatic-reconnect confirmation to this new203 run. Confirm later original reconnect and preserve the current transaction. Next inspect retained kernel/scanner evidence and qualify an explicit scan-completion wait before considering Wonder/AWDL activation; no replay, forced unload or Apple-ready claim. Redacted machine receipt: `research/popsicle-cycle0203-phone-receipt.json`.
