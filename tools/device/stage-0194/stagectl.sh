#!/system/bin/sh
# Only observation and atomic stock backup. No driver/service mutation entry point.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
SC_ACTION=${1:-check}
[ "$#" -le 1 ] || exit 2
case "$SC_ACTION" in check|status|backup) ;; *) echo 'Allowed: check|status|backup; loading disabled'; exit 2;; esac
[ "$(id -u)" = 0 ] || exit 1
SC_WLAN=qca_cld3_peach_v2
SC_PROVIDER=opairshare_wonder_provider
SC_STATE=/data/adb/xairdrop17-stage0194-backup
SC_LOCK=/dev/xairdrop17-wlan-trial.lock
SC_LOG=
SC_OWN=0
case "$0" in */*) sc_dir=${0%/*};; *) exit 2;; esac
SC_BUNDLE=$(CDPATH= cd -- "$sc_dir" && pwd -P) || exit 1
case "$SC_BUNDLE" in /data/adb/modules/xairdrop17_stage0194|/data/adb/modules_update/xairdrop17_stage0194) ;; *) exit 1;; esac
sc_parent=$SC_BUNDLE
while :; do
    [ ! -L "$sc_parent" ] && [ "$(stat -c %u "$sc_parent")" = 0 ] || exit 1
    sc_mode=$(stat -c %a "$sc_parent") || exit 1
    case "$sc_mode" in ''|*[!0-7]*|*[2367][0-7]|*[0-7][2367]) exit 1;; esac
    case "${#sc_mode}" in 3|4) ;; *) exit 1;; esac
    [ "$sc_parent" = /data/adb ] && break
    sc_parent=${sc_parent%/*}
done
for sc_boot_file in stage-io.sh SHA256SUMS; do
    [ -f "$SC_BUNDLE/$sc_boot_file" ] && [ ! -L "$SC_BUNDLE/$sc_boot_file" ] &&
    [ "$(stat -c %u "$SC_BUNDLE/$sc_boot_file")" = 0 ] || exit 1
    sc_mode=$(stat -c %a "$SC_BUNDLE/$sc_boot_file") || exit 1
    case "$sc_mode" in ''|*[!0-7]*|*[2367][0-7]|*[0-7][2367]) exit 1;; esac
    case "${#sc_mode}" in 3|4) ;; *) exit 1;; esac
done
# Verify retained files before sourcing executable helper code.
(cd "$SC_BUNDLE" && sha256sum -c SHA256SUMS) || { echo INTEGRITY_BLOCKED_BEFORE_SOURCE; exit 1; }
. "$SC_BUNDLE/stage-io.sh"
sc_bundle || { echo BUNDLE_BLOCKED; exit 1; }
sc_absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
sc_small() {
    [ -f "$1" ] && sc_private "$1" || return 1
    sc_size=$(stat -c %s "$1") || return 1
    case "$sc_size" in ''|*[!0-9]*) return 1;; esac
    [ "$sc_size" -le 256 ] && sc_text=$(cat "$1") && [ "$sc_text" = "$2" ]
}
sc_archive() {
    sc_old=$(sc_key prior_archive_path) || return 1
    [ -d "$sc_old" ] && sc_private "$sc_old" &&
    sc_small "$sc_old/boot-id" "$(sc_key prior_boot_id)" &&
    sc_small "$sc_old/phase" active &&
    sc_small "$sc_old/manifest.sha256" "$(sc_key prior_manifest_sha256)" &&
    [ -f "$sc_old/$SC_WLAN.ko" ] && sc_private "$sc_old/$SC_WLAN.ko" &&
    sc_hash_matches "$sc_old/$SC_WLAN.ko" "stock.$SC_WLAN.sha256"
}
sc_ready() {
    sc_environment && sc_original_cnss && sc_expect_wlan stock && sc_cnss_holder "$SC_WLAN" && sc_interfaces || return 1
    for sc_old in /data/adb/xairdrop17-stockcnss-transaction /data/adb/xairdrop17-pair-transaction /dev/xairdrop17-pair.lock /dev/xairdrop17-wlan-trial; do
        sc_absent "$sc_old" || return 1
    done
    for sc_m in wonder wonder_sysctl opairshare_wonder_provider opairshare_route_b_probe oneplus13_wonder_provider; do
        sc_absent "/sys/module/$sc_m" || return 1
    done
    sc_archive
}
sc_verify_backup() {
    sc_snapshot=$1
    [ -d "$sc_snapshot" ] && sc_private "$sc_snapshot" || return 1
    sc_small "$sc_snapshot/boot-id" "$(cat /proc/sys/kernel/random/boot_id)" &&
    sc_small "$sc_snapshot/manifest.sha256" "$(sc_hash "$SC_BUNDLE/deployment.tsv")" &&
    sc_small "$sc_snapshot/phase" backup-only &&
    sc_small "$sc_snapshot/wifi.before" "$sc_wifi" &&
    [ -f "$sc_snapshot/hals" ] && sc_private "$sc_snapshot/hals" &&
    [ "$(cat "$sc_snapshot/hals")" = "$sc_hal_list" ] &&
    [ -f "$sc_snapshot/$SC_WLAN.ko" ] && sc_private "$sc_snapshot/$SC_WLAN.ko" &&
    sc_hash_matches "$sc_snapshot/$SC_WLAN.ko" "stock.$SC_WLAN.sha256"
}
if [ "$SC_ACTION" = check ] || [ "$SC_ACTION" = status ]; then
    sc_absent "$SC_LOCK" && sc_ready || { echo CHECK_BLOCKED_NO_DRIVER_EFFECTS; exit 1; }
    printf 'STAGE0194_CHECK_PASS_ONLY\nfirmware=%s\napply_enabled=false\n' "$(sc_key firmware)"
    exit 0
fi
[ "$SC_BUNDLE" = /data/adb/modules/xairdrop17_stage0194 ] || { echo BACKUP_REQUIRES_INSTALLED_PATH; exit 1; }
umask 077
mkdir "$SC_LOCK" || { echo LOCK_PRESENT_PRESERVE_STATE; exit 1; }
SC_OWN=1
sc_lock_id=$(stat -c %d:%i "$SC_LOCK") || exit 1
sc_unlock() {
    if [ "$SC_OWN" = 1 ] && [ "$(stat -c %d:%i "$SC_LOCK" 2>/dev/null)" = "$sc_lock_id" ]; then rmdir "$SC_LOCK" 2>/dev/null || :; fi
}
trap sc_unlock 0
trap 'exit 130' INT
trap 'exit 143' TERM
sc_ready || { echo BACKUP_PREFLIGHT_BLOCKED; exit 1; }
sc_boot=$(cat /proc/sys/kernel/random/boot_id) && sc_wifi=$(sc_wifi_state) && sc_hal_list=$(sc_hals) || exit 1
[ -n "$sc_hal_list" ] || { echo NO_RUNNING_HAL_PRESERVE_STATE; exit 1; }
# An interrupted attempt blocks even if another completed backup also exists.
for sc_incomplete in "$SC_STATE".preparing.*; do sc_absent "$sc_incomplete" || { echo INCOMPLETE_BACKUP_PRESERVED; exit 1; }; done
if ! sc_absent "$SC_STATE"; then
    sc_verify_backup "$SC_STATE" || { echo BACKUP_STATE_PRESERVED_NOT_REPLAYABLE; exit 1; }
    echo STAGE0194_EXISTING_BACKUP_VERIFIED_ONLY
    exit 0
fi
sc_tmp=$SC_STATE.preparing.$$
mkdir "$sc_tmp" || exit 1
sc_source=$(sc_stock_file "$SC_WLAN") || exit 1
cp "$sc_source" "$sc_tmp/$SC_WLAN.ko" &&
printf '%s\n' "$sc_boot" > "$sc_tmp/boot-id" &&
sc_hash "$SC_BUNDLE/deployment.tsv" > "$sc_tmp/manifest.sha256" &&
printf '%s\n' "$sc_wifi" > "$sc_tmp/wifi.before" &&
printf '%s\n' "$sc_hal_list" > "$sc_tmp/hals" &&
printf 'backup-only\n' > "$sc_tmp/phase" && sc_verify_backup "$sc_tmp" || { echo INCOMPLETE_BACKUP_PRESERVED; exit 1; }
sc_ready && [ "$(cat /proc/sys/kernel/random/boot_id)" = "$sc_boot" ] &&
[ "$(sc_wifi_state)" = "$sc_wifi" ] && [ "$(sc_hals)" = "$sc_hal_list" ] && sc_absent "$SC_STATE" || { echo BACKUP_RECHECK_BLOCKED; exit 1; }
sc_tmp_id=$(stat -c %d:%i "$sc_tmp") && sc_parent_dev=$(stat -c %d /data/adb) || exit 1
[ "${sc_tmp_id%%:*}" = "$sc_parent_dev" ] || exit 1
if mv -T -n -- "$sc_tmp" "$SC_STATE"; then sc_rc=0; else sc_rc=$?; fi
[ "$sc_rc" = 0 ] && sc_absent "$sc_tmp" && [ "$(stat -c %d:%i "$SC_STATE")" = "$sc_tmp_id" ] && sc_verify_backup "$SC_STATE" || { echo BACKUP_UNCERTAIN_PRESERVE_BOTH; exit 1; }
echo STAGE0194_BACKUP_VERIFIED_ONLY_NO_DRIVER_EFFECTS
