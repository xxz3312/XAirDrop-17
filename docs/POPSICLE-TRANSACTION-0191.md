# 0191 — inspect retained transaction without archive or replay

The last uploaded capture still lacks required identities (rejected in 0190), reports firmware 4.0.6.0 and shows a retained stock-CNSS transaction. No newer 0190 capture has arrived. This batch works on the independent retained-state blocker; it changes neither expected firmware nor installation authority.

## Upstream references

Before implementation, both upstream main SHAs were unchanged: OPAirDrop `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`) and XAirDrop `891ffe6ccf040fdc86975b4fc649add002dbebcb` (`module/action.sh`). OPAirDrop uses boot-bound state and retains old-boot state separately; XAirDrop uses reboot recovery and rejects half-loaded stacks. Reuse boot association and preservation principles. Do not copy automatic state moves or live restore operations onto this target after the known 0132 reboot and unresolved firmware identity. Local `popsicle-stock-cnss-io.sh` defines the actual retained snapshot/journal format: boot-id, deployment manifest SHA, stock WLAN backup, Wi-Fi baseline, HAL list and phase (including an unfinished phase.new).

## Implemented boundary

`tools/device/popsicle-transaction-0191.sh` is a standalone root/Termux read-only collector, accepting no action arguments and sourcing no files. It emits only TSV on stdout. It checks private/root-owned path components, refuses symlinks and nonregular/FIFO state files, bounds small text fields to 256 bytes, hashes the backup/HAL list without printing their contents, and repeats boot ID, directory inode identity and phase observations. Parent failures cannot masquerade as transaction absence. Independent digest counts reject silently suppressed hash functions. Missing or unreadable critical state produces an incomplete capture. It never writes, moves, removes or replays the transaction and never calls framework, module, reboot or init_boot operations.

`tools/kernel/stock_cnss_transaction.py` rejects malformed/missing/duplicate/unexpected fields and checks recorded boot syntax, observed changes, known journal phases, unfinished journal presence, exact old deployment manifest and captured stock backup SHA. It classifies a complete observation as:

| Result | Meaning |
| --- | --- |
| NO_TRANSACTION_RECORDED | The collector observed no retained directory |
| SAME_BOOT_TRANSACTION_PRESERVED | The record belongs to the observed current boot |
| PRIOR_BOOT_RECORD_ONLY | The record belongs to a different boot and its selected recorded identities match |
| TRANSACTION_RECORD_BLOCKED | A record is inconsistent, unfinished, unknown or unreadable |

Every result keeps archive/replay/load/runtime authority false. Even a prior-boot record does not prove the current phone is running qualified stock bytes or make a move/delete safe. Future mutation requires independent executor qualification and fresh serialized checks. These snapshots cannot prevent arbitrary ABA races and are not cryptographic attestation. Firmware 4.0.6.0 remains unqualified.

## Validation

Local 72 device host test cases: 54 passed, 18 mksh cases skipped because the local shell is absent. All 110 kernel Python tests pass. New transaction cases exercise actual collector behavior on synthetic files, never a phone: same/prior/absent states without writes, symlink/directory/ownership rejection, FIFO/oversized/missing fields, boot/phase/inode/manifest/backup mutations, partial journal, empty HAL file, argument/root rejection, suppressed digest and malformed captures. The shared CI requires mksh and tests the full matrix; its result is pending at submission. No native rebuild is requested.

## Phone use

Keep the new 0190 identity report; it is still required independently. To inspect the retained transaction, download `popsicle-transaction-0191.sh` into Download and run:

```sh
su -c '/system/bin/sh /sdcard/Download/popsicle-transaction-0191.sh' > /sdcard/Download/xairdrop-0191-transaction.tsv
```

Return the report even if capture fails. No old module must be reinstalled for this standalone check. The two retired diagnostics modules can stay uninstalled; do not manually delete the retained transaction. The collector itself writes no files; redirection creates the report only.

Host classification:

```sh
python3 tools/kernel/stock_cnss_transaction.py --capture xairdrop-0191-transaction.tsv --output transaction-0191-result.json
```

Next evidence needed: complete current identity (0190) and actual retained-state inventory (0191), then qualify the new firmware/deployment/recovery contract. No installation package is produced.
