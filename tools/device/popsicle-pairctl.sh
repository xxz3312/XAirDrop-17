#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Explicit runtime-only pair trial; never writes partitions/vendor/module files.
set -u
PATH=/system/bin:/system/xbin
export PATH
case "$0" in */*) script_dir=${0%/*};; *) script_dir=.;; esac
BUNDLE=$(CDPATH= cd -- "$script_dir" && pwd -P) || exit 1
STATE=/data/adb/xairdrop17-pair-transaction
LOCK=/dev/xairdrop17-pair.lock
SHARED_LOCK=/dev/xairdrop17-wlan-trial.lock
OWN_SHARED_LOCK=0
WLAN=qca_cld3_peach_v2
PROVIDER=opairshare_wonder_provider
ACTION=${1:-check}
case "$ACTION" in check|backup|apply|restore|archive|status) ;; *) echo 'Usage: pairctl check|backup|apply|restore|archive|status'; exit 2;; esac
[ "$(id -u)" = 0 ] || { echo 'Run as root.'; exit 1; }
pp_message() { printf '%s\n' "$*"; }
pp_hash() {
    sum=$(sha256sum "$1") || return 1
    printf '%s\n' "${sum%% *}"
}
pp_key() {
    wanted=$1; key_count=0; found=
    while IFS='	' read -r key value extra; do
        if [ "$key" = "$wanted" ]; then
            [ -z "$extra" ] || return 1
            key_count=$((key_count+1)); found=$value
        fi
    done < "$BUNDLE/deployment.tsv"
    [ "$key_count" = 1 ] && [ -n "$found" ] || return 1
    printf '%s\n' "$found"
}

pp_environment() {
    [ "$(getprop ro.product.device)" = "$(pp_key device)" ] || return 1
    [ "$(getprop ro.build.version.incremental)" = "$(pp_key firmware)" ] || return 1
    [ "$(uname -r)" = "$(pp_key kernel)" ] || return 1
    [ "$(uname -m)" = aarch64 ] || return 1
    [ "$(getprop sys.boot_completed)" = 1 ] || return 1
    [ -r /proc/sys/kernel/random/boot_id ] || return 1
    slot=$(getprop ro.boot.slot_suffix)
    case "$slot" in _a|_b) ;; *) return 1;; esac
    boot="/dev/block/by-name/boot$slot"
    [ -b "$boot" ] && [ "$(pp_hash "$boot")" = "$(pp_key boot_sha256)" ] || return 1
}
pp_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    mode=$(stat -c %a "$1") || return 1
    [ "$((0$mode & 022))" = 0 ]
}
pp_verify_bundle() {
    case "$BUNDLE" in /data/adb/*) ;; *) return 1;; esac
    parent=$BUNDLE
    while :; do
        pp_private "$parent" || return 1
        [ "$parent" = /data/adb ] && break
        parent=${parent%/*}; [ -n "$parent" ] || parent=/
    done
    for f in SHA256SUMS deployment.tsv popsicle-pairctl.sh popsicle-pair-engine.sh kernel/cnss2.ko kernel/qca_cld3_peach_v2.ko kernel/opairshare_wonder_provider.ko; do
        [ -f "$BUNDLE/$f" ] && pp_private "$BUNDLE/$f" || return 1
    done
    (cd "$BUNDLE" && sha256sum -c SHA256SUMS) || return 1
    [ "$(pp_key schema)" = 1 ] || return 1
    for m in cnss2 "$WLAN" "$PROVIDER"; do
        [ "$(pp_hash "$BUNDLE/kernel/$m.ko")" = "$(pp_key "candidate.$m.sha256")" ] || return 1
    done
}
pp_no_conflict() {
    [ ! -d /dev/xairdrop17-wlan-trial ] || return 1
    [ ! -d "$SHARED_LOCK" ] || [ "$OWN_SHARED_LOCK" = 1 ] || return 1
    [ ! -d /sys/module/wonder ] || return 1
}
pp_expect_absent() { [ ! -d "/sys/module/$1" ]; }
pp_expect_module() {
    [ -d "/sys/module/$1" ] && [ "$(cat "/sys/module/$1/initstate")" = live ] || return 1
    note="/sys/module/$1/notes/.note.gnu.build-id"
    [ -f "$note" ] && [ "$(pp_hash "$note")" = "$(pp_key "$2.$1.note_sha256")" ]
}
pp_holders() {
    [ -d "/sys/module/$1/holders" ] || return 1
    names=$(ls -1 "/sys/module/$1/holders") || return 1
    [ "$names" = "$2" ]
}
pp_zero_refs() { [ "$(cat "/sys/module/$1/refcnt")" = 0 ]; }
pp_healthy() {
    [ "$(cat "/sys/module/$WLAN/parameters/mishare_load_error")" = 0 ] || return 1
    [ -w "/sys/module/$PROVIDER/parameters/mishare_live_unload" ]
}
pp_ifaces() {
    for f in /sys/class/net/*; do
        case "${f##*/}" in ap*|swlan*|softap*|wlan[1-9]*) return 1;; esac
    done
}
pp_stock_path() {
    for d in /vendor_dlkm/lib/modules /vendor/lib/modules; do
        f="$d/$1.ko"
        if [ -f "$f" ] && [ "$(pp_hash "$f")" = "$(pp_key "stock.$1.sha256")" ]; then printf '%s\n' "$f"; return 0; fi
    done
    return 1
}
pp_running_hals() {
    getprop | sed -n 's/^\[init\.svc\.\(vendor\.wifi_hal[^]]*\)\]: \[running\]$/\1/p' | sort
}
pp_wifi_state() {
    out=$(/system/bin/cmd wifi status) || return 1
    case "$out" in 'Wifi is enabled'*) printf '1\n';; 'Wifi is disabled'*) printf '0\n';; *) return 1;; esac
}
pp_no_transaction() { [ ! -e "$STATE" ] && [ ! -L "$STATE" ]; }
pp_journal() {
    [ -d "$STATE" ] && pp_private "$STATE" || return 1
    printf '%s\n' "$1" > "$STATE/phase.new" || return 1
    sync || return 1
    mv "$STATE/phase.new" "$STATE/phase" || return 1
    sync
}
pp_snapshot() {
    pp_no_transaction || return 1
    # Also verifies that the original on-disk files match the audited capture.
    c=$(pp_stock_path cnss2) && w=$(pp_stock_path "$WLAN") || return 1
    before=$(pp_wifi_state) || return 1
    hals=$(pp_running_hals)
    [ -n "$hals" ] || return 1
    for h in $hals; do case "$h" in vendor.wifi_hal*[!a-zA-Z0-9_.-]*) return 1;; vendor.wifi_hal*) ;; *) return 1;; esac; done
    umask 077
    mkdir "$STATE" || return 1
    cp "$c" "$STATE/cnss2.ko" && cp "$w" "$STATE/$WLAN.ko" || return 1
    cat /proc/sys/kernel/random/boot_id > "$STATE/boot-id" || return 1
    pp_hash "$BUNDLE/deployment.tsv" > "$STATE/manifest.sha256" || return 1
    printf '%s\n' "$before" > "$STATE/wifi.before" || return 1
    printf '%s\n' "$hals" > "$STATE/hals" || return 1
    pp_verify_snapshot || return 1
    pp_journal backup-only
}
pp_verify_snapshot() {
    pp_private "$STATE" || return 1
    [ "$(cat "$STATE/boot-id")" = "$(cat /proc/sys/kernel/random/boot_id)" ] || return 1
    [ "$(cat "$STATE/manifest.sha256")" = "$(pp_hash "$BUNDLE/deployment.tsv")" ] || return 1
    for m in cnss2 "$WLAN"; do
        pp_private "$STATE/$m.ko" && [ "$(pp_hash "$STATE/$m.ko")" = "$(pp_key "stock.$m.sha256")" ] || return 1
    done
    case "$(cat "$STATE/wifi.before")" in 0|1) ;; *) return 1;; esac
    [ -s "$STATE/hals" ] || return 1
    while IFS= read -r h; do case "$h" in vendor.wifi_hal*[!a-zA-Z0-9_.-]*) return 1;; vendor.wifi_hal*) ;; *) return 1;; esac; done < "$STATE/hals"
}
pp_require_active() { pp_verify_snapshot && [ "$(cat "$STATE/phase")" = active ]; }
pp_archive() {
    pp_idle && pp_identify stock && pp_private "$STATE" || return 1
    old_boot=$(cat "$STATE/boot-id") || return 1
    case "$old_boot" in ''|*[!0-9a-f-]*) return 1;; esac
    [ "${#old_boot}" = 36 ] || return 1
    [ "$old_boot" != "$(cat /proc/sys/kernel/random/boot_id)" ] || return 1
    [ ! -e "$STATE.previous.$old_boot" ] && [ ! -L "$STATE.previous.$old_boot" ] || return 1
    mv "$STATE" "$STATE.previous.$old_boot"
}

