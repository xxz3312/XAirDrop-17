# 0193 — actual kernel payload match and prior-boot record archival

## Evidence now confirmed

The uploaded raw boot matches the complete 0190 identity capture (`84e5aded3a181265b4a53132d3e4aafa29a8946112b166b8bc78f0724da390e8`). Its 42,170,880-byte kernel payload SHA is `f6cf6ea11ea55b989b551f97a7cc1f83368ba7d9367d6e1cbd86b1752e82c998`, exactly the previously reviewed kernel payload. This is byte identity, not a release-string inference. Whole-boot bytes differ; the exact cause outside the kernel payload has not been established. No init_boot was requested, read or written by these tools.

The corrected 0192 capture SHA is `481d26e93f602670a94b9aa27f5d56259ff17f60bccc434bc84d97c38b5b0ba2`. It confirms Android parent metadata `/data=1000:1000:771`, `/data/adb=0:0:700`. The retained transaction belongs to boot `722369de-3820-40a5-9e3d-88f2432f1176`, different from the current capture. Phase is active, no phase.new exists, phase and directory identity were stable, and the old manifest SHA and stock WLAN backup match. Thus it is a prior-boot record; it must not be replayed. Current uploaded module files/notes still identify stock CNSS2/WLAN.

`research/popsicle-stock-4.0.6-0193.json` records the new evidence and an **archive-only** profile. The old installation/deployment/loader profiles remain untouched. Neither the matching payload nor this profile certifies new firmware behavior, driver loading/unloading, runtime teardown, RF or Apple transfer.

## Upstream and command scope

Rechecked upstream main: OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`, `module/bin/control.sh` (boot-bound state retirement and lock); XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`, `module/action.sh` (exclusive mkdir lock and retained stock drivers). Reuse prior-boot preservation and exclusive operation. Use the existing local `/dev/xairdrop17-wlan-trial.lock` to serialize with the old local controller, rather than a separate unrelated lock. Do not copy upstream driver/service restore paths.

New `popsicle-archive-0193.sh` is standalone and accepts only check (default) or explicit archive. Check performs reads only. Archive creates the shared ephemeral lock, revalidates exact current 4.0.6.0/boot/release/stock-file/loaded-note identities, rejects candidate/legacy state, and authenticates the exact reviewed old boot/active phase/manifest/backup/HAL list/Wi-Fi baseline. It rejects incomplete journals, unsafe ownership/permissions/symlinks, existing destination and source filesystem mismatch. The boot, source inode and small record are rechecked under the cooperative lock.

The sole record mutation is `mv -T -n --` of the entire directory to:

`/data/adb/xairdrop17-stockcnss-transaction.previous.0193.722369de-3820-40a5-9e3d-88f2432f1176`

Android [Toybox generated options](https://android.googlesource.com/platform/external/toybox/+/refs/tags/android-13.0.0_r28/android/device/generated/newtoys.h) include mv's -T and -n; the actual command exit status and post-move source absence/destination inode are also checked. An unsupported/failing command cannot announce success. No existing target is intentionally overwritten or merged. All contents, including logs not parsed by the classifier, stay in the preserved directory. No rm, restore, replay, module, framework, Wi-Fi, partition write or automatic retry. If a move reports failure after side effects, stop and preserve both paths; do not automatically undo it. Exit cleanup removes only the matching lock inode owned by this invocation.

This is cooperative serialization with this project's old executor, not exclusion of arbitrary other root programs/OTA or cryptographic device attestation. It does not qualify any new driver-installation executor. The archive remains available for later investigation/recovery review.

## Validation

Local device host matrix: 118 tests, 79 passed, 39 mksh tests skipped locally. Kernel Python: 110 passed. The 20 new shell cases (ten per shell) perform real renames only inside temporary fixture directories; Android boot/devices/identities are explicit synthetic fixtures. They check byte/inode preservation, default no-write behavior, occupied destination, foreign lock preservation, all selected record failures, current boot/note/firmware and cross-filesystem rejection, symlinks/private permissions, before/after/no-op move failure, preservation of a replaced lock and no replay on a second invocation. Production pins are checked separately against the archive-only evidence file. [Actions 43450934023](https://github.com/xxz3312/XAirDrop-17/actions/runs/43450934023) passed at `f83f7c4152158a7d5542c3c835c97cc139229245`: all 118 device host cases (including all 39 mksh cases without skips) and 110 kernel Python tests passed. No native driver build.

## Manual operation after CI

Download the pinned standalone `popsicle-archive-0193.sh` into Download. To archive the reviewed historical record:

```sh
su -c '/system/bin/sh /sdcard/Download/popsicle-archive-0193.sh archive' > /sdcard/Download/xairdrop-0193-archive.txt 2>&1
```

For a read-only preview, omit archive or use check. Successful archive emits `ARCHIVED_RECORD_ONLY_NOT_FOR_INSTALL` and the preserved path. A blocked/uncertain result means preserve files and return the log; do not delete, overwrite or rerun blindly. No old module needs reinstalling. No reboot is required for this directory rename.

Phone archival has not yet been executed or observed. Installation still needs the new candidate deployment/recovery executor qualification and staged device acceptance; configured START/public backend initialization remain closed. No installation package is produced here.
