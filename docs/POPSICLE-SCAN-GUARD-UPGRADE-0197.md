# 0197 — same-ID scan-aware diagnostic upgrade

## Scope and evidence

0195 stopped after original WLAN removal, before a logged provider insertion. Kernel logs show a system_server lazy AIDL request restarting the stopped HAL. 0196 then reported ten stopped-HAL samples with Wi-Fi and scan-always disabled while original WLAN remained loaded, followed by restoration of both original enabled toggles. These facts justify a bounded scan-aware deployment test, not a claim that the specific old gate or every lazy restart source is proved.

Before implementation, rechecked XAirDrop `585e850e3e026bf9eae90f654dafd01746bc5ec9` (`module/action.sh`) and OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`). Reuse retained original CNSS2, fixed module ordering, exclusive locking and observed Wi-Fi/HAL baselines. Add the phone-reviewed framework scan toggle to account for the observed popsicle lazy-start behavior. No platform init configuration, system_server stop, firmware override, forced unload, backend START, native Apple service or RF arguments are added.

## Fixed identity and preserved failure

The module ID remains `xairdrop17_cycle0195`; name becomes `XAirDrop-17`, version `0.0.197-scan-guard`, versionCode `197`. Installation replaces the current 0195 code directory; external 0194 backup, prior 0193 archive and old 0195 failed transaction remain intact. Old published packages and their pinned sources are unchanged.

Installer and manager Action run read-only checks. They accept only either the exact reviewed prior-boot 0195 failure at the active transaction path, or the same fully verified record already archived under `.previous.0195.<old-boot-id>`. They never clear it or replay its phase. Known legacy state is not a cycle admission: the separate explicit `archive-0195` action validates original live stock identity, private ownership, old boot, exact manifest/phase/baselines, the returned command/kernel-log hashes and original backup bytes, then preserves the entire directory using same-filesystem no-clobber rename with inode/post-validation checks. Conflicting, same-boot, interrupted, corrupt or unknown records block. A no-op or uncertain rename cannot authorize a cycle. Only the empty active path plus verified old archive allows a fresh transaction.

## Scan-aware cycle and labelled observations

A fresh transaction atomically captures current boot, deployment digest, original WLAN bytes, Wi-Fi flag, scan-always flag, running HAL inventory and interface baseline. Snapshot publication and preserved history are verified before effects. Every fixed effect has synced intent/returned/done markers. Readiness predicates have explicit `GATE:<label>:rc=<value>` records, and HAL/framework observations log the values used in their decisions. Nested gate labels retain their own positional argument rather than a shared mutable label.

The sequence is scan-off, Wi-Fi off, HAL stop, ten stable stock-HAL samples, original WLAN removal, provider insertion, diagnostic WLAN insertion, candidate WLAN removal, provider removal, original WLAN reinsertion, HAL start, original scan toggle restoration, original Wi-Fi restoration and baseline verification. All native operations again require Wi-Fi/scan off, HAL stopped, original CNSS2 identity, expected note/holder/refcount and fixed-file checks. A HAL restart after stock removal produces a named failed gate and no provider insertion. The candidate HAL is never started. Refcounts/holders can block deletion; there is no force flag or live-unload sysfs write.

## Failure and settings recovery

Any error stops native operations; a failed command may have changed state. The old failed phase is never rewritten as success. Framework-only cleanup is attempted once when transaction ownership and exact original CNSS2/WLAN, absent provider and expected holders can still be confirmed. It restores captured HAL/scan/Wi-Fi settings and observes their baseline, including after a catchable signal. Cleanup has no module loader operation. If hardware identity is absent/candidate/unknown, no settings restoration is attempted in that unsafe context; preserve state and reboot to original drivers.

`recover-settings` is a separate post-reboot operation. It requires exact current stock identity and a private failed 0197 transaction from a different boot bound to this installed manifest, validated toggles/HALs/backup plus the preserved reviewed 0195 archive. It restores framework settings only, writes a separate recovery log and leaves the failed phase/old logs unchanged. It never enables cycle replay. This covers scan-always remaining disabled if a failure occurs with original WLAN absent, or a reboot prevents same-boot trap cleanup. Unknown state/firmware/profile requires new inspection, not automatic migration.

The cooperative lock and ownership checks cannot exclude arbitrary other root software or all asynchronous framework behavior. Host fixtures and ELF audit do not establish native load/unload, firmware, private ABI/KCFI or Apple transfer success. A phone trial can still stop or reboot; reboot-first recovery remains part of the experimental handoff.

## Validation

Host tests execute the actual new controller/adapter with synthetic files and controlled framework/native command models. They cover same-ID replacement, read-only install check, explicit inode-preserving archive, corrupt/current-boot/conflicting old state, both enabled/disabled toggle baselines, all before/after-effect failures, no native replay, lazy HAL restart after removal, busy candidate, pre-native framework cleanup, journal failures, signal cleanup, post-reboot settings recovery without changing phase and integrity before source. The 0196 probe regression matrix and kernel audit tool tests run in the same CI. Actual unchanged raw ELF audit and package production are separate steps, with no driver recompilation or byte rewriting.

Local 43 diagnostic tests ran: 23 passed and 20 mksh cases skipped locally; all 110 kernel-tool tests passed. Real immutable-ELF reinspection and ZIP CRC passed. The 168,803,736-byte local ZIP SHA256 is `6c63f8381aca2fbe35ef8738b8080a79c44a2033ce05d7d10922342c612a25cc`; its shell files match current source. Full sh/mksh CI and phone 0197 archive/cycle/recovery acceptance are pending.

## Phone handoff after final CI

Install the ZIP over the existing 0195 module and reboot normally. Keep original backups/history. This does not add another module ID and does not run a cycle at boot. The existing 0194 entry is historical and is not automatically deleted.

One Termux command checks, explicitly preserves the reviewed old failure, and then starts the fresh scan-aware diagnostic trial:

```sh
su -c '/system/bin/sh /data/adb/modules/xairdrop17_cycle0195/cyclectl.sh check && /system/bin/sh /data/adb/modules/xairdrop17_cycle0195/cyclectl.sh archive-0195 && /system/bin/sh /data/adb/modules/xairdrop17_cycle0195/cyclectl.sh cycle' > /sdcard/Download/xairdrop-0197-cycle.txt 2>&1
```

Wi-Fi disconnects temporarily; keep the terminal open and return the log, including a blocked/failed result. No retry, transaction deletion or manual insmod/rmmod. If it fails with Wi-Fi unavailable, disable the module and reboot normally, then recover captured settings with:

```sh
su -c '/system/bin/sh /data/adb/modules/xairdrop17_cycle0195/cyclectl.sh recover-settings' > /sdcard/Download/xairdrop-0197-recovery.txt 2>&1
```

Return the recovery log too. Do not uninstall the module before recovering its saved settings. Apple discovery, handshake and bidirectional transfer remain later acceptance goals.
