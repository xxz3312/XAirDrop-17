#!/system/bin/sh
# One experimental broadcast, using the already active 0049 WLAN and 0051 bundle.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$#" = 2 ] || fail 'Usage: sh popsicle-vendor-feedback-test.sh /path/0051-bundle /path/new-log-directory'
[ "$(id -u)" = 0 ] || fail 'Run with su.'
bundle=$(cd "$1" && pwd)
mkdir "$2" || fail 'Log directory must be new.'
logs=$(cd "$2" && pwd)
lock=/data/local/tmp/xairdrop-vendor-feedback.lock
mkdir "$lock" || fail 'Another feedback test owns the lock; inspect its process before removing a stale lock.'
monitor=xfbtmon0
own_monitor=0
own_wonder=0
relay_pid=
evidence=0
cleanup() {
    rc=$?
    trap - 0 INT TERM HUP
    if [ -n "$relay_pid" ]; then
        kill -TERM "$relay_pid" 2>/dev/null || true
        wait "$relay_pid" || true
    fi
    if [ "$own_wonder" = 1 ]; then
        if sh "$bundle/popsicle-rx-start.sh" stop > "$logs/stop.txt" 2>&1; then
            own_wonder=0
        else
            echo 'CLEANUP_FAILED: Wonder remains; do not restore WLAN before stopping it.' >&2
            rc=1
        fi
    fi
    if [ "$own_monitor" = 1 ]; then
        if [ -d /sys/module/wonder ]; then
            echo 'CLEANUP_FAILED: keeping native monitor while Wonder remains loaded.' >&2
            rc=1
        elif ! { ip link set "$monitor" down && iw dev "$monitor" del; } >> "$logs/stop.txt" 2>&1; then
            echo 'CLEANUP_FAILED: native monitor remains.' >&2
            rc=1
        fi
    fi
    dmesg > "$logs/dmesg.txt" 2>&1 || true
    printf 'exit=%s\n' "$rc" > "$logs/result.txt"
    rmdir "$lock" || true
    if [ "$rc" = 0 ] && [ "$evidence" = 1 ]; then
        echo 'TOKEN_TEST_PASS: one native completion and token NOACK. Peer reception and AWDL remain unverified.'
    fi
    echo "Logs: $logs"
    echo 'WLAN unchanged; use the 0049 restore command after successful cleanup.'
    exit "$rc"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
for tool in iw ip sha256sum awk grep insmod rmmod; do command -v "$tool" >/dev/null || fail "Missing $tool"; done
[ "$(cat /sys/module/qca_cld3_peach_v2/parameters/mishare_action_tx)" = Y ] || fail 'Start the 0049 experimental WLAN first.'
[ ! -d /sys/module/wonder ] || fail 'Existing Wonder session; refusing to take ownership.'
[ ! -e /sys/class/net/wonder0 ] || fail 'wonder0 already exists.'
[ ! -e "/sys/class/net/$monitor" ] || fail 'Test monitor already exists.'
(cd "$bundle" && sha256sum -c SHA256SUMS) > "$logs/checksums.txt" 2>&1 || fail 'Bundle checksum failed.'
[ -x "$bundle/action-tx-0051" ] || fail 'Run chmod 755 on action-tx-0051 first.'
for file in wonder.ko popsicle-rx-start.sh action-vendor.bin; do [ -f "$bundle/$file" ] || fail "Missing $file"; done
freq() { iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}'; }
freq_before=$(freq)
case "$freq_before" in ''|*[!0-9]*) fail 'STA must be connected.' ;; esac
[ "$freq_before" -ge 2400 ] && [ "$freq_before" -le 5900 ] || fail 'Unsupported frequency.'
phy=$(iw dev wlan0 info | awk '$1=="wiphy"{print $2; exit}')
case "$phy" in ''|*[!0-9]*) fail 'Cannot identify native PHY.' ;; esac
printf 'freq=%s\n' "$freq_before" > "$logs/setup.txt"
iw phy "phy$phy" interface add "$monitor" type monitor >> "$logs/setup.txt" 2>&1
own_monitor=1
ip link set "$monitor" up >> "$logs/setup.txt" 2>&1
sh "$bundle/popsicle-rx-start.sh" start "$bundle/wonder.ko" "$monitor" tx-feedback >> "$logs/setup.txt" 2>&1
own_wonder=1
"$bundle/action-tx-0051" vendor-action-relay --listen wonder0 --dev wlan0 --freq "$freq_before" \
    --feedback --rewrite-source --max-frames 1 --seconds 30 --timeout-ms 10000 > "$logs/feedback.log" 2>&1 &
relay_pid=$!
ready=0
n=0
while [ "$n" -lt 15 ]; do
    if grep -q '^{"event":"relay_ready","mode":"token_feedback","transport":"vendor_action"}$' "$logs/feedback.log"; then ready=1; break; fi
    kill -0 "$relay_pid" 2>/dev/null || break
    sleep 1
    n=$((n + 1))
done
[ "$ready" = 1 ] || fail 'Relay did not become ready; no frame injected.'
[ "$(freq)" = "$freq_before" ] || fail 'STA channel changed; no frame injected.'
"$bundle/action-tx-0051" inject --dev wonder0 --frame "$bundle/action-vendor.bin" --rewrite-source > "$logs/inject.txt" 2>&1
relay_rc=0
wait "$relay_pid" || relay_rc=$?
relay_pid=
[ "$relay_rc" = 0 ] || fail "Relay exited $relay_rc; inspect feedback.log."
grep -q '"event":"vendor_action_tx_status","native_status":0,' "$logs/feedback.log" || fail 'No native completion.'
grep -q '"event":"feedback_complete","token":"[0-9][0-9]*","outcome":1}' "$logs/feedback.log" || fail 'No token NOACK completion.'
grep -q '"event":"feedback_summary","completed":1,"failed":0,"rejected":0,"reported":1,' "$logs/feedback.log" || fail 'Unexpected summary.'
evidence=1
