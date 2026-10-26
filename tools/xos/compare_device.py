#!/usr/bin/env python3
"""Compare reference imports with captured device exports; no ELF is executed.

This reports candidate symbol coverage, not the Android linker's actual load scope.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROW = re.compile(r'^\s*\d+:\s+\S+\s+\d+\s+.+?\s+(GLOBAL|WEAK|LOCAL)\s+(DEFAULT|PROTECTED|HIDDEN|INTERNAL)\s+(\S+)\s+(\S+)', re.M)


def symbol_sets(text):
    strong, weak, exports = set(), set(), set()
    for bind, vis, ndx, name in ROW.findall(text):
        if ndx == 'UND':
            if bind in ('GLOBAL', 'WEAK'):
                (weak if bind == 'WEAK' else strong).add(name.replace('@@', '@'))
        elif bind in ('GLOBAL', 'WEAK') and vis in ('DEFAULT', 'PROTECTED'):
            exports.add(name.replace('@@', '@'))
            # Only a default version (or an unversioned definition) supplies a bare name.
            if '@@' in name or '@' not in name:
                exports.add(name.split('@')[0])
    return strong, weak, exports


def inspect(path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x02\x01' or len(data) < 20 or data[18:20] != b'\xb7\x00':
        raise ValueError('Expected AArch64 ELF64: ' + str(path))
    def readelf(*args):
        return subprocess.check_output(['readelf', '-W', *args, str(path)], text=True, env={'LC_ALL': 'C'})
    strong, weak, exports = symbol_sets(readelf('--dyn-syms'))
    needed = re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', readelf('-d'))
    return dict(sha256=hashlib.sha256(data).hexdigest(), needed=needed,
                strong=strong, weak=weak, exports=exports,
                soname=re.findall(r'\(SONAME\).*?\[([^\]]+)\]', readelf('-d')))


def compare(reference, device):
    from audit_reference import PROFILE
    profile = json.loads(PROFILE.read_text())
    refs = {}
    for name, expected in profile['entries'].items():
        path = reference / Path(name).name
        info = inspect(path)
        if info['sha256'] != expected:
            raise ValueError('Reference fingerprint mismatch: ' + name)
        refs[path.name] = info
    # Explicit candidate scope: reference directory, then captured system/lib64.
    # Never silently choose a vendor or product ABI to fill a missing system symbol.
    system = {p.name: inspect(p) for p in sorted((device / 'libs/system/lib64').glob('*.so'))}
    # Explicitly capture the loader's exports when ld-android.so is its SONAME.
    loader = None
    for relative in ('libs/apex/com.android.runtime/bin/linker64', 'libs/system/bin/linker64'):
        path = device / relative
        if path.is_file():
            info = inspect(path)
            if info['soname'] == ['ld-android.so']:
                loader = info
                system.setdefault('ld-android.so', info)
                break
    candidates = {**system, **refs}
    providers = {}
    for name, info in candidates.items():
        for symbol in info['exports']:
            providers.setdefault(symbol, []).append(name)
    results = {}
    for name, info in refs.items():
        results[name] = {
            'strong_import_count': len(info['strong']),
            'missing_strong_imports': sorted(info['strong'] - providers.keys()),
            'unresolved_weak_imports': sorted(info['weak'] - providers.keys()),
            'needed_not_captured': sorted(set(info['needed']) - candidates.keys()),
        }
    # Walk all available dependencies from both startup and dlopen roots.
    missing, visited = set(), set()
    pending = list(refs)
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        if name not in candidates:
            missing.add(name)
        else:
            pending.extend(candidates[name]['needed'])
    symbols_ok = all(not r['missing_strong_imports'] for r in results.values())
    return {
        'status': 'REFERENCE_IMPORT_CANDIDATES_COVERED_CLOSURE_INCOMPLETE' if symbols_ok and missing else
                  'REFERENCE_IMPORT_CANDIDATES_COVERED_RUNTIME_UNTESTED' if symbols_ok else 'REFERENCE_IMPORT_CANDIDATES_MISSING',
        'reference_results': results,
        'loader_captured_with_ld_android_soname': loader is not None,
        'transitive_dependencies_not_captured': sorted(missing),
        'device_system_library_sha256': {name: info['sha256'] for name, info in system.items()},
        'candidate_scope': 'Pinned four reference ELF files plus captured /system/lib64 files. Versioned symbols must match; IFUNC definitions included. Product/vendor candidates excluded.',
        'limitations': 'Candidate symbol coverage only; no actual linker resolution/order or dependency symbol closure proof. No constructors, service or radio code executed. Binder/VINTF/SELinux and runtime behavior remain untested.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-dir', type=Path, required=True)
    p.add_argument('--device-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    report = compare(a.reference_dir, a.device_dir)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
    print('Missing captured dependencies: ' + ', '.join(report['transitive_dependencies_not_captured']))


if __name__ == '__main__':
    main()
