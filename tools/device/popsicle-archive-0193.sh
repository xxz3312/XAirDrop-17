#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Archive one reviewed prior-boot record only; never delete/replay/load drivers.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
XA_ACTION=${1:-check}
[ "$#" -le 1 ] || exit 2
case "$XA_ACTION" in check|archive) ;; *) echo 'Usage: check|archive'; exit 2;; esac
[ "$(id -u)" = 0 ] || { echo ROOT_REQUIRED; exit 1; }
XA_SRC=/data/adb/xairdrop17-stockcnss-transaction
XA_OLD=722369de-3820-40a5-9e3d-88f2432f1176
XA_DST=$XA_SRC.previous.0193.$XA_OLD
XA_LOCK=/dev/xairdrop17-wlan-trial.lock
XA_OWN=0
XA_LOCK_ID=
xa_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    xa_mode=$(stat -c %a "$1") || return 1
    case "$xa_mode" in ''|*[!0-7]*) return 1;; esac
    case "${#xa_mode}" in 3|4) ;; *) return 1;; esac
    case "$xa_mode" in *[2367][0-7]|*[0-7][2367]) return 1;; esac
}
xa_small() {
    [ -f "$1" ] && xa_private "$1" || return 1
    xa_size=$(stat -c %s "$1") || return 1
    case "$xa_size" in ''|*[!0-9]*) return 1;; esac
    [ "$xa_size" -le 256 ] && xa_text=$(cat "$1") && [ "$xa_text" = "$2" ]
}
xa_hash() {
    xa_sum=$(sha256sum "$1") || return 1
    [ "${xa_sum%% *}" = "$2" ]
}
xa_absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
xa_note() {
    [ -d "/sys/module/$1" ] && [ "$(cat "/sys/module/$1/initstate")" = live ] &&
    xa_hash "/sys/module/$1/notes/.note.gnu.build-id" "$2"
}
xa_stock_file() {
    xa_found=0
    for xa_area in /vendor/lib/modules /vendor_dlkm/lib/modules; do
        xa_file=$xa_area/$1.ko
        if [ -f "$xa_file" ]; then xa_hash "$xa_file" "$2" || return 1; xa_found=1; fi
    done
    [ "$xa_found" = 1 ]
}
xa_record() {
    [ -d "$XA_SRC" ] && xa_private "$XA_SRC" && xa_absent "$XA_DST" &&
    xa_absent "$XA_SRC/phase.new" &&
    xa_small "$XA_SRC/boot-id" "$XA_OLD" && xa_small "$XA_SRC/phase" active &&
    xa_small "$XA_SRC/manifest.sha256" 6918ee93d70679181c42507ddcf48a8d4b59f12e23ca68a8c2985d252adc8e2a && xa_small "$XA_SRC/wifi.before" 1 &&
    [ -f "$XA_SRC/qca_cld3_peach_v2.ko" ] && xa_private "$XA_SRC/qca_cld3_peach_v2.ko" &&
    xa_hash "$XA_SRC/qca_cld3_peach_v2.ko" 202977cadf13b330a21838f3dd222cb0886eb0649d705937a778d7da69085f75 &&
    [ -f "$XA_SRC/hals" ] && xa_private "$XA_SRC/hals" && xa_hash "$XA_SRC/hals" dd68eff1a98e1f749b70c35576cc235dd56e6943d93466c5389c5eb7f64a3619
}
xa_check() {
    [ -d /data ] && [ ! -L /data ] || return 1
    xa_data=$(stat -c %u:%g:%a /data) || return 1
    case "$xa_data" in 1000:1000:771|1000:1000:0771) ;; *) xa_private /data || return 1;; esac
    [ -d /data/adb ] && xa_private /data/adb || return 1
    [ "$(getprop ro.product.device)" = popsicle ] &&
    [ "$(getprop ro.build.version.incremental)" = OS4.0.6.0.XPBCNXM ] &&
    [ "$(getprop sys.boot_completed)" = 1 ] && [ "$(uname -m)" = aarch64 ] &&
    [ "$(uname -r)" = 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k ] || return 1
    xa_slot=$(getprop ro.boot.slot_suffix) || return 1
    case "$xa_slot" in _a|_b) ;; *) return 1;; esac
    [ -b "/dev/block/by-name/boot$xa_slot" ] && xa_hash "/dev/block/by-name/boot$xa_slot" 84e5aded3a181265b4a53132d3e4aafa29a8946112b166b8bc78f0724da390e8 || return 1
    xa_boot=$(cat /proc/sys/kernel/random/boot_id) || return 1
    case "$xa_boot" in ''|*[!0-9a-f-]*) return 1;; esac
    case "$xa_boot" in ????????-????-????-????-????????????) ;; *) return 1;; esac
    [ "${#xa_boot}" = 36 ] && [ "$xa_boot" != "$XA_OLD" ] || return 1
    for xa_foreign in wonder wonder_sysctl opairshare_wonder_provider opairshare_route_b_probe oneplus13_wonder_provider; do
        xa_absent "/sys/module/$xa_foreign" || return 1
    done
    for xa_foreign in /data/adb/xairdrop17-pair-transaction /dev/xairdrop17-pair.lock /dev/xairdrop17-wlan-trial /dev/xairdrop.lock; do
        xa_absent "$xa_foreign" || return 1
    done
    xa_stock_file cnss2 6e0494f4535ee6e7923493abe75db2e50e3216cf204334639a52d84e23c51a37 && xa_stock_file qca_cld3_peach_v2 202977cadf13b330a21838f3dd222cb0886eb0649d705937a778d7da69085f75 &&
    xa_note cnss2 fd452273270f45ac4dd89fb08b4e7c281c99f46bdbd23d1289be52c9ec5c99c3 && xa_note qca_cld3_peach_v2 e2db5a4c55b3664d2aa3d5ce4dc24af67df31f58d88f4e65121fd5aa0b050ecd && xa_record || return 1
    xa_src_id=$(stat -c %d:%i "$XA_SRC") && xa_parent_dev=$(stat -c %d /data/adb) || return 1
    [ "${xa_src_id%%:*}" = "$xa_parent_dev" ] &&
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$xa_boot" ] &&
    [ "$(getprop ro.boot.slot_suffix)" = "$xa_slot" ]
}
xa_unlock() {
    if [ "$XA_OWN" = 1 ] && [ "$(stat -c %d:%i "$XA_LOCK" 2>/dev/null)" = "$XA_LOCK_ID" ]; then
        rmdir "$XA_LOCK" 2>/dev/null || :
    fi
}
if [ "$XA_ACTION" = check ]; then
    xa_absent "$XA_LOCK" && xa_check || { echo ARCHIVE_CHECK_BLOCKED_NO_CHANGES; exit 1; }
    echo 'ARCHIVE_CHECK_PASS_RECORD_ONLY; no install/runtime authority'
    exit 0
