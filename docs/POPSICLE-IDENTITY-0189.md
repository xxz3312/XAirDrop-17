# 0189 — fresh read-only identity capture before deployment qualification

0188's independent artifact audit (Actions 43404033165) and the separately triggered full diagnostic build (Actions 43404033249) both succeeded. Candidate deployment planning continues to use the immutable, independently audited 0187 artifact, not newly produced or substituted bytes.

Before implementation, rechecked upstream main commits: OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d`, `module/bin/control.sh`; XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb`, `module/action.sh`. Reuse their separation of stock modules and candidate modules, identity diagnostics and preserved original CNSS2. Do not copy their swap/restore actions into this collector: the known 0132 reboot and absence of a new qualified executor require a read-only boundary. The original 0135 deployment profile and all existing controller/engine files remain unchanged.

## Concrete deliverables

- `tools/device/popsicle-identity-0189.sh`: standalone Android shell, no arguments/actions, no sourced code, no Wi-Fi/framework operations, no module load/unload, no init_boot access. Reads active boot hash, stock module files and loaded GNU build notes, device/firmware/kernel/slot/boot-completion/boot-ID observations, candidate module presence and retained transaction presence. Emits TSV to stdout only. Protected reads require root. I/O failure marks capture incomplete; no unreadable field becomes a match.
- `tools/kernel/stock_cnss_identity.py`: host parser/evaluator. Reject duplicate, unknown, missing and malformed fields; require exact captured stock file hashes/loaded notes/boot/kernel/firmware, stable before/after observations and absence of candidate/retained transaction state. If both vendor trees supply a module, both must match. A successful result is only `CAPTURED_STOCK_IDENTITY_MATCH_ONLY`, always with `load_authorized=false` and `runtime_certified=false`.
- A separate Python/shell-only CI runs 43 device host tests and 110 kernel Python tests and publishes the collector with its digest. No native build trigger is changed.

The host tests use temporary filesystem/command fixtures and regular files in place of block devices. They verify actual shell behavior with real fixture file hashing, no file changes, root/I/O failure, rejected action arguments, changed identities/boot observations, missing modules, conflicting file copies and malformed captures. These are not phone results. Independent [Actions 43423838657](https://github.com/xxz3312/XAirDrop-17/actions/runs/43423838657) passed at `b831718f5ae74753195f01a2e19b58d9fbe466e3`; it ran the shell/Python tests only and published the standalone collector with its digest.

## Phone collection (Termux)

Download the standalone script from the committed GitHub source into Download, keeping its name `popsicle-identity-0189.sh`. Then run:

```sh
su -c '/system/bin/sh /sdcard/Download/popsicle-identity-0189.sh' > /sdcard/Download/xairdrop-0189-identity.tsv
```

Return `xairdrop-0189-identity.tsv`, including an incomplete capture if the command fails. Do not execute old apply scripts, delete transaction state, disable Wi-Fi or reboot for this check. The collector itself writes no files; the Termux redirection creates only the report. It does not require ADB or installation as a KSU module.

Host evaluation after the real capture arrives:

```sh
python3 tools/kernel/stock_cnss_identity.py --capture xairdrop-0189-identity.tsv --output identity-0189-result.json
```

Captured stock target is OS4.0.5.0.XPBCNXM and kernel `6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k`. A different current identity must be investigated with new evidence, never accepted by editing expected hashes to silence a mismatch.

## Remaining boundary

No current phone evidence has arrived. A text capture is not cryptographic attestation or permission to unload a live driver. Before/after observations do not prevent ABA changes; the future executor must recheck under its own serialization. Unload-readiness, HAL/driver quiescence, candidate packaging, backup/failure retention/reboot recovery and staged device acceptance remain necessary. This checkpoint neither creates nor qualifies a new installation executor and does not open configured START, backend initialization, RF or Apple transfer.
