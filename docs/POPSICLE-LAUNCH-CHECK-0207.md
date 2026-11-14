# 0207 — post-commit / before-first-START observation

0205/0206 established one ordinary candidate HAL/WLAN association, validated IP, a uniquely correlated10-result scan callback and exact original-driver restoration. That evidence does not establish Wonder initialization or an active PAS session. Keep the accepted phone package205, original CNSS2,194 backup and every retained transaction/archive unchanged.

## Upstream and implementation gap

Rechecked XAirDrop585e850e3e026bf9eae90f654dafd01746bc5ec9 module/action.sh and OPAirDrop28a3a1dbc9f515fa5705417a3973616e5ae6180d module/bin/control.sh plus kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch. Both native paths distinguish driver/provider/Wonder loading from interface initialization and actual radio readiness; stock CNSS2 stays. Do not copy their passthru parameters or synchronous native Wonder implementation into this different managed popsicle backend. Our existing mishare_backend_init still returns EOPNOTSUPP after canonical parsing; configured runtime START also explicitly refuses rate-configured sessions. Active configured retirement and parent/firmware lifetime must be qualified with activation, rather than remove that refusal following a successful ordinary scan.

## New internal observation

Added managed_launch_check -> fresh native scope and exact managed parent -> request_bridge_launch_check_locked -> CURRENT native regulatory/request preflight -> host_launch_check_locked -> coherent runtime snapshot -> start_launch_check. The predicate reuses all canonical configuration/receipt/DP ownership/radio-pristine/provenance checks, and additionally requires the preview to have been committed. A valid completed but uncommitted preview stays EINPROGRESS. Previously plan-commit-check accepted either side of scalar adoption; it cannot alone serve as post-commit observation.

Every poll validates the frozen full request, current HDD/PSOC/PDEV identity, NSS/current channel policy, BSSID, rate/retry receipts, adopted native encoder summary, DP cookie/stats ownership and absence of old command/fence/recovery history. Busy/work/pending states and errors propagate without caching readiness or replaying native work. Managed ownership and scope are released on each acquired path. Zero means only a coherent post-commit/before-first-START observation; it is not a reusable permission, parent lifetime lease, firmware ACK, radio UP or RX/TX.

There is intentionally no START submission in this batch. The configured active stop/recovery contract and native parent/firmware coordination remain prerequisites. No public callback, service, sysfs toggle or boot loader invokes this observation. No driver byte rewrite, module ID change, phone command or new installation package.

## Validation

Local110 Python kernel-tool tests, Python syntax and diff checks passed. One existing full CI batch will execute production C with ASan/UBSan, request/native-policy and managed-scope cases, existing lifecycle regressions and the complete target build. Native compilation is Actions-only. New pure observations cover16 band/retry/rate modes,192 invalid-configuration cases, absent/uncommitted receipts, input immutability and a required-commit mutation. Actual production host/managed paths add repeated observations in both ordinary and recovery-retirement scenarios,17 failure children and five mutations; bridge fixtures add result/current-policy/full-request/no-replay coverage and a validation-bypass mutation. Native synchronization, firmware and radio behavior remain modeled boundaries, not phone acceptance.
