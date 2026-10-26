#!/usr/bin/env python3
"""Check Wonder's real ELF callback relocations against stock allocator slots.

Compile assertions can be bypassed by an inactive Kbuild file. This checks the
linked bytes independently; it is only a bounded allocator-table check.
"""
import hashlib
from pathlib import Path
import struct

from module_abi import inspect
from module_exports import load


def check_table(table, relocations):
    expected = {
        0x250: 'ieee80211_emulate_add_chanctx',
        0x258: 'ieee80211_emulate_remove_chanctx',
        0x260: 'ieee80211_emulate_change_chanctx',
    }
    if len(table) < 0x2f8:
        raise ValueError('Truncated mac80211 ops table')
    for offset, name in expected.items():
        if relocations.get(offset) != name:
            raise ValueError(f'Wrong callback relocation at {offset:#x}: expected {name}')
    for offset in [0, 8, 16, 0x30, 0x40, 0x48, 0x80, 0x2f0]:
        if offset not in relocations:
            raise ValueError(f'Missing mandatory callback at {offset:#x}')
    for offset in [0x268, 0x270]:
        if offset in relocations or table[offset:offset + 8] != bytes(8):
            raise ValueError(f'Unexpected assign/unassign callback at {offset:#x}')
    return {
        'status': 'ALLOCATOR_TABLE_OFFSETS_MATCH_ONLY',
        'ops_table_bytes': len(table),
        'channel_relocations': {hex(k): v for k, v in expected.items()},
        'mandatory_allocator_callbacks_have_relocations': True,
        'assign_and_unassign_are_null': True,
        'limitations': 'Not full mac80211 ABI, KCFI or runtime certification.',
    }


def audit(path):
    inspect(path)  # Reject non-AArch64/non-relocatable input first.
    data, sections = load(path)
    symtab = next(s for s in sections if s['type'] == 2)
    strings = sections[symtab['link']]
    names = data[strings['off']:strings['off'] + strings['size']]
    symbols = []
    for i in range(symtab['size'] // 24):
        name, info, _, section, value, size = struct.unpack_from(
            '<IBBHQQ', data, symtab['off'] + i * 24)
        symbols.append((names[name:names.index(b'\0', name)].decode(),
                        section, value, size, info))
    matches = [s for s in symbols if s[0] == 'wonder_mac80211_ops']
    if len(matches) != 1:
        raise ValueError('Expected exactly one wonder_mac80211_ops symbol')
    _, index, start, size, info = matches[0]
    if info & 15 != 1 or not 0 < index < len(sections):
        raise ValueError('Expected defined OBJECT callback table')
    target = sections[index]
    if start + size > target['size']:
        raise ValueError('Callback table outside section')
    relocations = {}
    for section in sections:
        if section['type'] != 4 or section['info'] != index:
            continue
        if section['link'] != symtab['idx'] or section['size'] % 24:
            raise ValueError('Unsupported callback relocation metadata')
        for i in range(section['size'] // 24):
            offset, rel_info, addend = struct.unpack_from(
                '<QQq', data, section['off'] + i * 24)
            if not start <= offset < start + size:
                continue
            if rel_info & 0xffffffff != 257 or offset % 8:
                raise ValueError('Expected aligned R_AARCH64_ABS64 callback relocation')
            offset -= start
            if offset in relocations:
                raise ValueError('Duplicate callback relocation')
            symbol = symbols[rel_info >> 32]
            if symbol[0].startswith('ieee80211_emulate_') and addend != 0:
                raise ValueError('Unexpected callback helper addend')
            relocations[offset] = symbol[0]
    position = target['off'] + start
    report = check_table(data[position:position + size], relocations)
    report['wonder_sha256'] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return report
