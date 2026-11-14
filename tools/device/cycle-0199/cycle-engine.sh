#!/system/bin/sh
# IO-free diagnostic round trip. Adapter owns identities, journal and effects.
cy_step() {
    [ "$#" = 1 ] || return 2
    case "$1" in scan-off|scan-restore|wifi-off|hals-stop|remove-stock|insert-provider|insert-candidate|remove-candidate|remove-provider|insert-stock|hals-start|wifi-restore) ;; *) return 2;; esac
    cy_gate "$1:original-cnss" cy_original && cy_gate "$1:transaction-owner" cy_owned || return 1
    cy_journal "intent:$1" || return 1
    if cy_effect "$1"; then cy_rc=0; else cy_rc=$?; fi
    cy_journal "returned:$1:$cy_rc" || return 1
    [ "$cy_rc" = 0 ] || return "$cy_rc"
    cy_gate "$1:original-cnss" cy_original && cy_gate "$1:transaction-owner" cy_owned || return 1
    cy_journal "done:$1"
}
cy_run() {
    cy_preflight && cy_snapshot || return 1
    cy_step scan-off && cy_gate scan-disabled cy_scan_off || return 1
    cy_step wifi-off && cy_gate wifi-disabled cy_wifi_off || return 1
    cy_step hals-stop && cy_gate hal-stable-before-unload cy_hals_stable || return 1
    cy_step remove-stock && sc_wlan_absent && sc_cnss_holder '' || return 1
    cy_step insert-provider && sc_expect_provider || return 1
    cy_step insert-candidate && sc_expect_wlan candidate && sc_cnss_holder "$SC_WLAN" || return 1
    cy_journal candidate-pair-live || return 1
    # No HAL/native START with the candidate. Only an identity diagnostic.
    cy_step remove-candidate && sc_wlan_absent && sc_cnss_holder '' || return 1
    cy_step remove-provider && sc_provider_absent || return 1
    cy_step insert-stock && sc_expect_wlan stock && sc_cnss_holder "$SC_WLAN" || return 1
    cy_step hals-start && cy_hals_running || return 1
    cy_step scan-restore && cy_gate scan-baseline cy_scan_matches || return 1
    cy_step wifi-restore && cy_gate framework-baseline cy_baseline_restored || return 1
    cy_original && sc_expect_wlan stock && sc_provider_absent && sc_cnss_holder "$SC_WLAN" || return 1
    cy_journal restored
}
