#!/usr/bin/env python3
"""Offline popsicle module evidence audit. Never loads or patches a module.

Reconstructed checkpoint tool; not a byte-for-byte recovery of the lost script.
Use actual export tables, never imported CRC expectations as Module.symvers.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

from module_abi import inspect, symvers
from module_exports import exports


def audit(stock, dependencies, kernel_symvers, candidate=None):
    original = inspect(stock)
    if original['modinfo'].get('name') != ['qca_cld3_peach_v2']:
        raise ValueError('Stock input is not qca_cld3_peach_v2')
    if not original['versions']:
        raise ValueError('Stock input has no module version evidence')
    available = symvers(kernel_symvers)
    conflicts = {}
    for path in dependencies:
        dependency = inspect(path)
        if dependency['modinfo'].get('vermagic') != original['modinfo'].get('vermagic'):
            raise ValueError(f'Dependency vermagic differs: {Path(path).name}')
        for name, crc in exports(path).items():
            if name in available and available[name] != crc:
                conflicts[name] = {'first': available[name], 'other': crc}
            else:
                available[name] = crc

    def coverage(module):
        versions = module['versions']
        return {
            'records': len(versions),
            'matched': sum(available.get(name) == crc for name, crc in versions.items()),
            'mismatches': {name: {'required': crc, 'exported': available[name]}
                           for name, crc in versions.items()
                           if name in available and available[name] != crc},
            'missing': sorted(set(versions) - available.keys()),
            'undefined_without_version': sorted(set(module['undefined']) - versions.keys()),
        }

    result = {
        'status': 'ABI_EVIDENCE_ONLY',
        'stock_sha256': original['sha256'],
        'stock_vermagic': original['modinfo'].get('vermagic'),
        'stock': coverage(original),
        'export_conflicts': conflicts,
        'limitations': 'No proof of structure layout, KCFI, protected-symbol access, '
                      'firmware support, radio operation or AirDrop transfer.',
    }
    if candidate:
        built = inspect(candidate)
        identity = {key: {'stock': original['modinfo'].get(key),
                          'candidate': built['modinfo'].get(key)}
                    for key in ('name', 'vermagic')
                    if original['modinfo'].get(key) != built['modinfo'].get(key)}
        result['candidate'] = coverage(built)
        result['candidate_sha256'] = built['sha256']
        result['identity_mismatches'] = identity
        result['candidate_import_delta'] = {
            'added': sorted(built['versions'].keys() - original['versions'].keys()),
            'removed': sorted(original['versions'].keys() - built['versions'].keys()),
        }
        if identity or result['candidate']['mismatches'] or not built['versions']:
            result['status'] = 'REJECT'
    if conflicts or result['stock']['mismatches']:
        result['status'] = 'REJECT'
    elif result['status'] != 'REJECT' and (
        result['stock']['missing'] or result['stock']['undefined_without_version'] or
        (candidate and (result['candidate']['missing'] or
                        result['candidate']['undefined_without_version']))
    ):
        result['status'] = 'INCOMPLETE'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--dependency', type=Path, action='append', default=[])
    parser.add_argument('--kernel-symvers', type=Path, action='append', required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = audit(args.stock, args.dependency, args.kernel_symvers, args.candidate)
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        args.out.write_text(serialized)
    else:
        print(serialized, end='')
    return {'REJECT': 1, 'INCOMPLETE': 2}.get(result['status'], 0)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, struct.error, StopIteration) as error:
        print(f'error: {error}', file=sys.stderr)
        sys.exit(3)
