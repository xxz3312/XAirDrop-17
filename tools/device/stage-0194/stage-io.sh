#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Adapter functions only; constants and dispatch are owned by stock-cnssctl.
# Framework capture follows XAirDrop action.sh fw()/wifi_state().
sc_log() { [ -z "${SC_LOG:-}" ] || printf '%s\n' "$*" >> "$SC_LOG"; }
sc_error() { printf '%s\n' "BLOCKED:$*" >&2; sc_log "BLOCKED:$*"; return 1; }
sc_hash() {
    sc_sum=$(sha256sum "$1") || return 1
    printf '%s\n' "${sc_sum%% *}"
}
sc_hash_matches() {
    sc_actual_hash=$(sc_hash "$1") && sc_expected_hash=$(sc_key "$2") || return 1
    [ "$sc_actual_hash" = "$sc_expected_hash" ]
}
sc_private() {
    [ ! -L "$1" ] && [ "$(stat -c %u "$1")" = 0 ] || return 1
    sc_mode=$(stat -c %a "$1") || return 1
    case "$sc_mode" in ''|*[!0-7]*) return 1;; esac
    case "${#sc_mode}" in 3|4) ;; *) return 1;; esac
    case "$sc_mode" in *[2367][0-7]|*[0-7][2367]) return 1;; esac
}
sc_key() {
    sc_wanted=$1; sc_count=0; sc_found=
    while IFS='	' read -r sc_k sc_v sc_extra; do
        if [ "$sc_k" = "$sc_wanted" ]; then
            [ -z "$sc_extra" ] || return 1
            sc_count=$((sc_count+1)); sc_found=$sc_v
        fi
    done < "$SC_BUNDLE/deployment.tsv"
    [ "$sc_count" = 1 ] && [ -n "$sc_found" ] || return 1
    printf '%s\n' "$sc_found"
}
sc_android() {
    sc_tool=$1; shift
    case "$sc_tool" in cmd) /system/bin/cmd "$@";; svc) /system/bin/svc "$@";; *) return 2;; esac
}
sc_capture() {
    if sc_out=$("$@" 2>&1); then sc_status=0; else sc_status=$?; fi
    sc_log "COMMAND:$*:rc=$sc_status" && sc_log "$sc_out" || return 1
    [ "$sc_status" = 0 ] || printf '%s\n' "$sc_out" >&2
    return "$sc_status"
}
sc_wifi_state() {
    if sc_wifi_out=$(sc_android cmd wifi status 2>&1); then sc_wifi_rc=0; else sc_wifi_rc=$?; fi
    sc_log "WIFI_STATUS:rc=$sc_wifi_rc:$sc_wifi_out"
    [ "$sc_wifi_rc" = 0 ] || return 1
    case "$sc_wifi_out" in 'Wifi is enabled'*) printf '1\n';; 'Wifi is disabled'*) printf '0\n';; *) return 1;; esac
}
sc_hals() {
    # Stream like upstream hal_services(). Android printf may be external:
    # never pass the complete property dump through an exec argument.
    # Keep a producer receipt so getprop failure cannot look like no HALs.
    sc_inventory=$(
        {
            if getprop; then sc_prop_rc=0; else sc_prop_rc=$?; fi
            printf '\nSC_GETPROP_RC:%s\n' "$sc_prop_rc"
        } | sed -n -e 's/^\[init\.svc\.\(vendor\.wifi_hal[^]]*\)\]: \[running\]$/\1/p' -e '/^SC_GETPROP_RC:/p'
    ) || return 1
    sc_receipt=; sc_services=
    while IFS= read -r sc_line; do
        case "$sc_line" in
            SC_GETPROP_RC:*)
                [ -z "$sc_receipt" ] || return 1
                sc_receipt=$sc_line;;
            '') ;;
            *)
                sc_valid_hal "$sc_line" || return 1
                if [ -z "$sc_services" ]; then sc_services=$sc_line
                else sc_services="$sc_services
$sc_line"; fi;;
        esac
    done <<EOF
$sc_inventory
EOF
    [ "$sc_receipt" = SC_GETPROP_RC:0 ] || return 1
    sort <<EOF
