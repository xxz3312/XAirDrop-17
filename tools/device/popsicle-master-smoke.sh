#!/system/bin/sh
# Component bind/unbind/rebind only. Never create or raise a wireless interface.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-master-smoke-$tag
report=/sdcard/Download/17pm-master-result-$tag.tar.gz
provider_dev=/sys/bus/platform/devices/qcom,cnss-vendor-wlan-wonder
master_dev=/sys/bus/platform/devices/wonder
phy=/sys/class/ieee80211/wonder
mkdir -p "$work" /sdcard/Download || exit 1
chmod 700 "$work" || exit 1
own_mac=0
own_provider=0
own_probe=0
own_master=0
mac_added=0
tested=0
phase=preflight
net_before=$(ls -1 /sys/class/net) || exit 1
exec 3>&1
exec >"$work/test.log" 2>&1
say() { printf '%s\n' "$*"; printf '%s\n' "$*" >&3; }
fail() { say "FAIL: $*"; exit 1; }
snapshot() {
    # Keep warning headers and surrounding stack frames, not just our caller.
    dmesg 2>&1 | grep -iE -B 8 -A 40 'wonder|opairshare|ieee80211_alloc_hw_nm|unknown symbol|disagrees|version magic|cfi failure|WARNING:.*mac80211|oops:|kernel panic|avc:.*module_load' | tail -n 400
}
last_bind() { dmesg 2>&1 | grep -F 'Connected to wlan ver 5 (cur: wonder ver 7)' | tail -n 1; }
last_unbind() { dmesg 2>&1 | grep -F 'Unregistered vendor operations.' | tail -n 1; }
finish() {
    rc=$1
    trap - 0 1 2 15
    if [ "$own_master" = 1 ]; then
        if rmmod wonder; then own_master=0; else rc=1; say 'FAIL: Wonder unload failed; preserving dependencies.'; fi
    fi
    if [ "$own_probe" = 1 ] && [ "$own_master" = 0 ]; then
        if rmmod opairshare_route_b_probe; then own_probe=0; else rc=1; say 'FAIL: probe unload failed; preserving dependencies.'; fi
    fi
    if [ "$own_provider" = 1 ] && [ "$own_master" = 0 ] && [ "$own_probe" = 0 ]; then
        if rmmod opairshare_wonder_provider; then own_provider=0; else rc=1; say 'FAIL: provider unload failed.'; fi
    fi
    if [ "$own_mac" = 1 ] && [ "$own_master" = 0 ] && [ "$own_probe" = 0 ] && [ "$own_provider" = 0 ]; then
        if rmmod mac80211; then own_mac=0; else rc=1; say 'FAIL: temporary stock mac80211 could not unload.'; fi
    fi
    if [ "$tested" = 1 ] && [ "$own_master" = 0 ] && [ "$own_probe" = 0 ] && [ "$own_provider" = 0 ]; then
        if [ -e "$provider_dev" ] || [ -e "$master_dev" ] || [ -e "$phy" ] ||
           [ -d /sys/module/wonder ] || [ -d /sys/module/opairshare_route_b_probe ] ||
           [ -d /sys/module/opairshare_wonder_provider ]; then
            rc=1; say 'FAIL: temporary module/device/PHY remains after cleanup.'
        fi
    fi
    if [ "$mac_added" = 1 ] && [ "$own_mac" = 0 ] && [ -d /sys/module/mac80211 ]; then
        rc=1; say 'FAIL: temporary mac80211 still present.'
    fi
    [ -d /sys/module/qca_cld3_peach_v2 ] || { rc=1; say 'FAIL: stock WLAN module absent.'; }
    net_after=$(ls -1 /sys/class/net)
    [ "$net_after" = "$net_before" ] || { rc=1; say 'FAIL: network interface names changed during test.'; }
    printf '%s\n' "$net_before" >"$work/net-before.txt"
    printf '%s\n' "$net_after" >"$work/net-after.txt"
    snapshot >"$work/dmesg-after.txt"
    if [ "$rc" = 0 ] && [ "$tested" = 1 ]; then status=PASS_MASTER_BIND_UNBIND_REBIND; else status=FAIL_OR_INTERRUPTED; fi
    printf 'status=%s\nphase=%s\nexit_code=%s\nmaster_still_owned=%s\nprobe_still_owned=%s\nprovider_still_owned=%s\nmac_still_owned=%s\nmac_loaded_by_test=%s\n' \
        "$status" "$phase" "$rc" "$own_master" "$own_probe" "$own_provider" "$own_mac" "$mac_added" >"$work/result.txt"
    say "$status (component lifecycle only, no wireless interfaces or traffic requested)"
    if [ "$own_master$own_probe$own_provider$own_mac" != 0000 ]; then
        say 'Save the report and reboot to clear remaining temporary modules. Do not force-unload.'
    fi
    if tar -czf "$report" -C "$work" device.txt result.txt test.log dmesg-before.txt dmesg-after.txt net-before.txt net-after.txt; then
        printf 'Upload report: %s\n' "$report" >&3
    else
        printf 'Could not package report; root-readable logs: %s\n' "$work" >&3
        rc=1
    fi
    exit "$rc"
}
trap 'finish $?' 0
trap 'exit 130' 1 2 15
{ getprop ro.product.device; getprop ro.build.version.incremental; uname -r; } >"$work/device.txt"
snapshot >"$work/dmesg-before.txt"
for tool in insmod rmmod sha256sum tar cp chmod dmesg grep tail; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing command: $tool"
done
[ "$(getprop ro.product.device)" = popsicle ] || fail 'Unexpected device.'
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || fail 'Unexpected firmware.'
[ "$(uname -r)" = 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k ] || fail 'Unexpected kernel.'
[ -d /sys/module/qca_cld3_peach_v2 ] && [ -d /sys/module/cfg80211 ] || fail 'Expected stock WLAN dependencies absent.'
[ ! -e /proc/sys/net/wonder/wonder_enable ] || fail 'Existing Wonder availability setup.'
[ ! -e "$provider_dev" ] && [ ! -e "$master_dev" ] && [ ! -e "$phy" ] || fail 'Existing Wonder device/PHY.'
for name in opairshare_wonder_provider opairshare_route_b_probe wonder; do
    [ ! -d "/sys/module/$name" ] || fail "Already loaded: $name"
    case "$name" in
        opairshare_wonder_provider) expected=8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a ;;
        opairshare_route_b_probe) expected=158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade ;;
        *) expected=967d50c09eb217ff4dacb47e505ad5c8ae11fae454c7afc28d0e72f1bf333755 ;;
    esac
    actual=$(sha256sum "$src/$name.ko") || fail "Missing $name.ko"
    [ "${actual%% *}" = "$expected" ] || fail "Checksum mismatch: $name"
    cp "$src/$name.ko" "$work/$name.ko" || fail "Cannot stage $name"
    chmod 600 "$work/$name.ko" || fail "Cannot set mode: $name"
    actual=$(sha256sum "$work/$name.ko") || fail "Cannot checksum staged $name"
    [ "${actual%% *}" = "$expected" ] || fail "Staged checksum mismatch: $name"
