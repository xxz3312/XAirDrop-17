#!/system/bin/sh
# Read-only predicate diagnostics for the exact delivered 0201 controller.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
[ "$#" = 0 ] && [ "$(id -u)" = 0 ] || exit 2
SC_BUNDLE=/data/adb/modules/xairdrop17_cycle0195
SC_WLAN=qca_cld3_peach_v2
SC_PROVIDER=opairshare_wonder_provider
CY_STATE=/data/adb/xairdrop17-cycle0195-transaction
CY_BACKUP=/data/adb/xairdrop17-stage0194-backup
CY_LOCK=/dev/xairdrop17-wlan-trial.lock
SC_LOG=
dg_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    dg_mode=$(stat -c %a "$1") || return 1
    case "$dg_mode" in ''|*[!0-7]*|*[2367][0-7]|*[0-7][2367]) return 1;; esac
    case "${#dg_mode}" in 3|4) ;; *) return 1;; esac
}
dg_parent=$SC_BUNDLE
while :; do
    dg_private "$dg_parent" || exit 1
    [ "$dg_parent" = /data/adb ] && break
    dg_parent=${dg_parent%/*}
done
for dg_f in SHA256SUMS stage-io.sh cycle-io.sh; do
    [ -f "$SC_BUNDLE/$dg_f" ] && dg_private "$SC_BUNDLE/$dg_f" || exit 1
done
dg_sum=$(sha256sum "$SC_BUNDLE/SHA256SUMS") || exit 1
[ "${dg_sum%% *}" = 5ade011bae0bd7ca5ffe4a959f4ea9916cecddd60c977ec26f353ec9a46bb05f ] || { echo REQUIRE_EXACT_DELIVERED_0201_CHECKSUM_INDEX; exit 1; }
(cd "$SC_BUNDLE" && sha256sum -c SHA256SUMS) || exit 1
. "$SC_BUNDLE/stage-io.sh"
. "$SC_BUNDLE/cycle-io.sh"
# Replace only the logger so preflight observations are visible before a journal.
# No controller dispatcher/engine, snapshot or effect function is called.
sc_log() { printf '%s\n' "$*"; }
cy_absent "$CY_LOCK" || { echo ACTIVE_LOCK_PRESERVE_STATE_NO_DIAG; exit 1; }
dg_failed=0
dg_check() {
    if "$@"; then dg_rc=0; else dg_rc=$?; fi
    printf 'READONLY_PREDICATE:%s:rc=%s\n' "$1" "$dg_rc"
    [ "$dg_rc" = 0 ] || dg_failed=1
    return 0
}
echo READONLY_0201_PREFLIGHT_DIAGNOSTICS_BEGIN
printf 'BOOT:'; cat /proc/sys/kernel/random/boot_id
dg_check cy_bundle
dg_check cy_stock_ready
dg_check cy_no_preparing
dg_check cy_absent "$CY_STATE"
dg_check cy_completed_archived
if [ -d "$CY_STATE" ] && dg_private "$CY_STATE"; then
    for dg_f in phase boot-id manifest.sha256; do
        if [ -f "$CY_STATE/$dg_f" ] && dg_private "$CY_STATE/$dg_f"; then
            printf 'CURRENT_%s:' "$dg_f"; cat "$CY_STATE/$dg_f"
        fi
    done
    if [ -f "$CY_STATE/commands.log" ] && dg_private "$CY_STATE/commands.log"; then
        echo CURRENT_COMMAND_JOURNAL_LAST_30_LINES
        tail -n 30 "$CY_STATE/commands.log"
    fi
fi
dg_check cy_framework
cy_hals=$(sc_hals); dg_hals_rc=$?
printf 'CURRENT_HAL_LIST:rc=%s:%s\n' "$dg_hals_rc" "$cy_hals"
[ "$dg_hals_rc" = 0 ] && [ -n "$cy_hals" ] || dg_failed=1
dg_iface=0; [ ! -d /sys/class/net/wlan0 ] || dg_iface=1
printf 'BASELINE:wifi=%s:scan=%s:wlan0=%s\n' "${cy_fw_wifi:-unknown}" "${cy_fw_scan:-unknown}" "$dg_iface"
[ "${cy_fw_wifi:-unknown}:$dg_iface" = 1:1 ] || dg_failed=1
dg_check cy_connected_status
if [ -x /system/bin/timeout ]; then echo ANDROID_TIMEOUT_PRESENT; else echo ANDROID_TIMEOUT_MISSING; fi
# Compare the direct, previously qualified pipe capture with the new timeout
# wrapper. Both paths only query status; no Wi-Fi setter or scan request.
if dg_direct=$(/system/bin/cmd wifi status 2>&1); then dg_direct_rc=0; else dg_direct_rc=$?; fi
printf 'DIRECT_WIFI_STATUS:rc=%s:%s\n' "$dg_direct_rc" "$dg_direct"
dg_check cy_observation_capabilities
echo READONLY_0201_PREFLIGHT_DIAGNOSTICS_END_NO_WIFI_OR_DRIVER_CONTROL
exit "$dg_failed"
