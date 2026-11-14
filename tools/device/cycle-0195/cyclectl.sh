#!/system/bin/sh
# Explicit one-shot diagnostic cycle. Never touches CNSS2, init_boot or RF controls.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
CY_ACTION=${1:-check}
[ "$#" -le 1 ] || exit 2
case "$CY_ACTION" in check|status|cycle) ;; *) echo 'Allowed: check|status|cycle'; exit 2;; esac
[ "$(id -u)" = 0 ] || exit 1
SC_WLAN=qca_cld3_peach_v2
SC_PROVIDER=opairshare_wonder_provider
SC_LOG=
CY_STATE=/data/adb/xairdrop17-cycle0195-transaction
CY_BACKUP=/data/adb/xairdrop17-stage0194-backup
CY_LOCK=/dev/xairdrop17-wlan-trial.lock
case "$0" in */*) cy_dir=${0%/*};; *) exit 2;; esac
SC_BUNDLE=$(CDPATH= cd -- "$cy_dir" && pwd -P) || exit 1
case "$SC_BUNDLE" in /data/adb/modules/xairdrop17_cycle0195|/data/adb/modules_update/xairdrop17_cycle0195) ;; *) exit 1;; esac
# Bootstrap does not source any code until retained bytes have been verified.
cy_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    cy_mode=$(stat -c %a "$1") || return 1
    case "$cy_mode" in ''|*[!0-7]*|*[2367][0-7]|*[0-7][2367]) return 1;; esac
    case "${#cy_mode}" in 3|4) ;; *) return 1;; esac
}
cy_parent=$SC_BUNDLE
while :; do
    cy_private "$cy_parent" || exit 1
    [ "$cy_parent" = /data/adb ] && break
    cy_parent=${cy_parent%/*}
done
for cy_file in SHA256SUMS stage-io.sh cycle-io.sh cycle-engine.sh; do
    [ -f "$SC_BUNDLE/$cy_file" ] && cy_private "$SC_BUNDLE/$cy_file" || exit 1
done
(cd "$SC_BUNDLE" && sha256sum -c SHA256SUMS) || { echo INTEGRITY_BLOCKED_BEFORE_SOURCE; exit 1; }
. "$SC_BUNDLE/stage-io.sh"
. "$SC_BUNDLE/cycle-io.sh"
. "$SC_BUNDLE/cycle-engine.sh"
cy_bundle || { echo CYCLE_BUNDLE_BLOCKED; exit 1; }
if [ "$CY_ACTION" != cycle ]; then
    cy_absent "$CY_LOCK" && cy_preflight || { echo CYCLE_CHECK_BLOCKED_NO_DRIVER_EFFECTS; exit 1; }
    echo STAGE0195_CHECK_PASS_ONLY
    exit 0
fi
[ "$SC_BUNDLE" = /data/adb/modules/xairdrop17_cycle0195 ] || exit 1
umask 077
mkdir "$CY_LOCK" || { echo LOCK_PRESENT_PRESERVE_STATE; exit 1; }
cy_lock_id=$(stat -c %d:%i "$CY_LOCK") || exit 1
cy_unlock() {
    if [ "$(stat -c %d:%i "$CY_LOCK" 2>/dev/null)" = "$cy_lock_id" ]; then rmdir "$CY_LOCK" 2>/dev/null || :; fi
}
trap cy_unlock 0
trap 'exit 130' INT
trap 'exit 143' TERM
if cy_run; then cy_result=0; else cy_result=$?; fi
if [ -n "$SC_LOG" ] && cy_owned && sc_private "$SC_LOG"; then
    (set -C; dmesg > "$CY_STATE/kernel.after.log" 2>&1) || :
    printf 'RESULT:%s\n' "$cy_result" >> "$SC_LOG" || cy_result=1
    sync || cy_result=1
    printf 'LOG:%s\n' "$SC_LOG"
    cat "$SC_LOG" || cy_result=1
fi
if [ "$cy_result" = 0 ]; then
    echo STAGE0195_DIAGNOSTIC_CYCLE_STOCK_RESTORED_ONLY
else
    echo STOPPED_PRESERVE_STATE_NO_RETRY_DISABLE_TRIAL_AND_REBOOT
fi
exit "$cy_result"
