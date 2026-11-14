#!/system/bin/sh
# Fixed-target adapter; no user-supplied flags or kernel parameter writes.
cy_absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
cy_small() {
    [ -f "$1" ] && sc_private "$1" && [ "$(stat -c %s "$1")" -le 256 ] || return 1
    [ "$(cat "$1")" = "$2" ]
}
cy_uuid() {
    case "$1" in ????????-????-????-????-????????????) ;; *) return 1;; esac
    case "$1" in *[!0-9a-f-]*) return 1;; esac
}
cy_bundle() {
    sc_private "$SC_BUNDLE/kernel" || return 1
    for cy_f in deployment.tsv SHA256SUMS stage-io.sh cycle-io.sh cycle-engine.sh cyclectl.sh kernel/qca_cld3_peach_v2.ko kernel/opairshare_wonder_provider.ko; do
        [ -f "$SC_BUNDLE/$cy_f" ] && sc_private "$SC_BUNDLE/$cy_f" || return 1
    done
    cy_absent "$SC_BUNDLE/kernel/cnss2.ko" &&
    [ "$(sc_key schema)" = 6 ] && [ "$(sc_key profile)" = stage0199-preserved-retrial-cycle ] &&
    [ "$(sc_key mode)" = diagnostic-defaults ] && [ "$(sc_key cycle_enabled)" = true ] &&
    [ "$(sc_key runtime_certified)" = false ] && [ "$(sc_key apply_enabled)" = false ] || return 1
    for cy_m in "$SC_WLAN" "$SC_PROVIDER"; do sc_hash_matches "$SC_BUNDLE/kernel/$cy_m.ko" "candidate.$cy_m.sha256" || return 1; done
}
cy_original() { sc_original_cnss; }
cy_backup() {
    [ -d "$CY_BACKUP" ] && sc_private "$CY_BACKUP" || return 1
    cy_small "$CY_BACKUP/phase" backup-only &&
    cy_small "$CY_BACKUP/manifest.sha256" "$(sc_key stage0194_manifest_sha256)" &&
    [ -f "$CY_BACKUP/boot-id" ] && sc_private "$CY_BACKUP/boot-id" &&
    [ "$(stat -c %s "$CY_BACKUP/boot-id")" -le 256 ] && cy_uuid "$(cat "$CY_BACKUP/boot-id")" &&
    [ -f "$CY_BACKUP/$SC_WLAN.ko" ] && sc_private "$CY_BACKUP/$SC_WLAN.ko" &&
    sc_hash_matches "$CY_BACKUP/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" || return 1
    # A previous boot's verified backup supplies bytes only, never current state.
    for cy_pending in "$CY_BACKUP".preparing.*; do cy_absent "$cy_pending" || return 1; done
}
cy_archive() {
    cy_old=$(sc_key prior_archive_path) || return 1
    [ -d "$cy_old" ] && sc_private "$cy_old" &&
    cy_small "$cy_old/phase" active && cy_small "$cy_old/boot-id" "$(sc_key prior_boot_id)" &&
    cy_small "$cy_old/manifest.sha256" "$(sc_key prior_manifest_sha256)" &&
    [ -f "$cy_old/$SC_WLAN.ko" ] && sc_private "$cy_old/$SC_WLAN.ko" &&
    sc_hash_matches "$cy_old/$SC_WLAN.ko" "stock.$SC_WLAN.sha256"
}
cy_foreign_absent() {
    for cy_f in /data/adb/xairdrop17-stockcnss-transaction /data/adb/xairdrop17-pair-transaction /dev/xairdrop17-pair.lock /dev/xairdrop17-wlan-trial; do cy_absent "$cy_f" || return 1; done
    for cy_m in wonder wonder_sysctl opairshare_route_b_probe oneplus13_wonder_provider; do cy_absent "/sys/module/$cy_m" || return 1; done
}
cy_snapshot() {
    cy_tmp=$CY_STATE.preparing.$$
    mkdir "$cy_tmp" || return 1
    cp "$CY_BACKUP/$SC_WLAN.ko" "$cy_tmp/$SC_WLAN.ko" &&
    printf '%s\n' "$cy_boot" > "$cy_tmp/boot-id" &&
    sc_hash "$SC_BUNDLE/deployment.tsv" > "$cy_tmp/manifest.sha256" &&
    printf '%s\n' "$cy_scan_before" > "$cy_tmp/scan.before" &&
    printf '%s\n' "$cy_before" > "$cy_tmp/wifi.before" &&
    printf '%s\n' "$cy_hals" > "$cy_tmp/hals" &&
    printf '%s\n' "$cy_iface" > "$cy_tmp/interface.before" &&
    printf 'prepared\n' > "$cy_tmp/phase" &&
    dmesg > "$cy_tmp/kernel.before.log" &&
    sc_hash_matches "$cy_tmp/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" || return 1
    # Re-observe identity, baseline and residue before publishing or any effects.
    sc_environment && cy_original && sc_expect_wlan stock && sc_provider_absent &&
    sc_cnss_holder "$SC_WLAN" && sc_interfaces && cy_foreign_absent && cy_backup && cy_archive && cy_aborted_archived &&
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$cy_boot" ] &&
    cy_framework && [ "$cy_fw_wifi:$cy_fw_scan" = "$cy_before:$cy_scan_before" ] && [ "$(sc_hals)" = "$cy_hals" ] && cy_absent "$CY_STATE" || return 1
    cy_tmp_id=$(stat -c %d:%i "$cy_tmp") && cy_dev=$(stat -c %d /data/adb) || return 1
    [ "${cy_tmp_id%%:*}" = "$cy_dev" ] && sync && mv -T -n -- "$cy_tmp" "$CY_STATE" &&
    cy_absent "$cy_tmp" && [ "$(stat -c %d:%i "$CY_STATE")" = "$cy_tmp_id" ] || return 1
    CY_STATE_ID=$cy_tmp_id
    SC_LOG=$CY_STATE/commands.log
    (set -C; : > "$SC_LOG") && cy_owned && cy_journal prepared
}
cy_owned() {
    [ -d "$CY_STATE" ] && sc_private "$CY_STATE" &&
    [ "$(stat -c %d:%i "$CY_STATE")" = "$CY_STATE_ID" ] &&
    cy_small "$CY_STATE/boot-id" "$cy_boot" && [ "$(cat /proc/sys/kernel/random/boot_id)" = "$cy_boot" ] &&
    cy_small "$CY_STATE/manifest.sha256" "$(sc_hash "$SC_BUNDLE/deployment.tsv")" &&
    cy_small "$CY_STATE/wifi.before" "$cy_before" &&
    cy_small "$CY_STATE/scan.before" "$cy_scan_before" &&
    cy_small "$CY_STATE/interface.before" "$cy_iface" &&
    [ -f "$CY_STATE/hals" ] && sc_private "$CY_STATE/hals" && [ "$(cat "$CY_STATE/hals")" = "$cy_hals" ] &&
    [ -f "$CY_STATE/$SC_WLAN.ko" ] && sc_private "$CY_STATE/$SC_WLAN.ko" &&
    sc_hash_matches "$CY_STATE/$SC_WLAN.ko" "stock.$SC_WLAN.sha256"
}
cy_journal() {
    cy_owned && cy_absent "$CY_STATE/phase.new" &&
    (set -C; printf '%s\n' "$1" > "$CY_STATE/phase.new") && sync &&
    mv -T -- "$CY_STATE/phase.new" "$CY_STATE/phase" &&
    cy_small "$CY_STATE/phase" "$1" && sc_log "PHASE:$1" && sync
}
cy_wait_wifi() {
    cy_n=0
    while [ "$cy_n" -lt 20 ]; do
        cy_seen=$(sc_wifi_state) || return 1
        [ "$cy_seen" != "$1" ] || return 0
        sleep 1; cy_n=$((cy_n+1))
    done
    return 1
}
cy_wifi_off() { cy_wait_wifi 0; }
cy_hals_state() {
    cy_n=0
    while [ "$cy_n" -lt 20 ]; do
        cy_ready=1
        while IFS= read -r cy_h; do
            cy_observed=$(getprop "init.svc.$cy_h") || return 1
            sc_log "HAL:$cy_h:expected=$1:actual=$cy_observed" || return 1
            [ "$cy_observed" = "$1" ] || cy_ready=0
        done < "$CY_STATE/hals"
        if [ "$cy_ready" = 1 ]; then
            cy_running=$(sc_hals) || return 1
            if [ "$1" = stopped ]; then [ -z "$cy_running" ]; else [ "$cy_running" = "$cy_hals" ]; fi
            return $?
        fi
        sleep 1; cy_n=$((cy_n+1))
    done
    return 1
}
cy_hals_stopped() { cy_hals_state stopped; }
cy_hals_running() { cy_hals_state running; }
cy_unloadable() {
    [ "$(cat "/sys/module/$1/refcnt")" = 0 ] && [ -z "$(ls -1 "/sys/module/$1/holders")" ]
}
cy_interface_baseline_restored() {
    cy_wait_wifi "$cy_before" && cy_hals_running || return 1
    cy_n=0
    while [ "$cy_n" -lt 20 ]; do
        cy_now=0; [ ! -d /sys/class/net/wlan0 ] || cy_now=1
        [ "$cy_now" != "$cy_iface" ] || return 0
        sleep 1; cy_n=$((cy_n+1))
    done
    return 1
}
cy_effect() {
    case "$1" in
        remove-stock|insert-provider|insert-candidate|remove-candidate|remove-provider|insert-stock)
            cy_gate "$1:original-cnss" cy_original &&
            cy_gate "$1:framework-quiet" cy_framework_quiet &&
            cy_gate "$1:hal-stopped" cy_hal_stopped_now &&
            cy_gate "$1:no-hotspot" sc_interfaces && cy_gate "$1:no-foreign-state" cy_foreign_absent || return 1;;
        scan-off|scan-restore|wifi-off|hals-stop|hals-start|wifi-restore) ;; *) return 2;;
    esac
    case "$1" in
        scan-off) sc_capture sc_android cmd wifi set-scan-always-available disabled;;
        scan-restore) sc_capture sc_android cmd wifi set-scan-always-available "$cy_scan_before";;
        wifi-off) sc_capture sc_android svc wifi disable;;
        hals-stop|hals-start)
            if [ "$1" = hals-stop ]; then cy_cmd=/system/bin/stop; else cy_cmd=/system/bin/start; fi
            while IFS= read -r cy_h; do
                sc_valid_hal "$cy_h" || return 1
                sc_capture "$cy_cmd" "$cy_h" || return "$?"
            done < "$CY_STATE/hals";;
        remove-stock) cy_gate "$1:stock-note" sc_expect_wlan stock && cy_gate "$1:provider-absent" sc_provider_absent && cy_gate "$1:holder" sc_cnss_holder "$SC_WLAN" && cy_gate "$1:unloadable" cy_unloadable "$SC_WLAN" && sc_capture /system/bin/rmmod "$SC_WLAN";;
        insert-provider) cy_gate "$1:wlan-absent" sc_wlan_absent && cy_gate "$1:holder-empty" sc_cnss_holder '' && cy_gate "$1:provider-absent" sc_provider_absent && cy_gate "$1:file-hash" sc_hash_matches "$SC_BUNDLE/kernel/$SC_PROVIDER.ko" "candidate.$SC_PROVIDER.sha256" && sc_capture /system/bin/insmod "$SC_BUNDLE/kernel/$SC_PROVIDER.ko";;
        insert-candidate) cy_gate "$1:wlan-absent" sc_wlan_absent && cy_gate "$1:holder-empty" sc_cnss_holder '' && cy_gate "$1:provider-note" sc_expect_provider && cy_gate "$1:file-hash" sc_hash_matches "$SC_BUNDLE/kernel/$SC_WLAN.ko" "candidate.$SC_WLAN.sha256" && sc_capture /system/bin/insmod "$SC_BUNDLE/kernel/$SC_WLAN.ko";;
        remove-candidate) cy_gate "$1:wlan-note" sc_expect_wlan candidate && cy_gate "$1:provider-note" sc_expect_provider && cy_gate "$1:holder" sc_cnss_holder "$SC_WLAN" && cy_gate "$1:unloadable" cy_unloadable "$SC_WLAN" && sc_capture /system/bin/rmmod "$SC_WLAN";;
        remove-provider) cy_gate "$1:wlan-absent" sc_wlan_absent && cy_gate "$1:holder-empty" sc_cnss_holder '' && cy_gate "$1:provider-note" sc_expect_provider && cy_gate "$1:unloadable" cy_unloadable "$SC_PROVIDER" && sc_capture /system/bin/rmmod "$SC_PROVIDER";;
        insert-stock) cy_gate "$1:wlan-absent" sc_wlan_absent && cy_gate "$1:provider-absent" sc_provider_absent && cy_gate "$1:holder-empty" sc_cnss_holder '' && cy_gate "$1:file-hash" sc_hash_matches "$CY_STATE/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" && sc_capture /system/bin/insmod "$CY_STATE/$SC_WLAN.ko";;
        wifi-restore)
            case "$cy_before" in 1) sc_capture sc_android svc wifi enable;; 0) sc_capture sc_android svc wifi disable;; *) return 1;; esac;;
    esac
}
cy_gate_command() { shift; "$@"; }
cy_gate() {
    [ "$#" -ge 2 ] || return 2
    if cy_gate_command "$@"; then cy_gate_rc=0; else cy_gate_rc=$?; fi
    sc_log "GATE:$1:rc=$cy_gate_rc" || return 1
    [ "$cy_gate_rc" = 0 ] || printf 'GATE_BLOCKED:%s:rc=%s\n' "$1" "$cy_gate_rc" >&2
    return "$cy_gate_rc"
}
cy_framework() {
    if cy_fw_out=$(sc_android cmd wifi status 2>&1); then cy_fw_rc=0; else cy_fw_rc=$?; fi
    sc_log "FRAMEWORK:rc=$cy_fw_rc:$cy_fw_out" || return 1
    [ "$cy_fw_rc" = 0 ] || return "$cy_fw_rc"
    cy_fw_wifi=unknown; cy_fw_scan=unknown
    while IFS= read -r cy_fw_line; do
        case "$cy_fw_line" in
            'Wifi is enabled') cy_fw_wifi=1;; 'Wifi is disabled') cy_fw_wifi=0;;
            'Wifi scanning is always available') cy_fw_scan=enabled;;
            'Wifi scanning is only available when wifi is enabled') cy_fw_scan=disabled;;
        esac
    done <<EOF
