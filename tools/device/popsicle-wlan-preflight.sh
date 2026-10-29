#!/system/bin/sh
# Read-only inventory for planning a reversible native WLAN trial.
# No module/network/partition mutations. Run as root; redirect output to a file.
set -u
echo '=== KERNEL / SLOT ==='
uname -r
getprop ro.boot.slot_suffix
getprop ro.boot.verifiedbootstate
echo '=== WLAN MODULE ==='
cat /proc/modules | grep -E '(^|[ ,])(qca_cld3[^ ,]*|wlan|cnss[^ ,]*|mac80211|wonder)([ ,]|$)'
for module in qca_cld3_peach_v2 wlan; do
    root=/sys/module/$module
    [ -d "$root" ] || continue
    echo "module=$module"
    cat "$root/refcnt" 2>/dev/null
    ls -l "$root/holders" 2>/dev/null
    for param in mishare_action_tx mishare_raw_tx; do
        [ ! -r "$root/parameters/$param" ] || {
            printf '%s=' "$param"
            cat "$root/parameters/$param"
        }
    done
done
echo '=== MODULE FILES ==='
for directory in /vendor_dlkm/lib/modules /odm_dlkm/lib/modules /vendor/lib/modules /odm/lib/modules; do
    [ -d "$directory" ] || continue
    echo "directory=$directory"
    find -L "$directory" -maxdepth 3 \( -name '*wlan*.ko' -o -name '*cld*.ko' -o -name '*peach*.ko' \) -print 2>/dev/null
    for file in "$directory"/modules.load "$directory"/modules.load.*; do
        [ -f "$file" ] || continue
        echo "load_list=$file"
        cat "$file"
    done
done
echo '=== INIT WLAN LOAD REFERENCES ==='
for directory in /vendor/etc/init /odm/etc/init; do
    [ -d "$directory" ] || continue
    grep -R -n -E '(insmod|modprobe|modules.load|qca_cld3|peach|wlan)' "$directory" 2>/dev/null
done
echo '=== END ==='