pp_wifi_off() {
    n=0
    while [ "$n" -lt 20 ]; do [ "$(pp_wifi_state)" = 0 ] && return 0; sleep 1; n=$((n+1)); done
    return 1
}
pp_wait_hals() {
    want=$1
    n=0
    while [ "$n" -lt 20 ]; do
        ready=1
        while IFS= read -r h; do [ "$(getprop "init.svc.$h")" = "$want" ] || ready=0; done < "$STATE/hals"
        [ "$ready" = 1 ] && return 0
        sleep 1; n=$((n+1))
    done
    return 1
}
pp_hals_stopped() { pp_wait_hals stopped && [ -z "$(pp_running_hals)" ]; }
pp_check_transaction() {
    pp_no_transaction || { pp_verify_snapshot && [ "$(cat "$STATE/phase")" = backup-only ]; }
}
pp_prepare_snapshot() {
    if pp_no_transaction; then pp_snapshot; return $?; fi
    pp_check_transaction || return 1
    [ "$(pp_wifi_state)" = "$(cat "$STATE/wifi.before")" ] || return 1
    [ "$(pp_running_hals)" = "$(cat "$STATE/hals")" ] || return 1
    pp_wait_hals running
}

pp_effect() {
    # No shell evaluation, user-supplied options, force flags or modprobe.
    case "$1" in remove|insert|stock-insert|live-unload) pp_wifi_off && pp_hals_stopped || return 1;; esac
    case "$1" in
        wifi-off) /system/bin/svc wifi disable;;
        hals-stop) while IFS= read -r h; do /system/bin/stop "$h" || return 1; done < "$STATE/hals";;
        hals-start) while IFS= read -r h; do /system/bin/start "$h" || return 1; done < "$STATE/hals";;
        wifi-on) /system/bin/svc wifi enable;;
        live-unload) printf '1\n' > "/sys/module/$PROVIDER/parameters/mishare_live_unload";;
        remove) case "$2" in cnss2|qca_cld3_peach_v2|opairshare_wonder_provider) /system/bin/rmmod "$2";; *) return 1;; esac;;
        insert) case "$2" in cnss2|qca_cld3_peach_v2|opairshare_wonder_provider) /system/bin/insmod "$BUNDLE/kernel/$2.ko";; *) return 1;; esac;;
        stock-insert) case "$2" in cnss2|qca_cld3_peach_v2) /system/bin/insmod "$STATE/$2.ko";; *) return 1;; esac;;
        *) return 1;;
    esac
}
pp_restore_services() {
    pp_change hals-start || return 1
    pp_wait_hals running || return 1
    if [ "$(cat "$STATE/wifi.before")" = 1 ]; then
        pp_change wifi-on || return 1
        n=0
        while [ "$n" -lt 20 ]; do [ "$(pp_wifi_state)" = 1 ] && return 0; sleep 1; n=$((n+1)); done
        return 1
    fi
}
# Read-only check/status do not create state or run lifecycle effects.
if [ "$ACTION" = status ]; then
    printf 'device='; getprop ro.product.device
    printf 'firmware='; getprop ro.build.version.incremental
    printf 'kernel='; uname -r
    printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
    slot=$(getprop ro.boot.slot_suffix)
    printf 'slot=%s\n' "$slot"
    case "$slot" in _a|_b)
        boot="/dev/block/by-name/boot$slot"
        if [ -b "$boot" ]; then printf 'boot_sha256='; pp_hash "$boot"; fi;;
    esac
    for m in cnss2 "$WLAN" "$PROVIDER"; do
        [ ! -d "/sys/module/$m" ] || {
            printf 'module=%s\ninitstate=' "$m"; cat "/sys/module/$m/initstate"
            printf 'refcnt='; cat "/sys/module/$m/refcnt"
            printf 'holders='; ls -1 "/sys/module/$m/holders"
            note="/sys/module/$m/notes/.note.gnu.build-id"
            if [ -r "$note" ]; then printf 'loaded_note_sha256='; pp_hash "$note"; else echo 'loaded_note_sha256=missing'; fi
        }
    done
    error="/sys/module/$WLAN/parameters/mishare_load_error"
    [ ! -r "$error" ] || { printf 'mishare_load_error='; cat "$error"; }
    [ ! -f "$STATE/phase" ] || { printf 'transaction_phase='; cat "$STATE/phase"; }
    echo 'STATUS_READ_ONLY_NOT_RUNTIME_CERTIFICATION'
    exit 0
