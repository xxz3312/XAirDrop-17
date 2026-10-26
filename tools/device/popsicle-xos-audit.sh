#!/system/bin/sh
# Read system state and copy selected ELF dependencies into a private report.
# Does not load modules, run donor executables, mount, register services or change policy.
set -u
[ "$(id -u)" = 0 ] || { echo 'Run with su.'; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || { echo 'Expected popsicle.'; exit 1; }
umask 077
tag=$(date +%Y%m%d-%H%M%S)-$$
work=/data/local/tmp/17pm-xos-audit-$tag
report=/sdcard/Download/17pm-xos-audit-$tag.tar.gz
mkdir -p "$work/libs" /sdcard/Download || exit 1
{
    getprop ro.product.device
    getprop ro.build.version.incremental
    getprop ro.build.version.sdk
    uname -r
    getenforce
    getconf PAGESIZE
} > "$work/device.txt" 2>&1
{
    dumpsys package com.miui.mishare.connectivity | grep -E 'codePath=|versionName=|versionCode=|appId=|userId=|NETWORK_FACTORY'
    service check com.domestic.xoscomm.IDomesticXOsComm/default
    ps -AZ | grep -E 'mishare|DomesticXOsComm'
    ls -ldZ /sys/class/net/xos0 /sys/class/ieee80211/wonder /proc/sys/net/wonder/wonder_enable
    cat /proc/sys/net/wonder/wonder_enable
} > "$work/state.txt" 2>&1
# Preserve separate candidate paths. File existence alone is not linker compatibility.
: > "$work/libraries.txt"
for name in liblog.so libbinder_ndk.so libutils.so libcutils.so libbase.so libc++.so libc.so libm.so libdl.so libnl.so libpcap.so; do
    for dir in /system/lib64 /system_ext/lib64 /product/lib64 /vendor/lib64 /apex/com.android.runtime/lib64/bionic; do
        file=$dir/$name
        [ -f "$file" ] || continue
        dest=$work/libs$dir
        mkdir -p "$dest" || exit 1
        if cp -L "$file" "$dest/$name"; then
            ls -lZ "$file" >> "$work/libraries.txt" 2>&1
            sha256sum "$file" >> "$work/libraries.txt" 2>&1
        else
            echo "COPY_FAILED $file" >> "$work/libraries.txt"
        fi
    done
done
if [ -r /linkerconfig/ld.config.txt ]; then
    cp /linkerconfig/ld.config.txt "$work/ld.config.txt" || exit 1
fi
{
    for file in /system/etc/selinux/*service_contexts /system_ext/etc/selinux/*service_contexts /product/etc/selinux/*service_contexts /vendor/etc/selinux/*service_contexts; do
        [ -f "$file" ] || continue
        echo "FILE $file"
        grep -iE 'xoscomm|domestic' "$file"
    done
    for dir in /vendor/etc/vintf /odm/etc/vintf /system_ext/etc/vintf; do
        [ -d "$dir" ] && grep -RinE 'xoscomm|IDomesticXOsComm' "$dir"
    done
} > "$work/service-config.txt" 2>&1
if tar -czf "$report" -C "$work" .; then
    echo "Report: $report"
    echo 'Dependency and service audit only; no donor code was executed.'
else
    echo "Packaging failed. Files retained at $work"
    exit 1
fi
