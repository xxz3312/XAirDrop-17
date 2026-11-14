# 0201 — candidate HAL and ordinary Wi-Fi lifecycle, then original restoration

## Evidence and upstream basis

0199 successfully loaded/unloaded the candidate WLAN/provider with HAL stopped. 0200 independently corroborated the exact journal, candidate firmware-ready event, original WLAN reload and restored associated/IP/Android-validated Wi-Fi. The candidate has not yet run with Android HAL enabled. The exact boot/manifest/all ten original-text hashes from 0200 qualify preservation of that completed transaction, never a generic failed-state reset.

Reviewed XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Both retain original CNSS2 and start HAL after loading the candidate stack. Extend the already qualified popsicle scan guard, one-shot transaction and exact identity gates around that lifecycle. Original CNSS2 stays loaded. Candidate native ELF bytes, CRC/vermagic, firmware and kernel parameters remain unchanged. No Apple/Wonder/native service, init_boot write or automatic boot trial.

AOSP WifiShellCommand at `5c18aa159c`, `service/java/com/android/server/wifi/WifiShellCommand.java`, supports status/help/start-scan/list-scan-results. Its start-scan handler calls startScan but returns zero without proving the asynchronous scan completed. ScanResultUtil lists cached results with age fields. Hence a submitted request or nonempty cache is not scan-completion proof. References: https://android.googlesource.com/platform/packages/modules/Wifi/+/5c18aa159c/service/java/com/android/server/wifi/WifiShellCommand.java and https://android.googlesource.com/platform/packages/modules/Wifi/+/refs/heads/main/framework/java/android/net/wifi/util/ScanResultUtil.java . Raw observation times, scan-result ages and framework status must be reviewed after the phone trial.

## Fixed installation identity and exact preservation

Stable ID `xairdrop17_cycle0195`, display XAirDrop-17, versionCode201. Installer and Action are read-only checks; boot is a no-op. The builder independently renders the original 0199 manifest and requires exact match before deriving schema7. `archive-0199` validates only the reviewed completed record (including stock backup bytes) and preserves its directory, inode and contents by same-filesystem no-clobber rename. Existing 0197/0195 archives, 0193 archive and 0194 stock backup remain required. Extra/hidden/recovery files, phase.new, unsafe paths/permissions, preparing state, live lock, changed hashes or occupied destinations block the operation.

New cycle requires that preserved record and an absent active path. A completed or failed 0201 record cannot match archive-0199 or be replayed. Archival itself never toggles Wi-Fi/HAL or executes loaders. Boot changes are allowed only with exact currently verified stock identity; historical state supplies preserved bytes/evidence, not current ownership.

## Explicit normal lifecycle

Require normally connected stock Wi-Fi with a completed supplicant state and an IP on the primary WifiInfo line. Verify read-only help and list-scan-results access before publishing a transaction or changing settings. All cmd/svc Binder calls are bounded with Android timeout and capture stdout/stderr through a pipe.

Save original toggles, disable scan-always/Wi-Fi, stop HAL and require ten stock stopped samples. Remove original WLAN and insert provider/candidate using unchanged exact identity/hash/holder/unloadable gates. Start candidate HAL, verify running, enable ordinary Wi-Fi and request one scan. Observe automatic association/IP for up to thirty two-second polling intervals (each Binder call is separately bounded); capture result ages and status. No manual Wi-Fi toggling, scanning or saved-network changes during the trial.

Then disable candidate Wi-Fi, verify framework quiet, stop HAL and require ten stopped-HAL observations with exact candidate/provider ownership before removal. Remove candidate/provider, reinsert the verified original backup, start original HAL and restore both original toggles. Original association restoration may occur shortly after the immediate baseline check; report status honestly.

Association/IP plus successful scan-request/list command return codes produce the explicit HAL/association-observed marker, with scan review still pending. This is not Apple readiness or new-scan-completion certification. A scan/query failure or association gap is an ordinary observation outcome: continue the normal identity-checked shutdown, restore stock, journal restored and return code3 with `STOCK_RESTORED_CANDIDATE_OBSERVATION_NOT_CONFIRMED_NO_REPLAY`. Do not emit candidate success, automatic extra framework cleanup or a needless reboot instruction for that outcome.

Ownership/identity/HAL inconsistency, signal, journal failure or native/framework effect failure blocks subsequent native commands. No forced unload, native retry or blind native rollback. Framework-only failure cleanup remains limited to exact original WLAN/CNSS2 present and provider absent. Otherwise preserve state and reboot to stock, then settings-only recovery; phase is not rewritten and loaders are never replayed.

## Validation and phone handoff

Focused actual-controller fixtures cover complete candidate start/association/stop/stock restoration, exact historical evidence refusal and preserved inode, capability failure before snapshot, command failure/association/primary-IP gaps with normal restoration, every new framework step and post-candidate native failure boundaries, busy modules, signal/late-HAL behavior and post-reboot settings-only recovery. Synthetic modules establish controller effect boundaries, not ABI/phone acceptance. Sh/mksh suites run concurrently in one CI, followed by actual immutable-ELF audit and deterministic package comparison; no native rebuild. Results are recorded separately after completion.

After qualification: cover-install via KernelSU, reboot as prompted, confirm version0.0.201, keep ordinary Wi-Fi connected and hotspot off. Execute check, archive-0199 and cycle once from Termux; do not touch Wi-Fi until terminal completion. Upload the new cycle log whether result0, result3 or failure. Keep all external backups and preserved transaction directories unchanged.

## Qualified package

CI [43573319942](https://github.com/xxz3312/XAirDrop-17/actions/runs/43573319942), source `6b6136b10c5657c182a46df8f18be70b36277f17`, passed 11 sh controller/policy cases, 10 mksh controller cases and 110 kernel-tool tests: total131, no skips. Both shell syntax groups and final immutable-ELF audit/package jobs passed. ZIP CRC, metadata, primary entry points and streamed candidate hashes were checked locally; both native files match the accepted original artifact bytes.

CI and local ZIP SHA256: `5dcf7e946020fad7b5aedfc0213055afe8a20c9700bbb297ca11d5e95f939ade`; 168,806,707 bytes. Stable module ID/versionCode201, no native rebuild, no automatic startup and no Apple service. Candidate HAL/association and scan freshness remain phone-pending. Success marker expressly leaves scan review pending; result3 means original restored but candidate observations were not fully confirmed.
