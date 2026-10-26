#!/system/bin/sh
# Opens normal MiShare settings and queries policy; does not impersonate the app.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$#" = 1 ] || { echo 'Usage: sh popsicle-xos-policy-audit.sh /path/to/probe-bundle'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || exit 1
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || { echo 'Firmware changed; fresh audit required.'; exit 1; }
bundle=$1
[ -f "$bundle/build.json" ] || exit 1
(cd "$bundle" && sha256sum -c policy.sha256) || exit 1
actual=$(sha256sum /system/lib64/libselinux.so) || exit 1
[ "${actual%% *}" = 45a2097adc900fb2dd877fa088dd9a04fac21c85957432af3647b2284a72961c ] || { echo 'libselinux changed; fresh audit required.'; exit 1; }
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-xos-policy-$tag
report=/sdcard/Download/17pm-xos-policy-$tag.tar.gz
mkdir -p "$work" /sdcard/Download || exit 1
cp "$bundle/xos-policy-probe" "$bundle/policy.sha256" "$work/" || exit 1
(cd "$work" && sha256sum -c policy.sha256) || exit 1
chmod 0500 "$work/xos-policy-probe" || exit 1
cp "$bundle/build.json" "$work/" || exit 1
{
    getprop ro.product.device
    getprop ro.build.version.incremental
    id
    getenforce
} > "$work/device.txt" 2>&1
getenforce > "$work/enforce-before.txt"
sha256sum /sys/fs/selinux/policy > "$work/policy-before.sha256" 2> "$work/policy-hash-errors.txt"
am start -n com.miui.mishare.connectivity/com.miui.mishare.activity.MiShareSettingsActivity > "$work/activity.txt" 2>&1
sleep 2
ps -AZ | grep -i mishare > "$work/mishare-processes.txt"
valid=0
: > "$work/identities.txt"
for pid in $(pidof com.miui.mishare.connectivity com.miui.mishare.connectivity:ui); do
    case "$pid" in *[!0-9]*|'') continue;; esac
    context=$(tr -d '\000' < "/proc/$pid/attr/current")
    uid=$(awk '/^Uid:/{print $2}' "/proc/$pid/status")
    printf 'pid=%s uid=%s context=%s\n' "$pid" "$uid" "$context" >> "$work/identities.txt"
    [ "$uid" = 10132 ] && [ "$context" = u:r:platform_app_36:s0:c512,c768 ] && valid=1
done
if [ "$valid" = 1 ]; then
    (
        unset LD_PRELOAD LD_AUDIT LD_DEBUG LD_LIBRARY_PATH
        timeout 15 "$work/xos-policy-probe" u:r:platform_app_36:s0:c512,c768
    ) > "$work/policy-query.txt" 2>&1
    probe_rc=$?
else
    echo 'No live MiShare process matched the captured identity; no policy queries made.' > "$work/policy-query.txt"
    probe_rc=2
fi
getenforce > "$work/enforce-after.txt"
sha256sum /sys/fs/selinux/policy > "$work/policy-after.sha256" 2>> "$work/policy-hash-errors.txt"
printf 'status=POLICY_QUERY_ONLY_NOT_APP_BINDER_TEST\nprobe_exit=%s\n' "$probe_rc" > "$work/result.txt"
rm -f "$work/xos-policy-probe"
if tar -czf "$report" -C "$work" .; then echo "Report: $report"; else echo "Packaging failed; files at $work"; exit 1; fi
