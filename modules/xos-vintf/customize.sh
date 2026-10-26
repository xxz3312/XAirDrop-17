# KernelSU installer context. No direct partition writes or live policy changes.
[ "${KSU:-}" = true ] || abort 'Install with KernelSU.'
[ "$(getprop ro.product.device)" = popsicle ] || abort 'Expected popsicle.'
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || abort 'Firmware changed; fresh audit required.'
mount_provider=0
for prop in /data/adb/modules/*/module.prop; do
    [ -f "$prop" ] || continue
    dir=${prop%/*}
    [ ! -e "$dir/disable" ] && [ ! -e "$dir/remove" ] || continue
    if grep -q '^metamodule=1$' "$prop" && [ -f "$dir/metamount.sh" ]; then mount_provider=1; fi
done
[ "$mount_provider" = 1 ] || abort 'An enabled KernelSU mounting metamodule is required to mount system/vendor. No files were written to system partitions.'
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
set_perm "$MODPATH/system/vendor/etc/vintf/manifest/manifest_xairdrop17_xos.xml" 0 0 0644 u:object_r:vendor_configs_file:s0
set_perm "$MODPATH/sepolicy.rule" 0 0 0644
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/service-smoke.sh" 0 0 0755
ui_print '- XOS VINTF declaration staged. Reboot to apply through the mounting metamodule.'
ui_print '- One measured SELinux find rule is included. No boot service, kernel modules or MiShare patches.'
ui_print '- After reboot, run this module Action to collect the registration report.'
