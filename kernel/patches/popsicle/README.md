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
