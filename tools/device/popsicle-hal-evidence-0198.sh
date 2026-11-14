#!/system/bin/sh
# Read-only system queries and copies; original transaction/module files stay unchanged.
set -eu
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
[ "$#" = 0 ] && [ "$(id -u)" = 0 ] || exit 2
xh_state=/data/adb/xairdrop17-cycle0195-transaction
xh_module=/data/adb/modules/xairdrop17_cycle0195
xh_output=/sdcard/Download/xairdrop-0198-evidence.tar.gz
[ ! -e /dev/xairdrop17-wlan-trial.lock ] && [ ! -L /dev/xairdrop17-wlan-trial.lock ] || { echo CYCLE_LOCK_PRESENT_NO_CAPTURE; exit 1; }
xh_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    xh_mode=$(stat -c %a "$1") || return 1
    case "$xh_mode" in ''|*[!0-7]*|*[2367][0-7]|*[0-7][2367]) return 1;; esac
    case "${#xh_mode}" in 3|4) ;; *) return 1;; esac
}
for xh_dir in /data/adb "$xh_state" /data/adb/modules "$xh_module"; do [ -d "$xh_dir" ] && xh_private "$xh_dir" || exit 1; done
for xh_required in phase boot-id manifest.sha256 commands.log; do [ -f "$xh_state/$xh_required" ] && xh_private "$xh_state/$xh_required" || exit 1; done
umask 077
xh_tmp=$(mktemp -d /data/local/tmp/xairdrop-0198.XXXXXX)
trap 'rm -rf -- "$xh_tmp"' 0
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
: > "$xh_tmp/original.sha256"
: > "$xh_tmp/capture-notes.txt"
for xh_file in phase phase.new boot-id manifest.sha256 wifi.before scan.before hals interface.before commands.log kernel.before.log kernel.after.log; do
    if [ -e "$xh_state/$xh_file" ] || [ -L "$xh_state/$xh_file" ]; then
        [ -f "$xh_state/$xh_file" ] && xh_private "$xh_state/$xh_file" || exit 1
        sha256sum "$xh_state/$xh_file" >> "$xh_tmp/original.sha256"
        cp "$xh_state/$xh_file" "$xh_tmp/$xh_file"
        cmp -s "$xh_state/$xh_file" "$xh_tmp/$xh_file"
    else printf 'MISSING:%s\n' "$xh_file" >> "$xh_tmp/capture-notes.txt"; fi
done
for xh_file in module.prop deployment.tsv SHA256SUMS; do
    [ -f "$xh_module/$xh_file" ] && xh_private "$xh_module/$xh_file" || exit 1
    cp "$xh_module/$xh_file" "$xh_tmp/installed-$xh_file"
done
{
    date '+%Y-%m-%dT%H:%M:%S%z'
    cat /proc/uptime /proc/sys/kernel/random/boot_id
    getprop ro.build.version.incremental
    getprop init.svc.vendor.wifi_hal_legacy
    getprop init.svc_debug_pid.vendor.wifi_hal_legacy
    for xh_m in cnss2 qca_cld3_peach_v2 opairshare_wonder_provider; do
        printf 'MODULE:%s\n' "$xh_m"
        if [ -d "/sys/module/$xh_m" ]; then
            cat "/sys/module/$xh_m/initstate"; sha256sum "/sys/module/$xh_m/notes/.note.gnu.build-id"
        else echo ABSENT; fi
    done
} > "$xh_tmp/current-state.txt" 2>&1
for xh_service in wifi wifiscanner wifip2p; do
    {
        echo "CAPTURE_BEGIN:$xh_service"
        if /system/bin/dumpsys -t 15 "$xh_service"; then xh_rc=0; else xh_rc=$?; fi
        echo "CAPTURE_END:$xh_service:rc=$xh_rc"
    } 2>&1 | cat > "$xh_tmp/framework-$xh_service.txt"
done
{
    echo CAPTURE_BEGIN:logcat
    if /system/bin/logcat -b all -d -v threadtime; then xh_rc=0; else xh_rc=$?; fi
    echo "CAPTURE_END:logcat:rc=$xh_rc"
} 2>&1 | grep -Ei 'wifi|wlan|servicemanager|CAPTURE_(BEGIN|END)' > "$xh_tmp/framework-logcat.txt"
sha256sum -c "$xh_tmp/original.sha256" > "$xh_tmp/original-verified-before-export.txt"
tar -czf "$xh_output" -C "$xh_tmp" .
sha256sum -c "$xh_tmp/original.sha256"
printf 'EVIDENCE_EXPORTED:%s\n' "$xh_output"
