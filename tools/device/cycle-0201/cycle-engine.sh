#!/system/bin/sh
# IO-free diagnostic round trip. Adapter owns identities, journal and effects.
cy_step() {
    [ "$#" = 1 ] || return 2
    case "$1" in scan-off|scan-restore|wifi-off|hals-stop|remove-stock|insert-provider|insert-candidate|remove-candidate|remove-provider|insert-stock|hals-start|wifi-restore|candidate-hals-start|candidate-wifi-on|candidate-wifi-off|candidate-hals-stop) ;; *) return 2;; esac
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
    cy_step candidate-hals-start && cy_gate candidate-hal-running cy_hals_running || return 1
    cy_step candidate-wifi-on && cy_gate candidate-wifi-enabled cy_wait_candidate_wifi || return 1
    cy_candidate_observe || return 1
    # Always use the explicit normal shutdown after ordinary observation gaps.
    # Never unload a candidate under a running HAL or use forced unload.
    cy_step candidate-wifi-off && cy_gate candidate-wifi-disabled cy_wifi_off || return 1
    cy_step candidate-hals-stop && cy_gate candidate-hal-stable-before-unload cy_candidate_quiet || return 1
    cy_step remove-candidate && sc_wlan_absent && sc_cnss_holder '' || return 1
    cy_step remove-provider && sc_provider_absent || return 1
    cy_step insert-stock && sc_expect_wlan stock && sc_cnss_holder "$SC_WLAN" || return 1
    cy_step hals-start && cy_hals_running || return 1
    cy_step scan-restore && cy_gate scan-baseline cy_scan_matches || return 1
    cy_step wifi-restore && cy_gate framework-baseline cy_baseline_restored || return 1
    cy_original && sc_expect_wlan stock && sc_provider_absent && sc_cnss_holder "$SC_WLAN" || return 1
    cy_journal restored || return 1
    cy_completed=1
    [ "$cy_runtime_ok" = 1 ] || return 3
}
