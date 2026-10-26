#!/usr/bin/env python3
"""Offline firmware structure and stock stub evidence; never certifies AWDL.

No firmware execution, extraction of partitions, external disassembler or compiler.
ELF magic inside payloads is only accepted after bounds and header validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from module_exports import load
from module_abi import inspect


def firmware_elf(data, base):
    if data[base:base + 7] != b'\x7fELF\x01\x01\x01' or base + 52 > len(data):
        raise ValueError('Not a complete little-endian ELF32 header')
    fields = struct.unpack_from('<HHIIIIIHHHHHH', data, base + 16)
    kind, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, shstr = fields
    if kind not in (2, 3) or version != 1 or ehsize != 52 or phsize != 32 or not 0 < phnum <= 256:
        raise ValueError('Unsupported ELF32 program header layout')
    if phoff < ehsize or base + phoff + phnum * phsize > len(data):
        raise ValueError('Truncated program header table')
    segments = []
    for i in range(phnum):
        typ, offset, va, pa, size, memsize, perms, align = struct.unpack_from('<IIIIIIII', data, base + phoff + i * phsize)
        if size and base + offset + size > len(data):
            raise ValueError('Segment exceeds file bounds')
        if typ == 1 and size > memsize:
            raise ValueError('LOAD file size exceeds memory size')
        segments.append({'type': typ, 'file_offset': offset, 'virtual_address': va,
                         'file_size': size, 'memory_size': memsize, 'flags': perms})
    if not any(s['type'] == 1 for s in segments):
        raise ValueError('No LOAD segments')
    return {'offset': base, 'machine': machine, 'machine_name': {40: 'ARM', 164: 'QDSP6'}.get(machine, 'OTHER'),
            'entry': entry, 'section_count': shnum, 'program_headers': segments}


def firmware_info(data):
    images, rejected = [], []
    start = 0
    while True:
        pos = data.find(b'\x7fELF', start)
        if pos < 0:
            break
        start = pos + 4
        try:
            images.append(firmware_elf(data, pos))
        except (ValueError, struct.error) as error:
            rejected.append({'offset': pos, 'reason': str(error)})
    if not images or images[0]['offset'] != 0:
        raise ValueError('No valid ELF image at file start')
    versions = []
    for match in re.finditer(rb'[\x20-\x7e]{6,}', data):
        if match[0].startswith((b'QC_IMAGE_VERSION_STRING=', b'IMAGE_VARIANT_STRING=')):
            versions.append({'offset': match.start(), 'text': match[0].decode('ascii')})
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'elf_images': images,
            'rejected_magic': rejected, 'version_strings': versions,
            'active_image_confirmed': False, 'passthru_support': 'UNVERIFIED'}


def module_functions(path):
    inspect(path)  # Require a little-endian AArch64 relocatable module.
    data, sections = load(path)
    table = next(s for s in sections if s['type'] == 2)
    strings = sections[table['link']]
    names = data[strings['off']:strings['off'] + strings['size']]
    if table['size'] % 24:
        raise ValueError('Invalid ELF64 symbol table size')
    found = []
    for pos in range(table['off'], table['off'] + table['size'], 24):
        name, info, other, index, value, size = struct.unpack_from('<IBBHQQ', data, pos)
        label = names[name:names.index(b'\0', name)].decode('utf-8', 'replace')
        if info & 15 != 2 or not re.search('wonder|passthru|passthrough|awdl', label, re.I):
            continue
        if not 0 < index < len(sections):
            continue
        sec = sections[index]
        if sec['type'] == 8 or value + size > sec['size']:
            raise ValueError('Function outside file-backed section')
        code = data[sec['off'] + value:sec['off'] + value + size]
        interpretation = 'REQUIRES_DISASSEMBLY'
        if code == bytes.fromhex('c0035fd6'):
            interpretation = 'AARCH64_RET_ONLY'
        elif code == bytes.fromhex('e00302aac0035fd6'):
            interpretation = 'AARCH64_MOV_X0_X2_RET_ONLY'
        found.append({'name': label, 'section': sec['name'], 'section_offset': value,
                      'file_offset': sec['off'] + value, 'bytes': size,
                      'code_hex': code.hex() if size <= 32 else None,
                      'interpretation': interpretation})
    return {'sha256': hashlib.sha256(data).hexdigest(), 'related_functions': found,
            'limitations': 'Exact bodies only: ret and argument-return helpers do not implement transmit themselves. This does not prove firmware support or absence of another path.'}


def audit(directory):
    root = Path(directory)
    firmware, modules = [], []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if path.name.endswith('.bin'):
            item = firmware_info(path.read_bytes())
            item['file'] = path.name
            firmware.append(item)
        elif path.name.endswith('.ko'):
            item = module_functions(path)
            item['file'] = path.name
            modules.append(item)
    if not firmware or not modules:
        raise ValueError('Require firmware candidates and stock WLAN module')
    return {'status': 'OFFLINE_STRUCTURE_AND_STUB_EVIDENCE_ONLY', 'firmware': firmware, 'modules': modules,
            'radio_usable': None, 'firmware_passthru_support': 'UNVERIFIED',
            'limitations': 'No commands sent to target firmware. Candidate names, embedded ELFs, strings and host stubs do not establish active firmware or vdev type 0x9 support.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
