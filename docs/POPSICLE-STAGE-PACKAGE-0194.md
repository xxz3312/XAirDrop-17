# 0194 — independent current candidate check/backup installation package

## Scope and evidence

0193's uploaded receipt reports the old active record successfully preserved under the exact prior-boot archive path. Current uploaded boot has the identical reviewed kernel payload; captured stock CNSS2/WLAN files and loaded notes match. Use that evidence only to stage a new candidate and verify an independent stock backup. Keep old 0135/0138 packages and all old installation/loader profiles unchanged.

Before implementation, upstream heads remained OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`) and XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` (`module/action.sh`). Reuse stock CNSS2 retention, explicit operation and exclusive locking, and reference their restore/failure handling. The known 0132 reboot and absence of current-candidate load acceptance require a narrower first installation: no driver/service actions at all. Do not copy automatic/live stack restoration. Local 0138 IO observations and integrity writer are reused under a separate module identity; the old bundle/evidence/controller are not retargeted.

## Implemented package

`tools/kernel/stock_cnss_stage0194.py` independently reaudits the exact complete 0187 diagnostic and validation ZIPs, requires the entire result equal the committed 0188 audit, rechecks the actual two selected raw ELF identities/notes/version coverage/CNSS2/private CRCs and copies only WLAN/provider byte-for-byte. No stripping, vermagic/CRC edits or native compilation. New package module ID is `xairdrop17_stage0194`, firmware exact 4.0.6.0, boot exact `84e5aded…390e8` and the observed release. Source commit remains `a4b9404257efe395cf3cf865a806bff5daba6f4b`.

The new controller accepts only check/status/backup. It rejects apply/archive/restore before reading helpers or making changes; the IO helper contains no driver effect implementation. Action runs check, boot service exits immediately, skip_mount is present, and there is no system overlay or init_boot operation. Loading, configured START, public backend initialization, RF and Apple transfer remain closed/unqualified. This is installable candidate-file staging, not a functional AirDrop module.

Runtime entry checks root-private path/file ownership and verifies retained checksums **before sourcing helper code**. It then rechecks package integrity, exact current stock identity, every present vendor copy (a valid copy cannot hide a conflicting one), absent legacy/candidate state and the preserved old archive. Separate installation/runtime checksum scopes permit KernelSU's deletion of customize.sh without weakening retained-file checks. Installer supports only KernelSU and runs the read-only check after permissions/integrity validation, including in modules_update. It performs no driver or Wi-Fi change.

Backup is allowed only from the installed modules path and takes the same exclusive lock as the old executor. It observes Wi-Fi and running HALs using the previously corrected command capture and large-property streaming logic, copies stock WLAN into a fresh preparing directory, records boot ID/manifest hash/baselines and backup-only phase, verifies everything, rechecks current identity/baselines, and publishes by same-filesystem no-clobber directory rename. Failures preserve incomplete/uncertain files and stop. Existing fully valid backup is verified without rewriting; any preparing residue blocks further attempts. Preserved 0193 archive is never changed. No automatic rollback, retry, Wi-Fi toggle or module operation.

This tests preservation and baseline observation for the future executor; it does not qualify native unload/load/recovery. Cooperative lock semantics do not exclude arbitrary other root programs or OTA. The future load-enabled executor still needs independent qualification and staged phone acceptance.

## Validation

Actual local artifact reinspection/staging succeeded with the two expected raw modules and all load/runtime/autostart flags false. This initial intermediate is not the final downloadable CI build. Local 140 device-host tests: 91 passed, 49 mksh cases skipped because the local shell is absent; kernel Python 110 passed. The new matrix exercises actual helper/controller filesystem behavior with explicit synthetic ELF/container fixtures, root/identity/old-state/lock failures, read-only check, unconditional apply rejection, backup publication/idempotence, both Wi-Fi baselines, HAL/transport errors, interrupted/uncertain preservation, corruption before sourcing and KSU's transient-installer deletion. Synthetic fixture bytes never establish ELF/ABI acceptance; actual artifact acceptance occurs separately during package production. Final CI [43465342560](https://github.com/xxz3312/XAirDrop-17/actions/runs/43465342560) passed all 140 device tests (including mksh) and 110 kernel tests without skips. Real-ELF reinspection and packaging passed. The resulting 168,798,643-byte ZIP has SHA256 `b218f6f44ccaea92cfee7e43580443cd3ff6a85e7d68632289dfb02ffbe90311`, identical to local production. Actions artifact 14057762272 contains the ZIP and build receipt. See `docs/research/popsicle-stage0194-ci.json`. The returned 2026-11-14 phone log now reports check and backup success; see the phone receipt below.

## Phone acceptance after CI

Install the new ZIP using KernelSU and reboot to activate the module directory. The installer and manager Action check only, and boot does not load the candidates. Then collect installed check and backup:

```sh
su -c '/system/bin/sh /data/adb/modules/xairdrop17_stage0194/stagectl.sh check && /system/bin/sh /data/adb/modules/xairdrop17_stage0194/stagectl.sh backup' > /sdcard/Download/xairdrop-0194-stage.txt 2>&1
```

Return this log, including a blocked or failed result. No manually downloaded sh file or ADB is required. Candidate staging check/backup is now phone-reported successful; driver loading/recovery remains unqualified. Do not use old apply actions or mutate the package to enable loading. New driver activation is absent from this package.

## Phone receipt — 2026-11-14

The uploaded `xairdrop-0194-stage.txt` (1,206 bytes; SHA256 `04b2d29ae96c59dd8ad2db0be631d668b50a3b8bd47f277fc0a666974787f077`) contains 52 checksum OK lines, exact firmware `OS4.0.6.0.XPBCNXM`, `apply_enabled=false`, and both expected check/backup success markers. The backup marker is emitted only after the controller verifies and publishes the independent stock backup and rechecks the preserved baseline. This is phone-returned script evidence, not an independent download of backup bytes, proof of native recovery, or Apple transfer acceptance. See `docs/research/popsicle-stage0194-phone-receipt.json`.

Next: independently qualify the current-candidate load/recovery executor before issuing a controlled driver trial. Keep 0194 check/backup-only and preserve the new backup and prior 0193 archive.
