#!/system/bin/sh
# 0063: controlled observation with unchanged 0062 driver and listener.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$#" = 3 ] || [ "$#" = 4 ] || fail 'Usage: sh popsicle-rx-control-0063.sh BUNDLE NEW_LOG_DIR EXPECTED_MHZ [--reconnect]'
reconnect=0
if [ "$#" = 4 ]; then [ "$4" = --reconnect ] || fail 'Unknown option.'; reconnect=1; fi
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
[ -x "$bundle/action-tx-0063" ] || fail 'chmod 755 action-tx-0063 first.'
mkdir "$2" || fail 'Log directory must be new.'
logs=$(cd "$2" && pwd)
lock=/data/local/tmp/xairdrop-mgmt-rx.lock
mkdir "$lock" || fail 'Another RX observation owns the lock.'
child_pid=
phase=setup
cleanup() {
    rc=$?
    trap - 0 INT TERM HUP
    if [ -n "$child_pid" ]; then kill -TERM "$child_pid" 2>/dev/null || true; wait "$child_pid" 2>/dev/null || true; fi
    cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-final.txt" 2>&1 || true
    iw dev wlan0 link > "$logs/wifi-final.txt" 2>&1 || true
    dmesg > "$logs/dmesg.txt" 2>&1 || true
    printf 'exit=%s\nlast_phase=%s\nexpected_mhz=%s\nreconnect_requested=%s\nairdrop_verified=false\n' "$rc" "$phase" "$expected" "$reconnect" > "$logs/result.txt"
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
if [ "$help_rc" = 0 ] && grep -q 'start-scan' "$logs/wifi-help.txt"; then
    scan_rc=0
    bounded scan-request cmd wifi start-scan || scan_rc=$?
    stable_wait 6
    result_rc=0
    bounded scan-results cmd wifi list-scan-results || result_rc=$?
    printf 'cached_scan_results_command_rc=%s\n' "$result_rc" > "$logs/scan-results-status.txt"
fi
printf 'help_rc=%s\nscan_request_rc=%s\nscan_execution_confirmed=false\n' "$help_rc" "$scan_rc" > "$logs/scan-status.txt"
snapshot scan-after
delta scan-before scan-after scan

if [ "$reconnect" = 1 ]; then
    phase=reconnect
    read_link && same_link || fail 'Initial AP/frequency must be restored before reconnect control.'
    snapshot reconnect-before
    echo 'RECONNECT_CONTROL: disconnecting wlan0 ONCE. Open Wi-Fi settings and tap the SAME saved network; keep Wi-Fi enabled. The script waits up to 90 seconds.'
    disconnect_rc=0
    bounded disconnect-command iw dev wlan0 disconnect || disconnect_rc=$?
    printf 'disconnect_command_rc=%s\n' "$disconnect_rc" > "$logs/reconnect-status.txt"
    [ "$disconnect_rc" = 0 ] || fail 'Disconnect request failed; no retry. Restore the driver after saving logs.'
    ticks=0; disconnected_seen=0; rejoined=0
    while [ "$ticks" -lt 45 ]; do
        driver_ok || fail 'Diagnostic driver disappeared during reconnect; do not interpret counter deltas.'
        read_link || fail 'Cannot read reconnect state.'
        if grep -q '^Not connected' "$logs/link-current.txt"; then disconnected_seen=1; fi
        if [ "$disconnected_seen" = 1 ] && same_link; then rejoined=1; break; fi
        sleep 2; ticks=$((ticks+1))
    done
    printf 'disconnected_sample_seen=%s\noriginal_bssid_and_frequency_seen=%s\n' "$disconnected_seen" "$rejoined" >> "$logs/reconnect-status.txt"
    [ "$rejoined" = 1 ] || fail 'Disconnect/rejoin transition was not observed within 90 seconds; reconnect manually and restore the original driver.'
    stable_wait 3
    snapshot reconnect-after
    delta reconnect-before reconnect-after reconnect
else
    echo 'reconnect=SKIPPED_NO_EXPLICIT_FLAG' >> "$logs/summary.txt"
fi

phase=awdl
read_link && same_link || fail 'Original AP/frequency required before AWDL observation.'
snapshot awdl-before
echo 'AWDL_OBSERVATION: keep the nearby Apple device awake with AirDrop sharing open, for 60 seconds.'
"$bundle/action-tx-0063" awdl-mgmt-listen --dev wlan0 --seconds 60 --max-frames 1000 > "$logs/mgmt-rx.log" 2>&1 &
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
phase=complete
echo 'RX_CONTROL_OBSERVATION_COMPLETE: inspect phase deltas; zero growth remains inconclusive, and growth is not AWDL/AirDrop success.'
