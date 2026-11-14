[ "${KSU:-}" = true ] || abort 'Install using KernelSU'
(cd "$MODPATH" && /system/bin/sha256sum -c INSTALL_SHA256SUMS && /system/bin/sha256sum -c SHA256SUMS) || abort 'Integrity failed'
set_perm_recursive "$MODPATH" 0 0 0700 0600
for cycle_script in "$MODPATH"/*.sh; do set_perm "$cycle_script" 0 0 0700; done
/system/bin/sh "$MODPATH/cyclectl.sh" check || abort 'Exact stock/0194 backup preflight failed'
ui_print '- 0197 scan-aware diagnostic cycle, same module ID; no automatic trial.'
ui_print '- Action checks only; init_boot is unchanged.'
