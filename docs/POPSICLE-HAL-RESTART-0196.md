# 0196 — framework lazy HAL restart after original WLAN removal

## Observed evidence and inference

The uploaded `xairdrop-0195-failure-evidence.tar.gz` contains the original transaction baseline, journal and kernel-before/kernel-after captures. Its manifest binds to the 0195 installation manifest, and its final phase agrees with the earlier standalone log. Raw logs remain private; only hashes and relevant system event times are committed in `research/popsicle-hal-restart-0196.json`.

Kernel uptime timeline:

| Seconds | Observed event |
| --- | --- |
| 258.117437 | init processes ctl.stop for vendor.wifi_hal_legacy |
| 259.289062 | original WLAN reports hard unload |
| 259.394797 | WLAN reports Driver De-initialized |
| 260.237141 | system_server requests missing Wi-Fi AIDL service as a lazy service |
| 260.237611 | init starts vendor.wifi_hal_legacy |
| 260.240443 | init records HAL running |

No provider insmod command is in the controller log. The HAL restart strongly supports the common `cy_hals_stopped` precondition as the blocking gate, but 0195 did not label each predicate, so the precise gate cannot be retrospectively certified. Do not claim a new driver crash, kernel ABI rejection or successful native restore. The logged scan-always-available flag was enabled; its role in causing the restart is a hypothesis requiring a bounded stock-driver test.

## Source comparison

Rechecked XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Their stop/wait/restore structure remains relevant; neither reviewed control file suppresses this specific lazy-start race or establishes a popsicle stopped-HAL interval. Do not repeat a module swap with extra sleep or blindly stop a restarted HAL after the original WLAN is gone.

AOSP `WifiShellCommand.java` at `5c18aa159c` implements `set-scan-always-available enabled|disabled` through `WifiService.setScanAlwaysAvailable`, and prints the flag in status. This is a framework operation, not a raw Settings.Global write; modern Wi-Fi also has its own configuration store. Source: https://android.googlesource.com/platform/packages/modules/Wifi/+/5c18aa159c/service/java/com/android/server/wifi/WifiShellCommand.java . AOSP behavior does not certify Xiaomi implementation or prove a single cause for this incident.

## Independent stock-only probe

`tools/device/popsicle-hal-probe-0196.sh` is a standalone direct-paste script, not a new installed module. Keep 0195 disabled and the old transaction/backup unchanged. It requires the observed device/firmware, running original HAL, recognizable Wi-Fi/scan state and live module notes. It snapshots both toggles and CNSS2/WLAN notes before mutation. Unknown baseline aborts without changes.

An EXIT/INT/TERM/HUP restoration trap is installed before the first framework command. Framework output is captured through a pipe, including failures. The script disables background scanning and Wi-Fi through the Wi-Fi service, verifies those states, stops HAL once, and records ten one-second observations including repeated cmd status calls. It never executes insmod/rmmod, writes init service configuration, stops system_server, touches trial records or installs a module. It then starts the original HAL, restores both exact original toggles and verifies their returned states plus module notes. A command that fails after changing state still enters restoration. If restoration fails, the output says so; it does not report success.

The phone-returned passing probe demonstrates a bounded stopped-HAL interval with the original module present. It does not prove HAL remains stopped across module removal, solve all lazy-start sources, or authorize retrying 0195. Uncatchable termination/reboot can prevent trap cleanup; the log prints the baseline toggles for explicit recovery if needed. Do not incorporate scan changes into a driver-loading profile until the test results and that profile's error/restore handling are independently reviewed.

## Validation

Local eight framework-fixture tests passed; eight corresponding mksh cases require CI. Fixtures test all four initial toggle combinations, unexpected HAL restart, failures after framework commands and HAL stop, failed restoration, unknown baseline and missing stock notes. The matrix also checks a late restart during observation and actual SIGTERM cleanup. Forbidden native module/configuration operations are absent and blocked in the fixtures. CI [43546465034](https://github.com/xxz3312/XAirDrop-17/actions/runs/43546465034) at `130b8f6cf88d135ec12d32a54df34e887be76e45` passed all 16 tests in sh/mksh without skips and both syntax checks. The script SHA256 is `ceaffb902eae598fdccf541f3fb46aecd7a27eadd259cce1bfca4c6f8bcd72f1`. No native driver compilation or module package rebuild occurred. Phone probe now reports passing as described below.

## Phone receipt — 2026-11-14

The uploaded `xairdrop-0196-hal.txt` has SHA256 `8ea503274a4e014cc56e6f39e015182c54ef1506908b30bb9cac54dd63f4b8a7`. Initial baseline was Wi-Fi enabled, scan-always enabled and HAL running. Both framework disable commands and HAL stop returned zero. Ten ordered observations (0–9) report HAL stopped, Wi-Fi disabled and scan disabled; the stock-only stability marker follows. HAL start and both original toggle-restoration commands returned zero. After asynchronous transition, status again reports both toggles enabled and the controller emits `HAL_PROBE_BASELINE_RESTORED`.

The status reports not connected both before and after, so this is toggle restoration, not Wi-Fi association/reconnection acceptance. Live stock module notes and final running HAL are assertions checked by the known controller before the restoration marker, not independent raw note recaptures in this upload. Machine evidence: `research/popsicle-hal-probe0196-phone-receipt.json`.

This supports scan-aware framework quiescence as the next deployment change. It does not establish a unique cause or guarantee a quiescent interval after stock WLAN removal. The future fixed-ID upgrade must preserve old failed state, bind fresh baseline settings and journal each readiness predicate, with independently reviewed failure/restore behavior. No old cycle retry or new loading command is issued by this receipt.
