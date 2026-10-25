#!/usr/bin/env bash
# Diagnostic Kbuild only. Never packages, flashes or loads a module.
# Usage: script PHASE BASELINE COMMON SOC WLAN DATAIPA CLANG RUST HOST OUT
set -euo pipefail
if [[ $# != 10 ]]; then
  echo 'Usage: popsicle_trial_build.sh configure|prepare|wlan-object|wlan-modules BASELINE COMMON SOC WLAN DATAIPA CLANG RUST HOST OUT' >&2
  exit 3
fi
phase=$1
case "$phase" in configure|prepare|wlan-object|wlan-modules) ;; *) echo 'Unknown phase' >&2; exit 3;; esac
baseline=$(realpath "$2")
common=$(realpath "$3")
soc=$(realpath "$4")
wlan=$(realpath "$5")
dataipa=$(realpath "$6")
clang=$(realpath "$7")
rust=$(realpath "$8")
host=$(realpath "$9")
# Resolve without creating directories until destructive-path checks have passed.
out=$(realpath -m "${10}")
for source_root in "$baseline" "$common" "$soc" "$wlan" "$dataipa" "$clang" "$rust" "$host"; do
  case "$out/" in "$source_root/"*) echo 'Output must be outside input directories' >&2; exit 3;; esac
  case "$source_root/" in "$out/"*) echo 'Output must not contain input directories' >&2; exit 3;; esac
done
for file in "$baseline/kernel-config.gz" "$common/Makefile" \
  "$wlan/qcacld-3.0/configs/canoe_gki_peach-v2_defconfig" \
  "$dataipa/drivers/platform/msm/include/linux/ipa.h" \
  "$clang/bin/clang" "$clang/lib/libclang.so" "$rust/bin/rustc" \
  "$host/usr/bin/bindgen" "$host/usr/bin/pahole"; do
  [[ -f "$file" ]] || { echo "Missing input: $file" >&2; exit 3; }
done
check_revision() {
  local actual
  actual=$(git -C "$1" rev-parse HEAD)
  [[ "$actual" == "$2" ]] || { echo "Unexpected source revision: $1 ($actual)" >&2; exit 3; }
}
check_revision "$common" e2b8ca7c8d0551a6124b1a7322f5ae532845f1b5
check_revision "$soc" 45705be1220b4cfa8100516ad86711656c0b634e
check_revision "$wlan" 36df473046706a5259942e1bf7222108dbbb860f
check_revision "$(git -C "$dataipa" rev-parse --show-toplevel)" 5ab2a689ff87d7d28c511f1762cf41c1b90d965a
hwid_include=${POPSICLE_HWID_INCLUDE:-$soc/drivers/misc/hwid}
if [[ "$phase" == wlan-* && ! -f "$hwid_include/hwid.h" ]]; then
  echo 'Missing HWID header. Supply POPSICLE_HWID_INCLUDE only after verifying its target ABI.' >&2
  exit 2
fi
target=qca_cld3_peach_v2.o
extra_symbols=()
if [[ "$phase" == wlan-modules ]]; then
  for input in "$out/Module.symvers" "$out/protected_module_names_list" "${POPSICLE_EXTRA_SYMBOLS:-}"; do
    [[ -s "$input" ]] || { echo "Missing real modpost input: $input" >&2; exit 2; }
  done
  [[ -z "${KBUILD_MODPOST_WARN:-}${KBUILD_MODPOST_NOFINAL:-}${KBUILD_NSDEPS:-}" ]] || {
    echo 'Refusing relaxed modpost settings' >&2; exit 3;
  }
  target=modules
  extra_symbols=("KBUILD_EXTRA_SYMBOLS=$POPSICLE_EXTRA_SYMBOLS")
fi
export PATH="$host/usr/bin:$rust/bin:$clang/bin:$PATH"
export M4="$host/usr/bin/m4"
export BISON_PKGDATADIR="$host/usr/share/bison"
export LD_LIBRARY_PATH="$host/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LIBCLANG_PATH="$clang/lib"
make_args=(-C "$common" "O=$out" ARCH=arm64 "LLVM=$clang/bin/"
  "HOSTCFLAGS=-I$host/usr/include"
  "HOSTLDFLAGS=-L$host/usr/lib/x86_64-linux-gnu")
