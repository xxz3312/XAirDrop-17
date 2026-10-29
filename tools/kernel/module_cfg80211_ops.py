#!/usr/bin/env python3
"""Bounded ELF audit for popsicle's stock TESTMODE-enabled cfg80211 ops ABI.

Stock allocator disassembly checks paired slots including ROC 0x1f8/0x200,
PNO 0x250/0x258 and P2P 0x290/0x298. GKI disables cfg80211, so its .config
alone does not describe the separately built vendor wireless module.
This verifies callback locations and INI prefix, not full ABI/KCFI/RF safety.
"""
import hashlib
from pathlib import Path
import struct
from module_abi import inspect
from module_exports import load

EXPECTED = {
    0x0: 'wlan_hdd_cfg80211_suspend_wlan',
    0x8: 'wlan_hdd_cfg80211_resume_wlan',
    0x18: 'wlan_hdd_add_virtual_intf',
    0x20: 'wlan_hdd_del_virtual_intf',
    0x28: 'wlan_hdd_cfg80211_change_iface',
    0x30: 'wlan_hdd_cfg80211_add_intf_link',
    0x38: 'wlan_hdd_cfg80211_del_intf_link',
    0x40: 'wlan_hdd_cfg80211_add_key',
    0x48: 'wlan_hdd_cfg80211_get_key',
    0x50: 'wlan_hdd_cfg80211_del_key',
    0x58: 'wlan_hdd_cfg80211_set_default_key',
    0x60: 'wlan_hdd_set_default_mgmt_key',
    0x68: 'wlan_hdd_cfg80211_set_default_beacon_key',
    0x70: 'wlan_hdd_cfg80211_start_ap',
    0x78: 'wlan_hdd_cfg80211_change_beacon',
    0x80: 'wlan_hdd_cfg80211_stop_ap',
    0x88: 'wlan_hdd_cfg80211_add_station',
    0x90: 'wlan_hdd_cfg80211_del_station',
    0x98: 'wlan_hdd_change_station',
    0xa0: 'wlan_hdd_cfg80211_get_station',
    0xa8: 'wlan_hdd_cfg80211_dump_station',
    0x118: 'wlan_hdd_cfg80211_change_bss',
    0x128: 'wlan_hdd_set_txq_params',
    0x138: 'wlan_hdd_cfg80211_set_mon_ch',
    0x140: 'wlan_hdd_cfg80211_scan',
    0x148: 'wlan_hdd_cfg80211_abort_scan',
    0x170: 'wlan_hdd_cfg80211_connect',
    0x178: 'wlan_hdd_cfg80211_update_connect_params',
    0x180: 'wlan_hdd_cfg80211_disconnect',
    0x1a0: 'wlan_hdd_cfg80211_set_wiphy_params',
    0x1a8: 'wlan_hdd_cfg80211_set_txpower',
    0x1b0: 'wlan_hdd_cfg80211_get_txpower',
    0x1d0: 'wlan_hdd_cfg80211_set_bitrate_mask',
    0x1d8: 'wlan_hdd_cfg80211_dump_survey',
    0x1e0: 'wlan_hdd_cfg80211_set_pmksa',
    0x1e8: 'wlan_hdd_cfg80211_del_pmksa',
    0x1f0: 'wlan_hdd_cfg80211_flush_pmksa',
    0x1f8: 'wlan_hdd_cfg80211_remain_on_channel',
    0x200: 'wlan_hdd_cfg80211_cancel_remain_on_channel',
    0x208: 'wlan_hdd_mgmt_tx',
    0x210: 'wlan_hdd_cfg80211_mgmt_tx_cancel_wait',
    0x218: 'wlan_hdd_cfg80211_set_power_mgmt',
    0x238: 'wlan_hdd_cfg80211_update_mgmt_frame_registrations',
    0x240: 'wlan_hdd_cfg80211_set_chainmask',
    0x248: 'wlan_hdd_cfg80211_get_chainmask',
    0x250: 'wlan_hdd_cfg80211_sched_scan_start',
    0x258: 'wlan_hdd_cfg80211_sched_scan_stop',
    0x260: 'wlan_hdd_cfg80211_set_rekey_data',
    0x268: 'wlan_hdd_cfg80211_tdls_mgmt',
    0x270: 'wlan_hdd_cfg80211_tdls_oper',
    0x288: 'wlan_hdd_cfg80211_get_channel',
    0x2a0: 'wlan_hdd_cfg80211_set_mac_acl',
    0x2b8: 'wlan_hdd_cfg80211_update_ft_ies',
    0x2d8: 'wlan_hdd_cfg80211_channel_switch',
    0x2e8: 'wlan_hdd_cfg80211_set_ap_channel_width',
    0x310: 'wlan_hdd_cfg80211_start_nan',
    0x318: 'wlan_hdd_cfg80211_stop_nan',
    0x320: 'wlan_hdd_cfg80211_add_nan_func',
    0x328: 'wlan_hdd_cfg80211_del_nan_func',
    0x330: 'wlan_hdd_cfg80211_nan_change_conf',
    0x358: 'wlan_hdd_cfg80211_external_auth',
    0x360: 'wlan_hdd_cfg80211_tx_control_port',
    0x380: 'wlan_hdd_cfg80211_update_owe_info',
    0x3e0: 'wlan_hdd_cfg80211_set_ttlm_mapping',
    0x3f0: 'wlan_hdd_cfg80211_setup_link_reconfig',
}


