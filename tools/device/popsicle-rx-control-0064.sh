#!/system/bin/sh
# 0064: scan-help compatibility and manual reconnect; unchanged 0062 binaries.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$#" = 3 ] || [ "$#" = 4 ] || fail 'Usage: sh popsicle-rx-control-0064.sh BUNDLE NEW_LOG_DIR EXPECTED_MHZ [--manual-reconnect]'
reconnect=0
if [ "$#" = 4 ]; then [ "$4" = --manual-reconnect ] || fail 'Unknown option.'; reconnect=1; fi
[ "$(id -u)" = 0 ] || fail 'Run as root in a local phone terminal.'
bundle=$(cd "$1" && pwd)
expected=$3
case "$expected" in 2437|5220|5745|5240) ;; *) fail 'Unsupported expected frequency.' ;; esac
params=/sys/module/qca_cld3_peach_v2/parameters
driver_ok() {
    [ "$(cat "$params/mishare_mgmt_rx" 2>/dev/null)" = Y ] &&
    [ -r "$params/mishare_mgmt_rx_diag" ] &&
    grep -q '^wma_events=' "$params/mishare_mgmt_rx_diag"
}
driver_ok || fail 'Load the diagnostic WLAN using run-mgmt-rx first.'
[ ! -d /sys/module/wonder ] || fail 'Stop Wonder first.'
[ -x "$bundle/action-tx-0064" ] || fail 'chmod 755 action-tx-0064 first.'
mkdir "$2" || fail 'Log directory must be new.'
logs=$(cd "$2" && pwd)
lock=/data/local/tmp/xairdrop-mgmt-rx.lock
mkdir "$lock" || fail 'Another RX observation owns the lock.'
child_pid=
phase=setup
manual_status=NOT_REQUESTED
cleanup() {
    rc=$?
    trap - 0 INT TERM HUP
    if [ -n "$child_pid" ]; then kill -TERM "$child_pid" 2>/dev/null || true; wait "$child_pid" 2>/dev/null || true; fi
    cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-final.txt" 2>&1 || true
    iw dev wlan0 link > "$logs/wifi-final.txt" 2>&1 || true
    dmesg > "$logs/dmesg.txt" 2>&1 || true
    printf 'exit=%s\nlast_phase=%s\nexpected_mhz=%s\nmanual_reconnect_requested=%s\nmanual_status=%s\nairdrop_verified=false\n' "$rc" "$phase" "$expected" "$reconnect" "$manual_status" > "$logs/result.txt"
    rmdir "$lock" || true
    echo "Logs: $logs"
    echo 'After this command exits, restore the original WLAN with popsicle-wlan-trial.sh restore.'
    exit "$rc"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
read_link() {
    iw dev wlan0 link > "$logs/link-current.txt" 2>&1 || return 1
    cat /proc/uptime >> "$logs/link-timeline.txt"
    cat "$logs/link-current.txt" >> "$logs/link-timeline.txt"
}
same_link() {
    grep -q '^Connected to ' "$logs/link-current.txt" || return 1
    freq=$(awk '/^[[:space:]]*freq:/ {sub(/\.0$/, "", $2);print $2;exit}' "$logs/link-current.txt")
    bssid=$(awk '/^Connected to / {print $3;exit}' "$logs/link-current.txt")
    [ "$freq" = "$expected" ] && [ "$bssid" = "$initial_bssid" ]
}
snapshot() {
    driver_ok || fail 'Diagnostic driver disappeared or was replaced; control invalid.'
    cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-$1.txt"
    # A decreasing field detects many reload/reset cases. It is not an epoch ID.
    if [ -f "$logs/diag-initial.txt" ] && [ "$1" != initial ]; then
        awk -F= 'NR==FNR {v[$1]=$2;next} $1!="owner_active" && $1 in v && $2<v[$1] {bad=1} END {exit bad}' \
            "$logs/diag-initial.txt" "$logs/diag-$1.txt" || fail 'Counters decreased; module reset/reload suspected.'
    fi
    read_link || fail 'Cannot read wlan0 link.'
    same_link || fail 'Snapshot is not on the original AP/frequency.'
    cp "$logs/link-current.txt" "$logs/wifi-$1.txt"
}
delta() {
    awk -F= 'NR==FNR {v[$1]=$2;next}
      $1=="owner_active" {print "owner_active_after=" $2;next}
      $1 in v {printf "%s_delta=%.0f\n",$1,$2-v[$1]}' \
        "$logs/diag-$1.txt" "$logs/diag-$2.txt" > "$logs/delta-$3.txt"
    growth=$(awk -F= '$1=="wma_events_delta" {print $2}' "$logs/delta-$3.txt")
    case "$growth" in ''|*[!0-9]*) fail 'Invalid WMA delta.' ;; esac
    if [ "$growth" -gt 0 ]; then verdict=WMA_GROWTH_OBSERVED; else verdict=INCONCLUSIVE_NO_WMA_GROWTH; fi
    printf 'phase=%s wma_events_delta=%s verdict=%s\n' "$3" "$growth" "$verdict" | tee -a "$logs/summary.txt"
}
stable_wait() {
    ticks=0
    while [ "$ticks" -lt "$1" ]; do
        driver_ok || fail 'Diagnostic driver disappeared.'
        read_link && same_link || fail 'Connection/BSSID/frequency changed during a stable phase.'
        sleep 2
        ticks=$((ticks+1))
    done
}
bounded() {
    output=$1; shift
    "$@" > "$logs/$output.txt" 2>&1 &
    child_pid=$!
    ticks=0
    while kill -0 "$child_pid" 2>/dev/null; do
        if [ "$ticks" -ge 10 ]; then
            kill -TERM "$child_pid" 2>/dev/null || true
            wait "$child_pid" 2>/dev/null || true
            child_pid=
            return 124
        fi
        sleep 1; ticks=$((ticks+1))
    done
    command_rc=0
    wait "$child_pid" || command_rc=$?
    child_pid=
    return "$command_rc"
}
(cd "$bundle" && sha256sum -c SHA256SUMS) > "$logs/checksums.txt" 2>&1 || fail 'Bundle checksum failed.'
read_link || fail 'Cannot read initial link.'
initial_bssid=$(awk '/^Connected to / {print $3;exit}' "$logs/link-current.txt")
[ -n "$initial_bssid" ] && same_link || fail 'Connect the intended AP and frequency first.'
date > "$logs/started.txt"
snapshot initial
phase=quiet
echo 'QUIET_BASELINE: keep this terminal running.'
stable_wait 5
snapshot quiet-after
delta initial quiet-after quiet

