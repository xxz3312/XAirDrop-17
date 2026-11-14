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
    [ "$(sc_key schema)" = 4 ] && [ "$(sc_key profile)" = stage0195-diagnostic-cycle ] &&
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
cy_preflight() {
    sc_environment && cy_foreign_absent && cy_original && sc_expect_wlan stock &&
    sc_provider_absent && sc_cnss_holder "$SC_WLAN" && sc_interfaces && cy_backup && cy_archive &&
    cy_absent "$CY_STATE" || return 1
    for cy_pending in "$CY_STATE".preparing.*; do cy_absent "$cy_pending" || return 1; done
    cy_before=$(sc_wifi_state) && cy_hals=$(sc_hals) && [ -n "$cy_hals" ] || return 1
    cy_boot=$(cat /proc/sys/kernel/random/boot_id) && cy_uuid "$cy_boot" || return 1
    cy_iface=0; [ ! -d /sys/class/net/wlan0 ] || cy_iface=1
    [ "$cy_before" = 0 ] || [ "$cy_iface" = 1 ]
}
cy_snapshot() {
    cy_tmp=$CY_STATE.preparing.$$
    mkdir "$cy_tmp" || return 1
    cp "$CY_BACKUP/$SC_WLAN.ko" "$cy_tmp/$SC_WLAN.ko" &&
    printf '%s\n' "$cy_boot" > "$cy_tmp/boot-id" &&
    sc_hash "$SC_BUNDLE/deployment.tsv" > "$cy_tmp/manifest.sha256" &&
    printf '%s\n' "$cy_before" > "$cy_tmp/wifi.before" &&
    printf '%s\n' "$cy_hals" > "$cy_tmp/hals" &&
    printf '%s\n' "$cy_iface" > "$cy_tmp/interface.before" &&
    printf 'prepared\n' > "$cy_tmp/phase" &&
    dmesg > "$cy_tmp/kernel.before.log" &&
    sc_hash_matches "$cy_tmp/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" || return 1
    # Re-observe identity, baseline and residue before publishing or any effects.
    sc_environment && cy_original && sc_expect_wlan stock && sc_provider_absent &&
    sc_cnss_holder "$SC_WLAN" && sc_interfaces && cy_foreign_absent && cy_backup && cy_archive &&
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$cy_boot" ] &&
    [ "$(sc_wifi_state)" = "$cy_before" ] && [ "$(sc_hals)" = "$cy_hals" ] && cy_absent "$CY_STATE" || return 1
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
        while IFS= read -r cy_h; do [ "$(getprop "init.svc.$cy_h")" = "$1" ] || cy_ready=0; done < "$CY_STATE/hals"
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
cy_baseline_restored() {
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
            cy_original && cy_wifi_off && cy_hals_stopped && sc_interfaces && cy_foreign_absent || return 1;;
        wifi-off|hals-stop|hals-start|wifi-restore) ;; *) return 2;;
    esac
    case "$1" in
        wifi-off) sc_capture sc_android svc wifi disable;;
        hals-stop|hals-start)
            if [ "$1" = hals-stop ]; then cy_cmd=/system/bin/stop; else cy_cmd=/system/bin/start; fi
            while IFS= read -r cy_h; do
                sc_valid_hal "$cy_h" || return 1
                sc_capture "$cy_cmd" "$cy_h" || return "$?"
            done < "$CY_STATE/hals";;
        remove-stock) sc_expect_wlan stock && sc_provider_absent && sc_cnss_holder "$SC_WLAN" && cy_unloadable "$SC_WLAN" && sc_capture /system/bin/rmmod "$SC_WLAN";;
        insert-provider) sc_wlan_absent && sc_cnss_holder '' && sc_provider_absent && sc_hash_matches "$SC_BUNDLE/kernel/$SC_PROVIDER.ko" "candidate.$SC_PROVIDER.sha256" && sc_capture /system/bin/insmod "$SC_BUNDLE/kernel/$SC_PROVIDER.ko";;
        insert-candidate) sc_wlan_absent && sc_cnss_holder '' && sc_expect_provider && sc_hash_matches "$SC_BUNDLE/kernel/$SC_WLAN.ko" "candidate.$SC_WLAN.sha256" && sc_capture /system/bin/insmod "$SC_BUNDLE/kernel/$SC_WLAN.ko";;
        remove-candidate) sc_expect_wlan candidate && sc_expect_provider && sc_cnss_holder "$SC_WLAN" && cy_unloadable "$SC_WLAN" && sc_capture /system/bin/rmmod "$SC_WLAN";;
        remove-provider) sc_wlan_absent && sc_cnss_holder '' && sc_expect_provider && cy_unloadable "$SC_PROVIDER" && sc_capture /system/bin/rmmod "$SC_PROVIDER";;
        insert-stock) sc_wlan_absent && sc_provider_absent && sc_cnss_holder '' && sc_hash_matches "$CY_STATE/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" && sc_capture /system/bin/insmod "$CY_STATE/$SC_WLAN.ko";;
        wifi-restore)
            case "$cy_before" in 1) sc_capture sc_android svc wifi enable;; 0) sc_capture sc_android svc wifi disable;; *) return 1;; esac;;
    esac
}
