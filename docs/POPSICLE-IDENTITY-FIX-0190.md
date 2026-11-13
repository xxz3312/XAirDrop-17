# 0190 — reject incomplete phone capture; fix shell hash collection

The uploaded 0189 capture SHA256 is `67439775541ff98b48b42c294e931db7a048d7327ca6fc325ca713ff3f4a8670`. Strict evaluation rejected it: all seven required digest fields are absent despite its complete marker. Firmware reports OS4.0.6.0.XPBCNXM (captured target remains 4.0.5.0), the kernel release string is unchanged, and the stock-CNSS transaction directory is present. These are observations, not a complete identity match. No stock profile/hash is changed to accept the new firmware.

Before editing, upstream heads remained OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` and XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`. Checked OPAirDrop `module/bin/kernel-identity.sh` and XAirDrop `module/action.sh`: preserve exact note/file identity and stock modules; do not run their swap/restore actions to investigate this capture failure.

The 0189 collector used the generic shell helper name `hash`, which also names a predefined mksh alias. Android's [mksh regression source](https://android.googlesource.com/platform/external/mksh/+/e7f792145aac8945c9d259af653f50cbf2486b5b/src/check.t) documents `hash='\\builtin alias -t'`. This is a shell-compatibility candidate for the silent omission; a mandatory mksh reproduction test is added rather than treating the host dash-only pass as proof of Android behavior.

## Changes

- New standalone `tools/device/popsicle-identity-0190.sh` uses `xi_digest` and counts expected hash requests independently from successful emissions. Silent digest omission cannot set the complete marker. Historical 0189 source remains for regression reproduction; use 0190 for fresh collection.
- Strict host parsing still rejects missing/extra fields and now names them. CLI writes a structured `CAPTURE_INVALID_BLOCKED` report and exits nonzero instead of ending with a traceback. Both capture stage tags are recognized without relaxing stock identity requirements.
- Added suppressed-helper mutation, seven-missing-hash rejection, structured CLI-error checks, mandatory mksh shell matrix and historical omission reproduction. CI installs a binary mksh dependency and runs shell/Python checks only. Local result: 46 tests passed, 10 mksh tests skipped because mksh is absent locally; 110 kernel Python tests passed. Mandatory mksh CI is pending at submission.
- No driver build/load, installer, old profile retarget or transaction cleanup.

## Old modules shown in KernelSU

`XAirDrop-17 Stock CNSS2 Trial 0.0.138` is the old manual diagnostics package pinned to 4.0.5.0. Its boot service immediately exits and there is no custom uninstall script. `XAirDrop 17 XOS VINTF Declaration 0.2` is the earlier systemless declaration/lookup-policy test module, also pinned to 4.0.5.0; its package has no boot/uninstall scripts. Neither is required for the standalone collector. They can be uninstalled through KernelSU, followed by a normal reboot; do not press the Trial action. No init_boot changes are part of these packages' uninstall paths. This conclusion is based on repository package contents, not an independent hash verification of installed copies.

Uninstalling these packages does not qualify or remove the separately retained `/data/adb/xairdrop17-stockcnss-transaction`. Preserve it for read-only examination. No blanket rm/archive command is authorized by this checkpoint.

## Fresh collection

After any intended module removal/reboot, download `popsicle-identity-0190.sh` and run:

```sh
su -c '/system/bin/sh /sdcard/Download/popsicle-identity-0190.sh' > /sdcard/Download/xairdrop-0190-identity.tsv
```

Return the new TSV even on failure. The script only reads; Termux redirection creates the report. Firmware 4.0.6.0 needs new compatibility evidence even if boot/modules turn out unchanged. Any retained transaction must be examined before designing an archive/recovery action. Loading remains unauthorized.
