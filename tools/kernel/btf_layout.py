#!/usr/bin/env python3
"""Read-only, bounded comparison of selected standalone little-endian BTF layouts.

This does not validate function prototypes, pointer targets, KCFI or loadability.
Input must be raw standalone BTF, not ELF or split module BTF.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


class Btf:
    def __init__(self, data):
        self.sha256 = hashlib.sha256(data).hexdigest()
        if len(data) < 24:
            raise ValueError('Truncated BTF header')
        magic, version, flags, hdr, toff, tlen, soff, slen = struct.unpack_from('<HBBIIIII', data)
        if magic != 0xeb9f or version != 1 or flags or hdr < 24:
            raise ValueError('Unsupported BTF format')
        if hdr + max(toff + tlen, soff + slen) > len(data):
            raise ValueError('Truncated BTF sections')
        self.strings = data[hdr + soff:hdr + soff + slen]
        if not self.strings or self.strings[0] != 0:
            raise ValueError('Standalone BTF string table required')
        raw = data[hdr + toff:hdr + toff + tlen]
        self.types = [None]
        pos = 0
        while pos < len(raw):
            if pos + 12 > len(raw):
                raise ValueError('Truncated BTF type')
            name, info, size = struct.unpack_from('<III', raw, pos)
            kind, count, flag = (info >> 24) & 31, info & 65535, bool(info >> 31)
            stride = {1: 4, 2: 0, 3: 12, 4: count * 12, 5: count * 12,
                      6: count * 8, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0,
                      12: 0, 13: count * 8, 14: 4, 15: count * 12,
                      16: 0, 17: 4, 18: 0, 19: count * 12}.get(kind)
            if stride is None or pos + 12 + stride > len(raw):
                raise ValueError('Unsupported or truncated BTF kind')
            payload = raw[pos + 12:pos + 12 + stride]
            self.types.append(dict(name=self.string(name), kind=kind, size=size,
                                   count=count, flag=flag, payload=payload))
            pos += 12 + stride

    def string(self, offset):
        if not 0 <= offset < len(self.strings):
            raise ValueError('Invalid BTF string offset')
        end = self.strings.find(b'\0', offset)
        if end < 0:
            raise ValueError('Unterminated BTF string')
        return self.strings[offset:end].decode('utf-8')

    def descriptor(self, index, seen=()):
        if not index:
            return {'kind': 'void', 'size': 0}
        if index in seen or not 0 < index < len(self.types):
            raise ValueError('Invalid or cyclic BTF value type')
        t = self.types[index]
        kind = t['kind']
        if kind in (8, 9, 10, 11, 18):
            return self.descriptor(t['size'], seen + (index,))
        if kind == 2:
            # AArch64 target only; pointee ABI is explicitly outside this check.
            return {'kind': 'pointer', 'size': 8}
        if kind == 3:
            element, _, count = struct.unpack('<III', t['payload'])
            value = self.descriptor(element, seen + (index,))
            return {'kind': 'array', 'size': value['size'] * count,
                    'count': count, 'element': value}
        if kind in (1, 4, 5, 6, 16, 19):
            return {'kind': kind, 'name': t['name'], 'size': t['size']}
        return {'kind': kind, 'name': t['name'], 'size': None}

    def layouts(self, name):
        result = []
        for t in self.types[1:]:
            if t['kind'] not in (4, 5) or t['name'] != name:
                continue
            members = []
            for pos in range(0, len(t['payload']), 12):
                n, typ, offset = struct.unpack_from('<III', t['payload'], pos)
                members.append({'name': self.string(n),
                                'bit_offset': offset & 0xffffff if t['flag'] else offset,
                                'bitfield_size': offset >> 24 if t['flag'] else 0,
                                'type': self.descriptor(typ)})
            layout = {'kind': t['kind'], 'size': t['size'], 'members': members}
            if layout not in result:
                result.append(layout)
        return result


class RecordedLayouts:
    """Selected stock metadata; never substitutes for a base BTF binary."""
    def __init__(self, data):
        if data.get('pointer_size') != 8 or not data.get('types'):
            raise ValueError('AArch64 stock layout metadata required')
        self.sha256 = data['source_btf_sha256']
        self.types = data['types']

    def layouts(self, name):
        return self.types.get(name, [])


def compare(stock, candidate, names):
    result = {'status': 'SELECTED_LAYOUTS_MATCH_ONLY', 'types': {},
              'stock_btf_sha256': stock.sha256, 'candidate_btf_sha256': candidate.sha256,
              'limitations': 'Selected direct members and value sizes only. Anonymous nested '
                             'types and pointer targets are not expanded. No function prototype, '
                             'KCFI, runtime, firmware or AirDrop compatibility validation.'}
    for name in names:
        a, b = stock.layouts(name), candidate.layouts(name)
        state = 'MISSING_OR_AMBIGUOUS' if len(a) != 1 or len(b) != 1 else (
            'MATCH' if a == b else 'DIFFERENT')
        result['types'][name] = {'status': state, 'stock': a, 'candidate': b}
    states = {entry['status'] for entry in result['types'].values()}
    if 'DIFFERENT' in states:
        result['status'] = 'REJECT_SELECTED_LAYOUT_DIFFERENCE'
    elif 'MISSING_OR_AMBIGUOUS' in states or not names:
        result['status'] = 'INCOMPLETE'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--stock-json', action='store_true', help='Use recorded stock layout metadata')
    p.add_argument('--types', nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    stock = (RecordedLayouts(json.loads(args.stock.read_text())) if args.stock_json
             else Btf(args.stock.read_bytes()))
    result = compare(stock, Btf(args.candidate.read_bytes()), args.types)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    for name, entry in result['types'].items():
        print(name, entry['status'])
    return 0 if result['status'] == 'SELECTED_LAYOUTS_MATCH_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
