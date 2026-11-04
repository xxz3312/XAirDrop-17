# 0105 Host parent allocation references

## Implementation

The production HDD host now acquires a Linux device reference, a PSOC object-manager reference and a PDEV object-manager reference before entering the host registry or allocating adapter/sync resources. PDEV must belong to that exact PSOC. A refused reference unwinds only the references already acquired; a foreign PDEV unwinds all three. No owner is published on failure.

The references remain owned by the host through runtime drain, SSR-batch polling/rejection and sync-unregister failure. Successful close first drains runtime, unregisters/waits/closes the adapter and destroys sync, then releases PDEV, PSOC and device in reverse order, removes the host registry entry and frees the owner. Create failures after registration use the same reverse release. Existing idle/mode admission remains active through adapter/sync teardown and reference release.

All five later host operations assert the transition against the pinned device and reject a changed HDD device, PSOC or PDEV with EUCLEAN before touching session, runtime or adapter state. Runtime creation uses the pinned PDEV.

## Verification

Pending Actions execution. The existing production-host sanitizer fixture now covers all acquisition failures, inconsistent PDEV ancestry, reverse release and retention through pending/error exits. Each of three replaced identities is checked at all five operations, both before and after a runtime token exists (30 refusals). Seven new mutation controls remove an identity check, an unpin or the PDEV-parent check; six existing idle/mode mutation controls remain.

The full diagnostic build continues to compile the actual production helper into WLAN and checks module linking/dependencies. Reference primitives in the host fixture are modeled; they do not execute native physical object deletion.

## Remaining boundary

These references retain allocations only. They do not retain HDD context, native component state, firmware, IRQ/DMA or transport readiness. The caller must retain HDD and serialize the complete native parent lifetime throughout every call and between asynchronous polls. Holding object-manager references can delay deletion; an automatic teardown caller must first retire the host through a qualified coordinator. No native remove/SSR caller or backend activation is added here. Standalone runtime owners are unchanged and still require their caller's lifetime contract. Real NDI/Wonder init, complete AWDL RX/TX and Apple discovery/handshake/file transfer remain pending. No phone operation is needed for this stage.
