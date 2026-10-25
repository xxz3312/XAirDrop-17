#!/system/bin/sh
# First device test: one temporary sysctl module; no radio or availability enable.
set -u

if [ "$(id -u)" != 0 ]; then
    echo 'Run with su -c "sh /path/to/run-test.sh"'
    exit 1
fi
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-sysctl-smoke-$tag
report=/sdcard/Download/17pm-sysctl-result-$tag.tar.gz
mkdir -p "$work" /sdcard/Download || exit 1
chmod 700 "$work" || exit 1
owned=0
tested=0
phase=preflight
exec 3>&1
exec >"$work/test.log" 2>&1

say() { printf '%s\n' "$*"; printf '%s\n' "$*" >&3; }
fail() { say "FAIL: $*"; exit 1; }
snapshot() {
    dmesg 2>&1 | grep -iE 'wonder|sysctl|module|vermagic|unknown symbol|disagrees|cfi|avc:|denied' | tail -n 160
}
finish() {
    rc=$1
    trap - 0 1 2 15
    if [ "$owned" = 1 ]; then
        if rmmod wonder_sysctl; then
            owned=0
            say 'Temporary module unloaded.'
        else
            rc=1
            say 'FAIL: could not unload wonder_sysctl; save this report and reboot to clear it.'
        fi
    fi
    if [ "$tested" = 1 ] && [ "$owned" = 0 ]; then
        if [ -e /proc/sys/net/wonder/wonder_enable ] || [ -d /sys/module/wonder_sysctl ]; then
            rc=1
            say 'FAIL: module or node still present after unload.'
        fi
    fi
    snapshot >"$work/dmesg-after.txt"
    if [ "$rc" = 0 ] && [ "$tested" = 1 ]; then
        status=PASS_SYSCTL_LOAD_READ_UNLOAD
    else
        status=FAIL_OR_INTERRUPTED
    fi
    printf 'status=%s\nphase=%s\nexit_code=%s\nmodule_still_owned=%s\n' \
        "$status" "$phase" "$rc" "$owned" >"$work/result.txt"
    say "$status (no radio or AirDrop functionality tested)"
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
for tool in insmod rmmod sha256sum tar cat cp chmod; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing command: $tool"
done
[ "$(getprop ro.product.device)" = popsicle ] || fail 'Unexpected device.'
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || fail 'Unexpected firmware; do not bypass this check.'
[ "$(uname -r)" = 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k ] || fail 'Unexpected running kernel.'
[ ! -e /proc/sys/net/wonder/wonder_enable ] || fail 'Wonder node already exists; leaving it untouched.'
[ ! -d /sys/module/wonder_sysctl ] || fail 'Module already loaded; leaving it untouched.'
[ -f "$src/wonder_sysctl.ko" ] || fail 'Extract the complete ZIP before running.'
expected=b7ac3e8dd7d3544cfdfe67ea39b3b546fcc734897fe64478f20a88893532f625
actual=$(sha256sum "$src/wonder_sysctl.ko") || fail 'Cannot checksum module.'
[ "${actual%% *}" = "$expected" ] || fail 'Module checksum mismatch.'
cp "$src/wonder_sysctl.ko" "$work/wonder_sysctl.ko" || fail 'Cannot stage module.'
chmod 600 "$work/wonder_sysctl.ko" || fail 'Cannot set staged file mode.'
actual=$(sha256sum "$work/wonder_sysctl.ko") || fail 'Cannot checksum staged module.'
[ "${actual%% *}" = "$expected" ] || fail 'Staged module checksum mismatch.'

phase=insmod
say 'Loading wonder_sysctl only; default availability must remain 0.'
insmod "$work/wonder_sysctl.ko" || fail 'insmod failed; see the report. Do not force-load.'
owned=1
tested=1
phase=read-node
value=$(cat /proc/sys/net/wonder/wonder_enable) || fail 'Wonder node is missing/unreadable.'
say "wonder_enable=$value"
[ "$value" = 0 ] || fail 'Unexpected availability value.'
phase=unload
# The EXIT handler unloads our module, checks removal and saves the report.
exit 0
