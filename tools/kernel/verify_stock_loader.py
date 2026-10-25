#!/usr/bin/env python3
"""Recheck recorded, manually reviewed loader bytes against the uploaded boot.

This verifies provenance and byte ranges, not arbitrary kernel semantics.
No image or module is modified. This is not a module loading test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from popsicle_modpost import stock_loader_evidence


def verify(boot, expected):
    evidence = stock_loader_evidence(expected)
    if evidence is None:
        raise ValueError('No reviewed loader evidence')
    raw = Path(boot).read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence['boot_sha256']:
        raise ValueError('Boot image does not match the audited capture')
    if raw[:8] != b'ANDROID!' or struct.unpack_from('<I', raw, 40)[0] != 4:
        raise ValueError('Expected Android boot header v4')
    size = struct.unpack_from('<I', raw, 8)[0]
    kernel = raw[4096:4096 + size]
    if hashlib.sha256(kernel).hexdigest() != evidence['kernel_sha256']:
        raise ValueError('Kernel checksum mismatch')
    for name, region in evidence['regions'].items():
        offset = int(region['file_offset'], 16)
        data = kernel[offset:offset + region['size']]
        if (data.hex() != region['bytes_hex'] or
                hashlib.sha256(data).hexdigest() != region['sha256']):
            raise ValueError(f'Reviewed loader region mismatch: {name}')
    offset = int(evidence['delimiter_file_offset'], 16)
    if kernel[offset:offset + 2].hex() != evidence['delimiter_hex']:
        raise ValueError('Vermagic delimiter mismatch')
    offset = int(evidence['kernel_vermagic_file_offset'], 16)
    if kernel[offset:].split(b'\0', 1)[0].decode() != evidence['target_vermagic']:
        raise ValueError('Target kernel vermagic mismatch')
    return {'status': 'RECORDED_STOCK_CODE_BYTES_VERIFIED',
            'kernel_sha256': evidence['kernel_sha256'],
            'limitations': evidence['limitations']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('boot', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    expected = json.loads((root / 'kernel/abi/popsicle-stock-module-header.json').read_text())
    print(json.dumps(verify(args.boot, expected), indent=2))
