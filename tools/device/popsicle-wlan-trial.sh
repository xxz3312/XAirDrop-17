#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Runtime swap flow adapted from Leekin2/XAirDrop module/action.sh at
# eb1fe215c6473a8dbcc6edf6cf1e67d93f250f76. Target: popsicle native 6.12 WLAN.
# Manual only. Original module files, boot configuration and partitions stay intact.
set -u
BUNDLE=${2:-${0%/*}}
STATE=/dev/xairdrop17-wlan-trial
LOCK=/dev/xairdrop17-wlan-trial.lock
NAME=qca_cld3_peach_v2
PROVIDER=opairshare_wonder_provider
PROVIDER_OWNED=0
CHANGED=0
KEEP=0
HALS=
BEFORE=
STOCK=
die() { echo "ERROR: $*"; exit 1; }
loaded() { grep -q "^$NAME " /proc/modules; }
fw() { tool=$1; shift; out=$(/system/bin/"$tool" "$@" 2>&1); rc=$?; printf '%s\n' "$out"; return "$rc"; }
wifi_state() {
    out=$(/system/bin/cmd wifi status 2>&1)
    case "$out" in 'Wifi is enabled'*) echo 1;; 'Wifi is disabled'*) echo 0;; *) echo unknown;; esac
}
wait_wifi() {
    n=0
    while [ "$n" -lt 20 ]; do
        [ "$(wifi_state)" != "$1" ] || return 0
        sleep 1; n=$((n+1))
    done
    return 1
}
wait_wlan() {
    n=0
    while [ "$n" -lt 25 ]; do
        [ ! -d /sys/class/net/wlan0 ] || return 0
        sleep 1; n=$((n+1))
    done
    return 1
}
stop_hals() {
    for h in $HALS; do
        /system/bin/stop "$h" || return 1
        n=0
        while [ "$(getprop "init.svc.$h")" != stopped ]; do
            [ "$n" -lt 10 ] || return 1
            sleep 1; n=$((n+1))
        done
    done
}
start_hals() {
    failed=0
    for h in $HALS; do /system/bin/start "$h" || failed=1; done
    [ "$failed" = 0 ]
}
restore_stock() {
    echo 'Restoring original WLAN and previous Wi-Fi state.'
    fw svc wifi disable && wait_wifi 0 || return 1
    stop_hals || return 1
    sleep 2
    # Never unload an unknown stack or a newly attached Wonder bridge.
    [ ! -d /sys/module/wonder ] || { echo 'Stop Wonder before restore.'; return 1; }
    if loaded && [ -e "/sys/module/$NAME/parameters/mishare_action_tx" ]; then
        rmmod "$NAME" || return 1
    fi
    if ! loaded; then insmod "$STOCK" || return 1; fi
    wait_wlan || return 1
    # WLAN's strong import must be released before removing our provider.
    if [ "$PROVIDER_OWNED" = 1 ] && [ -d "/sys/module/$PROVIDER" ]; then
        rmmod "$PROVIDER" || return 1
        PROVIDER_OWNED=0
    fi
    start_hals || return 1
    if [ "$BEFORE" = 1 ]; then fw svc wifi enable && wait_wifi 1 || return 1; fi
    rm -f "$STATE/wifi.before" "$STATE/hal.services" "$STATE/stock.path" "$STATE/provider.owned"
    rmdir "$STATE" || return 1
    echo 'STOCK_RESTORED (wlan0 present; association not verified).'
}
finish() {
    finish_exit_rc=$?
    trap - 0 INT TERM
    if [ "$CHANGED" = 1 ] && [ "$KEEP" = 0 ]; then
        if ! restore_stock; then
            echo 'RESTORE_FAILED: reboot to load the unchanged original driver.'
            finish_exit_rc=1
        fi
    fi
    if [ "$ACTION" != restore ] && [ "$CHANGED" = 0 ] && [ "$KEEP" = 0 ] && [ "$PROVIDER_OWNED" = 1 ]; then
        rmmod "$PROVIDER" || { echo 'Provider cleanup failed; reboot before another trial.'; finish_exit_rc=1; }
    fi
    rmdir "$LOCK" 2>/dev/null || true
    exit "$finish_exit_rc"
}
[ "$(id -u)" = 0 ] || die 'Run as root.'
case "${1:-check}" in check|run|run-mgmt-rx|restore|status) ;; *) die 'Usage: sh popsicle-wlan-trial.sh check|run|run-mgmt-rx|restore|status [bundle]';; esac
ACTION=${1:-check}
ENABLE_MGMT_RX=0
if [ "$ACTION" = run-mgmt-rx ]; then ENABLE_MGMT_RX=1; ACTION=run; fi
if [ "$ACTION" = status ]; then
    grep "^$NAME " /proc/modules || true
    for p in mishare_action_tx mishare_raw_tx mishare_mgmt_rx mishare_mgmt_rx_routed; do
        f=/sys/module/$NAME/parameters/$p
        [ ! -r "$f" ] || { printf '%s=' "$p"; cat "$f"; }
    done
    [ ! -d "$STATE" ] || echo 'Runtime trial state is present.'
    exit 0
fi
[ "$(getprop ro.product.device)" = popsicle ] || die 'This trial is only for popsicle.'
case "$(uname -r)" in 6.12.69-android16-6-*) ;; *) die 'Unexpected kernel; collect a fresh preflight.';; esac
[ "$(getprop sys.boot_completed)" = 1 ] || die 'Wait for Android boot to finish.'
mkdir "$LOCK" 2>/dev/null || die 'Another WLAN trial is running.'
trap finish 0
trap 'exit 130' INT
trap 'exit 143' TERM
if [ "$ACTION" = restore ]; then
    [ -r "$STATE/wifi.before" ] && [ -r "$STATE/hal.services" ] && [ -r "$STATE/stock.path" ] || die 'No complete runtime trial state.'
    [ "$(cat "$STATE/provider.owned" 2>/dev/null)" = 1 ] || die 'Missing provider ownership state; reboot to restore.'
    PROVIDER_OWNED=1
    BEFORE=$(cat "$STATE/wifi.before")
    HALS=$(cat "$STATE/hal.services")
    STOCK=$(cat "$STATE/stock.path")
    case "$BEFORE" in 0|1) ;; *) die 'Invalid saved Wi-Fi state.';; esac
    case "$STOCK" in /vendor/lib/modules/qca_cld3_peach_v2.ko|/vendor_dlkm/lib/modules/qca_cld3_peach_v2.ko) ;; *) die 'Invalid original module path.';; esac
    for h in $HALS; do case "$h" in vendor.wifi_hal*) ;; *) die 'Invalid saved HAL service.';; esac; done
    restore_stock || die 'Restore failed; reboot to restore original driver.'
    exit 0
fi
[ ! -d "$STATE" ] || die 'A previous runtime trial exists; use restore or reboot.'
loaded || die 'Original WLAN is not loaded.'
[ ! -e "/sys/module/$NAME/parameters/mishare_action_tx" ] || die 'Experimental WLAN is already loaded.'
[ ! -d /sys/module/wonder ] || die 'Stop the existing Wonder bridge first.'
[ ! -d "/sys/module/$PROVIDER" ] || die 'An existing provider is loaded; reboot before this isolated trial.'
AP=$(ls /sys/class/net | grep -E '^(ap|swlan|softap)|^wlan[1-9]|^ap_br' || true)
[ -z "$AP" ] || die 'Disable hotspot/secondary WLAN before trial.'
STOCK=/vendor_dlkm/lib/modules/qca_cld3_peach_v2.ko
[ -r "$STOCK" ] || STOCK=/vendor/lib/modules/qca_cld3_peach_v2.ko
[ -r "$STOCK" ] || die 'Original WLAN module file is missing.'
BEFORE=$(wifi_state)
case "$BEFORE" in 0|1) ;; *) die 'Cannot determine original Wi-Fi state.';; esac
HALS=$(getprop | sed -n 's/^\[init\.svc\.\(vendor\.wifi_hal[^]]*\)\]: \[running\]$/\1/p')
[ -n "$HALS" ] || die 'No recognized running Wi-Fi HAL; collect service inventory.'
for h in $HALS; do case "$h" in *[!a-zA-Z0-9_.-]*) die 'Unexpected HAL name.';; esac; done
[ -r "$BUNDLE/kernel/$PROVIDER.ko" ] && [ -r "$BUNDLE/kernel/$NAME.ko" ] && [ -r "$BUNDLE/SHA256SUMS" ] || die 'Incomplete bundle.'
(cd "$BUNDLE" && sha256sum -c SHA256SUMS) || die 'Bundle checksum failed.'
echo "CHECK_OK wifi_before=$BEFORE HAL=[$HALS] stock=$STOCK"
[ "$ACTION" = run ] || exit 0
# Resolve the mandatory private import before disrupting working stock WLAN.
insmod "$BUNDLE/kernel/$PROVIDER.ko" || die 'Provider load failed; original WLAN and Wi-Fi were not changed.'
PROVIDER_OWNED=1
[ -d "/sys/module/$PROVIDER" ] || die 'Provider did not register; original WLAN was not changed.'
umask 077
mkdir "$STATE" || die 'Cannot save trial state.'
printf '%s\n' "$BEFORE" > "$STATE/wifi.before"
printf '%s\n' "$HALS" > "$STATE/hal.services"
printf '%s\n' "$STOCK" > "$STATE/stock.path"
printf '1\n' > "$STATE/provider.owned"
CHANGED=1
fw svc wifi disable && wait_wifi 0 || die 'Wi-Fi did not disable.'
stop_hals || die 'Wi-Fi HAL did not stop.'
sleep 2
echo 'Unloading original WLAN with ordinary rmmod (no force).'
rmmod "$NAME" || die 'Original WLAN is busy; no forced unload.'
if [ "$ENABLE_MGMT_RX" = 1 ]; then
    insmod "$BUNDLE/kernel/$NAME.ko" mishare_action_tx=1 mishare_raw_tx=0 mishare_mgmt_rx=1 || die 'Trial driver load failed.'
    [ "$(cat "/sys/module/$NAME/parameters/mishare_mgmt_rx" 2>/dev/null)" = Y ] || die 'Management RX opt-in was not enabled.'
else
    insmod "$BUNDLE/kernel/$NAME.ko" mishare_action_tx=1 mishare_raw_tx=0 || die 'Trial driver load failed.'
fi
[ "$(cat "/sys/module/$NAME/parameters/mishare_action_tx" 2>/dev/null)" = Y ] || die 'Action backend is not enabled.'
wait_wlan || die 'Trial driver did not create wlan0.'
start_hals || die 'HAL restart failed.'
if [ "$BEFORE" = 1 ]; then fw svc wifi enable && wait_wifi 1 || die 'Wi-Fi did not enable.'; fi
KEEP=1
echo 'TRIAL_DRIVER_ACTIVE (module/Wi-Fi readiness only; RF/AWDL not verified).'
echo 'Use restore to return to stock; reboot also reloads the original driver.'