mkdir -p "$out"
for source_root in "$common" "$soc" "$wlan"; do
  git -C "$source_root" diff --stat HEAD
done > "$out/source-delta.txt"
# Reject malformed archives before replacing the diagnostic output config.
gzip -t "$baseline/kernel-config.gz"
gzip -dc "$baseline/kernel-config.gz" > "$out/.config"
make "${make_args[@]}" olddefconfig
python3 - "$baseline/kernel-config.gz" "$out/.config" <<'PY'
import gzip, json, sys
from pathlib import Path
def parse(text):
    return dict(line.split('=', 1) for line in text.splitlines()
                if line.startswith('CONFIG_') and '=' in line)
stock = parse(gzip.decompress(Path(sys.argv[1]).read_bytes()).decode())
built = parse(Path(sys.argv[2]).read_text())
delta = {key: {'stock': stock.get(key), 'configured': built.get(key)}
         for key in sorted(stock.keys() | built.keys()) if stock.get(key) != built.get(key)}
Path(sys.argv[2]).with_name('stock-config-delta.json').write_text(json.dumps(delta, indent=2) + '\n')
critical = ['CONFIG_RUST', 'CONFIG_CFI_CLANG', 'CONFIG_CFI_ICALL_NORMALIZE_INTEGERS',
            'CONFIG_CC_VERSION_TEXT', 'CONFIG_CLANG_VERSION',
            'CONFIG_RUSTC_VERSION_TEXT', 'CONFIG_RUSTC_VERSION',
            'CONFIG_BINDGEN_VERSION_TEXT',
            'CONFIG_MODVERSIONS', 'CONFIG_EXTENDED_MODVERSIONS', 'CONFIG_GENDWARFKSYMS',
            'CONFIG_ARM64_4K_PAGES', 'CONFIG_LTO_NONE', 'CONFIG_DEBUG_INFO_BTF',
            'CONFIG_DEBUG_INFO_BTF_MODULES', 'CONFIG_MODULE_SIG_PROTECT',
            'CONFIG_MODULE_UNLOAD', 'CONFIG_SMP', 'CONFIG_PREEMPT', 'CONFIG_PREEMPT_DYNAMIC']
bad = [key for key in critical if stock.get(key) != built.get(key)]
if bad:
    raise SystemExit('Refusing changed critical configuration: ' + ', '.join(bad))
print(f'Critical settings retained; {len(delta)} configuration differences require review.')
PY
[[ "$phase" != configure ]] || exit 0
jobs=${POPSICLE_BUILD_JOBS:-4}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid job count' >&2; exit 3; }
make "${make_args[@]}" "-j$jobs" modules_prepare
[[ "$phase" != prepare ]] || exit 0
if [[ ! -e "$wlan/qcacld-3.0/cmn" && ! -L "$wlan/qcacld-3.0/cmn" ]]; then
  ln -s ../qca-wifi-host-cmn "$wlan/qcacld-3.0/cmn"
fi
[[ "$(realpath "$wlan/qcacld-3.0/cmn")" == "$wlan/qca-wifi-host-cmn" ]] || {
  echo 'Unexpected cmn source' >&2; exit 3;
}
make "${make_args[@]}" "-j$jobs" \
  "M=$wlan/qcacld-3.0" MODNAME=qca_cld3_peach_v2 \
  "WLAN_ROOT=$wlan/qcacld-3.0" CONFIG_QCA_CLD_WLAN=m \
  CONFIG_QCA_CLD_WLAN_PROFILE=canoe_gki_peach-v2 \
  CONFIG_IPA_OUT_OF_TREE=y \
  "DATA_IPA_INC=$dataipa/drivers/platform/msm/include" \
  "EXTRA_CFLAGS=-I$soc/include -I$hwid_include -DCONFIG_IPA3_MODULE=1 -DCONFIG_ARM_SMMU_MODULE=1 -DCONFIG_QCOM_IOMMU_UTIL_MODULE=1" \
  "${extra_symbols[@]}" "$target"
echo 'Diagnostic compilation finished; no load, firmware or AirDrop compatibility is implied.'
