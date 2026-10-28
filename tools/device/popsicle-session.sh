#!/system/bin/sh
# Foreground session orchestration. Native WLAN/mac80211 stay loaded.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
action=${1:-help}
[ "$#" = 0 ] || shift
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
monitor=misharemon0
tx=wlan0
freq=
raw=0
rewrite=0
configure_monitor=0
seconds=300
frames=10000
lock=/data/local/tmp/xairdrop-session.lock
wlan_module=qca_cld3_peach_v2
log=
while [ "$#" != 0 ]; do
    case "$1" in
        --raw) raw=1; shift ;;
        --rewrite-source) rewrite=1; shift ;;
        --configure-monitor) configure_monitor=1; shift ;;
        --bundle|--monitor|--tx|--freq|--seconds|--max-frames|--lock|--wlan-module|--log)
            key=$1; [ "$#" -ge 2 ] || fail "Missing value for $key"
            case "$key" in
                --bundle) bundle=$2 ;; --monitor) monitor=$2 ;; --tx) tx=$2 ;;
                --freq) freq=$2 ;; --seconds) seconds=$2 ;; --max-frames) frames=$2 ;;
                --lock) lock=$2 ;; --wlan-module) wlan_module=$2 ;; --log) log=$2 ;;
            esac
            shift 2 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
[ -n "$log" ] || log=$bundle/session.log
case "$action" in
    status)
        [ ! -f "$lock/owner" ] || cat "$lock/owner"
        sh "$bundle/popsicle-rx-start.sh" status || true
        [ ! -f "$log" ] || tail -n 20 "$log"
        exit 0 ;;
    run) ;;
    *) echo 'Usage: sh popsicle-session.sh run --bundle DIR --tx wlan0 --freq MHz [--monitor misharemon0] [--raw] [--rewrite-source] [--seconds 300] [--max-frames 10000]'; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || fail 'Run with su.'
for name in "$monitor" "$tx" "$wlan_module"; do
    case "$name" in ''|*[!a-zA-Z0-9_.-]*) fail 'Invalid interface/module name.' ;; esac
done
[ "${#monitor}" -le 15 ] && [ "${#tx}" -le 15 ] && [ "$monitor" != "$tx" ] || fail 'Invalid interface pair.'
for value in "$freq" "$seconds" "$frames"; do
    case "$value" in ''|*[!0-9]*) fail 'Frequency and limits must be positive integers.' ;; esac
done
[ "$freq" -ge 2300 ] && [ "$freq" -le 5900 ] || fail 'Frequency out of range.'
[ "$seconds" -ge 1 ] && [ "$seconds" -le 86400 ] || fail 'Duration out of range.'
[ "$frames" -ge 1 ] && [ "$frames" -le 100000 ] || fail 'Frame limit out of range.'
for tool in ip iw readlink awk sh; do command -v "$tool" >/dev/null || fail "Missing $tool"; done
[ -x "$bundle/action-tx" ] && [ -f "$bundle/wonder.ko" ] && [ -f "$bundle/popsicle-rx-start.sh" ] || fail 'Bundle needs action-tx, wonder.ko and popsicle-rx-start.sh.'
if iw phy wonder info >/dev/null 2>&1; then fail 'Wonder is already registered; stop that session first.'; fi
if [ "$raw" = 1 ]; then
    [ "$(cat "/sys/module/$wlan_module/parameters/mishare_raw_tx" 2>/dev/null)" = Y ] || fail 'RAW requires patched WLAN already loaded with mishare_raw_tx=1.'
fi
channel() {
    iw dev "$1" info | awk '/^[[:space:]]*channel / {gsub(/[()]/,"",$3); print $3; exit}'
}
[ "$(channel "$tx")" = "$freq" ] || fail 'Native TX interface must already operate on the requested frequency.'
# The launcher borrows existing interfaces; it only configures a monitor it creates.
phy_path=$(readlink -f "/sys/class/net/$tx/phy80211") || fail 'Cannot resolve native PHY.'
phy=${phy_path##*/}
[ -n "$phy" ] && [ "$phy" != wonder ] || fail 'TX must belong to a native PHY.'
umask 077
mkdir "$lock" || fail 'Session lock exists; another session may be running.'
own_monitor=0
own_rx=0
child=
cleanup() {
    rc=$?
    trap - 0 1 2 15
    if [ -n "$child" ]; then
        kill -TERM "$child" 2>/dev/null || true
        wait "$child" 2>/dev/null || true
    fi
    keep_monitor=0
    if [ "$own_rx" = 1 ]; then
        if ! sh "$bundle/popsicle-rx-start.sh" stop; then
            echo 'RX stop failed; preserving the monitor for diagnosis.' >&2
            keep_monitor=1; rc=1
        fi
    fi
    if [ "$own_monitor" = 1 ] && [ "$keep_monitor" = 0 ]; then
        ip link set "$monitor" down || rc=1
        iw dev "$monitor" del || rc=1
    fi
    rm -f "$lock/owner"
    rmdir "$lock" || rc=1
    exit "$rc"
}
trap cleanup 0
trap 'exit 130' 1 2 15
printf 'pid=%s\nmonitor=%s\ntx=%s\nfreq=%s\nraw=%s\n' "$$" "$monitor" "$tx" "$freq" "$raw" >"$lock/owner"
monitor_evidence=readback
if iw dev "$monitor" info >/dev/null 2>&1; then
    if [ "$configure_monitor" = 1 ]; then
        iw dev "$monitor" set freq "$freq" HT20
        monitor_evidence=command_accepted
    else
        [ "$(channel "$monitor")" = "$freq" ] || fail 'Borrowed monitor channel is unknown/different; use --configure-monitor to set it explicitly.'
    fi
else
    iw phy "$phy" interface add "$monitor" type monitor
    own_monitor=1
    ip link set "$monitor" up
    iw dev "$monitor" set freq "$freq" HT20
    monitor_evidence=command_accepted
fi
[ "$(channel "$tx")" = "$freq" ] || fail 'Native TX interface changed channel during setup.'
monitor_freq=$(channel "$monitor")
if [ -n "$monitor_freq" ]; then
    [ "$monitor_freq" = "$freq" ] || fail 'Native monitor reports a different channel.'
    monitor_evidence=readback
fi
sh "$bundle/popsicle-rx-start.sh" start "$bundle/wonder.ko" "$monitor"
own_rx=1
mode=relay
[ "$raw" = 0 ] || mode=relay-all
set -- "$mode" --listen wonder0 --dev "$tx" --freq "$freq" --seconds "$seconds" --max-frames "$frames"
[ "$rewrite" = 0 ] || set -- "$@" --rewrite-source
printf 'SESSION_START monitor=%s tx=%s freq=%s raw=%s rx_channel_evidence=%s\n' "$monitor" "$tx" "$freq" "$raw" "$monitor_evidence" >>"$log"
"$bundle/action-tx" "$@" >>"$log" 2>&1 &
child=$!
echo "Session process started; inspect relay_ready in log. Ctrl-C stops and cleans up. Log: $log"
result=0
wait "$child" || result=$?
child=
exit "$result"
