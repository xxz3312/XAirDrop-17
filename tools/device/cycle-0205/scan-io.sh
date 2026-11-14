#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Fixed firmware's observed scanner log contract. No scan retries or controls here.
cs_valid_dump() {
    case "$cs_data" in *'WifiScanningService - Log Begin ----'*'WifiScanningService - Log End ----'*) return 0;; *) return 1;; esac
}
cs_listener_id() {
    case "$1" in *'WifiScannerInternal$ScanListener@'*) ;; *) return 1;; esac
    cs_id_tail=${1#*'WifiScannerInternal$ScanListener@'}
    cs_id_tail=${cs_id_tail%%]*}
    case "$cs_id_tail" in ''|*[!0-9a-f]*) return 1;; esac
    [ "${#cs_id_tail}" -le 16 ] || return 1
    printf '%s\n' "$cs_id_tail"
}
cs_seen_ids() {
    cs_seen=' '
    while IFS= read -r cs_seen_line; do
        case "$cs_seen_line" in *' - '*'ClientInfo[uid=1000, package=com.android.shell,'*)
            cs_seen_id=$(cs_listener_id "$cs_seen_line") || continue
            case "$cs_seen" in *" $cs_seen_id "*) ;; *) cs_seen="$cs_seen$cs_seen_id ";; esac;;
        esac
    done <<EOF
$cs_data
EOF
    printf '%s\n' "$cs_seen"
}
cs_new_request() {
    cs_new_ids=' '; cs_new_count=0; cs_new_target=
    while IFS= read -r cs_req_line; do
        case "$cs_req_line" in *' - addSingleScanRequest: ClientInfo[uid=1000, package=com.android.shell,'*'WorkSource{0 com.android.shell}'*)
            cs_req_id=$(cs_listener_id "$cs_req_line") || continue
            case "$cs_baseline_ids" in *" $cs_req_id "*) continue;; esac
            case "$cs_new_ids" in *" $cs_req_id "*) continue;; esac
            cs_new_ids="$cs_new_ids$cs_req_id "; cs_new_count=$((cs_new_count+1))
            cs_new_target=$cs_req_id; cs_request_line=$cs_req_line;;
        esac
    done <<EOF
$cs_data
EOF
}
cs_callback() {
    cs_outcome=pending; cs_results=0; cs_success=0; cs_failure=0; cs_invalid=0; cs_callback_line=
    while IFS= read -r cs_cb_line; do
        case "$cs_cb_line" in
            *' - singleScanResults: ClientInfo[uid=1000, package=com.android.shell,'*|*' - singleScanFailed: ClientInfo[uid=1000, package=com.android.shell,'*) ;;
            *) continue;;
        esac
        cs_cb_id=$(cs_listener_id "$cs_cb_line") || continue
        [ "$cs_cb_id" = "$cs_target" ] || continue
        case "$cs_cb_line" in
            *' - singleScanFailed: '*) cs_failure=1; cs_callback_line=$cs_cb_line;;
            *' - singleScanResults: '*',results='*)
                cs_n=${cs_cb_line##*',results='}
                case "$cs_n" in ''|*[!0-9]*) cs_invalid=1; continue;; esac
                [ "${#cs_n}" -le 4 ] || { cs_invalid=1; continue; }
                if [ "$cs_success" = 1 ] && [ "$cs_results" != "$cs_n" ]; then cs_invalid=1; fi
                cs_success=1; cs_results=$cs_n; cs_callback_line=$cs_cb_line;;
            *) cs_invalid=1;;
        esac
    done <<EOF
