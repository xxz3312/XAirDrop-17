# 0097 Native DP peer free and VDEV CHILD release

Implementation prepared; unified Actions compilation/validation pending.

This stage extends 0096 with the pinned, byte-identical `dp_peer_unref_delete()`
body. A separate host heap DP peer represents the owner of the DP VDEV CHILD
reference. Modeled admission clears its peer-ID mapping, then selected callers
release CONFIG/HTT/TX and optional RX references through the original function.
Nonfinal releases must preserve both objects. Native finalization requires an
invalid peer ID and empty AST, removes optional inactive-list membership, calls
cleanup endpoints in original order, frees actual host peer storage, and returns
the CHILD reference into native `dp_vdev_unref_delete()`. That function frees
host VDEV storage before the existing production runtime callback is invoked
through the 0096 checking trampoline.

All 104 previous composite sequences use native peer finalization. Sixteen new
combinations cover reference tracing, RX's original per-module-counter bypass,
reversed CONFIG/HTT release order, inactive-list absence, extra peer TX refs,
extra VDEV HTT refs and optional VDEV notification. Ten added peer mutations
cover final-ref admission, mapped-ID guard, inactive unlink, AST guard, state,
cleanup, lock/txrx order, peer free and CHILD put. Two additional rejection cases
exercise unmodified native mapped-ID and AST admission, alongside 34 inherited
controls. These are expected checks until CI acceptance is recorded.

DP peer and object-manager peer are separate objects. The firmware unmap handler
and real peer allocation/delete/map APIs do not execute. Construction, reference
acquisition, ID-map invalidation, peer-gone gate and release scheduling remain
fixture models; this does not establish a production DP-to-ObjMgr bridge. AST
starts empty; SAWF/state/peer cleanup/monitor/txrx/minidump endpoints and platform
locks/lists/atomics are models. Sanitizers observe actual host heap free, not a
kernel allocator. Inherited components and shutdown coordinator remain modeled
or absent. No production kernel change, radio activation, phone test, firmware,
real concurrency, active SSR or AirDrop certification is included.
