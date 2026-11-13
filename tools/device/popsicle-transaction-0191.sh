#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Standalone read-only retained-transaction inventory. No archive/remove/replay.
set -u
PATH=/system/bin:/system/xbin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH
[ "$#" = 0 ] || { echo 'No action arguments accepted.' >&2; exit 2; }
xt_error=0
xt_expected_digests=0
xt_valid_digests=0
xt_emit() {
    case "$2" in ''|*'	'*|*'
'*) printf '%s\tINVALID_VALUE\n' "$1"; xt_error=1;;
        *) printf '%s\t%s\n' "$1" "$2";; esac
}
xt_meta() {
    [ ! -L "$1" ] || return 1
    xt_uid=$(stat -c %u "$1") && xt_mode=$(stat -c %a "$1") || return 1
    [ "$xt_uid" = 0 ] || return 1
    case "$xt_mode" in ''|*[!0-7]*) return 1;; esac
    case "${#xt_mode}" in 3|4) ;; *) return 1;; esac
    case "$xt_mode" in *[2367][0-7]|*[0-7][2367]) return 1;; esac
}
xt_read() {
    xt_key=$1; xt_path=$2; xt_required=$3
    if [ ! -e "$xt_path" ] && [ ! -L "$xt_path" ]; then
        xt_emit "$xt_key.status" MISSING; xt_emit "$xt_key.value" -
        [ "$xt_required" = 0 ] || xt_error=1
        return
    fi
    if [ -f "$xt_path" ] && xt_meta "$xt_path"; then
        xt_size=$(stat -c %s "$xt_path") || xt_size=INVALID
        case "$xt_size" in ''|*[!0-9]*) xt_size=99999;; esac
        if [ "$xt_size" -le 256 ] && xt_value=$(cat "$xt_path" 2>/dev/null); then
            xt_emit "$xt_key.status" OK; xt_emit "$xt_key.value" "$xt_value"; return
        fi
    fi
    xt_emit "$xt_key.status" REJECTED; xt_emit "$xt_key.value" -; xt_error=1
}
xt_digest() {
    xt_key=$1; xt_path=$2
    if [ -f "$xt_path" ] && [ -s "$xt_path" ] && xt_meta "$xt_path" && xt_sum=$(sha256sum "$xt_path" 2>/dev/null); then
        xt_sha=${xt_sum%% *}
        case "$xt_sha" in ''|*[!0-9a-f]*) xt_sha=INVALID;; esac
        if [ "${#xt_sha}" = 64 ]; then
            xt_emit "$xt_key.status" OK; xt_emit "$xt_key.sha256" "$xt_sha"
            xt_valid_digests=$((xt_valid_digests+1)); return
        fi
    fi
    xt_emit "$xt_key.status" REJECTED; xt_emit "$xt_key.sha256" -; xt_error=1
}
xt_emit schema 1
xt_emit stage 0191
xt_identity=$(id -u) || xt_identity=UNKNOWN
xt_emit uid "$xt_identity"
[ "$xt_identity" = 0 ] || { xt_emit capture_status ROOT_REQUIRED; exit 1; }
xt_boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null) || { xt_boot=UNREADABLE; xt_error=1; }
xt_emit boot_id "$xt_boot"
xt_dir=/data/adb/xairdrop17-stockcnss-transaction
if ! xt_meta /data || ! xt_meta /data/adb; then
    xt_emit transaction.present UNKNOWN; xt_error=1
elif [ ! -e "$xt_dir" ] && [ ! -L "$xt_dir" ]; then
    xt_emit transaction.present 0
else
    xt_emit transaction.present 1
    # Never traverse a symlink or an untrusted writable transaction parent.
    if [ -d "$xt_dir" ] && xt_meta /data && xt_meta /data/adb && xt_meta "$xt_dir"; then
        xt_before=$(stat -c %d:%i "$xt_dir") || { xt_before=UNREADABLE; xt_error=1; }
        xt_emit transaction.identity "$xt_before"
        for xt_file in boot-id phase manifest.sha256 wifi.before phase.new; do
            xt_required=1; [ "$xt_file" != phase.new ] || xt_required=0
            xt_read "$xt_file" "$xt_dir/$xt_file" "$xt_required"
        done
        xt_expected_digests=2
        xt_digest backup "$xt_dir/qca_cld3_peach_v2.ko"
        xt_digest hals "$xt_dir/hals"
        # Repeat mutable journal and directory identity observations.
        xt_read phase.after "$xt_dir/phase" 1
        xt_after=$(stat -c %d:%i "$xt_dir") || { xt_after=UNREADABLE; xt_error=1; }
        xt_emit transaction.identity.after "$xt_after"
    else
        xt_emit transaction.access REJECTED; xt_error=1
    fi
fi
xt_boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null) || { xt_boot=UNREADABLE; xt_error=1; }
xt_emit boot_id.after "$xt_boot"
if [ "$xt_error" = 0 ] && [ "$xt_valid_digests" = "$xt_expected_digests" ]; then xt_emit capture_status CAPTURE_COMPLETE_RECORD_ONLY
else xt_emit capture_status CAPTURE_INCOMPLETE; exit 1; fi