done
phase=stock-mac80211
stock_mac=
for path in /vendor/lib/modules/mac80211.ko /vendor_dlkm/lib/modules/mac80211.ko /system_dlkm/lib/modules/mac80211.ko; do
    if [ -f "$path" ]; then stock_mac=$path; break; fi
done
[ -n "$stock_mac" ] || fail 'Stock mac80211 missing; no modules loaded.'
actual=$(sha256sum "$stock_mac") || fail 'Cannot checksum stock mac80211.'
[ "${actual%% *}" = 01b40a32346277f30b807d31c4acd7011e18c38bdff594282f5e835d40f40dec ] || fail 'Stock mac80211 differs from captured baseline.'
if [ ! -d /sys/module/mac80211 ]; then
    say 'Temporarily loading the verified stock mac80211 dependency.'
    insmod "$stock_mac" || fail 'Stock mac80211 load failed; do not force-load.'
    own_mac=1
    mac_added=1
fi
# File identity alone cannot identify an already-loaded image. Compare its
# exported build-id note too, before loading any experimental module.
actual=$(sha256sum /sys/module/mac80211/notes/.note.gnu.build-id) || fail 'Cannot verify loaded mac80211 build ID.'
[ "${actual%% *}" = 899f5b3a74a889052e6cd74bf50381e29d67fcd156b09bdfe9baf01add52a7aa ] || fail 'Loaded mac80211 build ID differs from captured baseline.'
before_bind=$(last_bind)
before_unbind=$(last_unbind)
phase=load-provider
insmod "$work/opairshare_wonder_provider.ko" || fail 'Provider load failed.'
own_provider=1
phase=load-probe
insmod "$work/opairshare_route_b_probe.ko" || fail 'Probe load failed.'
own_probe=1
phase=load-master
say 'Loading Wonder master without creating a network interface.'
insmod "$work/wonder.ko" || fail 'Wonder load failed.'
own_master=1
tested=1
[ -d "$master_dev/driver" ] && [ -e "$phy" ] || fail 'Wonder platform probe did not bind/register its PHY.'
bound=$(last_bind)
[ -n "$bound" ] && [ "$bound" != "$before_bind" ] || fail 'No fresh component bind confirmation.'
say 'Initial component binding confirmed.'
[ "$(ls -1 /sys/class/net)" = "$net_before" ] || fail 'A network interface appeared; stopping.'
phase=unregister-live-probe
rmmod opairshare_route_b_probe || fail 'Live probe removal failed.'
own_probe=0
unbound=$(last_unbind)
[ -n "$unbound" ] && [ "$unbound" != "$before_unbind" ] || fail 'No fresh operations-unregister confirmation.'
say 'Operations unregistered while master remains loaded.'
phase=rebind-probe
insmod "$work/opairshare_route_b_probe.ko" || fail 'Probe reload failed.'
own_probe=1
rebound=$(last_bind)
[ -n "$rebound" ] && [ "$rebound" != "$bound" ] || fail 'No fresh component rebind confirmation.'
say 'Component rebind confirmed.'
phase=cleanup
# EXIT handler unloads master, probe, provider, then only our stock dependency.
exit 0
