# Popsicle baseline patches

Apply in numeric order to MiCode WLAN commit
`36df473046706a5259942e1bf7222108dbbb860f`.

1. Use the correct T2LM enum constant without changing its numeric value.
2. Include link-reconfiguration prototypes from their own header.
3. Compile TSF GPIO helpers only when the actual GPIO IRQ branch is selected.

Patch 3 follows `wlan_hdd_tsf_plus_init` branch precedence: NOIRQ first,
external GPIO sync second, external GPIO IRQ third. The canoe profile enables
`CONFIG_WLAN_SYNC_TSF_PLUS_NOIRQ=y`, so its GPIO IRQ helper is unused.
Previously the unconditional PLD definitions retained an unnecessary reference
to `cnss_get_wlan_tsf_gpio`, absent from the recorded stock provider exports.

The patch changes no profile options, adds no stub or fake success return,
and retains the original implementation when the GPIO IRQ branch is selected.
Fresh object compilation and symbol inspection are delegated to GitHub Actions.

4. `0004-mishare-passthru-host-modes.patch` appends the host QDF/DP PASSTHRU
   identifiers and their conversion without renumbering existing modes. MLME
   registration and firmware-type conversion explicitly reject the new mode;
   HDD also refuses it before the existing unknown-mode assertion. This does
   not add a firmware type, policy table rows, adapter implementation or TX/RX.
   Actions compares the original and patched C functions for all legacy modes
   and checks the new rejection paths before compiling the complete WLAN.

5. `0005-mishare-host-lifecycle.patch` adds a private DOWN PASSTHRU factory
   while keeping the original hdd_open_adapter signature and rejection behavior.
   Its netdev open/type-change/delete paths reject ordinary control. The private
   factory's registered-netdev rollback saves the MAC before adapter reclamation.
   The real lifecycle helper C/header are overlaid from kernel/popsicle-hdd and
   built into WLAN; there is no module init, export, runtime caller or radio path.

6. `0006-mishare-wonder-table-lifetime.patch` wires an optional typed table
   registration after successful HDD probe and synchronous detach before HDD
   context teardown. The module parameter is false by default and read-only.
   Callbacks remain metadata-only/unsupported, with no host handle published.
   A strong dependency on the private provider pins its module while WLAN is
   loaded; actual provider Module.symvers records are included in strict modpost.

15. `0015-mishare-wma-ndi-compat.patch` adapts the existing SM8750 WMA
    PAS-host/NDI-firmware route to the target's native functions. One predicate
    governs self-peer creation, removal and synchronous-delete waiting. It also
    routes START/channel responses, DP MAC ID and NDI post-start setup. A bound
    PAS/NDI legacy context can use host-only UP; unpublished host-only components
    are rejected. No type selection, CREATE owner, MLME activation, TX/RX, module
    parameter, auto-start or firmware acceptance is added. Actions runs actual
    extracted peer create/delete/detach and UP functions with mocked external
    operations, followed by complete target WLAN compilation and strict linking.

16. `0016-mishare-owned-ndi-create-delete.patch` adds an explicitly owned
    resource CREATE route: native parameter preparation, pre-wire timer setup,
    WMI CREATE and DP attach retain separate outcomes and stats ownership.
    The optional runtime owner API drives DELETE without the generic early DP
    detach, observes real DELETE versus timeout at native origins, and waits
    for DP's final-free callback before object-manager destruction. Legacy
    CREATE/DELETE helpers remain unchanged; only owned DELETE origins branch.
    Unknown/partially published failures retain resources. No runtime caller,
    START, legacy/session/self-peer preparation, TX/RX or SSR recovery is added.

17. `0017-mishare-owned-legacy-wma-self-peer.patch` adds checked local legacy
    preparation/unwind and dedicated WMA slot/reference binding. The owner uses
    native DEFAULT peer creation and a distinct 0x12 hold-request type for peer
    deletion. Real/timeout notifications follow native request cleanup; only
    their matching stable owner token can advance teardown. WMA/legacy survive
    until confirmed peer/vdev deletion and DP final-free. Native peer errors
    quarantine; no CSR, generic post-create configuration, START or radio caller
    is introduced. Existing native paths match their recorded source hashes
    after removing the bounded additions (plus a pre-truncation event-ID guard).

18. `0018-mishare-owned-pe-session.patch` adds a private host PE role and
    an owned MC request with exact VDEV references, flush cleanup and actual
    completion. Native PE creation/destruction are paired before self-peer,
    VDEV and DP teardown. Foreign/recycled session identity is rejected; failed
    or cancelled deletion quarantines. An owned constructor failure releases
    its MAC VDEV reference. No radio command or runtime caller is enabled.
