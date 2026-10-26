#!/system/bin/sh
# Manual action only; never executed at boot.
set -u
[ "$(id -u)" = 0 ] || exit 1
MODDIR=${0%/*}
self_ns=$(readlink /proc/self/ns/mnt) || exit 1
init_ns=$(readlink /proc/1/ns/mnt) || exit 1
[ -n "$self_ns" ] && [ -n "$init_ns" ] || exit 1
if [ "$self_ns" != "$init_ns" ]; then
    command -v nsenter >/dev/null 2>&1 || { echo 'nsenter unavailable; cannot check init mount namespace.'; exit 1; }
    exec nsenter -t 1 -m -- /system/bin/sh "$0" "$@"
fi
manifest=/vendor/etc/vintf/manifest/manifest_xairdrop17_xos.xml
[ -r "$manifest" ] || { echo 'VINTF fragment not visible to init. Reboot and check the mounting metamodule.'; exit 1; }
actual=$(sha256sum "$manifest") || exit 1
[ "${actual%% *}" = '@MANIFEST_SHA256@' ] || { echo 'Unexpected mounted VINTF fragment; stopped.'; exit 1; }
reference=/sdcard/Download/XAirDrop-reference-1.0.zip
[ -f "$reference" ] || { echo "Reference ZIP missing: $reference"; exit 1; }
echo 'VINTF fragment is visible in init namespace. Starting manual registration diagnostic.'
exec /system/bin/sh "$MODDIR/service-smoke.sh" "$reference"
