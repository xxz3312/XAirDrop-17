# 0208 — internal configured START / ordinary STOP and retirement

0207 dce381b877ddac740d892a2dfbeb3b9ae5830dfe passed all eight required jobs in Actions43599564193. Keep the installed/accepted205 module, original CNSS2,194 backup and all historical transactions unchanged. No new phone install or command is part of this source batch.

## Upstream

Rechecked unchanged XAirDrop585e850e3e026bf9eae90f654dafd01746bc5ec9 and OPAirDrop28a3a1dbc9f515fa5705417a3973616e5ae6180d. Refer to module/action.sh, module/bin/control.sh and OPAirDrop kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch. Preserve their separation of provider/driver lifetime from real interface STOP and callback-dependent destruction. The popsicle managed backend has distinct asynchronous owner/parent/firmware contracts, so do not copy OnePlus passthru flags, replace original CNSS2 or treat synchronous upstream shutdown as local qualification.

## Internal execution

New runtime_configured_start authenticates the runtime token against the registry before dereference. Require a committed owned native encoder receipt, full successful rate/retry/BSSID history, actual VDEV ID and parent/event/PE/ref/DP/stats/timer resources, exact frequency, no old radio/fence history, no reset/ordinary-retirement state and no work/reservation. Mark attempted before invoking the existing native radio controller. Record the returned result, retaining non-null partial owners on error. Repeated attempts return EALREADY; an unexpected zero from radio_open cannot be called success. The old raw START still refuses configured sessions.

The internal caller MUST retain and serialize the complete native parent/firmware lifetime and recheck the full frozen request and current native policy before first START. No public Wonder callback, host adapter factory entry, worker, parameter or service calls this new API. It does not acquire that lifetime lease. Public initialization stays closed.

New runtime_configured_stop uses a fresh authenticated controller snapshot before calling native drain. Pending START stays pending without publishing close/STOP or synthetic cancellation. Only fully-UP ordinary STOP/WAIT_STOP/DOWN progression is supported. Quiesced/fenced/failed/partial START sessions retain resources; active configured SSR/remove recovery is not admitted. Stop-post/other hard native drain errors are sticky. No forced unload, state clearing, phase projection or blind native retry.

After real ordinary DOWN, keep start_attempted/stop_attempted/host_up/down_attempted/down_accepted as historical facts. Only a released controller with exact successful configured STOP receipt, no pending users/work, no errors/fence/reset history and matching original configuration permits ordinary PE/peer/DELETE/DP cleanup. Existing acknowledgments and final refs gate every native release; ordinary_completed is not final VDEV free. Before terminal proof, generic destroy continues refusing configured radio. SSR eligibility is deliberately unchanged and remains closed for this class.

## Verification

Local110 Python tests, Python syntax and diff checks passed. The existing full CI runs one batch; the new configured-radio composite is the first native stop-admission step so failures surface early. It executes production runtime/configuration MC/encoder and existing actual native SM/controller and ordinary cleanup bodies. Matrix512 spans two bands, four retry pairs, callback timing and32 native cleanup variants. Sixteen first-START refusals, seven radio faults, six cleanup faults and six mutations check identity, no replay, pending START retention, ordinary STOP-before-PE ordering, true DOWN proof, unchanged rate/retry/preview records and complete final release.

Primitive locks, scheduling, WMI execution/firmware delivery and object refs/unmap retain the inherited explicit models. Native parent coordination and public host integration are not installed by this batch. No phone RF, long-term reliability, AWDL RX/TX, Apple discovery/handshake/transfer claim follows from fixtures or a full build. A source artifact is not a phone installation package.

## Current CI handoff

Production source a05958f4c1a2c1c9ef1206b9a415d449a5e4886e runs in Actions43604892297, diagnostic job132477308922. Full compilation and CNSS provider interfaces passed; strict linking/layout/offline module checks are not yet finally accepted. The original stop job failed a fixture expectation during an owned pending MC reservation. Fixture-only fixes correct EINPROGRESS vs EOPNOTSUPP, multiline entry discovery and the inherited engine output marker. No production source changed. Focused source cfefff822ef8c42cf290d9c1dd595b16fd11ae02 / Actions43605506637 / job132479161536 passed the new512-case composite, mutations and every existing stop regression. API compare confirms only the fixture and its focused workflow differ from production build source. This record does not claim the original overall run passed.

Per the user's preference, stop waiting and provide CI links; inspect the result on the next continue request. The fixture/report/preference merge uses skip-ci because native production bytes are unchanged and the focused stop workflow already passed. Do not cancel the ongoing target build or start a duplicate build for these test/documentation changes. No install bundle or phone action.
