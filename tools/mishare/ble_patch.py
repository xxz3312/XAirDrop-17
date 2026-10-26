# SPDX-License-Identifier: GPL-3.0-only
"""Exact-input MiShare BLE DEX patch, adapted from Leekin2/XAirDrop patches/build.py.

No availability bypass, network broker, Wi-Fi policy, share sheet or radio changes.
Compilation is run by GitHub Actions. Local assembly only copies verified ZIP entries.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / 'profile.json').read_text())
CLASS = Path('smali/a/u0.smali')
VERSION_OLD = '    const/16 v3, 0x12\n\n    aput-byte v3, v2, v0\n'
VERSION_NEW = VERSION_OLD + '\n    const/16 v3, 0xa\n\n    aput-byte v0, v2, v3\n'
OFFSET_OLD = '    const/4 v5, 0x4\n\n    invoke-static {v3, v1, v2, v5, v4}, Ljava/lang/System;->arraycopy'
OFFSET_NEW = OFFSET_OLD.replace('const/4 v5, 0x4', 'const/16 v5, 0xb')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_apk(path, expected):
    if digest(Path(path).read_bytes()) != expected:
        raise ValueError('Unexpected complete APK hash')
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('Duplicate APK entries')
        for name, sha in PROFILE['shared_entries'].items():
            if digest(archive.read(name)) != sha:
                raise ValueError('Unexpected shared APK entry: ' + name)


def patch_text(text):
    # Refuse duplicates, already patched input and instruction/register drift.
    if text.count(VERSION_OLD) != 1 or text.count(OFFSET_OLD) != 1 or VERSION_NEW in text:
        raise ValueError('BLE instruction anchors do not match unpatched input exactly')
    header = '.method public final declared-synchronized b(Lcom/xiaomi/sharop/service/AirDropService;)V'
    start = text.index(header)
    end = text.index('.end method', start)
    for anchor in [VERSION_OLD, OFFSET_OLD, '    const/4 v0, 0x1',
                   '    const/4 v1, 0x0', '    const/16 v2, 0x14', '    const/16 v3, 0x4c']:
        if anchor not in text[start:end]:
            raise ValueError('BLE method/register semantics changed')
    return text.replace(VERSION_OLD, VERSION_NEW).replace(OFFSET_OLD, OFFSET_NEW)


def normalize_smali(text):
    """Only ignore empty lines and explicitly encoded static default values.

    Smali assembly removes redundant static false/zero/null initializers.
    Never normalize methods, nonzero values or non-static fields.
    """
    result = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith('.field ') and ' static ' in line and ' = ' in line:
            declaration, value = line.rsplit(' = ', 1)
            typ = declaration.rsplit(':', 1)[-1]
            default = ((typ == 'Z' and value == 'false') or
                       (typ in ['I', 'B', 'S', 'C'] and value == '0x0') or
                       (typ == 'J' and value == '0x0L') or
                       ((typ.startswith('L') or typ.startswith('[')) and value == 'null'))
            if default:
                line = declaration
        result.append(line)
    return '\n'.join(result)


def run(*args):
    subprocess.run(list(map(str, args)), check=True)


def build(reference, apktool, work, output):
    verify_apk(reference, PROFILE['public_reference_sha256'])
    if digest(Path(apktool).read_bytes()) != PROFILE['apktool_sha256']:
        raise ValueError('Unexpected apktool hash')
    # Fresh subdirectory only; no force-delete of caller-owned paths.
    work.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    decoded = work / 'decoded'
    run('java', '-jar', apktool, 'd', '--no-res', '-o', decoded, reference)
    originals = {str(p.relative_to(decoded)): digest(p.read_bytes()) for p in decoded.rglob('*.smali')}
    path = decoded / CLASS
    path.write_text(patch_text(path.read_text()))
    expected_classes = {str(p.relative_to(decoded)): digest(normalize_smali(p.read_text()).encode())
                        for p in decoded.rglob('*.smali')}
    changed = [name for name, sha in originals.items() if digest((decoded / name).read_bytes()) != sha]
    if changed != [str(CLASS)]:
        raise ValueError('Unexpected changed smali classes: ' + repr(changed))
    rebuilt = work / 'rebuilt.apk'
    run('java', '-jar', apktool, 'b', '-o', rebuilt, decoded)
    with zipfile.ZipFile(rebuilt) as z:
        dex = z.read('classes.dex')
    # Re-disassemble the compiled result, not just the source text.
    checked = work / 'checked'
    run('java', '-jar', apktool, 'd', '--no-res', '-o', checked, rebuilt)
    result = (checked / CLASS).read_text()
    if result.count(VERSION_NEW) != 1 or result.count(OFFSET_NEW) != 1:
        raise ValueError('Compiled BLE DEX does not contain the expected patch')
    compiled_classes = {str(p.relative_to(checked)): digest(normalize_smali(p.read_text()).encode())
                        for p in checked.rglob('*.smali')}
    if compiled_classes != expected_classes:
        raise ValueError('Compiled classes differ beyond patched BLE instructions and redundant static defaults')
    (output / 'classes.dex').write_bytes(dex)
    report = {'status': 'BUILT_BLE_PATCH_ONLY_NOT_RUNTIME_TESTED',
              'changed_smali_classes': changed, 'patched_dex_sha256': digest(dex),
              'compiled_all_classes_compared': True,
              'normalization_scope': 'Empty lines and redundant static false/zero/null field initializers only.',
              'input_dex_sha256': PROFILE['shared_entries']['classes.dex'],
              'profile': PROFILE,
              'limitations': 'Not a signed installable APK, XOS service, network broker, AWDL driver or functional AirDrop package. Wi-Fi and region logic remain original.'}
    (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')


def assemble(original, payload, destination):
    """Use the user's exact original package; never donor resources/native libs."""
    verify_apk(original, PROFILE['target_apk_sha256'])
    report = json.loads((payload / 'manifest.json').read_text())
    if report['profile'] != PROFILE or report['status'] != 'BUILT_BLE_PATCH_ONLY_NOT_RUNTIME_TESTED':
        raise ValueError('Unexpected patch manifest')
    dex = (payload / 'classes.dex').read_bytes()
    if digest(dex) != report['patched_dex_sha256'] or digest(dex) == PROFILE['shared_entries']['classes.dex']:
        raise ValueError('Unexpected or unchanged patch DEX')
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(destination, 'x') as dst:
        for info in src.infolist():
            dst.writestr(info, dex if info.filename == 'classes.dex' else src.read(info.filename))
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(destination) as dst:
        if set(src.namelist()) != set(dst.namelist()):
            raise ValueError('APK entry set changed')
        for name in src.namelist():
            if name != 'classes.dex' and src.read(name) != dst.read(name):
                raise ValueError('Non-target entry changed: ' + name)
    print('Assembled code payload only; signature is invalid and ZIP alignment unverified. Do not install or mount this output.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    for name in ['reference', 'apktool', 'work', 'output']:
        b.add_argument('--' + name, type=Path, required=True)
    a = sub.add_parser('assemble')
    for name in ['original', 'payload', 'destination']:
        a.add_argument('--' + name, type=Path, required=True)
    args = vars(p.parse_args()); command = args.pop('command')
    (build if command == 'build' else assemble)(**args)
