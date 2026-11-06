#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# IO-free policy core. The future device adapter supplies sc_* observations,
# journal and effects. Sourcing this file performs no device operations.
# Upstream: XAirDrop action.sh and OPAirDrop control.sh retain stock CNSS2.
# No restore/replay: the initial deployment contract uses reboot recovery.

sc_change() {
    [ "$#" = 1 ] || return 2
    case "$1" in
        wifi-off|hals-stop|remove-wlan|insert-provider|insert-wlan|hals-start|wifi-restore) ;;
        *) return 2;;
    esac
    sc_original_cnss || return 1
    sc_journal "intent:$1" || return 1
    # The adapter must preserve the actual command's exit status. Do not
    # pipe a kernel command into tee and accidentally record tee's status.
    if sc_effect "$1"; then sc_rc=0; else sc_rc=$?; fi
    sc_journal "returned:$1:$sc_rc" || return 1
    [ "$sc_rc" = 0 ] || return "$sc_rc"
    sc_original_cnss || return 1
    sc_journal "done:$1"
}

sc_start_stock_cnss() {
    sc_environment || return 1
    sc_bundle || return 1
    sc_no_other_transaction || return 1
    sc_original_cnss || return 1
    sc_expect_wlan stock || return 1
    sc_provider_absent || return 1
    sc_interfaces || return 1
    sc_cnss_holder qca_cld3_peach_v2 || return 1
    sc_snapshot || return 1
    sc_journal prepared || return 1

    sc_change wifi-off || return 1
    sc_wifi_is_off || return 1
    sc_change hals-stop || return 1
    sc_hals_are_stopped || return 1
    sc_expect_wlan stock || return 1
    sc_wlan_unloadable || return 1
    sc_change remove-wlan || return 1
    sc_wlan_absent || return 1
    sc_cnss_holder '' || return 1

    sc_change insert-provider || return 1
    sc_expect_provider || return 1
    sc_change insert-wlan || return 1
    sc_expect_wlan candidate || return 1
    sc_cnss_holder qca_cld3_peach_v2 || return 1

    sc_change hals-start || return 1
    sc_hals_are_running || return 1
    sc_change wifi-restore || return 1
    sc_wifi_matches_snapshot || return 1
    sc_original_cnss || return 1
    sc_expect_wlan candidate || return 1
    sc_expect_provider || return 1
    sc_cnss_holder qca_cld3_peach_v2 || return 1
    sc_journal active
}
