# 0195 — explicit diagnostic WLAN/provider load and stock restore

## Evidence and upstream

0194's exact uploaded log reports installed check and independent stock backup success on OS4.0.6.0.XPBCNXM. It does not certify a driver load. The new package is an explicit experimental diagnostic cycle using independently reaudited raw 0187 candidates, stock CNSS2 retained. It leaves the installed 0194 package, its backup and the prior-boot 0193 archive unchanged.

Before implementation, XAirDrop main was `585e850e3e026bf9eae90f654dafd01746bc5ec9`: reviewed `module/action.sh` and the new `releases/1.2.1-test/README.md`. The changes since our previous review are release documentation; the repository action is unchanged. The new release describes another device/kernel and a test scope that still excludes iPhone discovery/transfer. OPAirDrop main remains `28a3a1dbc9f515fa5705417a3973616e5ae6180d`, `module/bin/control.sh`. Reuse their retained CNSS2, explicit lock, Wi-Fi/HAL stop-before-swap, provider/WLAN order, reverse removal and original-state restoration. Their automatic runtime starts, patched firmware, RX arguments and partial automatic cleanup are not copied: the 0132 incident and missing current-candidate load acceptance require a smaller first diagnostic. No upstream phone result qualifies popsicle.

## One-shot sequence

`check` and manager Action are read-only; installation checks the current exact stock identity and 0194 backup; boot is a no-op. `cycle` is accepted only from the installed `xairdrop17_cycle0195` path, under the existing shared exclusive lock. It performs:

1. Validate exact firmware/kernel/active boot, all stock copies, loaded notes/holders, absence of foreign state/candidate modules, intact 0194 backup and preserved 0193 archive.
2. Observe fresh boot/Wi-Fi/HAL/interface state. Copy the independently hash-verified stock WLAN into a new private preparing directory. Verify bytes and baselines before no-clobber, same-filesystem publication of a separate transaction.
3. Disable Wi-Fi, confirm it, stop and confirm HAL. Remove only the original WLAN after zero-reference/empty-holder checks. Insert provider then WLAN without any module arguments.
4. Verify the live candidate identities and original CNSS2 holder. While Wi-Fi/HAL remain stopped, remove only the known candidate WLAN after the same unloadability checks, then the known provider after zero-reference/empty-holder checks.
5. Insert the exact verified original WLAN backup, verify its note/holder, restart the captured HALs, restore the captured Wi-Fi state/interface baseline and recheck original CNSS2/WLAN plus absent provider. Record `restored` and emit `STAGE0195_DIAGNOSTIC_CYCLE_STOCK_RESTORED_ONLY`.

The candidate HAL never starts. No Wonder, mac80211 swap, firmware overlay, public backend initialization, configured START, native Apple service, RF control, live-unload sysfs request, forced unload or init_boot operation is included. Kernel module initialization itself is a real experimental native operation; this design cannot guarantee absence of panic, firmware failure or reboot.

Every fixed effect has persisted intent/actual returned status/done markers and original CNSS2/transaction ownership checks around it. A nonzero command can have changed state; it stops the sequence without attempting further module operations or claiming recovery. A positive refcount or unexpected holder blocks deletion. Incomplete/complete transactions and preparing residue block replay. A failed or interrupted cycle requires preserved logs and a stock-driver reboot; this package has no partial live recovery or retry command. Only the complete observed round trip can qualify load/restoration for these bytes.

0194 backup bytes can survive an intervening install reboot: their original manifest and stock content are checked, but their boot/Wi-Fi/HAL values are never used as current baseline. 0195 captures current baseline independently. No old record is overwritten, deleted or automatically archived.

## Validation and phone handoff

Host fixtures execute the actual controller/adapter on private synthetic files, with both Wi-Fi baselines and before/after-effect failures at all ten command boundaries. They verify journal failures, original CNSS identity drift, busy candidate refusal, wrong stock reinsert, transport/copy/log failures, foreign locks/state, prior-boot backup use, no replay and integrity-before-source. Synthetic module/command behavior does not certify kernel ABI or native restoration. Actual ELF audit/package production is a separate CI step, with no native rebuild or byte rewriting.

Local validation: 166 device-host tests ran, 105 passed and 61 mksh cases skipped locally; 110 kernel-tool tests passed. Real-ELF reinspection, current-script comparison and ZIP CRC passed. Local ZIP SHA256 is `133f64faee055422082222646d192a4886afe24689dcea5002e27fecbe405b5f` (168,801,167 bytes). Full mksh/ELF packaging CI and phone cycle acceptance are pending.

Install the new ZIP through KernelSU and reboot normally. Keep the 0194 module and its backup. After boot, one explicit Termux command runs check then the diagnostic round trip:

```sh
su -c '/system/bin/sh /data/adb/modules/xairdrop17_cycle0195/cyclectl.sh check && /system/bin/sh /data/adb/modules/xairdrop17_cycle0195/cyclectl.sh cycle' > /sdcard/Download/xairdrop-0195-cycle.txt 2>&1
```

Wi-Fi disconnects temporarily. Keep the terminal open. Return the log even on failure; do not rerun `cycle`. If Wi-Fi does not recover, disable the 0195 trial and reboot normally. In case a reboot interrupts the command, collect the retained transaction's `phase`, `commands.log`, and available kernel logs before any further work. Apple discovery/handshake/transfer are later acceptance steps.
