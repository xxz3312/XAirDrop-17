#!/usr/bin/env python3
"""Audit the pinned LPC/OCC header-copy path; never infer phone firmware coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import re

FILTER = 'qca-wifi-host-cmn/dp/wifi3.0/monitor/dp_mon_filter.c'
ENUM = 'qca-wifi-host-cmn/dp/wifi3.0/monitor/dp_mon_filter.h'
RX = 'qca-wifi-host-cmn/dp/wifi3.0/monitor/dp_rx_mon.c'
CFG = 'qcacld-3.0/core/hdd/src/wlan_hdd_cfg80211.c'


def tokens(source):
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', source, flags=re.S)


def block(source, pattern):
    clean = tokens(source)
    match = re.search(pattern, clean)
    if not match:
        raise ValueError('Expected source definition absent: ' + pattern)
    start = clean.index('{', match.start())
    depth = 1
    for pos in range(start + 1, len(clean)):
        depth += (clean[pos] == '{') - (clean[pos] == '}')
        if depth == 0:
            return clean[start + 1:pos]
    raise ValueError('Unterminated source definition')


def function(source, name):
    return block(source, r'\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{')


def audit(wlan, project):
    paths = {p: (wlan / p).read_text() for p in [FILTER, ENUM, RX, CFG]}
    filt = function(paths[FILTER], 'dp_mon_set_local_pkt_capture_rx_filter')
    start = function(paths[FILTER], 'dp_mon_start_local_pkt_capture')
    rx = function(paths[RX], 'dp_rx_handle_local_pkt_capture')
    enum = block(paths[ENUM], r'enum\s+dp_rx_hdr_dma_length\s*\{')
    if not re.search(r'rx_hdr_length\s*=\s*RX_HDR_DMA_LENGTH_256B\s*;', filt):
        raise ValueError('Header length is no longer the audited fixed-256 setting')
    if not re.search(r'packet_header\s*=\s*1\s*;', filt):
        raise ValueError('Expected RX header TLV capture not found')
    if 'dp_mon_set_local_pkt_capture_rx_filter(pdev, filter)' not in start:
        raise ValueError('Capture startup no longer calls the audited filter')
    if not all(x in rx for x in ['HAL_TLV_STATUS_HEADER', 'qdf_nbuf_clone(nbuf)',
                                 'first_msdu_payload', 'payload_len', 'qdf_nbuf_trim_tail']):
        raise ValueError('RX header-copy reconstruction path changed')
    lengths = {int(n): int(value) for n, value in re.findall(r'RX_HDR_DMA_LENGTH_(\d+)B\s*=\s*(\d+)', enum)}
    if lengths.get(256) != 3:
        raise ValueError('256-byte header DMA encoding changed; do not guess an enum')
    registration = function(paths[CFG], '__wlan_hdd_cfg80211_update_mgmt_frame_registrations')
    wonder_path = 'kernel/wonder/mac80211.c'
    tool_path = 'native/wireless/action_tx.c'
    wonder = (project / wonder_path).read_text()
    tool = (project / tool_path).read_text()
    bridge = function(wonder, 'wonder_rx_80211_frame')
    listener = function(tool, 'awdl_main')
    buffer = re.search(r'unsigned\s+char\s+frame\[(\d+)\]', listener)
    if not buffer or 'MSG_TRUNC' not in listener:
        raise ValueError('Listener buffer/receive contract changed')
    return {
        'status': 'SOURCE_HEADER_COPY_LIMIT_FOUND_NOT_FIRMWARE_CERTIFICATION',
        'configured_header_bytes': 256,
        'header_dma_encodings': lengths,
        'maximum_declared_header_bytes': max(lengths),
        'uses_header_tlv_copy': True,
        'wonder_bridge_has_trim_call': bool(re.search(r'\b(?:p?skb_trim|skb_put|skb_pull)\s*\(', bridge)),
        'listener_buffer_bytes': int(buffer[1]),
        'listener_requests_full_datagram_length': True,
        'registration_callback_programs_sme': bool(re.search(r'\bsme_\w+\s*\(', registration)),
        'registration_scope': 'only audited update_mgmt_frame_registrations body; not all firmware paths',
        'stock_binary_matches_audited_source': False,
        'full_frame_rx_implemented': False,
        'evidence_sha256': {**{p: hashlib.sha256(s.encode()).hexdigest() for p, s in paths.items()},
                            wonder_path: hashlib.sha256(wonder.encode()).hexdigest(),
                            tool_path: hashlib.sha256(tool.encode()).hexdigest()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan-source', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.wlan_source, args.project)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])


if __name__ == '__main__':
    main()
