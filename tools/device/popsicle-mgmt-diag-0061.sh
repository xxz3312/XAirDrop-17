#!/system/bin/sh
# 0061: channel-controlled PE/HDD diagnostic observation; no radio policy changes.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$#" = 3 ] || fail 'Usage: sh popsicle-mgmt-diag-0061.sh BUNDLE NEW_LOG_DIR EXPECTED_MHZ'
[ "$(id -u)" = 0 ] || fail 'Run as root.'
bundle=$(cd "$1" && pwd)
expected=$3
case "$expected" in 2437|5220|5745|5240) ;; *) fail 'Use 2437, 5220, 5745, or 5240 (baseline).' ;; esac
params=/sys/module/qca_cld3_peach_v2/parameters
[ "$(cat "$params/mishare_mgmt_rx" 2>/dev/null)" = Y ] || fail 'Start run-mgmt-rx first.'
[ -r "$params/mishare_mgmt_rx_diag" ] || fail '0061 diagnostic WLAN required; old 0058 driver has no counters.'
grep -q '^register_ml_default=' "$params/mishare_mgmt_rx_diag" || fail '0061 ML-default diagnostic WLAN required.'
[ ! -d /sys/module/wonder ] || fail 'Stop Wonder first.'
[ -x "$bundle/action-tx-0061" ] || fail 'chmod 755 action-tx-0061 first.'
mkdir "$2" || fail 'Log directory must be new.'
logs=$(cd "$2" && pwd)
lock=/data/local/tmp/xairdrop-mgmt-rx.lock
mkdir "$lock" || fail 'Another observation owns the lock.'
listener_pid=
cleanup() {
    rc=$?
    trap - 0 INT TERM HUP
    if [ -n "$listener_pid" ]; then
        kill -TERM "$listener_pid" 2>/dev/null || true
        wait "$listener_pid" 2>/dev/null || true
    fi
    cat "$params/mishare_mgmt_rx_routed" > "$logs/routed-after.txt" 2>&1 || true
    cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-after.txt" 2>&1 || true
    if [ -f "$logs/diag-before.txt" ]; then
        awk -F= 'NR==FNR {before[$1]=$2; next}
          $1=="owner_active" {print "owner_active_after=" $2; next}
          $1 in before {printf "%s_delta=%.0f\n",$1,$2-before[$1]}' \
          "$logs/diag-before.txt" "$logs/diag-after.txt" > "$logs/diag-delta.txt" || true
    fi
    iw dev wlan0 link > "$logs/wifi-after.txt" 2>&1 || true
    iw dev > "$logs/interfaces-after.txt" 2>&1 || true
    dmesg > "$logs/dmesg.txt" 2>&1 || true
    printf 'exit=%s\nexpected_mhz=%s\nairdrop_verified=false\n' "$rc" "$expected" > "$logs/result.txt"
    rmdir "$lock" || true
    echo "Logs: $logs"
    exit "$rc"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
check_channel() {
    iw dev wlan0 link > "$logs/link-current.txt" 2>&1 || return 1
    cat "$logs/link-current.txt" >> "$logs/channel-timeline.txt"
    echo '---' >> "$logs/channel-timeline.txt"
    grep -q '^Connected to ' "$logs/link-current.txt" || return 1
    actual=$(awk '/^[[:space:]]*freq:/ {sub(/\.0$/, "", $2); print $2; exit}' "$logs/link-current.txt")
    [ "$actual" = "$expected" ]
}
(cd "$bundle" && sha256sum -c SHA256SUMS) > "$logs/checksums.txt" 2>&1 || fail 'Checksum failed.'
date > "$logs/started.txt"
iw dev > "$logs/interfaces-before.txt" 2>&1 || true
iw phy > "$logs/phy.txt" 2>&1 || true
cat "$params/mishare_mgmt_rx_routed" > "$logs/routed-before.txt"
cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-before.txt"
check_channel || fail 'STA disconnected or unexpected frequency; connect the intended AP first.'
cp "$logs/link-current.txt" "$logs/wifi-before.txt"
for round in 1 2 3; do
    check_channel || fail 'Channel changed before this round.'
    cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-round-$round-before.txt"
    echo "ROUND=$round expected_mhz=$expected" | tee -a "$logs/channel-timeline.txt"
    "$bundle/action-tx-0061" awdl-mgmt-listen --dev wlan0 --seconds 60 --max-frames 1000 > "$logs/mgmt-rx-$round.log" 2>&1 &
    listener_pid=$!
    ticks=0
    while kill -0 "$listener_pid" 2>/dev/null; do
        check_channel || fail 'Channel changed or STA disconnected during observation; this run is invalid.'
        ticks=$((ticks+1))
        [ "$ticks" -le 35 ] || fail 'Listener exceeded bounded observation time.'
        sleep 2
    done
    listener_rc=0
    wait "$listener_pid" || listener_rc=$?
    listener_pid=
    cat "$params/mishare_mgmt_rx_diag" > "$logs/diag-round-$round-after.txt"
    cat "$logs/mgmt-rx-$round.log"
    [ "$listener_rc" = 0 ] || fail "Listener exited $listener_rc; no retry."
    grep -q '"event":"awdl_mgmt_ready"' "$logs/mgmt-rx-$round.log" || fail 'Missing registration acknowledgement.'
    grep -q '"event":"awdl_mgmt_rx_summary"' "$logs/mgmt-rx-$round.log" || fail 'Missing listener summary.'
    check_channel || fail 'Channel changed at round completion.'
done
echo 'MGMT_DIAG_OBSERVATION_COMPLETE: three rounds ended; inspect events/parsed/lengths. Zero frames is inconclusive.'
