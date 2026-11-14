# 0199 — preserve the exact pre-unload abort before one fresh diagnostic

## Scope and upstream reference

Rechecked Leekin2/XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and Weverses/OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Reuse their retained-original-CNSS architecture and explicit stop/swap/restore sequence. This phone needs the already qualified scan-off interval and exact preserved-transaction eligibility; neither upstream supplies a safe generic way to discard this record. No candidate ELF, CRC, vermagic, firmware, init_boot, RF parameter or Apple service changes.

0198 returned ten stopped-HAL samples from a connected stock baseline. Retained framework history places SystemUI enable before 0197 cleanup. This supports operator interference during the old observation, but does not certify HAL stability after stock WLAN removal or any candidate load.

## Preservation contract

Use stable module ID `xairdrop17_cycle0195`, display name XAirDrop-17, versionCode199. Installer and Action check only; boot remains a no-op. The builder independently re-renders the original 0197 deployment manifest and requires its exact evidence hash before deriving schema6. Original 0195 archive, 0193 archive and 0194 backup remain required.

`archive-0197` accepts only the exact uploaded boot, manifest, phase `done:hals-stop`, baselines and three complete journal/kernel log hashes. All ten text files are pinned byte-for-byte; the stock backup is hashed independently. It rejects symlinks, unsafe ownership/permissions, phase.new, hidden/extra files, a live shared lock, preparing state and destination collisions. The directory is renamed without clobber on the same filesystem; inode and all original contents are revalidated. It can run in the same boot because this specific record proves no native command was reached; this exception does not apply to other phases or future failures.

The preserved name is `/data/adb/xairdrop17-cycle0195-transaction.previous.0197.7773c0b0-e133-47e4-b507-46a8bcd18751`. No previous archive is deleted or replayed. An already correct archive is verification-only. Fresh cycle requires an absent active path and exact preserved history, checked again before snapshot publication. Any new failed or completed transaction blocks another cycle and cannot pass the 0197 archival contract.

## Phone run after qualification

Install the same-ID 0199 package using KernelSU and activate the update as required by the manager. Do not remove old external backups/records. Run `check`, `archive-0197`, then `cycle` once. The trial temporarily turns Wi-Fi off; do not touch Wi-Fi, scanning, hotspot or Wi-Fi settings until the terminal prints the completion line and returns. It retains ten stopped-HAL samples plus all per-native-command gates. Candidate WLAN/provider are checked while HAL remains stopped, removed immediately, then stock WLAN/HAL/settings are restored. There is no automatic boot/native startup.

If exact original hardware is present on failure, framework-only cleanup may restore baseline without implying driver success. The final result distinguishes this from a failure needing reboot and post-reboot settings recovery. Neither branch retries native actions or rewrites the failed phase. A failed run must be reviewed before another trial. Association/interface restoration is not Internet verification.

## Validation

Local controller fixtures exercise exact-byte corruption for every file, residue/symlink/permission/lock/collision refusal, unchanged inode/archive contents, same-boot and post-reboot eligibility, no automatic archival, a complete successful fixed native sequence, all before/after-effect failures with prefix-only native effects, post-unload HAL restart refusal, settings-only recovery and replay blocking. CI also runs the historical controller, observations and kernel tool tests under sh/mksh where applicable, then audits the immutable raw ELF and reproduces the same package without a native rebuild. CI results and package hashes are recorded separately after completion; phone load/restore remains pending.

Local run: new controller suite 10 passed / 9 mksh cases skipped because mksh is absent locally; all 110 kernel-tool tests passed. ZIP CRC/version/schema and both raw candidate ELF byte hashes were checked independently. CI [43555492783](https://github.com/xxz3312/XAirDrop-17/actions/runs/43555492783), source `53713576d8553d9c5aa42ae0fcdd7c9270f6d397`, passed all 180 tests (43 historical diagnostics, 19 retrial, 8 observations and 110 kernel tools), with no skips. Both sh/mksh syntax checks and immutable raw-ELF packaging passed. CI ZIP SHA256 exactly matches the local package: `dc2dd8197827c5f2e3403e6f456bf4a3957af7e003225c67bfd0aaa93944ffe3` (168,804,779 bytes). No native rebuild. Phone round trip remains pending.

## Phone receipt: diagnostic round trip passed; association pending

The 14,017-byte phone log (SHA256 `f5699abfecc31a5efff3ffe3e64b36b4d1b57426990c351a846f2b431d51d04d`) reports check and exact 0197 preservation success, ten stopped-HAL samples, then all six native commands returning zero in the fixed order: remove stock WLAN, insert provider, insert candidate WLAN, remove candidate WLAN, remove provider, insert stock WLAN. Candidate-pair-live, restored, RESULT:0 and the final success marker are present. Controller identity/holder checks passed throughout and original CNSS2 was retained. This is the first accepted phone-reported 0199 diagnostic load/unload/stock-restore round trip; retained raw kernel logs have not been independently reviewed from this text-only receipt.

HAL is running and both original Wi-Fi/scan toggles are enabled at the end. Final status explicitly says Wi-Fi is not connected. The framework-baseline gate checks toggles/HAL/interface, not association, DHCP or Internet. Therefore automatic reconnect is not certified. The candidate was never run with HAL enabled, so candidate framework startup, scanning/connection and Apple discovery/transfer remain pending. Do not replay cycle, archive this new transaction using archive-0197, or remove backups. Next qualify retained kernel evidence and restored association before designing the candidate-HAL trial. Raw SSID/MAC/BSSID/IP stay out of the repository.
