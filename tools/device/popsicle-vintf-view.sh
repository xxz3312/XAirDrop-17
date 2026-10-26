#!/system/bin/sh
# Read-only view comparison. Does not launch XOS, refresh caches or modify mounts.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || { echo 'Expected popsicle.'; exit 1; }
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-vintf-view-$tag
report=/sdcard/Download/17pm-vintf-view-$tag.tar.gz
mkdir -p "$work" /sdcard/Download || exit 1
{
    date
    getprop ro.product.device
    getprop ro.build.version.incremental
    uname -r
    cat /proc/uptime
    cat /proc/sys/kernel/random/boot_id
    id
    ps -AZ | grep -E 'servicemanager|ksud'
    for name in vintf checkvintf lshal nsenter; do command -v "$name"; done
    for file in /data/adb/modules/xairdrop17_xos_vintf/module.prop /data/adb/modules/xairdrop17_xos_vintf/disable /data/adb/modules_update/xairdrop17_xos_vintf/module.prop; do
        [ ! -e "$file" ] || ls -lZ "$file"
    done
} > "$work/device.txt" 2>&1
VIEW_CODE=$(cat <<'VIEW'
manifest=/vendor/etc/vintf/manifest/manifest_xairdrop17_xos.xml
echo '== mount namespace =='
readlink /proc/self/ns/mnt
echo '== VINTF fragment =='
if [ -r "$manifest" ]; then echo fragment_readable=1; else echo fragment_readable=0; fi
ls -ldZ /vendor/etc/vintf/manifest
ls -lZ "$manifest"
sha256sum "$manifest"
cat "$manifest"
echo '== APEX manifest cache input =='
stat -c '%n dev=%d inode=%i mtime=%Y mode=%a uid=%u gid=%g' /apex/apex-info-list.xml
sha256sum /apex/apex-info-list.xml
echo '== XOS declarations in system configuration =='
for dir in /vendor/etc/vintf /odm/etc/vintf /system/etc/vintf /system_ext/etc/vintf; do
    [ ! -d "$dir" ] || grep -RinE 'com.domestic.xoscomm|IDomesticXOsComm' "$dir"
done
echo '== selected mount topology =='
grep -E ' /vendor | /system | /vendor/etc/vintf| /system/vendor| - overlay ' /proc/self/mountinfo
echo view_commands_completed
VIEW
)
/system/bin/sh -c "$VIEW_CODE" > "$work/caller-view.txt" 2>&1
if command -v nsenter >/dev/null 2>&1; then
    nsenter -t 1 -m -- /system/bin/sh -c "$VIEW_CODE" > "$work/init-view.txt" 2>&1
    printf 'init_view_exit=%s\n' "$?" > "$work/result.txt"
    pids=$(pidof servicemanager)
    if [ -z "$pids" ]; then echo 'servicemanager_pid_not_found' >> "$work/result.txt"; fi
    for pid in $pids; do
        case "$pid" in *[!0-9]*|'') continue;; esac
        {
            echo "pid=$pid"
            readlink "/proc/$pid/exe"
            readlink "/proc/$pid/ns/mnt"
            cat "/proc/$pid/attr/current"
        } > "$work/servicemanager-$pid-process.txt" 2>&1
        nsenter -t "$pid" -m -- /system/bin/sh -c "$VIEW_CODE" > "$work/servicemanager-$pid-view.txt" 2>&1
        printf 'servicemanager_%s_view_exit=%s\n' "$pid" "$?" >> "$work/result.txt"
    done
else
    echo 'nsenter_unavailable' > "$work/result.txt"
fi
# Relevant retained log messages; this command never clears the log buffer.
logcat -b all -d -v threadtime -t 5000 '*:V' 2> "$work/logcat-errors.txt" |
    grep -iE 'xoscomm|manifest_xairdrop17|libvintf|VINTF declaration error|Failed to (parse|fetch).*manifest' |
    tail -n 150 > "$work/vintf-log.txt"
echo 'status=READ_ONLY_VIEW_EVIDENCE_NO_SERVICE_OR_CACHE_CHANGES' >> "$work/result.txt"
if tar -czf "$report" -C "$work" .; then
    echo "Report: $report"
else
    echo "Packaging failed; files retained at $work"
    exit 1
fi