$cy_fw_out
EOF
    case "$cy_fw_wifi:$cy_fw_scan" in 0:enabled|0:disabled|1:enabled|1:disabled) return 0;; *) return 1;; esac
}
cy_framework_quiet() { cy_framework && [ "$cy_fw_wifi:$cy_fw_scan" = 0:disabled ]; }
cy_scan_wait() {
    cy_scan_n=0
    while [ "$cy_scan_n" -lt 20 ]; do
        cy_framework || return 1
        [ "$cy_fw_scan" != "$1" ] || return 0
        sleep 1; cy_scan_n=$((cy_scan_n+1))
    done
    return 1
}
cy_scan_off() { cy_scan_wait disabled; }
cy_scan_matches() { cy_scan_wait "$cy_scan_before"; }
cy_hal_stopped_now() {
    while IFS= read -r cy_h; do
        cy_observed=$(getprop "init.svc.$cy_h") || return 1
        sc_log "HAL:$cy_h:expected=stopped:actual=$cy_observed" || return 1
        [ "$cy_observed" = stopped ] || return 1
    done < "$CY_STATE/hals"
    cy_running=$(sc_hals) && [ -z "$cy_running" ]
}
cy_hals_stable() {
    cy_hals_stopped || return 1
    cy_sample=0
    while [ "$cy_sample" -lt 10 ]; do
        cy_gate "hal-sample-$cy_sample:framework" cy_framework_quiet &&
        cy_gate "hal-sample-$cy_sample:hal" cy_hal_stopped_now &&
        cy_gate "hal-sample-$cy_sample:cnss" cy_original && sc_expect_wlan stock || return 1
        sc_log "HAL_STABLE_SAMPLE:$cy_sample" || return 1
        sleep 1; cy_sample=$((cy_sample+1))
    done
    cy_hal_stopped_now && cy_framework_quiet
}
cy_baseline_restored() {
    cy_scan_matches && cy_interface_baseline_restored
}
cy_stock_ready() {
    cy_gate environment sc_environment && cy_gate foreign-state cy_foreign_absent &&
    cy_gate original-cnss cy_original && cy_gate stock-note sc_expect_wlan stock &&
    cy_gate provider-absent sc_provider_absent && cy_gate cnss-holder sc_cnss_holder "$SC_WLAN" &&
    cy_gate no-hotspot sc_interfaces && cy_gate stock-backup cy_backup && cy_gate old-0193-archive cy_archive
}
cy_legacy_destination() {
    cy_legacy_boot=$(sc_key legacy195.boot_id) && cy_uuid "$cy_legacy_boot" || return 1
    CY_LEGACY_DEST=$CY_STATE.previous.0195.$cy_legacy_boot
}
cy_legacy_record() {
    cy_legacy_path=$1
    [ -d "$cy_legacy_path" ] && sc_private "$cy_legacy_path" && cy_absent "$cy_legacy_path/phase.new" || return 1
    cy_small "$cy_legacy_path/phase" 'returned:insert-provider:1' &&
    cy_small "$cy_legacy_path/boot-id" "$(sc_key legacy195.boot_id)" &&
    [ "$(cat /proc/sys/kernel/random/boot_id)" != "$(sc_key legacy195.boot_id)" ] &&
    cy_small "$cy_legacy_path/manifest.sha256" "$(sc_key legacy195.manifest_sha256)" &&
    cy_small "$cy_legacy_path/wifi.before" 1 && cy_small "$cy_legacy_path/interface.before" 1 &&
    cy_small "$cy_legacy_path/hals" vendor.wifi_hal_legacy || return 1
    for cy_legacy_file in commands.log kernel.before.log kernel.after.log; do
        [ -f "$cy_legacy_path/$cy_legacy_file" ] && sc_private "$cy_legacy_path/$cy_legacy_file" &&
        sc_hash_matches "$cy_legacy_path/$cy_legacy_file" "legacy195.$cy_legacy_file.sha256" || return 1
    done
    [ -f "$cy_legacy_path/$SC_WLAN.ko" ] && sc_private "$cy_legacy_path/$SC_WLAN.ko" &&
    sc_hash_matches "$cy_legacy_path/$SC_WLAN.ko" "stock.$SC_WLAN.sha256"
}
cy_no_preparing() {
    for cy_pending in "$CY_STATE".preparing.*; do cy_absent "$cy_pending" || return 1; done
}
# Exact observed pre-unload abort only. This is not a generic reset/retry API.
cy_aborted_destination() {
    cy_aborted_boot=$(sc_key aborted197.boot_id) && cy_uuid "$cy_aborted_boot" || return 1
    CY_ABORTED_DEST=$CY_STATE.previous.0197.$cy_aborted_boot
}
cy_aborted_record() {
    cy_aborted_path=$1
    [ -d "$cy_aborted_path" ] && sc_private "$cy_aborted_path" && cy_absent "$cy_aborted_path/phase.new" || return 1
    cy_aborted_count=0
    # Reject unexpected residue, including recovery logs or hidden files.
    for cy_aborted_member in "$cy_aborted_path"/* "$cy_aborted_path"/.[!.]* "$cy_aborted_path"/..?*; do
        cy_absent "$cy_aborted_member" && continue
        case "${cy_aborted_member##*/}" in
            boot-id|manifest.sha256|phase|wifi.before|scan.before|interface.before|hals|commands.log|kernel.before.log|kernel.after.log|qca_cld3_peach_v2.ko) ;;
            *) return 1;;
        esac
        cy_aborted_count=$((cy_aborted_count+1))
    done
    [ "$cy_aborted_count" = 11 ] || return 1
    for cy_aborted_file in boot-id manifest.sha256 phase wifi.before scan.before interface.before hals commands.log kernel.before.log kernel.after.log; do
        [ -f "$cy_aborted_path/$cy_aborted_file" ] && sc_private "$cy_aborted_path/$cy_aborted_file" &&
        sc_hash_matches "$cy_aborted_path/$cy_aborted_file" "aborted197.$cy_aborted_file.sha256" || return 1
    done
    cy_small "$cy_aborted_path/boot-id" "$cy_aborted_boot" &&
    cy_small "$cy_aborted_path/manifest.sha256" "$(sc_key aborted197.manifest_sha256)" &&
    cy_small "$cy_aborted_path/phase" done:hals-stop &&
    [ -f "$cy_aborted_path/$SC_WLAN.ko" ] && sc_private "$cy_aborted_path/$SC_WLAN.ko" &&
    sc_hash_matches "$cy_aborted_path/$SC_WLAN.ko" "stock.$SC_WLAN.sha256"
}
cy_history_ready() {
    cy_legacy_destination && cy_legacy_record "$CY_LEGACY_DEST" && cy_aborted_destination
}
cy_aborted_archived() { cy_history_ready && cy_aborted_record "$CY_ABORTED_DEST"; }
cy_install_check() {
    cy_stock_ready && cy_no_preparing && cy_history_ready || return 1
    if cy_absent "$CY_STATE"; then cy_aborted_record "$CY_ABORTED_DEST"
    else cy_absent "$CY_ABORTED_DEST" && cy_aborted_record "$CY_STATE"; fi
}
cy_preflight() {
    cy_stock_ready && cy_no_preparing && cy_absent "$CY_STATE" && cy_aborted_archived || return 1
    cy_framework && cy_before=$cy_fw_wifi && cy_scan_before=$cy_fw_scan &&
    cy_hals=$(sc_hals) && [ -n "$cy_hals" ] || return 1
    cy_boot=$(cat /proc/sys/kernel/random/boot_id) && cy_uuid "$cy_boot" || return 1
    cy_iface=0; [ ! -d /sys/class/net/wlan0 ] || cy_iface=1
    [ "$cy_before" = 0 ] || [ "$cy_iface" = 1 ]
}
cy_archive_aborted() {
    cy_stock_ready && cy_no_preparing && cy_history_ready || return 1
    if cy_absent "$CY_STATE"; then
        cy_aborted_record "$CY_ABORTED_DEST" || return 1
        echo STAGE0199_EXISTING_0197_ARCHIVE_VERIFIED_ONLY
        return 0
    fi
    cy_absent "$CY_ABORTED_DEST" && cy_aborted_record "$CY_STATE" || return 1
    cy_aborted_id=$(stat -c %d:%i "$CY_STATE") && cy_aborted_dev=$(stat -c %d /data/adb) || return 1
    [ "${cy_aborted_id%%:*}" = "$cy_aborted_dev" ] && sync || return 1
    mv -T -n -- "$CY_STATE" "$CY_ABORTED_DEST" || return 1
    cy_absent "$CY_STATE" && [ "$(stat -c %d:%i "$CY_ABORTED_DEST")" = "$cy_aborted_id" ] &&
    cy_aborted_record "$CY_ABORTED_DEST" || { echo ARCHIVE_UNCERTAIN_PRESERVE_STATE; return 1; }
    echo STAGE0199_0197_PREUNLOAD_RECORD_PRESERVED_ONLY
}
cy_restore_framework() {
    cy_restore_rc=0
    while IFS= read -r cy_h; do
        sc_valid_hal "$cy_h" || return 1
        sc_capture /system/bin/start "$cy_h" || cy_restore_rc=1
    done < "$CY_STATE/hals"
    sc_capture sc_android cmd wifi set-scan-always-available "$cy_scan_before" || cy_restore_rc=1
    case "$cy_before" in 1) cy_wifi_arg=enable;; 0) cy_wifi_arg=disable;; *) return 1;; esac
    sc_capture sc_android svc wifi "$cy_wifi_arg" || cy_restore_rc=1
    cy_baseline_restored || cy_restore_rc=1
    [ "$cy_restore_rc" = 0 ]
}
cy_failure_cleanup() {
    # Only framework restoration when exact original hardware identity is present.
    # No driver insertion/removal and no phase rewrite after any failure.
    cy_owned && cy_original && sc_expect_wlan stock && sc_provider_absent &&
    sc_cnss_holder "$SC_WLAN" && cy_foreign_absent || { echo FRAMEWORK_RECOVERY_SKIPPED_STOCK_NOT_CONFIRMED; return 1; }
    cy_restore_framework && { echo STAGE0199_FAILURE_FRAMEWORK_BASELINE_RESTORED_ONLY; return 0; }
    echo FRAMEWORK_BASELINE_RECOVERY_INCOMPLETE
    return 1
}
cy_recover_settings() {
    # Post-reboot only. A previous failed record supplies settings, never loader replay.
    cy_stock_ready && cy_aborted_archived &&
    cy_no_preparing && [ -d "$CY_STATE" ] && sc_private "$CY_STATE" || return 1
    cy_small "$CY_STATE/manifest.sha256" "$(sc_hash "$SC_BUNDLE/deployment.tsv")" || return 1
    for cy_recover_f in boot-id phase wifi.before scan.before interface.before hals; do
        [ -f "$CY_STATE/$cy_recover_f" ] && sc_private "$CY_STATE/$cy_recover_f" &&
        [ "$(stat -c %s "$CY_STATE/$cy_recover_f")" -le 4096 ] || return 1
    done
    cy_saved_boot=$(cat "$CY_STATE/boot-id") && cy_uuid "$cy_saved_boot" &&
    [ "$cy_saved_boot" != "$(cat /proc/sys/kernel/random/boot_id)" ] || return 1
    cy_saved_phase=$(cat "$CY_STATE/phase")
    case "$cy_saved_phase" in prepared|candidate-pair-live|intent:*|returned:*|done:*) ;; *) return 1;; esac
    cy_before=$(cat "$CY_STATE/wifi.before"); cy_scan_before=$(cat "$CY_STATE/scan.before"); cy_iface=$(cat "$CY_STATE/interface.before"); cy_hals=$(cat "$CY_STATE/hals")
    case "$cy_before:$cy_iface:$cy_scan_before" in [01]:[01]:enabled|[01]:[01]:disabled) ;; *) return 1;; esac
    [ -n "$cy_hals" ] || return 1
    while IFS= read -r cy_h; do sc_valid_hal "$cy_h" || return 1; done < "$CY_STATE/hals"
    [ -f "$CY_STATE/$SC_WLAN.ko" ] && sc_private "$CY_STATE/$SC_WLAN.ko" &&
    sc_hash_matches "$CY_STATE/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" || return 1
    SC_LOG=$CY_STATE/framework-recovery.$$.log
    (set -C; : > "$SC_LOG") || return 1
    cy_restore_framework || return 1
    echo STAGE0199_POST_REBOOT_SETTINGS_RESTORED_NO_CYCLE_REPLAY
}
