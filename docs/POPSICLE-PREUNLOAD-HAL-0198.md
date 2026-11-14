# 0198 — HAL running before original WLAN removal; manual action reported

## Correction: manual Wi-Fi action, timing unresolved

After the initial interpretation, the user clarified that Wi-Fi was manually enabled, scanned and connected after starting the command. The timing relative to sample 7, cleanup and command completion is not yet known. Manual enablement while the test was still running can request HAL startup; this is a plausible external cause, not evidence of a spontaneous restart. If it occurred after command completion, the earlier HAL event requires separate attribution. The captured cleanup commands/marker and final connected state remain observations, but connection/restoration cannot be attributed to the script alone. Do not use this run to conclude scan-off is insufficient or shorten/disable guards; clarify operator timing before further tests.

0197's phone-returned log reports the reviewed old-record archive marker, seven successful stopped samples (0–6), then `GATE:hal-sample-7:hal:rc=1` with actual HAL running. Framework quiet still returned zero and the status showed Wi-Fi/scan disabled. There is no remove-stock intent or insmod/rmmod command. The last logged phase is done:hals-stop. Framework-only failure cleanup then reports success; both toggles and HAL are enabled/running and Wi-Fi is associated again. Association is not Internet validation. Raw SSID/BSSID/MAC/IP and the full upload stay private; only the receipt hash and redacted outcome are committed.

This is a pre-native safety abort with cleanup commands and a restored final state, not a passed native round trip or independently attributable automatic recovery. The operator clarification prevents this run from determining scan-guard sufficiency. The connected starting state differs from 0196, but neither that difference nor manual operation timing is yet sufficient for a unique causal claim.

Rechecked upstream XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Keep their original-CNSS2 architecture and explicit ownership/stop checks. Neither reviewed path establishes an attribution or safe suppression for this observed popsicle restart; no blind extra stop, shorter wait or native retry is adopted.

## Read-only evidence export

`tools/device/popsicle-hal-evidence-0198.sh` does not source the installed module or execute service/settings/module control. It rejects an active trial lock, unsafe/symlink/private source paths and missing core transaction files. It copies only named text metadata/journal/kernel logs and installed version/manifest/checksum metadata to a fresh private temporary directory, verifies copied bytes, and records source checksums. Driver binaries and old backup/archive directories are excluded.

The script queries current module notes, properties and timed dumps of wifi/wifiscanner/wifip2p, plus filtered Wi-Fi/WLAN/servicemanager logcat. Dump stdout/stderr is streamed through a pipe before file output, preserving the previously required Binder descriptor boundary; actual query return codes are included in capture receipts, even if a query fails or a service is unavailable. It verifies original source checksums before and after tar export and cleans only its own temporary directory. It does not modify the installed package, failed phase, original logs or backup files. Current framework dumps are current-state evidence, not proof of past requests; retained kernel logs and any surviving logcat must be correlated with their timestamps.

The result is `/sdcard/Download/xairdrop-0198-evidence.tar.gz`. Keep Wi-Fi usable and leave the module/transaction unchanged. Healthy current Wi-Fi does not require the previous generic reboot/recover instruction. Do not repeat cycle or stop HAL again for this collection.

## Regression and validation

A focused fixture injects HAL running during status observation 7, executes the actual 0197 controller, and requires the labelled guard failure, zero native effects, original failed phase retained, automatic framework restoration and no replay. The collector tests verify unchanged sources, no binary/unrelated-log export, pipe-bound dump output, failed-query receipts and lock/missing/symlink rejection. The same tests run under sh and mksh. These simulations are not native/firmware acceptance.

Local four tests passed, with four mksh cases skipped locally. CI [43552353408](https://github.com/xxz3312/XAirDrop-17/actions/runs/43552353408) passed all eight sh/mksh tests and both syntax checks. Collector SHA256 is `4464c63e2f32c9ae64eafea05afafa7431271437574f706ab7962556a95ec4d1`. This qualifies collector isolation and guard behavior under external HAL state changes, not the cause of the phone event. No native build/package was produced. Clarification of manual-operation timing is pending before further phone instructions.