$sc_services
EOF
}
sc_valid_hal() {
    case "$1" in vendor.wifi_hal*) ;; *) return 1;; esac
    case "$1" in *[!a-zA-Z0-9_.-]*) return 1;; esac
}
sc_note_matches() {
    [ -d "/sys/module/$1" ] && [ "$(cat "/sys/module/$1/initstate")" = live ] || return 1
    sc_hash_matches "/sys/module/$1/notes/.note.gnu.build-id" "$2.$1.note_sha256"
}
sc_original_cnss() { sc_note_matches cnss2 stock || sc_error ORIGINAL_CNSS2_IDENTITY; }
sc_expect_wlan() { sc_note_matches "$SC_WLAN" "$1" || sc_error "WLAN_IDENTITY:$1"; }
sc_expect_provider() { sc_note_matches "$SC_PROVIDER" candidate || sc_error PROVIDER_IDENTITY; }
sc_provider_absent() { [ ! -d "/sys/module/$SC_PROVIDER" ]; }
sc_wlan_absent() { [ ! -d "/sys/module/$SC_WLAN" ]; }
sc_cnss_holder() {
    sc_hold=$(ls -1 /sys/module/cnss2/holders) || return 1
    [ "$sc_hold" = "$1" ] || sc_error CNSS2_HOLDERS
}
sc_wlan_unloadable() {
    sc_wlan_holders=$(ls -1 "/sys/module/$SC_WLAN/holders") || return 1
    [ "$(cat "/sys/module/$SC_WLAN/refcnt")" = 0 ] &&
    [ -z "$sc_wlan_holders" ] || sc_error WLAN_BUSY
}
sc_interfaces() {
    for sc_f in /sys/class/net/*; do
        case "${sc_f##*/}" in ap*|swlan*|softap*|wlan[1-9]*) sc_error HOTSPOT_INTERFACE; return 1;; esac
    done
}
sc_stock_file() {
    sc_selected=
    for sc_d in /vendor_dlkm/lib/modules /vendor/lib/modules; do
        sc_f="$sc_d/$1.ko"
        if [ -f "$sc_f" ]; then
            sc_hash_matches "$sc_f" "stock.$1.sha256" || return 1
            sc_selected=$sc_f
        fi
    done
    [ -n "$sc_selected" ] || return 1
    printf '%s\n' "$sc_selected"
}

sc_environment() {
    [ "$(getprop ro.product.device)" = "$(sc_key device)" ] &&
    [ "$(getprop ro.build.version.incremental)" = "$(sc_key firmware)" ] &&
    [ "$(uname -r)" = "$(sc_key kernel)" ] && [ "$(uname -m)" = aarch64 ] &&
    [ "$(getprop sys.boot_completed)" = 1 ] || { sc_error DEVICE_OR_KERNEL; return 1; }
    sc_slot=$(getprop ro.boot.slot_suffix)
    case "$sc_slot" in _a|_b) ;; *) return 1;; esac
    [ -b "/dev/block/by-name/boot$sc_slot" ] && sc_hash_matches "/dev/block/by-name/boot$sc_slot" boot_sha256 || return 1
    sc_stock_file cnss2 >/dev/null && sc_stock_file "$SC_WLAN" >/dev/null
}
sc_bundle() {
    case "$SC_BUNDLE" in /data/adb/modules/xairdrop17_stage0194|/data/adb/modules_update/xairdrop17_stage0194) ;; *) return 1;; esac
    sc_parent=$SC_BUNDLE
    while :; do
        sc_private "$sc_parent" || return 1
        [ "$sc_parent" = /data/adb ] && break
        sc_parent=${sc_parent%/*}
    done
    sc_private "$SC_BUNDLE/kernel" || return 1
    for sc_f in deployment.tsv SHA256SUMS stagectl.sh stage-io.sh kernel/qca_cld3_peach_v2.ko kernel/opairshare_wonder_provider.ko; do
        [ -f "$SC_BUNDLE/$sc_f" ] && sc_private "$SC_BUNDLE/$sc_f" || return 1
    done
    [ ! -e "$SC_BUNDLE/kernel/cnss2.ko" ] || return 1
    (cd "$SC_BUNDLE" && sha256sum -c SHA256SUMS) || return 1
    [ "$(sc_key schema)" = 3 ] && [ "$(sc_key profile)" = stage0194-check-backup ] &&
    [ "$(sc_key apply_enabled)" = false ] &&
    [ "$(sc_key mode)" = diagnostic-defaults ] && [ "$(sc_key runtime_certified)" = false ] || return 1
    for sc_m in "$SC_WLAN" "$SC_PROVIDER"; do
        sc_hash_matches "$SC_BUNDLE/kernel/$sc_m.ko" "candidate.$sc_m.sha256" || return 1
    done
}
sc_verify_snapshot() {
    [ -d "$SC_STATE" ] && sc_private "$SC_STATE" || return 1
    for sc_f in boot-id manifest.sha256 wifi.before hals "$SC_WLAN.ko"; do
        [ -f "$SC_STATE/$sc_f" ] && sc_private "$SC_STATE/$sc_f" || return 1
    done
    [ "$(cat "$SC_STATE/boot-id")" = "$(cat /proc/sys/kernel/random/boot_id)" ] &&
    [ "$(cat "$SC_STATE/manifest.sha256")" = "$(sc_hash "$SC_BUNDLE/deployment.tsv")" ] &&
    sc_hash_matches "$SC_STATE/$SC_WLAN.ko" "stock.$SC_WLAN.sha256" || return 1
    case "$(cat "$SC_STATE/wifi.before")" in 0|1) ;; *) return 1;; esac
    [ -s "$SC_STATE/hals" ] || return 1
    while IFS= read -r sc_h; do sc_valid_hal "$sc_h" || return 1; done < "$SC_STATE/hals"
}