phase=scan
snapshot scan-before
help_rc=0
bounded wifi-help cmd wifi help || help_rc=$?
scan_rc=125
scan_supported=0
if [ "$help_rc" != 124 ] && grep -Eq '^[[:space:]]*start-scan([[:space:]]|$)' "$logs/wifi-help.txt"; then
    scan_supported=1
    scan_rc=0
    bounded scan-request cmd wifi start-scan || scan_rc=$?
    stable_wait 6
    result_rc=0
    bounded scan-results cmd wifi list-scan-results || result_rc=$?
    printf 'cached_scan_results_command_rc=%s\n' "$result_rc" > "$logs/scan-results-status.txt"
fi
printf 'help_rc=%s\nscan_supported_by_help=%s\nscan_request_rc=%s\nscan_execution_confirmed=false\n' "$help_rc" "$scan_supported" "$scan_rc" > "$logs/scan-status.txt"
snapshot scan-after
delta scan-before scan-after scan
printf 'scan_supported_by_help=%s scan_request_rc=%s\n' "$scan_supported" "$scan_rc" >> "$logs/summary.txt"


phase=awdl
read_link && same_link || fail 'Original AP/frequency required before AWDL observation.'
snapshot awdl-before
echo 'AWDL_OBSERVATION: keep the nearby Apple device awake with AirDrop sharing open, for 60 seconds.'
"$bundle/action-tx-0064" awdl-mgmt-listen --dev wlan0 --seconds 60 --max-frames 1000 > "$logs/mgmt-rx.log" 2>&1 &
child_pid=$!
ticks=0
while kill -0 "$child_pid" 2>/dev/null; do
    driver_ok || fail 'Diagnostic driver disappeared during listener.'
    read_link && same_link || fail 'AP/frequency changed during AWDL observation.'
    [ "$ticks" -lt 35 ] || fail 'Listener timed out.'
    sleep 2; ticks=$((ticks+1))
