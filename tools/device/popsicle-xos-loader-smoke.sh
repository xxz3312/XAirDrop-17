#!/system/bin/sh
# Run RTLD_NOW/dlsym in a bounded subprocess. Library constructors DO execute.
# Never call XOS functions or start the service; no modules, mounts or policy changes.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$#" = 2 ] || { echo 'Usage: sh popsicle-xos-loader-smoke.sh /path/to/XAirDrop-1.0.zip /path/to/probe-bundle'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || exit 1
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || { echo 'Firmware changed; collect a fresh audit first.'; exit 1; }
for tool in sha256sum unzip timeout tar cmp cp chmod; do command -v "$tool" >/dev/null 2>&1 || { echo "Missing tool: $tool"; exit 1; }; done
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
# Refuse an existing radio/service setup. This check never enables availability.
for item in /proc/sys/net/wonder/wonder_enable /sys/class/ieee80211/wonder /sys/class/net/xos0; do
    [ ! -e "$item" ] || { echo "Existing XOS/Wonder state: $item; stopped."; exit 1; }
done
service check com.domestic.xoscomm.IDomesticXOsComm/default | grep -q ': not found' || { echo 'XOS service already present or status unknown; stopped.'; exit 1; }
bundle=$2
[ -f "$bundle/xos-loader-probe" ] && [ -f "$bundle/probe.sha256" ] || { echo 'Probe bundle missing.'; exit 1; }
(cd "$bundle" && sha256sum -c probe.sha256) || exit 1
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-xos-loader-$tag
stage=$work/reference
report=/sdcard/Download/17pm-xos-loader-$tag.tar.gz
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
# Copy the CI-built probe to private storage and recheck after copying.
cp "$bundle/xos-loader-probe" "$work/xos-loader-probe" || exit 1
cp "$bundle/probe.sha256" "$work/probe.sha256" || exit 1
(cd "$work" && sha256sum -c probe.sha256) || exit 1
chmod 0500 "$work/xos-loader-probe" || exit 1
(
    unset LD_PRELOAD LD_AUDIT LD_DEBUG LD_LIBRARY_PATH
    export LD_LIBRARY_PATH="$stage:/system/lib64"
    timeout 15 "$work/xos-loader-probe" "$stage"
) > "$work/report/probe.txt" 2>&1
probe_rc=$?
cp "$bundle/build.json" "$work/report/" || exit 1
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
[ "$probe_rc" = 0 ] && [ "$unchanged" = 1 ] &&
    grep -qx PASS_DLOPEN_DLSYM_ONLY_NO_SERVICE_OR_RADIO_CALLS "$work/report/probe.txt" && status=PASS_DLOPEN_DLSYM_ONLY
printf 'status=%s\nprobe_exit=%s\nstate_unchanged=%s\n' "$status" "$probe_rc" "$unchanged" > "$work/report/result.txt"
# Do not distribute donor binary files in the report.
rm -f "$stage/DomesticXOsComm" "$stage/com.domestic.xoscomm-V1-ndk.so" "$stage/libxos.so" "$stage/libev.so"
rmdir "$stage" 2>/dev/null
if tar -czf "$report" -C "$work/report" .; then
    echo "$status"
    echo "Report: $report"
    echo 'dlopen/dlsym only; constructors ran, XOS entry points were not called.'
else
    echo "Packaging failed. Logs: $work/report"
    exit 1
fi
[ "$status" = PASS_DLOPEN_DLSYM_ONLY ]
