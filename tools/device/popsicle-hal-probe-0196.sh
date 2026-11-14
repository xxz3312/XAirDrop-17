#!/system/bin/sh
# Stock-driver HAL stability probe; no module loader, overlay or init_boot operations.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
[ "$#" = 0 ] && [ "$(id -u)" = 0 ] || exit 2
[ "$(getprop ro.product.device)" = popsicle ] && [ "$(getprop ro.build.version.incremental)" = OS4.0.6.0.XPBCNXM ] || exit 2
[ "$(getprop init.svc.vendor.wifi_hal_legacy)" = running ] || { echo BASELINE_HAL_NOT_RUNNING; exit 1; }
hp_fw() {
    if HP_OUT=$("$@" 2>&1); then HP_RC=0; else HP_RC=$?; fi
    printf 'CMD:%s rc=%s\n%s\n' "$*" "$HP_RC" "$HP_OUT"
    return "$HP_RC"
}
hp_status() {
    hp_fw /system/bin/cmd wifi status || return 1
    HP_WIFI=unknown; HP_SCAN=unknown
    while IFS= read -r hp_line; do
        case "$hp_line" in
            'Wifi is enabled') HP_WIFI=enabled;; 'Wifi is disabled') HP_WIFI=disabled;;
            'Wifi scanning is always available') HP_SCAN=enabled;;
            'Wifi scanning is only available when wifi is enabled') HP_SCAN=disabled;;
        esac
    done <<EOF
$HP_OUT
EOF
    case "$HP_WIFI:$HP_SCAN" in enabled:enabled|enabled:disabled|disabled:enabled|disabled:disabled) return 0;; *) echo UNKNOWN_WIFI_SCAN_BASELINE; return 1;; esac
}
hp_status || exit 1
HP_WIFI_BEFORE=$HP_WIFI; HP_SCAN_BEFORE=$HP_SCAN
printf 'BASELINE:WIFI=%s SCAN=%s HAL=running\n' "$HP_WIFI_BEFORE" "$HP_SCAN_BEFORE"
HP_CNSS=$(sha256sum /sys/module/cnss2/notes/.note.gnu.build-id) &&
HP_WLAN=$(sha256sum /sys/module/qca_cld3_peach_v2/notes/.note.gnu.build-id) || exit 1
hp_notes() {
    [ "$(cat /sys/module/cnss2/initstate)" = live ] &&
    [ "$(cat /sys/module/qca_cld3_peach_v2/initstate)" = live ] &&
    [ "$(sha256sum /sys/module/cnss2/notes/.note.gnu.build-id)" = "$HP_CNSS" ] &&
    [ "$(sha256sum /sys/module/qca_cld3_peach_v2/notes/.note.gnu.build-id)" = "$HP_WLAN" ]
}
hp_notes || exit 1
hp_restore() {
    hp_restore_rc=0
    hp_fw /system/bin/start vendor.wifi_hal_legacy || hp_restore_rc=1
    hp_fw /system/bin/cmd wifi set-scan-always-available "$HP_SCAN_BEFORE" || hp_restore_rc=1
    hp_fw /system/bin/cmd wifi set-wifi-enabled "$HP_WIFI_BEFORE" || hp_restore_rc=1
    hp_restore_seen=0; hp_restore_n=0
    while [ "$hp_restore_n" -lt 20 ]; do
        if hp_status && [ "$HP_WIFI:$HP_SCAN" = "$HP_WIFI_BEFORE:$HP_SCAN_BEFORE" ] &&
            [ "$(getprop init.svc.vendor.wifi_hal_legacy)" = running ] && hp_notes; then hp_restore_seen=1; break; fi
        sleep 1; hp_restore_n=$((hp_restore_n+1))
    done
    [ "$hp_restore_rc:$hp_restore_seen" = 0:1 ]
}
hp_cleanup() {
    hp_result=$?
    trap - 0 INT TERM HUP
    if hp_restore; then echo HAL_PROBE_BASELINE_RESTORED; else echo HAL_PROBE_RESTORE_FAILED_REBOOT_STOCK_DRIVER; hp_result=2; fi
    exit "$hp_result"
}
trap hp_cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
# Install the restoration trap before the first possibly-partial mutation.
hp_fw /system/bin/cmd wifi set-scan-always-available disabled || exit 1
hp_fw /system/bin/cmd wifi set-wifi-enabled disabled || exit 1
hp_ready=0; hp_n=0
while [ "$hp_n" -lt 20 ]; do
    if hp_status && [ "$HP_WIFI:$HP_SCAN" = disabled:disabled ]; then hp_ready=1; break; fi
    sleep 1; hp_n=$((hp_n+1))
done
[ "$hp_ready" = 1 ] && hp_notes || exit 1
hp_fw /system/bin/stop vendor.wifi_hal_legacy || exit 1
hp_stopped=0; hp_n=0
while [ "$hp_n" -lt 10 ]; do
    [ "$(getprop init.svc.vendor.wifi_hal_legacy)" != stopped ] || { hp_stopped=1; break; }
    sleep 1; hp_n=$((hp_n+1))
done
[ "$hp_stopped" = 1 ] || { echo HAL_STOP_NOT_CONFIRMED; exit 1; }
hp_n=0
while [ "$hp_n" -lt 10 ]; do
    hp_hal=$(getprop init.svc.vendor.wifi_hal_legacy) || exit 1
    hp_status && hp_notes || exit 1
    printf 'OBSERVATION:%s HAL=%s WIFI=%s SCAN=%s\n' "$hp_n" "$hp_hal" "$HP_WIFI" "$HP_SCAN"
    [ "$hp_hal:$HP_WIFI:$HP_SCAN" = stopped:disabled:disabled ] || { echo HAL_RESTART_OR_FRAMEWORK_STATE_DRIFT; exit 1; }
    sleep 1; hp_n=$((hp_n+1))
done
[ "$(getprop init.svc.vendor.wifi_hal_legacy)" = stopped ] && hp_notes || exit 1
echo HAL_STABLE_10_SAMPLES_STOCK_DRIVER_ONLY
