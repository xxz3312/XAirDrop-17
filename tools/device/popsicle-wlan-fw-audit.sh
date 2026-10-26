#!/system/bin/sh
# Read ordinary firmware/module files only; do not open devices or debugfs.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$#" = 0 ] || { echo 'Usage: sh popsicle-wlan-fw-audit.sh'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || { echo 'Unexpected device.'; exit 1; }
[ "$(getprop ro.build.version.incremental)" = OS4.0.5.0.XPBCNXM ] || { echo 'Firmware changed; collect a fresh device profile first.'; exit 1; }
for tool in sha256sum tar find readlink wc cp cmp ip dmesg tr sort grep basename rm getenforce; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Missing tool: $tool"; exit 1; }
done
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-wlan-fw-$tag
report=/sdcard/Download/17pm-wlan-fw-$tag.tar.gz
mkdir -p "$work/files" /sdcard/Download || exit 1
state() {
    getenforce
    ip link show
    grep -E '^qca_cld3_peach_v2 ' /proc/modules
    for p in /proc/sys/net/wonder/wonder_enable /sys/class/ieee80211/wonder /sys/class/net/xos0; do
        if [ -e "$p" ]; then echo "PRESENT $p"; else echo "ABSENT $p"; fi
    done
}
state > "$work/state-before.txt" 2>&1
{
    getprop ro.product.device
    getprop ro.build.version.incremental
    uname -r
    id
    for p in /sys/module/qca_cld3_peach_v2/version /sys/module/qca_cld3_peach_v2/srcversion /sys/module/firmware_class/parameters/path; do
        if [ -f "$p" ] && [ -r "$p" ]; then printf '%s: ' "$p"; cat "$p"; echo; fi
    done
    readlink -f /sys/class/net/wlan0/device 2>/dev/null
} > "$work/device.txt" 2>&1
# Existing kernel messages only: never enable tracing or issue a WLAN command.
dmesg > "$work/dmesg-all.tmp" 2> "$work/dmesg-errors.txt"
grep -iE 'cnss.*(fw|firmware|target|chip|board)|wlan.*(firmware|fw.ver|fw.build|target.ver)|firmware.*(amss|qwlan|wlanmdsp)|wmi.*(service.ready|service.bitmap|passthru|unsupported|vdev.*type)' "$work/dmesg-all.tmp" > "$work/firmware-log.txt"
rm -f "$work/dmesg-all.tmp"
: > "$work/firmware-candidates.txt"
# Paths used by Android firmware lookup; no partition reads or recursive /sys reads.
for root in /vendor/firmware /vendor/firmware_mnt/image /odm/firmware; do
    [ -d "$root" ] || continue
    find -L "$root" -maxdepth 7 -type f \( -iname 'amss*.bin' -o -iname 'qwlan*.bin' -o -iname 'wlanmdsp.mbn' -o -iname 'wlanmdsp.mdt' -o -iname 'wlanmdsp.b[0-9][0-9]' \) >> "$work/firmware-candidates.txt" 2>> "$work/find-errors.txt"
