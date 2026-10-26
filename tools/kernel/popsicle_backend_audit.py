#!/usr/bin/env python3
"""Read-only inventory of the pinned WLAN backend's porting gaps.

Identifier presence and monitor support are never radio/AWDL certification.
No source rewriting, compilation, interface creation or firmware commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PIN = '36df473046706a5259942e1bf7222108dbbb860f'
HDD = 'qcacld-3.0/core/hdd/'
NATIVE = {
    'adapter_lifecycle': (HDD + 'src/wlan_hdd_main.c', ['hdd_open_adapter', 'hdd_close_adapter', 'hdd_start_adapter', 'hdd_stop_adapter']),
    'driver_lifecycle': (HDD + 'src/wlan_hdd_driver_ops.c', ['hdd_soc_load_unlock', '__hdd_soc_remove']),
    'monitor_frequency': (HDD + 'src/wlan_hdd_main.c', ['wlan_hdd_set_mon_chan']),
    'monitor_control': (HDD + 'src/wlan_hdd_rx_monitor.c', ['hdd_enable_monitor_mode', 'hdd_disable_monitor_mode']),
    'management_tx': (HDD + 'src/wlan_hdd_p2p.c', ['wlan_hdd_mgmt_tx']),
}
REQUIRED = {
    'hdd_wonder_backend': (HDD + 'src/wlan_hdd_wondertap.c', ['wlan_hdd_wondertap_register_ops', 'wlan_hdd_wondertap_unregister_ops']),
    'hdd_backend_contract': (HDD + 'inc/wlan_hdd_wondertap.h', ['hdd_wondertap_context']),
    'host_passthru_mode': ('qca-wifi-host-cmn/qdf/inc/qdf_types.h', ['QDF_PASSTHRU_MODE']),
    'datapath_passthru_mode': ('qca-wifi-host-cmn/dp/inc/cdp_txrx_cmn_struct.h', ['wlan_op_mode_passthru']),
    'firmware_passthru_type': ('fw-api/fw/wmi_unified.h', ['WMI_VDEV_TYPE_WIFI_PASSTHRU']),
    'backend_build_entry': ('qcacld-3.0/Kbuild', ['wlan_hdd_wondertap']),
}


def code_only(text):
    # Keep quoted literals out too: log text is not an implementation.
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda m: '\n' * m[0].count('\n'), text, flags=re.S)


def identifiers(text, names):
    code = code_only(text)
    return {name: bool(re.search(r'\b' + re.escape(name) + r'\b', code)) for name in names}


def inventory(root):
    root = Path(root)
    evidence = {}
    def inspect(relative, names):
        path = root / relative
        if not path.is_file():
            return {'file': relative, 'exists': False, 'identifiers': {n: False for n in names}}
        data = path.read_bytes()
        evidence[relative] = hashlib.sha256(data).hexdigest()
        return {'file': relative, 'exists': True,
                'identifiers': identifiers(data.decode(), names)}
    native = {key: inspect(*value) for key, value in NATIVE.items()}
    missing_native = [k for k, v in native.items() if not all(v['identifiers'].values())]
    if missing_native:
        raise ValueError('Native source anchors changed: ' + ', '.join(missing_native))
    required = {key: inspect(*value) for key, value in REQUIRED.items()}
    missing = [k for k, v in required.items() if not all(v['identifiers'].values())]
    main = (root / (HDD + 'src/wlan_hdd_main.c')).read_text()
    match = re.search(r'\bwlan_mon_drv_ops\s*=\s*\{(.*?)\};', code_only(main), re.S)
    if not match:
        raise ValueError('Cannot locate monitor net_device_ops initializer')
    monitor_tx = bool(re.search(r'\.ndo_start_xmit\s*=', match[1]))
    return {
        'status': 'SOURCE_PORT_REQUIRED' if missing else 'SOURCE_IDENTIFIERS_PRESENT_REVIEW_REQUIRED',
        'native_anchors': native, 'port_requirements': required,
        'missing_source_plumbing': missing,
        'monitor_netdev_has_start_xmit': monitor_tx,
        'file_sha256': evidence,
        'radio_usable': None, 'firmware_passthru_support': 'UNVERIFIED',
        'limitations': 'Source identifiers only: even all present does not prove implementations, semantics, ownership, ABI, KCFI, firmware support, loading, TX/RX or AWDL. Monitor RX and management TX are distinct paths; no assumption of raw data injection or firmware type 0x9 support.',
    }


def audited_inventory(root):
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('Unexpected WLAN source commit: ' + head)
    report = inventory(root)
    report['source_commit'] = head
    # Includes compatibility patches; HEAD alone does not identify working bytes.
    report['source_dirty'] = bool(subprocess.check_output(
        ['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'], text=True).strip())
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-source-plumbing', action='store_true')
    args = parser.parse_args()
    result = audited_inventory(args.wlan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"{result['status']}: {len(result['missing_source_plumbing'])} missing source groups; firmware unverified")
    raise SystemExit(2 if args.require_source_plumbing and result['missing_source_plumbing'] else 0)
