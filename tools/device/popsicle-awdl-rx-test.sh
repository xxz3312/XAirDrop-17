#!/system/bin/sh
# Bounded receive observation through native LPC and Wonder; no transmission.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$#" = 2 ] || [ "$#" = 3 ] || fail 'Usage: sh popsicle-awdl-rx-test.sh /path/0055-bundle /path/new-log-directory [lpc|occ]'
operating_mode=${3:-lpc}
case "$operating_mode" in lpc|occ) ;; *) fail 'Unknown operating mode; use lpc or occ.' ;; esac
[ "$(id -u)" = 0 ] || fail 'Run with su.'
bundle=$(cd "$1" && pwd)
mkdir "$2" || fail 'Log directory must be new.'
logs=$(cd "$2" && pwd)
lock=/data/local/tmp/xairdrop-awdl-rx.lock
mkdir "$lock" || fail 'Another RX test owns the lock; inspect its process before removing a stale lock.'
monitor=xawdlmon0
own_monitor=0
own_wonder=0
listener_pid=
evidence=0
cleanup() {
    rc=$?
    trap - 0 INT TERM HUP
    if [ -n "$listener_pid" ]; then
        kill -TERM "$listener_pid" 2>/dev/null || true
        wait "$listener_pid" || true
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
        echo 'RX_OBSERVATION_COMPLETE: inspect awdl_rx_summary; zero observations is not a discovery success.'
    fi
    echo "Logs: $logs"
    echo 'Driver was not switched by this script.'
    exit "$rc"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
for tool in iw ip sha256sum awk grep insmod rmmod; do command -v "$tool" >/dev/null || fail "Missing $tool"; done

[ ! -d /sys/module/wonder ] || fail 'Existing Wonder session; refusing to take ownership.'
[ ! -e /sys/class/net/wonder0 ] || fail 'wonder0 already exists.'
[ ! -e "/sys/class/net/$monitor" ] || fail 'Test monitor already exists.'
(cd "$bundle" && sha256sum -c SHA256SUMS) > "$logs/checksums.txt" 2>&1 || fail 'Bundle checksum failed.'
[ -x "$bundle/action-tx-0055" ] || fail 'Run chmod 755 on action-tx-0055 first.'
for file in wonder.ko popsicle-rx-start.sh; do [ -f "$bundle/$file" ] || fail "Missing $file"; done
freq() { iw dev wlan0 link | awk '/freq:/{printf "%d", $2; exit}'; }
# QCA LPC requires inactive secondary non-monitor interfaces. Do not change them here.
if [ -e /sys/class/net/p2p0 ]; then
    p2p_flags=$(cat /sys/class/net/p2p0/flags)
    [ "$((p2p_flags & 1))" = 0 ] || fail 'p2p0 is UP; explicitly bring it down before LPC RX and restore it after testing.'
fi
freq_before=$(freq)
case "$freq_before" in ''|*[!0-9]*) fail 'STA must be connected.' ;; esac
[ "$freq_before" -ge 2400 ] && [ "$freq_before" -le 5900 ] || fail 'Unsupported frequency.'
phy=$(iw dev wlan0 info | awk '$1=="wiphy"{print $2; exit}')
case "$phy" in ''|*[!0-9]*) fail 'Cannot identify native PHY.' ;; esac
printf 'freq=%s\nrequested_operating_mode=%s\nmode_verified=false\n' "$freq_before" "$operating_mode" > "$logs/setup.txt"
iw dev wlan0 link > "$logs/wifi-before.txt" 2>&1
iw phy "phy$phy" interface add "$monitor" type monitor >> "$logs/setup.txt" 2>&1
own_monitor=1
ip link set "$monitor" up >> "$logs/setup.txt" 2>&1
"$bundle/action-tx-0055" capture-start --dev "$monitor" --operating-mode "$operating_mode" >> "$logs/setup.txt" 2>&1
sh "$bundle/popsicle-rx-start.sh" start "$bundle/wonder.ko" "$monitor" >> "$logs/setup.txt" 2>&1
own_wonder=1
sh "$bundle/popsicle-rx-start.sh" status > "$logs/rx-before.txt" 2>&1
"$bundle/action-tx-0055" awdl-listen --dev wonder0 --seconds 60 --max-frames 10 > "$logs/awdl-rx.log" 2>&1 &
listener_pid=$!
listener_rc=0
wait "$listener_pid" || listener_rc=$?
listener_pid=
sh "$bundle/popsicle-rx-start.sh" status > "$logs/rx-after.txt" 2>&1 || true
iw dev wlan0 link > "$logs/wifi-after.txt" 2>&1 || true
printf 'freq_before=%s\nfreq_after=%s\n' "$freq_before" "$(freq)" > "$logs/channels.txt"
[ "$listener_rc" = 0 ] || fail "AWDL listener exited $listener_rc; inspect awdl-rx.log."
cat "$logs/awdl-rx.log"
evidence=1
