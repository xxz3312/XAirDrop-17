#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Explicit manual diagnostic trial. Never replaces/removes/inserts CNSS2.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
SC_WLAN=qca_cld3_peach_v2
SC_PROVIDER=opairshare_wonder_provider
SC_STATE=/data/adb/xairdrop17-stockcnss-transaction
SC_LOG_ROOT=/data/adb/xairdrop17-stockcnss-logs
SC_LOCK=/dev/xairdrop17-wlan-trial.lock
SC_OWN_LOCK=0
SC_LOG=
case "$0" in */*) sc_dir=${0%/*};; *) exit 2;; esac
SC_BUNDLE=$(CDPATH= cd -- "$sc_dir" && pwd -P) || exit 1
SC_ACTION=${1:-check}
case "$SC_ACTION" in check|status|backup|apply|archive) ;; *) echo 'Usage: stock-cnssctl check|status|backup|apply|archive'; exit 2;; esac
[ "$#" -le 1 ] && [ "$(id -u)" = 0 ] || { echo 'Run as root; one action only.'; exit 1; }
# Check ownership before sourcing the IO helper, which itself runs no actions.
sc_boot_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    sc_boot_mode=$(stat -c %a "$1") || return 1
    case "$sc_boot_mode" in ''|*[!0-7]*) return 1;; esac
    case "${#sc_boot_mode}" in 3|4) ;; *) return 1;; esac
    case "$sc_boot_mode" in *[2367][0-7]|*[0-7][2367]) return 1;; esac
}
case "$SC_BUNDLE" in /data/adb/modules/xairdrop17_stock_cnss|/data/adb/xairdrop17-stockcnss-*) ;; *) echo 'Invalid bundle location'; exit 1;; esac
sc_parent=$SC_BUNDLE
while :; do
    sc_boot_private "$sc_parent" || exit 1
    [ "$sc_parent" = /data/adb ] && break
    sc_parent=${sc_parent%/*}
done
sc_boot_private "$SC_BUNDLE/popsicle-stock-cnss-io.sh" || exit 1
. "$SC_BUNDLE/popsicle-stock-cnss-io.sh"
if [ "$SC_ACTION" = status ]; then
    printf 'device='; getprop ro.product.device
    printf 'kernel='; uname -r
    printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
    for sc_m in cnss2 "$SC_WLAN" "$SC_PROVIDER"; do
        if [ -d "/sys/module/$sc_m" ]; then
            printf 'module=%s state=' "$sc_m"; cat "/sys/module/$sc_m/initstate"
            printf 'note_sha256='; sc_hash "/sys/module/$sc_m/notes/.note.gnu.build-id"
        fi
    done
    if [ -f "$SC_STATE/phase" ]; then printf 'phase='; cat "$SC_STATE/phase"; fi
    echo 'STATUS_READ_ONLY_NOT_RUNTIME_CERTIFICATION'
    exit 0
fi
sc_bundle || { echo 'BUNDLE_BLOCKED'; exit 1; }
. "$SC_BUNDLE/popsicle-stock-cnss-engine.sh"
sc_preflight() {
    sc_environment && sc_no_other_transaction && sc_original_cnss &&
    sc_expect_wlan stock && sc_provider_absent && sc_interfaces && sc_cnss_holder "$SC_WLAN"
}
if [ "$SC_ACTION" = check ]; then
    sc_preflight || { echo 'CHECK_BLOCKED; no lifecycle effects'; exit 1; }
    echo 'CHECK_PASS_RECORDED_IDENTITY_ONLY; no runtime/RF certificate'
    exit 0
fi
umask 077
mkdir "$SC_LOCK" || { echo 'WLAN lock exists; preserve it and inspect.'; exit 1; }
SC_OWN_LOCK=1
trap 'rmdir "$SC_LOCK" 2>/dev/null || true' 0
trap 'exit 130' INT
trap 'exit 143' TERM
if [ -e "$SC_LOG_ROOT" ] || [ -L "$SC_LOG_ROOT" ]; then
    sc_private "$SC_LOG_ROOT" || exit 1
else
    mkdir "$SC_LOG_ROOT" || exit 1
fi
sc_log_dir="$SC_LOG_ROOT/$(date +%Y%m%d-%H%M%S)-$$"
mkdir "$sc_log_dir" || exit 1
SC_LOG="$sc_log_dir/commands.log"
: > "$SC_LOG" || exit 1
echo "LOG:$SC_LOG"
sc_log "ACTION:$SC_ACTION boot=$(cat /proc/sys/kernel/random/boot_id)"
case "$SC_ACTION" in
    backup) sc_preflight && sc_snapshot && sc_journal backup-only;;
    apply) sc_start_stock_cnss;;
    archive)
        # Preserve this profile's prior-boot transaction only. The old pair
        # transaction is never removed or archived by this new controller.
        sc_environment && sc_original_cnss && sc_expect_wlan stock && sc_provider_absent &&
        sc_private "$SC_STATE" && sc_private "$SC_STATE/boot-id" && {
            sc_old_boot=$(cat "$SC_STATE/boot-id")
            case "$sc_old_boot" in ''|*[!0-9a-f-]*) false;; *)
                [ "${#sc_old_boot}" = 36 ] &&
                [ "$sc_old_boot" != "$(cat /proc/sys/kernel/random/boot_id)" ] &&
                [ ! -e "$SC_STATE.previous.$sc_old_boot" ] && [ ! -L "$SC_STATE.previous.$sc_old_boot" ] &&
                mv "$SC_STATE" "$SC_STATE.previous.$sc_old_boot";;
            esac
        };;
esac
sc_result=$?
sc_log "RESULT:$sc_result"
sync
if [ "$sc_result" = 0 ]; then
    echo "DONE:$SC_ACTION (identity/readiness only; not Apple/RF certification)"
else
    echo 'STOPPED: preserve logs/state; no automatic rollback/retry. Disable this trial and reboot for original drivers.'
fi
exit "$sc_result"