fi
umask 077
mkdir "$XA_LOCK" || { echo LOCK_PRESENT_PRESERVE_STATE; exit 1; }
XA_OWN=1
XA_LOCK_ID=$(stat -c %d:%i "$XA_LOCK") || { echo LOCK_IDENTITY_UNREADABLE_PRESERVE_STATE; exit 1; }
trap xa_unlock 0
trap 'exit 130' INT
trap 'exit 143' TERM
xa_check || { echo ARCHIVE_BLOCKED_PRESERVE_STATE; exit 1; }
# Recheck the reviewed record/boot under the same cooperative legacy lock.
xa_saved_id=$xa_src_id
xa_record && [ "$(stat -c %d:%i "$XA_SRC")" = "$xa_saved_id" ] &&
[ "$(cat /proc/sys/kernel/random/boot_id)" = "$xa_boot" ] || { echo ARCHIVE_RECHECK_BLOCKED; exit 1; }
if mv -T -n -- "$XA_SRC" "$XA_DST"; then xa_move_rc=0; else xa_move_rc=$?; fi
if [ "$xa_move_rc" = 0 ] && xa_absent "$XA_SRC" &&
   [ -d "$XA_DST" ] && xa_private "$XA_DST" && [ "$(stat -c %d:%i "$XA_DST")" = "$xa_saved_id" ]; then
    printf 'ARCHIVED_RECORD_ONLY_NOT_FOR_INSTALL\narchive=%s\n' "$XA_DST"
else
    echo 'ARCHIVE_UNCERTAIN_PRESERVE_BOTH; no rollback/retry or deletion'
    exit 1
fi
