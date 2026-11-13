# 0188 — existing candidate artifact acceptance (no installation)

0187 source `a4b9404257efe395cf3cf865a806bff5daba6f4b` completed all eight required jobs in [Actions 43390041712](https://github.com/xxz3312/XAirDrop-17/actions/runs/43390041712). This checkpoint changes audit tooling and records only. Its independent audit reuses existing artifacts and requires no native rebuild; the repository's existing test-file push rule also automatically triggered the separate full build.

## Upstream comparison

Before implementation, rechecked OPAirDrop main `28a3a1dbc9f515fa5705417a3973616e5ae6180d` (`module/bin/control.sh`) and XAirDrop main `891ffe6ccf040fdc86975b4fc649add002dbebcb` (`module/action.sh`). Their control paths remain references for deployment structure, not evidence that these popsicle ELF bytes can load. Retain stock CNSS2 and the existing explicit deployment gates. Neither upstream supplies an acceptance record for this candidate/kernel pair.

## Independently checked actual artifacts

`stock_cnss_candidate_audit.py` binds the two downloaded ZIPs to their recorded GitHub digests, sizes, run/attempt and source commit. Both contain 64 JSON reports with identical bytes. It streams the nested diagnostic archive, accepts only the five expected regular ELF members, and reinspects their actual identities, build-note digests, version-record coverage and module headers. The WLAN SHA is `713467f62587746e11db656214bd5843b65cbc28a54340f6933c7fcd96d7dd1a`.

All 64 stock CNSS2 imports match the captured export CRCs. The actual provider's two private imports (`opairshare_set_wonder_managed_priv_data`, `opairshare_wlan_execution_close`) also match the actual WLAN version records. All seven selected-layout CI records bind to this WLAN hash. Complete identities are in `research/popsicle-candidate-0188-validation.json`; authoritative run/artifact metadata is retained separately in `research/popsicle-candidate-0188-ci.json`.

The raw WLAN ELF is 391,968,696 bytes including debug data. This audit does not strip, rewrite vermagic, forge CRCs or repackage it. Its release string differs from captured stock; the original CI records the captured loader's basic-version checks, not an exact vermagic match. Full kernel CRC comparison and selected private layout derivation remain CI evidence, not independently rederived by this new local auditor.

## Validation and authority

110 Python tests passed locally, including rejected source/workflow/job substitutions, digest/size/origin/expiry failures, unsafe or duplicate ZIP members and incomplete/substituted ELF records. A separate read-only Actions workflow repeats these tests, downloads the same existing artifacts and requires an identical audit report. The independent audit passed in [Actions 43404033165](https://github.com/xxz3312/XAirDrop-17/actions/runs/43404033165) at `e7ace31ffd4da2b88317961e838a78a5ad100474`, reproducing the committed JSON exactly. The separately triggered full build is not part of this immutable 0187 candidate acceptance.

Result: `CANDIDATE_RECORDS_VERIFIED_NOT_FOR_INSTALL`. This is not full C/KCFI/ABI, firmware, unload/load, RF or Apple certification. No phone command ran. Configured START and public backend initialization remain closed. Stock CNSS2 and init_boot are unchanged.

## Remaining before controlled installation

1. Obtain fresh phone/kernel/firmware/stock CNSS2 identity and require an exact supported target. Captured evidence targets OS4.0.5.0.XPBCNXM; the current phone identity has not been rechecked.
2. Qualify a new explicit deployment profile and executor against these exact candidate bytes, including backup, stop/failure retention and reboot recovery. The old 0135 bundle and its acceptance evidence remain pinned; this audit does not retarget them.
3. Pass staged device unload/load and recovery acceptance before enabling runtime/RF tests. Do not repeat the earlier three-module loading sequence that rebooted the phone.

Apple discovery, handshake and bidirectional transfer remain later device acceptance goals. No installation bundle is produced in 0188.
