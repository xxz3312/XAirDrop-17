#!/usr/bin/env python3
"""Strict modpost inputs and limited module header checks; no ABI certification."""
import ast
import hashlib
import json
from pathlib import Path
import struct

from module_abi import inspect, symvers
from module_exports import load

CORE_SYMVERS_SHA256 = '3484f2352f7bddb2f335b800b1d83a776f7dfd817d45f1261cadb794e9355530'
MODULES_BZL_SHA256 = '689ade794c7b3ac4cf0787ba74bfc3ced21814d35d775c02e435d4f2d715d584'


def protected_modules(source):
    # Literal lists only, never execute Starlark as Python. The pinned hash
    # guards the exact BUILD.bazel/get_gki_protected_modules_list semantics.
    data = Path(source).read_bytes()
    if hashlib.sha256(data).hexdigest() != MODULES_BZL_SHA256:
        raise ValueError('Unreviewed GKI protected-module list source')
    constants = {}
    for node in ast.parse(data.decode()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    selected = []
    for key in ['_COMMON_GKI_MODULES_LIST', '_ARM64_GKI_MODULES_LIST',
                '_KUNIT_FRAMEWORK_MODULES', '_KUNIT_COMMON_MODULES_LIST', '_KUNIT_CLK_MODULES_LIST']:
        selected.extend(constants[key])
    excluded = constants['_COMMON_UNPROTECTED_MODULES_LIST']
    return sorted(name.removesuffix('.ko') for name in selected if name not in excluded)


def write_inputs(common, out, core, vendor_json, destination):
    if hashlib.sha256(Path(core).read_bytes()).hexdigest() != CORE_SYMVERS_SHA256:
        raise ValueError('Official core symvers checksum mismatch')
    known = symvers([core])
    data = json.loads(Path(vendor_json).read_text())
    lines = []
    for module in data['modules']:
        for name, record in sorted(module['exports'].items()):
            if name in known:
                raise ValueError(f'Duplicate export provider: {name}')
            if record['export_type'] not in ['EXPORT_SYMBOL', 'EXPORT_SYMBOL_GPL']:
                raise ValueError('Unknown export license category')
            fields = [record['crc'], name, module['name'], record['export_type'], record['namespace']]
            if any('\t' in field or '\n' in field for field in fields):
                raise ValueError('Malformed real export field')
            lines.append('\t'.join(fields) + '\n')
            known[name] = record['crc']
    Path(destination).write_text(''.join(lines))
    # These are actual official core exports, not reconstructed import CRCs.
    (Path(out) / 'Module.symvers').write_bytes(Path(core).read_bytes())
    names = protected_modules(Path(common) / 'modules.bzl')
    (Path(out) / 'protected_module_names_list').write_text('\n'.join(names) + '\n')
    return known


def header_layout(path):
    inspect(path)  # Validate the ELF architecture and basic section bounds.
    data, sections = load(path)
    target = next(s for s in sections if s['name'] == '.gnu.linkonce.this_module')
    symbols = next(s for s in sections if s['type'] == 2)
    strings = sections[symbols['link']]
    names = data[strings['off']:strings['off'] + strings['size']]
    result = {'section_size': target['size'], 'init_offset': None, 'exit_offset': None}
    for relocation in sections:
        if relocation['type'] != 4 or relocation['info'] != target['idx']:
            continue
        for offset in range(0, relocation['size'], 24):
            location, info, _ = struct.unpack_from('<QQq', data, relocation['off'] + offset)
            name_offset, = struct.unpack_from('<I', data, symbols['off'] + (info >> 32) * 24)
            name = names[name_offset:names.index(b'\0', name_offset)].decode()
            if name in ['init_module', 'cleanup_module']:
                if info & 0xffffffff != 257:
                    raise ValueError('Unexpected module entry relocation type')
                result['init_offset' if name == 'init_module' else 'exit_offset'] = location
    if result['init_offset'] is None:
        raise ValueError('No module init relocation')
    return result


def merge_generated_exports(known, generated):
    # The loader rejects duplicate providers even when their CRCs agree.
    duplicate = sorted(known.keys() & generated.keys())
    if duplicate:
        raise ValueError('Duplicate generated export provider: ' + ', '.join(duplicate))
    known.update(generated)


def stock_loader_evidence(expected):
    reference = expected.get('loader_evidence')
    if not reference:
        return None
    root = Path(__file__).resolve().parents[2]
    path = (root / reference['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Loader evidence must be a repository file')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('Stock loader evidence checksum mismatch')
    data = json.loads(raw)
    if (data['firmware'] != expected['firmware'] or
            data['rule'] != 'basic_versions_ignore_release_prefix' or
            data['caller_uses_basic_versions'] is not True):
        raise ValueError('Unsupported or mismatched stock loader evidence')
    return data


def module_report(path, expected, available):
    module = inspect(path)
    layout = header_layout(path)
    bad = {name: {'recorded': crc, 'provider': available.get(name)}
           for name, crc in module['versions'].items() if available.get(name) != crc}
    unversioned = sorted(set(module['undefined']) - module['versions'].keys())
    _, sections = load(path)
    magic = module['modinfo'].get('vermagic', [])
    exact_magic = magic == [expected['vermagic']]
    basic_crcs = any(s['name'] == '__versions' and s['size'] for s in sections)
    # Reference ACK kernel/module/version.c:same_magic ignores the release
    # prefix only if the basic __versions section exists. Do not rewrite it.
    loader_magic = exact_magic or (basic_crcs and len(magic) == 1 and ' ' in magic[0]
                                   and ' ' in expected['vermagic']
                                   and magic[0].partition(' ')[2] == expected['vermagic'].partition(' ')[2])
    evidence = stock_loader_evidence(expected)
    target_magic = evidence['target_vermagic'] if evidence else None
    stock_match = bool(evidence and len(magic) == 1 and (
        magic[0] == target_magic or (basic_crcs and ' ' in magic[0] and ' ' in target_magic
                                    and magic[0].partition(' ')[2] == target_magic.partition(' ')[2])))
    verdict = (bool(module['versions']) and not bad and not unversioned
               and layout == expected['layout'] and (stock_match if evidence else loader_magic))
    status = 'REJECT' if not verdict else ('RECORDS_AND_HEADER_MATCH_ONLY' if exact_magic
                                           else 'REVIEW_KERNEL_RELEASE')
    if evidence and not stock_match:
        status = 'REJECT'
    elif verdict and stock_match:
        status = 'RECORDED_LOADER_CHECKS_MATCH_ONLY'
    return {'status': status,
            'sha256': module['sha256'], 'version_records': len(module['versions']),
            'version_record_mismatches': bad, 'layout': layout,
            'undefined_without_version': unversioned,
            'vermagic': module['modinfo'].get('vermagic'),
            'vermagic_exact_match': exact_magic,
            'vermagic_reference_loader_match': bool(loader_magic),
            'vermagic_stock_loader_match': stock_match,
            'stock_loader_kernel_sha256': evidence['kernel_sha256'] if evidence else None,
            'btf_present': any(s['name'] == '.BTF' for s in sections),
            'limitations': 'Modpost copies provider CRCs into imports; matching records do not '
                          'independently validate C declarations, private types, KCFI, full structure '
                          'layout, GKI access, firmware, loading or AirDrop operation.'}
