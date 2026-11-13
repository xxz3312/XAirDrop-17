[ "${KSU:-}" = true ] || abort 'Install using KernelSU'
(cd "$MODPATH" && /system/bin/sha256sum -c INSTALL_SHA256SUMS && /system/bin/sha256sum -c SHA256SUMS) || abort 'Integrity failed'
[ ! -e "$MODPATH/kernel/cnss2.ko" ] || abort 'CNSS2 replacement forbidden'
set_perm_recursive "$MODPATH" 0 0 0700 0600
for stage_script in "$MODPATH"/*.sh; do set_perm "$stage_script" 0 0 0700; done
/system/bin/sh "$MODPATH/stagectl.sh" check || abort 'Exact stock/archive identity preflight failed'
ui_print '- 0194 candidate staging and stock backup only.'
ui_print '- Action performs a read-only check. Driver loading is disabled.'
ui_print '- No boot loading or init_boot changes.'
