# 0210 — explicit internal typed host START, with caller-retained parents

## Accepted base and upstream

0209 source1e32b7143f6247f710dd7af23dba932fda75fc0f / Actions43616123462 passed both native/model and full target jobs; accepted in main25ac4ce72b4411124ec3dff5e2f83c6971b45911. Its initial failed fixture run remains recorded. This is software acceptance only; installed phone stays0205.

Rechecked upstream XAirDrop585e850e3e026bf9eae90f654dafd01746bc5ec9 and OPAirDrop28a3a1dbc9f515fa5705417a3973616e5ae6180d, unchanged. Retain the referenced action/control and native lifecycle separation from0209; do not copy upstream bypass or assume its radio/firmware results apply to popsicle.

## Change

Add explicit request_bridge_configured_start_locked and host_configured_start_locked. Typed callers must use the bridge entry: full frozen canonical request, original HDD/NSS/bridge identities, currently allowed native policy and attached host are checked each attempt. The host entry immediately reuses the real post-commit launch check, then invokes runtime_configured_start with that request frequency. Runtime independently authenticates owner and committed native receipts before its existing one-shot submission. No state projection, readiness ticket, implicit preparation, synthetic UP or retry is added. The new host entry is a lower-level primitive, not an independent full-request/country authorization boundary.

The functions require RTNL/exclusive transition and a caller already retaining the complete native HDD/component/firmware lifetime through asynchronous callbacks and every ordinary destruction poll. Per-call allocation references are insufficient. No managed/public initializer calls this API; public backend init remains closed. No automatic boot action, ELF/CRC rewrite, new module ID, phone command or install package. Active configured SSR/remove coordination remains unsupported and retains ownership.

Return EINPROGRESS after submission. Repeated host calls rerun launch admission and refuse the active state (EBUSY in the covered pending-start case); they do not report readiness or replay. Runtime keeps its own authoritative attempted/returned history. Existing0209 destruction first waits START/UP, then STOP/DOWN, then native ordinary PE/peer/DELETE/DP/final-free before adapter release. Sticky runtime errors and unsupported recovery retain original resources.

## Validation plan and boundaries

Local110 Python checks, syntax and whitespace checks pass. New native composite extracts exact production host launch/start and close bodies. It uses the accepted preparation/configuration/MC/native SM and runtime paths,512 ordinary cycles,13 start refusals,6 close refusals and6 cleanup faults; omission of host launch-result enforcement is a negative control. Repeated submission must refuse without replay. The full host/request-bridge model separately checks the new typed entry and country/MAC/BSSID/retry frozen-request mismatches before the modeled runtime submission. Existing0209 native close,0208 runtime, host ownership and raw factory/native regressions run again.

Host/RTNL/parent/HDD primitives and WMI/firmware delivery remain modeled. Full frozen request/current native policy and native firmware lifecycle are not one end-to-end factory/typed proof here. Complete parent/firmware lease coordination, managed launch, active configured recovery, real RF and Apple transfer remain unqualified. No installation artifact acceptance follows from this suite.

Dedicated branch codex/host-configured210 runs native prequalification before one full target compilation/link/interface/layout/offline-record build. CI is pending until explicitly reviewed. Main stays at accepted0209. Return the run link immediately without waiting for completion.
