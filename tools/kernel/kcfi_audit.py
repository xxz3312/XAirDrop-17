#!/usr/bin/env python3
"""Read-only comparison of actual ELF absolute __kcfi_typeid_* symbols.

Matching a type hash is limited evidence, not a prototype reconstruction.
Internal callback changes between driver revisions need source-level review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from module_abi import inspect
from module_exports import load


def type_ids(path):
    module = inspect(path)  # Require ELF64 little-endian AArch64 ET_REL.
    data, sections = load(path)
    table = next(s for s in sections if s['type'] == 2)
    strings = sections[table['link']]
    names = data[strings['off']:strings['off'] + strings['size']]
    result = {}
    prefix = '__kcfi_typeid_'
    if table['size'] % 24:
        raise ValueError('Truncated ELF symbol records')
    for pos in range(table['off'], table['off'] + table['size'], 24):
        name, info, _, index, value, _ = struct.unpack_from('<IBBHQQ', data, pos)
        if not 0 <= name < len(names):
            raise ValueError('Invalid ELF symbol name')
        label = names[name:names.index(b'\0', name)].decode('utf-8')
        if not label.startswith(prefix):
            continue
        # Absolute weak/global symbols encode an actual compiler type hash.
        if index != 0xfff1 or info >> 4 not in (1, 2) or value > 0xffffffff:
            raise ValueError(f'Unsupported KCFI symbol encoding: {label}')
        label = label[len(prefix):]
        if not label or label in result:
            raise ValueError('Empty or duplicate KCFI function name')
        result[label] = f'0x{value:08x}'
    return {'module_sha256': module['sha256'], 'type_ids': dict(sorted(result.items()))}


def compare(stock, candidate):
    a, b = stock['type_ids'], candidate['type_ids']
    common = sorted(a.keys() & b.keys())
    differences = {n: {'stock': a[n], 'candidate': b[n]} for n in common if a[n] != b[n]}
    return {'status': 'INCOMPLETE' if not common else (
                'REVIEW_TYPE_ID_DIFFERENCES' if differences else 'COMMON_TYPE_IDS_MATCH_ONLY'),
            'stock_module_sha256': stock['module_sha256'],
            'candidate_module_sha256': candidate['module_sha256'],
            'stock_type_ids': len(a), 'candidate_type_ids': len(b),
            'common_type_ids': len(common), 'matching_type_ids': len(common) - len(differences),
            'differences': differences, 'stock_only': sorted(a.keys() - b.keys()),
            'candidate_only': sorted(b.keys() - a.keys()),
            'limitations': 'Absolute compiler type hashes only. Does not reconstruct C '
                            'prototypes or prove internal call-site consistency, external '
                            'callback compatibility, absence of hash collisions, runtime '
                            'loading or firmware/AirDrop operation. A changed private '
                            'callback hash alone is not proof of a cross-module ABI failure.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--stock-json', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stock = json.loads(args.stock.read_text()) if args.stock_json else type_ids(args.stock)
    result = compare(stock, type_ids(args.candidate))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    print(f"Common type IDs: {result['common_type_ids']}; matched: {result['matching_type_ids']}")
    print(json.dumps(result['differences'], indent=2))
    return 0 if result['status'] == 'COMMON_TYPE_IDS_MATCH_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