done
sort -u "$work/firmware-candidates.txt" > "$work/candidates-sorted.txt"
: > "$work/manifest.tsv"
printf 'kind\tsource\tresolved\tbytes\tsha256\tresult\n' > "$work/manifest.tsv"
seen="$work/seen-hashes.txt"
: > "$seen"
firmware_count=0
module_count=0
total=0
limit=134217728
per_file=67108864
copy_candidate() {
    kind=$1
    source=$2
    real=$(readlink -f "$source") || return
    # Resolving a symlink may reach another firmware directory, never /dev or /proc.
    case "$real" in /vendor/*|/odm/*|/vendor_dlkm/*|/odm_dlkm/*|/system_dlkm/*|/mnt/vendor/*) ;; *)
        printf '%s\t%s\t%s\t0\t-\tOUTSIDE_FIRMWARE_MODULE_ROOTS\n' "$kind" "$source" "$real" >> "$work/manifest.tsv"; return;; esac
    [ -f "$real" ] && [ -r "$real" ] || return
    size=$(wc -c < "$real" | tr -d '[:space:]') || return
    case "$size" in ''|*[!0-9]*) return;; esac
    if [ "$size" -eq 0 ] || [ "$size" -gt "$per_file" ] || [ "$((total+size))" -gt "$limit" ]; then
        printf '%s\t%s\t%s\t%s\t-\tSIZE_LIMIT\n' "$kind" "$source" "$real" "$size" >> "$work/manifest.tsv"; return
    fi
    digest=$(sha256sum "$real") || return
    digest=${digest%% *}
    if [ "$kind" = module ] && [ "$(basename "$real")" != qca_cld3_peach_v2.ko ]; then
        printf '%s\t%s\t%s\t%s\t%s\tOTHER_WLAN_VARIANT_NOT_SELECTED\n' "$kind" "$source" "$real" "$size" "$digest" >> "$work/manifest.tsv"; return
    fi
    if [ "$kind" = module ] && [ "$digest" != 202977cadf13b330a21838f3dd222cb0886eb0649d705937a778d7da69085f75 ]; then
        printf '%s\t%s\t%s\t%s\t%s\tSTOCK_MODULE_HASH_CHANGED\n' "$kind" "$source" "$real" "$size" "$digest" >> "$work/manifest.tsv"; return
    fi
    if grep -Fqx "$digest" "$seen"; then
        printf '%s\t%s\t%s\t%s\t%s\tDUPLICATE\n' "$kind" "$source" "$real" "$size" "$digest" >> "$work/manifest.tsv"; return
    fi
    destination="$work/files/$digest-$(basename "$real")"
    cp "$real" "$destination" || return
    copied=$(sha256sum "$destination") || { rm -f "$destination"; return; }
    if [ "${copied%% *}" != "$digest" ]; then
        rm -f "$destination"
        printf '%s\t%s\t%s\t%s\t%s\tCOPY_HASH_MISMATCH\n' "$kind" "$source" "$real" "$size" "$digest" >> "$work/manifest.tsv"; return
    fi
    printf '%s\n' "$digest" >> "$seen"
    total=$((total+size))
    if [ "$kind" = firmware ]; then firmware_count=$((firmware_count+1)); else module_count=$((module_count+1)); fi
    printf '%s\t%s\t%s\t%s\t%s\tCOPIED\n' "$kind" "$source" "$real" "$size" "$digest" >> "$work/manifest.tsv"
}
# Prefer the already audited stock WLAN module before applying the total size cap.
for root in /vendor_dlkm/lib/modules /vendor/lib/modules /odm_dlkm/lib/modules /odm/lib/modules /system_dlkm/lib/modules; do
    [ -d "$root" ] || continue
    find -L "$root" -maxdepth 3 -type f -iname '*qca_cld*.ko' 2>> "$work/find-errors.txt" > "$work/module-candidates.tmp"
    while IFS= read -r file; do copy_candidate module "$file"; done < "$work/module-candidates.tmp"
done
while IFS= read -r file; do copy_candidate firmware "$file"; done < "$work/candidates-sorted.txt"
rm -f "$work/module-candidates.tmp" "$seen"
state > "$work/state-after.txt" 2>&1
unchanged=0
cmp -s "$work/state-before.txt" "$work/state-after.txt" && unchanged=1
status=FIRMWARE_CANDIDATES_COLLECTED_ACTIVE_IMAGE_UNCONFIRMED
[ "$firmware_count" -gt 0 ] || status=NO_FIRMWARE_CANDIDATE_COLLECTED
# ip link may change naturally during collection; report it without claiming the script caused it.
[ "$unchanged" = 1 ] || status=STATE_DIFFERENCE_REVIEW_REQUIRED
printf 'status=%s\nfirmware_files=%s\nstock_module_files=%s\nfile_bytes=%s\nstate_unchanged=%s\nfirmware_passthru_support=UNVERIFIED\n' "$status" "$firmware_count" "$module_count" "$total" "$unchanged" > "$work/result.txt"
cat > "$work/README.txt" <<'NOTE'
Read-only files and existing logs. No module loading, service start, Wi-Fi restart,
interface creation, firmware command, SELinux change or raw partition access.
Candidates may include unused firmware variants. Presence/absence of strings or
files does not prove support or lack of support for PASSTHRU/AWDL.
Split wlanmdsp segments, if present, are candidate files, not proof of active use.
No BDF/calibration, Wi-Fi profiles, passwords or private app directories collected.
NOTE
if tar -czf "$report" -C "$work" .; then
    echo "$status"
    echo "Report: $report"
    echo "Firmware candidates: $firmware_count; stock module: $module_count; bytes: $total"
    echo 'Candidate identity and offline inspection only; PASSTHRU support remains unverified.'
else
    echo "Packaging failed. Files: $work"
    exit 1
fi
