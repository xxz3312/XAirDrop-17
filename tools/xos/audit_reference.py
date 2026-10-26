#!/usr/bin/env python3
"""Inspect pinned reference ELF files as data. Never execute or modify them."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

PROFILE = Path(__file__).with_name('profile.json')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def elf_info(path):
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Expected little-endian AArch64 ELF64: ' + path.name)
    def readelf(*args):
        return subprocess.check_output(['readelf', '-W', *args, str(path)], text=True, env={'LC_ALL': 'C'})
    dynamic = readelf('-d')
    headers = readelf('-l')
    symbols = readelf('--dyn-syms')
    return {
        'sha256': sha(data),
        'needed': re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', dynamic),
        'interpreter': re.findall(r'Requesting program interpreter: ([^\]]+)', headers),
        'undefined_symbols': sorted(set(re.findall(r'^\s*\d+:.*?\bUND\s+(\S+)', symbols, re.M))),
        'exported_xos_symbols': sorted(set(re.findall(r'\b(domestic_xoscomm_\w+)\b', symbols))),
    }


def aggregation_words(data):
    offsets = [0x177f0, 0x177f4, 0x17a18, 0x17a1c]
    if len(data) < offsets[-1] + 4:
        raise ValueError('libxos too short for pinned instruction sites')
    return {hex(o): f'{struct.unpack_from("<I", data, o)[0]:08x}' for o in offsets}


def audit(archive, profile):
    if sha(archive.read_bytes()) != profile['archive_sha256']:
        raise ValueError('Reference archive hash mismatch')
    entries = {}
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory() as tmp:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate ZIP entry')
        for name, expected in profile['entries'].items():
            data = z.read(name)
            if sha(data) != expected:
                raise ValueError('Reference entry hash mismatch: ' + name)
            path = Path(tmp) / Path(name).name
            path.write_bytes(data)
            entries[name] = elf_info(path)
        lib = z.read('xos/libxos.so')
        words = aggregation_words(lib)
        if words != profile['aggregation_instruction_words']:
            raise ValueError('Pinned aggregation instructions changed')
        daemon = z.read('xos/DomesticXOsComm')
        if b'libxos.so\x00' not in daemon or b'dlopen\x00' not in daemon:
            raise ValueError('Expected dynamic libxos loading markers missing')
    bundled = {Path(n).name for n in entries}
    needed = sorted({n for info in entries.values() for n in info['needed']} - bundled)
    return {
        'status': 'REFERENCE_STATIC_AUDIT_ONLY_DEVICE_COMPATIBILITY_UNKNOWN',
        'archive_sha256': profile['archive_sha256'], 'entries': entries,
        'external_needed_union': needed, 'dynamic_library': 'libxos.so',
        'aggregation_instruction_words': words,
        'aggregation_error_bypass_already_present': True,
        'binder_evidence': 'Descriptor and three method names agree with the target APK; transaction encoding and runtime compatibility are not validated.',
        'not_validated': ['device symbol versions and linker namespace', 'Binder runtime', 'VINTF registration', 'SELinux access', 'AWDL firmware/backend and radio traffic'],
        'policy': 'No binaries are redistributed or executed. No service, VINTF, SELinux, sysctl or Wi-Fi changes. Do not treat forced aggregation success as driver support.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    report = audit(args.archive, json.loads(PROFILE.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])


if __name__ == '__main__':
    main()