$cs_data
EOF
    if [ "$cs_invalid" = 1 ] || [ "$cs_success:$cs_failure" = 1:1 ]; then cs_outcome=conflicting
    elif [ "$cs_failure" = 1 ]; then cs_outcome=failed
    elif [ "$cs_success" = 1 ]; then
        case "$cs_results" in 0|00|000|0000) cs_outcome=empty;; *) cs_outcome=complete;; esac
    fi
}
cs_query() {
    if cs_data=$(/system/bin/timeout -k 2 15 /system/bin/dumpsys -t 10 wifiscanner 2>&1); then cs_query_rc=0; else cs_query_rc=$?; fi
}
cy_observation_capabilities() {
    cy_base_observation_capabilities || return 1
    [ -x /system/bin/dumpsys ] || return 1
    cs_query
    sc_log "SCANNER_PREFLIGHT:rc=$cs_query_rc" || return 1
    [ "$cs_query_rc" = 0 ] && cs_valid_dump
}
cs_capture() {
    case "$1" in before|sample-[0-9]|sample-[0-9][0-9]) ;; *) return 1;; esac
    cy_candidate_owned && cy_hals_running || return 1
    cs_path=$CY_STATE/scanner.$1.log
    cy_absent "$cs_path" || return 1
    cs_query
    (set -C; printf '%s\n' "$cs_data" > "$cs_path") && sc_private "$cs_path" || return 1
    sc_log "SCANNER_CAPTURE:$1:rc=$cs_query_rc:sha256=$(sc_hash "$cs_path")" || return 1
}
cs_uptime() {
    IFS=' ' read -r cs_uptime_value cs_idle_ticks < /proc/uptime || return 1
    cs_seconds=${cs_uptime_value%%.*}
    case "$cs_seconds" in ''|*[!0-9]*) return 1;; esac
}
cs_wait() {
    cs_target=; cs_verdict=timeout; cs_positive=0; cs_completed=0
    cs_uptime || return 1
    cs_deadline=$((cs_seconds+45)); cs_poll=0
    while [ "$cs_poll" -lt 24 ]; do
        cy_candidate_owned && cy_hals_running || return 1
        cs_uptime || return 1
        [ "$cs_seconds" -le "$cs_deadline" ] || break
        cs_capture "sample-$cs_poll" || return 1
        if [ "$cs_query_rc" != 0 ] || ! cs_valid_dump; then cs_verdict=query_unavailable; break; fi
        cs_new_request
        if [ "$cs_new_count" -gt 1 ]; then cs_verdict=ambiguous; break; fi
        if [ "$cs_new_count" = 1 ]; then
            if [ -n "$cs_target" ] && [ "$cs_target" != "$cs_new_target" ]; then cs_verdict=ambiguous; break; fi
            if [ -z "$cs_target" ]; then
                cs_target=$cs_new_target
                sc_log "SCAN_REQUEST_MATCH:$cs_target:$cs_request_line" || return 1
            fi
        fi
        if [ -n "$cs_target" ]; then
            cs_callback
            if [ "$cs_outcome" != pending ]; then
                cs_verdict=$cs_outcome
                sc_log "SCAN_REQUEST_CALLBACK:$cs_target:$cs_callback_line" || return 1
                if [ "$cs_outcome" = complete ]; then cs_positive=1; cs_completed=1; fi
                [ "$cs_outcome" != empty ] || cs_completed=1
                break
            fi
        fi
        sleep 2; cs_poll=$((cs_poll+1))
    done
    sc_log "SCAN_WAIT_VERDICT:$cs_verdict:listener=$cs_target:results=${cs_results:-0}:poll=$cs_poll:completion=$cs_completed" || return 1
    cy_candidate_owned && cy_hals_running
}
cy_candidate_observe() {
    cy_runtime_ok=0; cy_association_ok=0; cy_scan_request_ok=0; cs_completed=0; cs_positive=0; cs_verdict=not_requested
    cy_candidate_owned && cy_hals_running || return 1
    cy_journal candidate-observing || return 1
    cy_obs=0
    while [ "$cy_obs" -lt 30 ]; do
        cy_candidate_owned && cy_hals_running || return 1
        if cy_framework && [ "$cy_fw_wifi:$cy_fw_scan" = 1:disabled ] && cy_connected_status; then cy_association_ok=1; break; fi
        sleep 2; cy_obs=$((cy_obs+1))
    done
    if [ "$cy_association_ok" = 1 ]; then
        cs_capture before || return 1
        if [ "$cs_query_rc" = 0 ] && cs_valid_dump; then
            cs_baseline_ids=$(cs_seen_ids) || return 1
            cy_journal candidate-scan-wait || return 1
            if sc_capture sc_android cmd wifi start-scan; then
                cy_scan_request_ok=1
                cs_wait || return 1
            else cs_verdict=request_rejected; fi
        else cs_verdict=baseline_unavailable; fi
    else cs_verdict=association_unavailable; fi
    cy_scan_list_ok=0
    if sc_capture sc_android cmd wifi list-scan-results; then cy_scan_list_ok=1; fi
    # Re-observe ordinary connection after the asynchronous scan interval.
    cy_association_ok=0
    if cy_framework && [ "$cy_fw_wifi:$cy_fw_scan" = 1:disabled ] && cy_connected_status; then cy_association_ok=1; fi
    sc_log "CANDIDATE_OBSERVATION:association_ip=$cy_association_ok:scan_request_rc0=$cy_scan_request_ok:scan_list_rc0=$cy_scan_list_ok:scan_completion=$cs_completed:positive_results=$cs_positive:verdict=$cs_verdict" || return 1
    if [ "$cy_association_ok:$cy_scan_request_ok:$cy_scan_list_ok:$cs_completed:$cs_positive" = 1:1:1:1:1 ]; then cy_runtime_ok=1; fi
    cy_candidate_owned && cy_hals_running
}