fi
pp_verify_bundle || { echo 'Bundle identity/permission/hash check failed.'; exit 1; }
. "$BUNDLE/popsicle-pair-engine.sh"
if [ "$ACTION" = check ]; then
    pp_idle && pp_check_transaction && pp_identify stock && pp_stock_path cnss2 && pp_stock_path "$WLAN" || { echo 'CHECK_BLOCKED; no lifecycle effects performed.'; exit 1; }
    echo 'CHECK_PASS_RECORDED_IDENTITY_ONLY; runtime ABI/RF not certified.'; exit 0
fi
# mkdir is the lock; never remove another process's lock or replay stale state.
umask 077
mkdir "$SHARED_LOCK" || { echo 'Shared WLAN lock exists; stop and inspect.'; exit 1; }
OWN_SHARED_LOCK=1
mkdir "$LOCK" || { rmdir "$SHARED_LOCK"; echo 'Pair lock exists; stop and inspect.'; exit 1; }
trap 'rmdir "$LOCK" 2>/dev/null || true; rmdir "$SHARED_LOCK" 2>/dev/null || true' 0
trap 'exit 130' INT
trap 'exit 143' TERM
case "$ACTION" in
    backup) pp_idle && pp_no_transaction && pp_identify stock && pp_snapshot;;
    apply) pp_start_pair;;
    restore) pp_restore_pair;;
    archive) pp_archive;;
esac
rc=$?
if [ "$rc" != 0 ]; then
    echo 'STOPPED: no automatic module rollback or retry. Preserve state/logs; reboot restores unchanged original boot files.'
else
    echo "DONE:$ACTION (recorded identity/readiness only; not Apple/RF certification)"
fi
exit "$rc"