def check_table(table, relocations):
    if len(table) != 0x418:
        raise ValueError('Wrong cfg80211_ops size; stock requires TESTMODE slots')
    if relocations != EXPECTED:
        bad = sorted(k for k in set(relocations) | set(EXPECTED)
                     if relocations.get(k) != EXPECTED.get(k))
        raise ValueError('Wrong cfg80211 callback slots: ' + ', '.join(hex(k) for k in bad))
    # Every unrelocated slot must be a real NULL, including TESTMODE and P2P.
    for offset in range(0, len(table), 8):
        if offset not in relocations and table[offset:offset+8] != bytes(8):
            raise ValueError('Nonzero unrelocated callback slot')
    return {'status': 'SELECTED_CFG80211_CALLBACK_SLOTS_MATCH_ONLY',
            'table_bytes': len(table), 'callbacks_checked': len(EXPECTED),
            'testmode_slots': ['0x1c0', '0x1c8'],
            'p2p_slots_null': True,
            'limitations': 'Not full cfg80211 ABI, function prototype, KCFI or RF certification.'}


CONTROL_SYMBOLS = {'wlan_hdd_state_fops', 'wlan_hdd_state_ctrl_param_open',
                   'wlan_hdd_state_ctrl_param_write', 'wlan_hdd_state_ctrl_param_release'}


def check_control_symbols(names):
    missing = CONTROL_SYMBOLS - set(names)
    if missing:
        raise ValueError('Missing Android /dev/wlan control implementation: ' + ', '.join(sorted(missing)))
    return {'status': 'CONTROL_IMPLEMENTATION_PRESENT_ONLY',
            'symbols': sorted(CONTROL_SYMBOLS),
            'limitations': 'Symbol presence does not prove device-node creation, HAL compatibility or Wi-Fi enable.'}


def audit(path):
    inspect(path)
    data, sections = load(path)
    tab = next(s for s in sections if s['type'] == 2)
    st = sections[tab['link']]
    strings = data[st['off']:st['off']+st['size']]
    syms = []
    for i in range(tab['size']//24):
        n, info, _, sh, v, z = struct.unpack_from('<IBBHQQ', data, tab['off']+24*i)
        syms.append((strings[n:strings.index(b'\0', n)].decode(), sh, v, z, info))
    matches = [s for s in syms if s[0] == 'wlan_hdd_cfg80211_ops']
    if len(matches) != 1:
        raise ValueError('Expected exactly one WLAN cfg80211 callback table')
    _, index, start, size, info = matches[0]
    if info & 15 != 1 or not 0 < index < len(sections):
        raise ValueError('Expected defined OBJECT callback table')
    target = sections[index]
    if start+size > target['size']:
        raise ValueError('Callback table outside section')
    funcs = {(s[1], s[2]): s[0] for s in syms if s[4] & 15 == 2}
    rel = {}
    for sec in sections:
        if sec['type'] != 4 or sec['info'] != index:
            continue
        if sec['link'] != tab['idx'] or sec['size'] % 24:
            raise ValueError('Unsupported relocation metadata')
        for i in range(sec['size']//24):
            offset, ri, add = struct.unpack_from('<QQq', data, sec['off']+i*24)
            offset -= start
            if not 0 <= offset < size:
                continue
            if ri & 0xffffffff != 257 or offset % 8 or offset in rel:
                raise ValueError('Invalid callback relocation')
            s = syms[ri >> 32]
            name = funcs.get((s[1], s[2]+add))
            if not name:
                raise ValueError('Callback does not resolve to a function')
            rel[offset] = name
    pos = target['off']+start
    report = check_table(data[pos:pos+size], rel)
    good = b'wlan/qca_cld/peach_v2/WCNSS_qcom_cfg.ini\0'
    wrong = b'wlan/qca_cld/qca_cld3_peach_v2/WCNSS_qcom_cfg.ini\0'
    if good not in data or wrong in data:
        raise ValueError('Wrong target INI prefix')
    report['android_wlan_control'] = check_control_symbols(s[0] for s in syms)
    report.update(wlan_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                  ini_prefix='wlan/qca_cld/peach_v2/')
    return report
