# 0096 Native DP VDEV final free and runtime completion

This stage extends 0095's composite with the pinned, unmodified
`dp_vdev_unref_delete()` body from `dp_main.c`. It does not change the
production kernel backend or enable radio capabilities.

The selected passthru cases allocate host heap DP VDEV storage. Modeled detach
registers the callback/token supplied by the existing production native bridge,
marks delete pending, publishes the optional inactive-list entry and releases
CONFIG through the original finalizer. The modeled peer-gone gate then allows
held HTT references and the final CHILD reference to be released. Native code
performs its ref checks, cleanup calls, inactive unlink, optional pre-free
notification, storage free and post-free completion. A checking trampoline
forwards the original callback token into the existing runtime callback only
after actual host heap release.

All 88 previous composite combinations use this path; 16 additional combinations
cover reference tracing, extra HTT references, optional notification and an
absent inactive-list entry. Eight new mutations target nonfinal release, cleanup,
unlink, notification, free, completion and callback-token handling, alongside
26 inherited controls. These are expected checks until CI acceptance is recorded.

DP construction, detach registration, initial reference ownership, late HTT
release, peer-gone admission, cleanup endpoints, optional notification, locks,
atomics and list representations remain models. No real DP peer unmap or
`dp_peer_unref_delete()` runs, and no direct DP-to-ObjMgr reference bridge is
asserted. Only passthru is selected. Inherited parent construction/components,
real kernel concurrency, automatic shutdown coordination, firmware and phone
validation remain outside this stage. Host heap free is not kernel allocator
execution. No AirDrop interoperability is certified.

Validation: implementation prepared; unified Actions verification pending.
