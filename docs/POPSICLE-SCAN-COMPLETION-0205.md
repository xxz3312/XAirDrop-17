# 0205 — one request, correlated completion, then ordinary restoration

## Phone evidence and upstream reference

203 established candidate HAL/association/IP. 0204 corroborates candidate and restored-stock Android network validation, firmware/loader chronology and the original transaction. It also shows that the explicit shell scan listener9f0b06f was pending when the controller disabled Wi-Fi; scanner disable was followed by that same listener's failure. The12 cache rows were from an earlier automatic connection scan. Do not infer full-band driver inability or explicit scan success from203.

Rechecked XAirDrop585e850e3e026bf9eae90f654dafd01746bc5ec9 (`module/action.sh`) and OPAirDrop28a3a1dbc9f515fa5705417a3973616e5ae6180d (`module/bin/control.sh`), unchanged. Retain original CNSS2, manual lifecycle ownership, ordinary shutdown and all per-loader guards. No forced unload, candidate ELF/CRC/vermagic/parameter change, firmware replacement, init_boot write, boot trial or Apple/Wonder service.

Checked AOSP WifiScanningServiceImpl request/result semantics: https://android.googlesource.com/platform/packages/modules/Wifi/+/refs/heads/master/service/java/com/android/server/wifi/scanner/WifiScanningServiceImpl.java . Active-request results and passive scan listeners have distinct log events; request acknowledgment alone is not completion. Runtime matching uses the exact format returned by this phone's qualified0204 dump, not an assumption that all vendor builds share it.

## Exact state preservation

Stable module ID `xairdrop17_cycle0195`, display XAirDrop-17, versionCode205. The builder independently renders203 and requires the exact reviewed203 manifest before deriving schema9. Installer/Action remain read-only checks. `archive-0203` accepts only the ten byte-pinned text files, exact restored phase/boot/manifest and verified original WLAN backup from the reviewed203 roundtrip. It renames the entire directory without clobber on the same filesystem, checks inode/contents again, and retains199/197/195/193 history and194 backup. It does not claim203's explicit scan passed.

A fresh cycle requires that exact archive and an absent active/preparing path, rechecked before publication. Any new205 record blocks replay, whether failed, restored with observation gap, or successful. Never delete data to bypass the gate. Post-reboot recovery restores settings only and also accepts the new candidate-scan-wait phase without replay or phase rewrite.

## Observation lifecycle

Keep the qualified203 start and stop sequence. Require read-only scanner dump access/complete local-log markers before any transaction/effect. After candidate HAL/Wi-Fi start, first observe primary association/IP. If association is absent, report an ordinary gap and restore stock; do not repeatedly request scans.

With association present, capture a private exclusive scanner.before.log. Record all existing root-shell listener hashes, including callbacks whose request lines might already have aged out. Issue start-scan exactly once. Poll bounded pipe-captured scanner dumps while continuously rechecking transaction ownership, candidate/provider notes and HAL state. Every snapshot is a new private scanner.sample-N.log with query rc and SHA256 in the command journal. No old records are overwritten.

Identify exactly one new addSingleScanRequest with package com.android.shell, WorkSource0 com.android.shell and the observed internal listener type. Exclude every baseline-seen hash, reject multiple new root requests, and match only that listener's active singleScanResults/singleScanFailed event. Passive-listener callbacks, background scans, cached lists, malformed counts, conflicting success/failure and unrelated IDs cannot establish success. This correlation assumes no concurrent external root-shell scan; users must not issue other Wi-Fi commands during the trial. Ambiguity is an observation gap, not a reason to guess a request.

A successful callback with positive result count, a subsequent successful list query and still-associated primary IP are required for result0. Empty successful callbacks are recorded but return3 for incomplete test qualification. Explicit failure, query/schema gaps, ambiguity or timeout return3 after the normal identity-checked candidate shutdown/removal and stock restoration. No scan is retried. The deadline is45 boottime seconds with at most24 polls; each dump is additionally bounded (10s server/15s process), so an in-flight query may finish beyond the deadline. Fixed sleeps only pace polling, never establish completion.

Ownership/HAL/signal/journal/native-control failures still stop subsequent native operations; framework-only cleanup requires exact original hardware identity. Do not unload a candidate with HAL running, bypass busy checks or add blind rollback. The ten stock and ten candidate stopped-HAL windows remain. No Internet throughput, long-term stability, every-band support or Apple readiness claim follows from one scan callback.

## Validation and phone handoff

Focused sh/mksh tests use actual controller/adapter scripts with synthetic hardware. They cover delayed completion despite existing association/cache, private request snapshots, exact203 evidence preservation, failed/empty/stale/wrong/ambiguous/conflicting/query-truncated outcomes with normal restoration, preflight refusal without effects, HAL loss in the new wait phase, signal handling and post-wait framework/native faults. Pure parser cases cover passive/unrelated callbacks, baseline callback-only IDs and malformed counts. Fixtures are not phone/ABI acceptance.

One CI runs the shell groups concurrently plus kernel-tool tests, followed by immutable real-ELF audit and deterministic ZIP reproduction. No native rebuild. After qualification: cover-install205 in KernelSU and reboot as prompted, keep normal Wi-Fi connected and hotspot off, execute check, archive-0203 and cycle once from Termux. Do not touch Wi-Fi/scanning until terminal completion; send the cycle log for every result. Existing kernel/scanner records and archives remain intact.
