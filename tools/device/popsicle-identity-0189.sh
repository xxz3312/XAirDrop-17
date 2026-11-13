#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Read-only evidence collection. No sourcing, lifecycle commands or filesystem writes.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
[ "$#" = 0 ] || { echo 'Usage: sh popsicle-identity-0189.sh (no actions accepted)' >&2; exit 2; }
err=0
emit() {
    case "$2" in *'	'*|*'
'*) printf '%s\tINVALID_MULTILINE\n' "$1"; err=1;;
        *) printf '%s\t%s\n' "$1" "$2";; esac
}
record() {
    key=$1; shift
    if value=$("$@" 2>/dev/null); then emit "$key" "$value"
    else emit "$key" UNREADABLE; err=1; fi
}
hash() {
    if sum=$(sha256sum "$2" 2>/dev/null); then
        digest=${sum%% *}
        case "$digest" in ''|*[!0-9a-f]*) emit "$1" INVALID_HASH; err=1; return;; esac
        if [ "${#digest}" = 64 ]; then emit "$1" "$digest"; return; fi
    fi
    emit "$1" UNREADABLE; err=1
}
properties() {
    suffix=$1
    record "device$suffix" getprop ro.product.device
    record "firmware$suffix" getprop ro.build.version.incremental
    record "slot$suffix" getprop ro.boot.slot_suffix
    record "boot_completed$suffix" getprop sys.boot_completed
    record "kernel$suffix" uname -r
    record "machine$suffix" uname -m
}
emit schema 1
emit stage 0189
record uid id -u
if [ "$value" != 0 ]; then emit capture_status ROOT_REQUIRED; exit 1; fi
record boot_id cat /proc/sys/kernel/random/boot_id
properties ''
slot=$(getprop ro.boot.slot_suffix 2>/dev/null) || slot=UNREADABLE
case "$slot" in
    _a|_b)
        boot=/dev/block/by-name/boot$slot
        if [ -b "$boot" ]; then hash boot_sha256 "$boot"
        else emit boot_sha256 UNREADABLE; err=1; fi;;
    *) emit boot_sha256 INVALID_SLOT; err=1;;
esac
for mod in cnss2 qca_cld3_peach_v2; do
    for area in vendor vendor_dlkm; do
        file=/$area/lib/modules/$mod.ko
        if [ -f "$file" ]; then
            emit "$mod.$area.present" 1
            hash "$mod.$area.sha256" "$file"
        else emit "$mod.$area.present" 0; fi
    done
    if [ -d "/sys/module/$mod" ]; then
        emit "$mod.loaded" 1
        record "$mod.initstate" cat "/sys/module/$mod/initstate"
        hash "$mod.note_sha256" "/sys/module/$mod/notes/.note.gnu.build-id"
    else emit "$mod.loaded" 0; fi
done
for mod in wonder wonder_sysctl opairshare_wonder_provider opairshare_route_b_probe oneplus13_wonder_provider; do
    if [ -d "/sys/module/$mod" ]; then emit "$mod.loaded" 1
    else emit "$mod.loaded" 0; fi
done
# Observe retained state; never remove or archive it.
for name in xairdrop17-pair-transaction xairdrop17-stockcnss-transaction; do
    file=/data/adb/$name
    if [ -e "$file" ] || [ -L "$file" ]; then emit "$name.present" 1
    else emit "$name.present" 0; fi
done
properties .after
record boot_id.after cat /proc/sys/kernel/random/boot_id
if [ "$err" = 0 ]; then emit capture_status CAPTURE_COMPLETE_NOT_FOR_INSTALL
else emit capture_status CAPTURE_INCOMPLETE; exit 1; fi
