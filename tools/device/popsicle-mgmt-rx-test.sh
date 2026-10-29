#!/system/bin/sh
# Full native management indication observation; no monitor, LPC, channel or TX.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$#" = 2 ] || fail 'Usage: sh popsicle-mgmt-rx-test.sh /path/0058-bundle /path/new-log-directory'
[ "$(id -u)" = 0 ] || fail 'Run with su.'
bundle=$(cd "$1" && pwd)
[ "$(cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx 2>/dev/null)" = Y ] || fail 'Start the new WLAN with run-mgmt-rx first.'
[ -r /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_diag ] || fail '0059 diagnostic WLAN required.'
[ ! -d /sys/module/wonder ] || fail 'Stop the previous Wonder session first.'
[ -x "$bundle/action-tx-0059" ] || fail 'Run chmod 755 action-tx-0059 first.'
mkdir "$2" || fail 'Log directory must be new.'
logs=$(cd "$2" && pwd)
lock=/data/local/tmp/xairdrop-mgmt-rx.lock
mkdir "$lock" || fail 'Another observation owns the lock; inspect its process first.'
listener_pid=
cleanup() {
    rc=$?
    trap - 0 INT TERM HUP
    if [ -n "$listener_pid" ]; then kill -TERM "$listener_pid" 2>/dev/null || true; wait "$listener_pid" || true; fi
    cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_routed > "$logs/routed-after.txt" 2>&1 || true
    cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_diag > "$logs/diag-after.txt" 2>&1 || true
    iw dev wlan0 link > "$logs/wifi-after.txt" 2>&1 || true
    dmesg > "$logs/dmesg.txt" 2>&1 || true
    printf 'exit=%s\n' "$rc" > "$logs/result.txt"
    rmdir "$lock" || true
    echo "Logs: $logs"
    echo 'Close this observation before restoring the original WLAN with popsicle-wlan-trial.sh restore.'
    exit "$rc"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
(cd "$bundle" && sha256sum -c SHA256SUMS) > "$logs/checksums.txt" 2>&1 || fail 'Bundle checksum failed.'
iw dev wlan0 link > "$logs/wifi-before.txt" 2>&1
cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_routed > "$logs/routed-before.txt"
cat /sys/module/qca_cld3_peach_v2/parameters/mishare_mgmt_rx_diag > "$logs/diag-before.txt"
"$bundle/action-tx-0059" awdl-mgmt-listen --dev wlan0 --seconds 60 --max-frames 10 > "$logs/mgmt-rx.log" 2>&1 &
listener_pid=$!
listener_rc=0
wait "$listener_pid" || listener_rc=$?
listener_pid=
cat "$logs/mgmt-rx.log"
[ "$listener_rc" = 0 ] || fail "Listener exited $listener_rc; no retry or monitor fallback."
echo 'MGMT_RX_OBSERVATION_COMPLETE: inspect parsed/over_256; zero is not AWDL success.'
