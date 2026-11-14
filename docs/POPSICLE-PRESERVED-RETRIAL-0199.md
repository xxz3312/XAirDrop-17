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
