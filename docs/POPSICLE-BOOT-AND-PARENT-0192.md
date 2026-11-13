# 0192 — actual partial stock match, changed boot and Android parent-policy repair

## Received evidence

The complete uploaded 0190 capture SHA is `80df4e2b49e76c7b89ea345f5211aa0abe7169679ecf3a82151d98d8d47c30a3`. Both vendor paths' CNSS2 and WLAN file SHA values and both loaded GNU note SHA values match captured stock. The observed release string also matches. Exact module observations and rejection reasons are retained in `research/popsicle-phone-0192-observations.json` without copying the uploaded files.

Firmware reports OS4.0.6.0.XPBCNXM instead of 4.0.5.0. Active boot SHA is `84e5aded3a181265b4a53132d3e4aafa29a8946112b166b8bc78f0724da390e8`, whereas the old capture was `a0ca3dd5c43f48e5ee7eb6eb602cc8fa4e9c2967c9eb5312530c3d50838d4a93`. The stock transaction remains present. The uploaded 0191 transaction capture SHA is `85be06f1fb3dedd489102cc3d6d2f766c677de8fd170ea6613ffc3fd371679cf`; it stopped at parent checks with UNKNOWN presence and did not inspect the record. It does not identify the actual failing parent's ownership/mode. No module-uninstall or reboot completion is inferred from these reports.

## Upstream and parent correction

Before editing, upstream main commits remained OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/root-runtime.sh`) and XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` (`module/action.sh`). Keep explicit root/tool handling and original stock modules; neither grants this target a firmware or state-cleanup pass.

[AOSP rootdir/init.rc](https://github.com/aosp-mirror/platform_system_core/blob/main/rootdir/init.rc) explicitly chowns `/data` to system:system and chmods it 0771. The old collector incorrectly required root/private ownership for `/data` as well as `/data/adb`, so it rejects this normal Android ancestor. Host fixtures reproduce the legacy failure for 1000:1000:771; the actual phone parent metadata is still needed to confirm its specific cause.

The new standalone `popsicle-transaction-0192.sh` accepts this exact Android ancestor signature (also its zero-prefixed mode rendering), while preserving root/private checks for `/data/adb`, transaction directory and files, symlink rejection, bounded text reads and digest completeness. Root-owned non-writable ancestors remain supported. It prints both parents' numeric owner/group/mode even on refusal. It performs no cleanup, restore, archive or module/framework operation.

The strict classifier supports both stages and now returns an explicit blocked classification for UNKNOWN presence. In 0192 it independently validates parent signatures, so a forged complete marker or unsupported parent cannot turn UNKNOWN into absent or trusted state. All archive/replay/load/runtime flags remain false.

## Boot comparison boundary

`stock_cnss_boot_delta.py` checks an uploaded raw boot against the SHA in the complete phone identity capture before parsing a bounded Android boot v4 image. It compares the whole extracted kernel payload with authenticated old loader evidence. Matching the release string is never substituted for matching bytes. A changed boot can contain an unchanged kernel payload (metadata/other sections can differ); this is a possibility, not a conclusion about this phone until the image arrives.

Synthetic image tests cover whole-boot changes with identical kernel payload, changed kernel with unchanged version observations, hash substitution, unstable observations, short/bad header and out-of-bounds kernel/ramdisk. Even a payload match does not update the accepted target or authorize loading. The old exact `verify_stock_loader.py` and all stock profiles remain unchanged.

Local validation: 98 device host cases, 69 passed and 29 mksh cases skipped locally; 110 kernel Python tests passed. CI requires mksh and runs the full matrix. [Actions 43447227303](https://github.com/xxz3312/XAirDrop-17/actions/runs/43447227303) passed at `8534ff252454fbe5dd9e25b2ba175e595bff1e37`: all 98 device host cases (including all 29 mksh cases without skips) and 110 kernel Python tests passed. No native driver build.

## Next phone evidence

No need to repeat the complete 0190 capture unless the phone reboots, changes slot or updates again. Preserve the transaction. Download `popsicle-transaction-0192.sh` into Download and run:

```sh
su -c '/system/bin/sh /sdcard/Download/popsicle-transaction-0192.sh' > /sdcard/Download/xairdrop-0192-transaction.tsv
```

Export a read-only copy of the currently active **boot**, not init_boot:

```sh
su -c 'slot=$(/system/bin/getprop ro.boot.slot_suffix); case "$slot" in _a|_b) /system/bin/cat "/dev/block/by-name/boot$slot";; *) exit 1;; esac' > /sdcard/Download/xairdrop-0192-boot.img
```

Send the TSV and raw image. These commands read device state; only Termux redirection writes new files to Download. No partition is written. A mismatched/truncated export will be rejected against the existing identity capture. Host comparison after upload:

```sh
python3 tools/kernel/stock_cnss_boot_delta.py --boot xairdrop-0192-boot.img --identity xairdrop-0190-identity.tsv --output boot-delta-0192.json
```

The remaining installation blockers are current boot/kernel provenance, new firmware qualification, retained-state examination and an independently qualified deployment/recovery executor. No install package is produced here.
