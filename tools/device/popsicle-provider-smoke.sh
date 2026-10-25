#!/system/bin/sh
# Temporary private provider/probe registration test; no radio backend or master.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run this script with su.'; exit 1; }
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-provider-smoke-$tag
report=/sdcard/Download/17pm-provider-result-$tag.tar.gz
device=/sys/bus/platform/devices/qcom,cnss-vendor-wlan-wonder
mkdir -p "$work" /sdcard/Download || exit 1
chmod 700 "$work" || exit 1
owned_provider=0
owned_probe=0
tested=0
phase=preflight
exec 3>&1
exec >"$work/test.log" 2>&1
say() { printf '%s\n' "$*"; printf '%s\n' "$*" >&3; }
fail() { say "FAIL: $*"; exit 1; }
snapshot() {
    dmesg 2>&1 | grep -iE 'opairshare|cnss-vendor-wlan-wonder|unknown symbol|disagrees|version magic|cfi failure|oops:|kernel panic|avc:.*module_load' | tail -n 160
}
finish() {
    rc=$1
    trap - 0 1 2 15
    if [ "$owned_probe" = 1 ]; then
        if rmmod opairshare_route_b_probe; then
            owned_probe=0
            say 'Probe unloaded; callbacks deregistered.'
        else
            rc=1
            say 'FAIL: probe unload failed; keeping its provider loaded. Save report and reboot.'
        fi
    fi
    if [ "$owned_provider" = 1 ] && [ "$owned_probe" = 0 ]; then
        if rmmod opairshare_wonder_provider; then
            owned_provider=0
            say 'Provider unloaded.'
        else
            rc=1
            say 'FAIL: provider unload failed. Save report and reboot.'
        fi
    fi
    if [ "$tested" = 1 ] && [ "$owned_provider" = 0 ] && [ "$owned_probe" = 0 ]; then
        if [ -e "$device" ] || [ -d /sys/module/opairshare_wonder_provider ] ||
           [ -d /sys/module/opairshare_route_b_probe ]; then
            rc=1
            say 'FAIL: private device or module remains after unload.'
        fi
    fi
    if [ ! -d /sys/module/qca_cld3_peach_v2 ]; then
        rc=1
        say 'FAIL: expected stock WLAN module is absent.'
    fi
    snapshot >"$work/dmesg-after.txt"
    if [ "$rc" = 0 ] && [ "$tested" = 1 ]; then
        status=PASS_PROVIDER_PROBE_REGISTER_UNREGISTER
    else
        status=FAIL_OR_INTERRUPTED
    fi
    printf 'status=%s\nphase=%s\nexit_code=%s\nprovider_still_owned=%s\nprobe_still_owned=%s\n' \
        "$status" "$phase" "$rc" "$owned_provider" "$owned_probe" >"$work/result.txt"
    say "$status (registration lifecycle only; no wireless traffic tested)"
    if tar -czf "$report" -C "$work" device.txt result.txt test.log dmesg-before.txt dmesg-after.txt; then
        printf 'Upload report: %s\n' "$report" >&3
    else
        printf 'Could not package report; root-readable logs: %s\n' "$work" >&3
        rc=1
    fi
    exit "$rc"
}
trap 'finish $?' 0
trap 'exit 130' 1 2 15
{
    getprop ro.product.device
    getprop ro.build.version.incremental
    uname -r
} >"$work/device.txt"
snapshot >"$work/dmesg-before.txt"
for tool in insmod rmmod sha256sum tar cp chmod; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing command: $tool"
done
[ "$(getprop ro.product.device)" = popsicle ] || fail 'Unexpected device.'
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || fail 'Unexpected firmware.'
[ "$(uname -r)" = 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k ] || fail 'Unexpected kernel.'
[ -d /sys/module/qca_cld3_peach_v2 ] || fail 'Expected stock WLAN module not loaded.'
[ ! -e /proc/sys/net/wonder/wonder_enable ] || fail 'Wonder node already exists; leave existing setup untouched.'
[ ! -d /sys/module/wonder ] || fail 'A Wonder master is already loaded.'
[ ! -e "$device" ] || fail 'Wonder platform device already exists.'
for name in opairshare_wonder_provider opairshare_route_b_probe; do
    [ ! -d "/sys/module/$name" ] || fail "Already loaded: $name"
    case "$name" in
        opairshare_wonder_provider) expected=8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a ;;
        *) expected=158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade ;;
    esac
    actual=$(sha256sum "$src/$name.ko") || fail "Missing module: $name"
    [ "${actual%% *}" = "$expected" ] || fail "Checksum mismatch: $name"
    cp "$src/$name.ko" "$work/$name.ko" || fail "Cannot stage $name"
    chmod 600 "$work/$name.ko" || fail "Cannot set mode for $name"
    actual=$(sha256sum "$work/$name.ko") || fail "Cannot checksum staged $name"
    [ "${actual%% *}" = "$expected" ] || fail "Staged checksum mismatch: $name"
done
phase=load-provider
say 'Loading private provider only.'
insmod "$work/opairshare_wonder_provider.ko" || fail 'Provider load failed; do not force-load.'
owned_provider=1
[ -d /sys/module/opairshare_wonder_provider ] || fail 'Provider module absent after load.'
[ -e "$device" ] || fail 'Provider platform device absent.'
phase=load-probe
say 'Loading probe to exercise duplicate-registration and competing-owner checks.'
insmod "$work/opairshare_route_b_probe.ko" || fail 'Probe checks/load failed.'
owned_probe=1
tested=1
[ -d /sys/module/opairshare_route_b_probe ] || fail 'Probe module absent after load.'
phase=unload-probe-then-provider
# EXIT handler always unloads in dependency order and packages the result.
exit 0
