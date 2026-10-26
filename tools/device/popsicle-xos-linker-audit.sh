#!/system/bin/sh
# List native dependency paths only. Never invoke donor entry points or constructors.
# Bionic --list skips relocation too: success does NOT validate symbol resolution.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$#" = 1 ] || { echo 'Usage: sh popsicle-xos-linker-audit.sh /path/to/XAirDrop-1.0.zip'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || exit 1
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || { echo 'Firmware changed; collect a fresh audit first.'; exit 1; }
for tool in sha256sum unzip timeout tar cmp; do command -v "$tool" >/dev/null 2>&1 || { echo "Missing tool: $tool"; exit 1; }; done
check_hash() { actual=$(sha256sum "$1") || return 1; [ "${actual%% *}" = "$2" ]; }
check_hash /system/bin/linker64 e6d7b18d770a8159e0670ca81e5357d10c47a56052db2e7d964c4da16498d305 || { echo 'Unexpected linker; stopped.'; exit 1; }
check_hash "$1" 64e81b259b920fd3946cf8b882089a607d9a01c07b240362044f108bf9d54419 || { echo 'Reference archive changed; stopped.'; exit 1; }
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-xos-linker-$tag
stage=$work/reference
report=/sdcard/Download/17pm-xos-linker-$tag.tar.gz
mkdir -p "$stage" "$work/report" /sdcard/Download || exit 1
# Verify all files before passing anything to the system linker. No executable bit.
extract() {
    unzip -p "$1" "xos/$2" > "$stage/$2" || return 1
    check_hash "$stage/$2" "$3" || return 1
    chmod 0400 "$stage/$2"
}
extract "$1" DomesticXOsComm 292827f7b433ec05a53ee198ca332e2cb3d5cea35571acd7abde130472bfde3d &&
extract "$1" com.domestic.xoscomm-V1-ndk.so f037bcea28e3dedf2a341cdc750d6b366a97be6f0aa837979b25a1c9f0e8f3ce &&
extract "$1" libxos.so a89bc4f3ed4734269ba576d5c128218c22ab778b6920c37236046c1129a69685 &&
extract "$1" libev.so 554dac637dcbca577da882260fe56b376893573b9f6ea9e77303021a3901cb0e || { echo 'Reference extraction/hash failed; stopped.'; exit 1; }
state() {
    service check com.domestic.xoscomm.IDomesticXOsComm/default
    ls -1 /sys/class/net
    for file in /proc/sys/net/wonder/wonder_enable /sys/class/ieee80211/wonder; do
        if [ -e "$file" ]; then echo "PRESENT $file"; else echo "ABSENT $file"; fi
    done
}
state > "$work/report/state-before.txt" 2>&1
{
    getprop ro.product.device
    getprop ro.build.version.incremental
    id
    sha256sum /system/bin/linker64
} > "$work/report/device.txt" 2>&1
# Inference tested in an isolated /data/local/tmp namespace, not an installed service.
# No LD_PRELOAD or extra environment is inherited by the linker subprocess.
list_only() (
    unset LD_PRELOAD LD_AUDIT LD_DEBUG LD_LIBRARY_PATH
    export LD_LIBRARY_PATH="$stage:/system/lib64"
    timeout 15 /system/bin/linker64 --list "$stage/$1"
)
list_only DomesticXOsComm > "$work/report/daemon-list.txt" 2>&1
daemon_rc=$?
list_only libxos.so > "$work/report/libxos-list.txt" 2>&1
libxos_rc=$?
# Capture the outstanding dependency for full offline symbol analysis.
mkdir -p "$work/report/libs/system/lib64" || exit 1
if [ -f /system/lib64/libapexsupport.so ]; then
    cp -L /system/lib64/libapexsupport.so "$work/report/libs/system/lib64/" || exit 1
    sha256sum /system/lib64/libapexsupport.so > "$work/report/libapexsupport-sha256.txt"
fi
state > "$work/report/state-after.txt" 2>&1
unchanged=0
cmp -s "$work/report/state-before.txt" "$work/report/state-after.txt" && unchanged=1
status=FAIL_OR_INCOMPLETE
[ "$daemon_rc" = 0 ] && [ "$libxos_rc" = 0 ] && [ "$unchanged" = 1 ] && status=PASS_DEPENDENCY_PATHS_ONLY
printf 'status=%s\ndaemon_list_exit=%s\nlibxos_list_exit=%s\nstate_unchanged=%s\n' "$status" "$daemon_rc" "$libxos_rc" "$unchanged" > "$work/report/result.txt"
# Do not distribute donor binary files in the report.
rm -f "$stage/DomesticXOsComm" "$stage/com.domestic.xoscomm-V1-ndk.so" "$stage/libxos.so" "$stage/libev.so"
rmdir "$stage" 2>/dev/null
if tar -czf "$report" -C "$work/report" .; then
    echo "$status"
    echo "Report: $report"
    echo 'Dependency listing only; no service registration, radio start or MiShare patch.'
else
    echo "Packaging failed. Logs: $work/report"
    exit 1
fi
[ "$status" = PASS_DEPENDENCY_PATHS_ONLY ]
