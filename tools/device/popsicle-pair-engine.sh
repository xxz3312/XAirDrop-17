#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Policy core. IO adapters are supplied by pairctl; no commands run on source.
pp_fail() { pp_message "BLOCKED: $*"; return 1; }
pp_idle() {
    pp_environment || return 1
    pp_verify_bundle || return 1
    pp_no_conflict || return 1
}
pp_identify() {
    pp_expect_module cnss2 "$1" || return 1
    pp_expect_module qca_cld3_peach_v2 "$1" || return 1
    if [ "$1" = candidate ]; then
        pp_expect_module opairshare_wonder_provider candidate || return 1
        pp_healthy || return 1
    else
        pp_expect_absent opairshare_wonder_provider || return 1
    fi
    pp_holders cnss2 qca_cld3_peach_v2 || return 1
    pp_holders qca_cld3_peach_v2 '' || return 1
    pp_ifaces || return 1
}
pp_change() {
    # Record intent BEFORE every effect. Never replay an interrupted effect.
    pp_journal "intent:$1:${2:-}" || return 1
    pp_effect "$@" || { pp_journal "failed:$1:${2:-}"; return 1; }
    pp_journal "done:$1:${2:-}" || return 1
}
pp_remove() {
    pp_expect_module "$1" "$2" || return 1
    pp_holders "$1" '' || return 1
    pp_zero_refs "$1" || return 1
    pp_change remove "$1" || return 1
    pp_expect_absent "$1" || return 1
}
pp_quiet() {
    pp_change wifi-off || return 1
    pp_wifi_off || return 1
    pp_change hals-stop || return 1
    pp_hals_stopped || return 1
}
pp_start_pair() {
    pp_idle || return 1
    pp_check_transaction || return 1
    pp_identify stock || return 1
    pp_prepare_snapshot || return 1
    pp_quiet || return 1
    pp_remove qca_cld3_peach_v2 stock || return 1
    pp_remove cnss2 stock || return 1
    pp_change insert opairshare_wonder_provider || return 1
    pp_expect_module opairshare_wonder_provider candidate || return 1
    pp_change insert cnss2 || return 1
    pp_expect_module cnss2 candidate || return 1
    # All radio/backend parameters remain at their default disabled values.
    pp_change insert qca_cld3_peach_v2 || return 1
    pp_identify candidate || return 1
    pp_restore_services || return 1
    pp_journal active || return 1
}
pp_restore_pair() {
    pp_idle || return 1
    pp_require_active || return 1
    pp_verify_snapshot || return 1
    pp_identify candidate || return 1
    pp_quiet || return 1
    # Any error here is terminal: never ordinary-rmmod a retained WLAN.
    pp_change live-unload || return 1
    pp_healthy || return 1
    pp_remove qca_cld3_peach_v2 candidate || return 1
    pp_remove cnss2 candidate || return 1
    pp_remove opairshare_wonder_provider candidate || return 1
    pp_change stock-insert cnss2 || return 1
    pp_expect_module cnss2 stock || return 1
    pp_change stock-insert qca_cld3_peach_v2 || return 1
    pp_identify stock || return 1
    pp_restore_services || return 1
    pp_journal restored || return 1
}
