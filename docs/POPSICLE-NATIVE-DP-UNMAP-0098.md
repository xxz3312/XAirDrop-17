# 0098 Native DP peer unmap and map-reference release

Implementation prepared; unified Actions compilation/validation pending.

This stage extends 0097 with four original functions: `dp_rx_peer_unmap_handler`,
`dp_peer_get_ref`, `__dp_peer_get_ref_by_id` and
`dp_peer_find_id_to_obj_remove`. The two original DP peer/VDEV finalizers remain
unchanged. Initial lifecycle and map CONFIG references are distinct; the native
lookup takes a temporary HTT reference using nonzero-ref admission. Native map
removal clears peer/txrx IDs and the map slot and returns its CONFIG reference
while holding the modeled map lock. Native unmap performs its remaining steps,
returns HTT and lifecycle CONFIG, and reaches native peer/VDEV final free when
all additional references are gone.

The 120 previous combinations now use native unmap. Thirty-two extra cases
combine offload, IPA, optional txrx/WDI notification, optional OL/partner hooks,
reference tracing and extra-reference release before/after unmap. Probes cover
unknown/boundary IDs, zero-ref lookup, WDS offload skip, both WDS AST results,
and duplicate delivery after peer storage is gone. WDS paths must return the
temporary HTT reference while retaining CONFIG references and the mapping.
Ten new mutations target lookup pinning, map slot/reference/txrx-ID removal,
Qref and flow cleanup, event/state order and the final HTT/CONFIG releases.
The 46 inherited controls run with their previous modeled unmap setup, preserving
the meaning of those tests. Counts are expected until accepted CI is recorded.

This executes native handler C from fixture calls, not real firmware delivery.
Initial construction, map/lifecycle reference acquisition, the map array,
platform atomics/locks, event/Qref/AST/flow/IPA/WDI/OL/partner/statistics endpoints,
peer-gone admission and release scheduling remain models. Peer create/map-add/
delete, firmware HTT parsing/transport and callback registration do not execute.
WDS AST helpers are modeled; STA and multiple-SOC/MLO ownership paths are not
selected. DP and ObjMgr peer objects remain distinct with no verified production
bridge. Inherited component/coordinator/concurrency boundaries remain. Host heap
free is not kernel allocator execution. No backend activation, active SSR,
phone/RF validation or AirDrop certification is included.
