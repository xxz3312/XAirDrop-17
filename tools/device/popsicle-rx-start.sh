#!/system/bin/sh
# Start the real RX bridge on a native monitor that the user already configured.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Run with su.'
action=${1:-status}
case "$action" in
status)
    for n in external_monitor external_tx physical_name opairshare_wonder_rx opairshare_wonder_rx_invalid; do
        f=/sys/module/wonder/parameters/$n
        [ ! -r "$f" ] || { printf '%s=' "$n"; cat "$f"; }
    done
    ip -s link show wonder0
    exit
    ;;
stop)
    [ "$(cat /sys/module/wonder/parameters/external_monitor)" = Y ] || fail 'Wonder is not in external monitor mode.'
    if [ -e /sys/class/net/wonder0 ]; then
        [ "$(basename "$(readlink -f /sys/class/net/wonder0/phy80211)")" = wonder ] || fail 'wonder0 belongs to another PHY.'
        ip link set wonder0 down
        iw dev wonder0 del
    fi
    rmmod wonder
    echo 'RX bridge stopped; native monitor and mac80211 left in place.'
    exit
    ;;
start) ;;
*) fail 'Usage: sh popsicle-rx-start.sh start /path/wonder.ko mon0 | status | stop' ;;
esac
[ "$#" = 3 ] || [ "$#" = 4 ] || fail 'start requires a Wonder .ko and an existing native monitor name; optional tx-feedback.'
ko=$2
monitor=$3
feedback=${4:-}
case "$feedback" in ''|tx-feedback) ;; *) fail 'Unknown start mode.' ;; esac
case "$monitor" in ''|*[!a-zA-Z0-9_.-]*) fail 'Invalid monitor name.' ;; esac
for tool in ip iw insmod rmmod readlink; do command -v "$tool" >/dev/null || fail "Missing $tool"; done
[ -f "$ko" ] || fail 'Wonder .ko not found.'
[ ! -d /sys/module/wonder ] || fail 'Wonder already loaded; stop its current session first.'
[ ! -e /sys/class/net/wonder0 ] || fail 'wonder0 already exists.'
[ -e "/sys/class/net/$monitor" ] || fail 'Native monitor interface does not exist.'
[ "$(cat "/sys/class/net/$monitor/type")" = 803 ] || fail 'Physical interface must emit radiotap (ARPHRD 803).'
iw dev "$monitor" info
[ -d /sys/module/mac80211 ] || fail 'Load the matching stock mac80211.ko first.'
own_module=0
own_iface=0
cleanup() {
    rc=$?
    trap - 0
    if [ "$rc" != 0 ]; then
        if [ "$own_iface" = 1 ]; then ip link set wonder0 down || true; iw dev wonder0 del || true; fi
        if [ "$own_module" = 1 ]; then rmmod wonder || true; fi
        echo 'Start failed; native monitor was not changed.' >&2
    fi
    exit "$rc"
}
trap cleanup 0
if [ "$feedback" = tx-feedback ]; then
    insmod "$ko" external_monitor=1 external_tx=1 physical_name="$monitor" virtual_name=wonder0
else
    insmod "$ko" external_monitor=1 physical_name="$monitor" virtual_name=wonder0
fi
own_module=1
[ -d /sys/class/ieee80211/wonder ] || fail 'Wonder PHY did not register; inspect dmesg.'
iw phy wonder interface add wonder0 type monitor
own_iface=1
ip link set wonder0 up
ip -s link show wonder0
echo 'RX bridge ready. Capture: tcpdump -i wonder0 -s 0 -w /data/local/tmp/wonder-rx.pcap'
echo 'Use status to check received frames. Channel is controlled on the native monitor.'
