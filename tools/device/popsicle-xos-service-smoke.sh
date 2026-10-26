#!/system/bin/sh
# Temporarily run the service entry point to diagnose registration only.
# Do not call start/status/stop, change VINTF/SELinux, or enable radio availability.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$#" = 1 ] || { echo 'Usage: sh popsicle-xos-service-smoke.sh /path/to/XAirDrop-1.0.zip'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || exit 1
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || { echo 'Firmware changed; collect a fresh audit first.'; exit 1; }
for tool in sha256sum unzip tar cmp pidof kill sleep logcat readlink; do command -v "$tool" >/dev/null 2>&1 || { echo "Missing tool: $tool"; exit 1; }; done
check_hash() {
    actual=$(sha256sum "$1") || return 1
    actual=${actual%% *}
    if [ "$actual" != "$2" ]; then
        printf 'Hash mismatch: %s\nexpected=%s\nactual=%s\n' "$1" "$2" "$actual" >&2
        return 1
    fi
}
check_hash /system/bin/linker64 b6dd216b7a775b8f04c825cada286bfe7ddaeecf2c0c10e617287118965abc00 || { echo 'Unexpected linker; stopped.'; exit 1; }
check_hash "$1" 64e81b259b920fd3946cf8b882089a607d9a01c07b240362044f108bf9d54419 || { echo 'Reference archive changed; stopped.'; exit 1; }
SVC=com.domestic.xoscomm.IDomesticXOsComm/default
for item in /proc/sys/net/wonder/wonder_enable /sys/class/ieee80211/wonder /sys/class/net/xos0; do
    [ ! -e "$item" ] || { echo "Existing XOS/Wonder state: $item; stopped."; exit 1; }
done
service check "$SVC" | grep -q ': not found' || { echo 'Existing service or status unknown; stopped.'; exit 1; }
[ -r /proc/self/exe ] && readlink /proc/self/exe >/dev/null || { echo 'Process ownership inspection unavailable; stopped.'; exit 1; }
[ -z "$(pidof DomesticXOsComm)" ] || { echo 'Existing service process; stopped.'; exit 1; }
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-xos-service-$tag
stage=$work/reference
report=/sdcard/Download/17pm-xos-service-$tag.tar.gz
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
# Run only our own process, with no restart loop or changes to service policy.
# It may abort because VINTF or SELinux is not configured; that is diagnostic evidence.
chmod 0500 "$stage/DomesticXOsComm" || exit 1
service_pid=
log_pid=
owns_service() {
    [ -n "$service_pid" ] && [ "$(readlink "/proc/$service_pid/exe" 2>/dev/null)" = "$stage/DomesticXOsComm" ]
}
cleanup() {
    if owns_service && kill -0 "$service_pid" 2>/dev/null; then
        kill -TERM "$service_pid" 2>/dev/null
        n=0
        while owns_service && kill -0 "$service_pid" 2>/dev/null && [ "$n" -lt 3 ]; do sleep 1; n=$((n+1)); done
        if owns_service && kill -0 "$service_pid" 2>/dev/null; then kill -KILL "$service_pid" 2>/dev/null; fi
    fi
    if [ -n "$log_pid" ]; then kill "$log_pid" 2>/dev/null; wait "$log_pid" 2>/dev/null; log_pid=; fi
}
trap 'cleanup; exit 130' 1 2 15
trap cleanup 0
# Record the phone's own logcat timestamp before launch. A post-exit dump avoids
# losing diagnostics when the daemon exits before a streaming logcat is attached.
start_time=$(date '+%m-%d %H:%M:%S.000')
(
    unset LD_PRELOAD LD_AUDIT LD_DEBUG LD_LIBRARY_PATH
    export LD_LIBRARY_PATH="$stage:/system/lib64"
    exec "$stage/DomesticXOsComm"
) > "$work/report/daemon.txt" 2>&1 &
service_pid=$!
observed_pid=$service_pid
registered=0
: > "$work/report/service-observations.txt"
n=0
while [ "$n" -lt 5 ]; do
    service check "$SVC" >> "$work/report/service-observations.txt" 2>&1
    service check "$SVC" | grep -q ': found' && registered=1
    kill -0 "$service_pid" 2>/dev/null || break
    sleep 1
    n=$((n+1))
done
ps -AZ | grep -E 'DomesticXOsComm|mishare' > "$work/report/processes.txt"
cleanup
if kill -0 "$service_pid" 2>/dev/null; then
    service_rc=125
    echo "Owned process not confirmed stopped: $service_pid" >> "$work/report/daemon.txt"
else
    wait "$service_pid" 2>/dev/null
    service_rc=$?
    service_pid=
fi
# Allow Android's log transport to deliver a fast-exit process's final messages.
sleep 1
collect_registration_log() {
    logcat -b all -d -v threadtime -T "$start_time" '*:V' 2> "$work/report/logcat-errors.txt" |
        grep -iE "DomesticXOs|xoscomm|libxos|servicemanager|LazyServiceRegistrar|VINTF|avc:.*denied|CANNOT LINK EXECUTABLE|[[:space:]]$observed_pid[[:space:]]" |
        tail -n 300 > "$work/report/registration-log.txt"
}
collect_registration_log
printf 'start_time=%s\nservice_pid=%s\n' "$start_time" "$observed_pid" > "$work/report/log-window.txt"
# Capture the outstanding dependency for full offline symbol analysis.
mkdir -p "$work/report/libs/system/lib64" || exit 1
if [ -f /system/lib64/libapexsupport.so ]; then
    cp -L /system/lib64/libapexsupport.so "$work/report/libs/system/lib64/" || exit 1
    sha256sum /system/lib64/libapexsupport.so > "$work/report/libapexsupport-sha256.txt"
fi
state > "$work/report/state-after.txt" 2>&1
unchanged=0
cmp -s "$work/report/state-before.txt" "$work/report/state-after.txt" && unchanged=1
status=REGISTRATION_BLOCKED_OR_NOT_OBSERVED
[ "$registered" = 1 ] && status=REGISTERED_ONLY_NOT_CLIENT_OR_RADIO_TESTED
[ "$unchanged" = 1 ] || status=STATE_CHANGED_REVIEW_REQUIRED
if [ -n "$(pidof DomesticXOsComm)" ]; then status=SERVICE_REMAINS_REVIEW_REQUIRED; fi
printf 'status=%s\nregistered_observed=%s\nservice_exit=%s\nstate_unchanged=%s\n' "$status" "$registered" "$service_rc" "$unchanged" > "$work/report/result.txt"
# Do not distribute donor binary files in the report.
if [ -z "$service_pid" ]; then
    rm -f "$stage/DomesticXOsComm" "$stage/com.domestic.xoscomm-V1-ndk.so" "$stage/libxos.so" "$stage/libev.so"
    rmdir "$stage" 2>/dev/null
else
    echo "Temporary service files retained at $stage; inspect report and reboot if process remains."
fi
if tar -czf "$report" -C "$work/report" .; then
    echo "$status"
    echo "Report: $report"
    echo 'Registration diagnostic only. No VINTF/SELinux changes or wireless entry point calls.'
else
    echo "Packaging failed. Logs: $work/report"
    exit 1
fi
[ "$status" = REGISTERED_ONLY_NOT_CLIENT_OR_RADIO_TESTED ]
