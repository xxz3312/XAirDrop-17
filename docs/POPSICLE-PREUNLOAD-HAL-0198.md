# 0198 — HAL restarted before original WLAN removal

0197's phone-returned log reports the reviewed old-record archive marker, seven successful stopped samples (0–6), then `GATE:hal-sample-7:hal:rc=1` with actual HAL running. Framework quiet still returned zero and the status showed Wi-Fi/scan disabled. There is no remove-stock intent or insmod/rmmod command. The last logged phase is done:hals-stop. Framework-only failure cleanup then reports success; both toggles and HAL are enabled/running and Wi-Fi is associated again. Association is not Internet validation. Raw SSID/BSSID/MAC/IP and the full upload stay private; only the receipt hash and redacted outcome are committed.

This is a successful safety abort and framework cleanup, not a passed diagnostic native round trip. It also disproves treating the previous bounded 0196 scan-off interval as a sufficient general guarantee. The current log does not identify who requested this restart. The connected starting state differs from the earlier disconnected 0196 probe, but that difference alone is not a demonstrated cause.

Rechecked upstream XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Keep their original-CNSS2 architecture and explicit ownership/stop checks. Neither reviewed path establishes an attribution or safe suppression for this observed popsicle restart; no blind extra stop, shorter wait or native retry is adopted.

## Read-only evidence export

`tools/device/popsicle-hal-evidence-0198.sh` does not source the installed module or execute service/settings/module control. It rejects an active trial lock, unsafe/symlink/private source paths and missing core transaction files. It copies only named text metadata/journal/kernel logs and installed version/manifest/checksum metadata to a fresh private temporary directory, verifies copied bytes, and records source checksums. Driver binaries and old backup/archive directories are excluded.

The script queries current module notes, properties and timed dumps of wifi/wifiscanner/wifip2p, plus filtered Wi-Fi/WLAN/servicemanager logcat. Dump stdout/stderr is streamed through a pipe before file output, preserving the previously required Binder descriptor boundary; actual query return codes are included in capture receipts, even if a query fails or a service is unavailable. It verifies original source checksums before and after tar export and cleans only its own temporary directory. It does not modify the installed package, failed phase, original logs or backup files. Current framework dumps are current-state evidence, not proof of past requests; retained kernel logs and any surviving logcat must be correlated with their timestamps.

The result is `/sdcard/Download/xairdrop-0198-evidence.tar.gz`. Keep Wi-Fi usable and leave the module/transaction unchanged. Healthy Wi-Fi after successful cleanup does not require the previous generic reboot/recover instruction. Do not repeat cycle or stop HAL again for this collection.

## Regression and validation

A focused fixture injects HAL running during status observation 7, executes the actual 0197 controller, and requires the labelled guard failure, zero native effects, original failed phase retained, automatic framework restoration and no replay. The collector tests verify unchanged sources, no binary/unrelated-log export, pipe-bound dump output, failed-query receipts and lock/missing/symlink rejection. The same tests run under sh and mksh. These simulations are not native/firmware acceptance.

Local four tests passed; four mksh cases require CI. No kernel tool rebuild, native compilation or module package is part of this observation checkpoint. Phone evidence export is pending.
