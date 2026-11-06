#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
[ "$(id -u)" = 0 ] || abort 'Root required'
[ "$(getprop ro.product.device)" = popsicle ] || abort 'Only audited popsicle is supported'
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || abort 'Firmware differs from the captured ABI'
[ "$(uname -r)" = 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k ] || abort 'Kernel differs from the captured boot'
(cd "$MODPATH" && /system/bin/sha256sum -c SHA256SUMS) || abort 'Payload integrity check failed'
[ ! -e "$MODPATH/kernel/cnss2.ko" ] || abort 'CNSS2 replacement is forbidden in this profile'
set_perm_recursive "$MODPATH" 0 0 0700 0600
for script in "$MODPATH"/*.sh; do set_perm "$script" 0 0 0700; done
ui_print '- Experimental WLAN/provider trial; stock CNSS2 is retained.'
ui_print '- No automatic driver loading during install or boot.'
ui_print '- Run the read-only check before using the Action button.'
ui_print '- Action starts one manual trial; failures stop without retry.'
ui_print '- This is not an Apple discovery/file-transfer release.'
