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