done
listener_rc=0
wait "$child_pid" || listener_rc=$?
child_pid=
[ "$listener_rc" = 0 ] || fail "Listener exited $listener_rc."
grep -q '"event":"awdl_mgmt_ready"' "$logs/mgmt-rx.log" || fail 'Missing registration ACK.'
grep -q '"event":"awdl_mgmt_rx_summary"' "$logs/mgmt-rx.log" || fail 'Missing listener summary.'
snapshot awdl-after
delta awdl-before awdl-after awdl
cat "$logs/mgmt-rx.log"
if [ "$reconnect" = 1 ]; then
    phase=manual-reconnect
    snapshot manual-before
    manual_status=WAITING_FOR_USER
    echo 'MANUAL_RECONNECT: use system Wi-Fi settings to disconnect and reconnect the SAME saved network. If no disconnect button exists, switch Wi-Fi off for about 5 seconds then on. Keep this terminal running; waiting up to 120 seconds.'
    # No network-mutating command is issued here. The user owns the UI action.
    ticks=0; disconnected_seen=0; rejoined=0; driver_changed=0
    while [ "$ticks" -lt 60 ]; do
        if ! driver_ok; then driver_changed=1; fi
        if read_link; then
            if grep -q '^Not connected' "$logs/link-current.txt"; then disconnected_seen=1; fi
            if [ "$disconnected_seen" = 1 ] && same_link; then rejoined=1; break; fi
        else
            # Missing wlan0 while Wi-Fi is off is an observed unavailable link.
            disconnected_seen=1
        fi
        sleep 2; ticks=$((ticks+1))
    done
    if [ "$rejoined" = 1 ]; then
        for settle in 1 2 3; do
            sleep 2
            if ! driver_ok; then driver_changed=1; fi
            if ! read_link || ! same_link; then rejoined=0; fi
        done
    fi
    printf 'automatic_disconnect_issued=false\ndisconnected_sample_seen=%s\noriginal_bssid_and_frequency_seen=%s\ndiagnostic_driver_disappeared=%s\n' "$disconnected_seen" "$rejoined" "$driver_changed" > "$logs/manual-status.txt"
    if [ "$driver_changed" = 1 ] || ! driver_ok; then
        manual_status=INVALID_DRIVER_CHANGED
    elif [ "$rejoined" != 1 ]; then
        manual_status=INCOMPLETE_TRANSITION_NOT_OBSERVED
    else
        # Keep the manual epoch separate: do not call the initial-epoch snapshot.
        cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-manual-after.txt"
        if ! awk -F= 'NR==FNR {v[$1]=$2;next} $1!="owner_active" && $1 in v && $2<v[$1] {bad=1} END {exit bad}' "$logs/diag-manual-before.txt" "$logs/diag-manual-after.txt"; then
            manual_status=INVALID_COUNTER_RESET
        else
            delta manual-before manual-after manual
            manual_status=TRANSITION_OBSERVED_CHECK_DELTA
        fi
    fi
    printf 'manual_status=%s\n' "$manual_status" | tee -a "$logs/summary.txt" >> "$logs/manual-status.txt"
    echo "Manual control: $manual_status. Earlier quiet/scan/AWDL logs remain available."
fi

phase=complete
echo 'RX_CONTROL_OBSERVATION_COMPLETE: collection ended. Inspect manual_status and phase deltas; zero growth is inconclusive, and growth is not AWDL/AirDrop success.'
