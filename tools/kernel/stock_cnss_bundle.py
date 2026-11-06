#!/usr/bin/env python3
"""Package the accepted 0133 raw WLAN/provider only; never load or rewrite ELF."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import zipfile

from module_abi import inspect
from module_exports import export_records
from popsicle_pair_bundle import note_hash
from stock_cnss_audit import audit

ROOT = Path(__file__).resolve().parents[2]
NAMES = {'wlan': 'qca_cld3_peach_v2', 'opairshare_wonder_provider': 'opairshare_wonder_provider'}
SCRIPTS = ['popsicle-stock-cnssctl.sh', 'popsicle-stock-cnss-io.sh',
           'popsicle-stock-cnss-engine.sh']


def write_integrity(bundle):
    # KernelSU removes customize.sh after installation. Verify it during
    # installation, but never require this transient script at runtime.
    if not (bundle / 'customize.sh').is_file():
        raise ValueError('Installation script missing before packaging')
    if any((bundle / name).exists() for name in ['SHA256SUMS', 'INSTALL_SHA256SUMS']):
        raise ValueError('Integrity files already exist')
    runtime = sorted(p for p in bundle.rglob('*') if p.is_file() and p.name != 'customize.sh')
    (bundle / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(bundle)) + '\n' for p in runtime))
    install = sorted(p for p in bundle.rglob('*') if p.is_file())
    (bundle / 'INSTALL_SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(bundle)) + '\n' for p in install))


def checker_update(package, output, baseline=None):
    baseline = baseline or json.loads((ROOT / 'kernel/abi/popsicle-stock-cnss-checker-base-0136.json').read_text())
    if baseline['bundle_sha256'] != '2a07638505b70bfaf2f8eba3bdce33185dc5ea61f2d34a4e0024fd34fa1e6ade':
        raise ValueError('Unknown original 0136 bundle')
    if output.exists():
        raise ValueError('Update output exists')
    allowed = {'module.prop', 'CHECK_FIRST.txt'}
    with zipfile.ZipFile(package) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or any(Path(n).is_absolute() or '..' in Path(n).parts for n in names):
            raise ValueError('Invalid package members')
        lines = source.read('SHA256SUMS').decode().splitlines()
        current = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in lines}
        expected = set(baseline['files']) - {'customize.sh'}
        if (len(current) != len(lines) or set(current) != expected
                or set(current) != set(names) - {'customize.sh', 'INSTALL_SHA256SUMS', 'SHA256SUMS'}):
            raise ValueError('Unexpected runtime manifest scope')
        if any(current[n] != baseline['files'][n] for n in expected - allowed):
            raise ValueError('A retained module/script changed; no checker-only update allowed')
        for name, digest in current.items():
            value = hashlib.sha256()
            with source.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(chunk)
            if value.hexdigest() != digest:
                raise ValueError('Package checksum mismatch: ' + name)
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as target:
            for name in sorted(allowed | {'SHA256SUMS'}):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                target.writestr(info, source.read(name))
    return {'sha256': sha(output), 'bytes': output.stat().st_size,
            'files': sorted(allowed | {'SHA256SUMS'}), 'retained_modules_and_scripts_changed': False}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def evidence():
    result = json.loads((ROOT / 'docs/research/popsicle-stock-cnss-0135-validation.json').read_text())
    required = {'workflow_run': 42271965465, 'required_jobs_success': 7,
                'build_source_commit': '93d2ea7571c723159dff83253003e427fd5677b9',
                'actual_wlan_cnss2_import_count': 64, 'actual_wlan_versions_count': 590,
                'actual_wlan_checked_or_live_arm_imports': [], 'actual_wlan_cnss2_crc_mismatches': {},
                'all_5_actual_ELF_SHA_and_version_counts_verified': True,
                'phone_executed': False, 'runtime_certified': False}
    if any(type(result.get(key)) is not type(value) or result[key] != value
           for key, value in required.items()):
        raise ValueError('Requires the exact independently accepted stock-CNSS2 checkpoint')
    return result


def verified_inputs(modules, accepted):
    result = {}
    for role, name in NAMES.items():
        path = modules / (name + '.ko')
        if path.is_symlink() or not path.is_file():
            raise ValueError('Expected raw regular module: ' + name)
        record = accepted['actual_module_records'][role]
        if sha(path) != record['sha256']:
            raise ValueError('Accepted raw ELF changed: ' + name)
        module = inspect(path)
        if (module['modinfo'].get('name') != [name] or note_hash(path) != record['note_sha256']
                or len(module['versions']) != record['version_records']
                or set(module['undefined']) - module['versions'].keys()):
            raise ValueError('Module identity or version coverage differs: ' + name)
        result[role] = {'path': path, 'module': module, 'record': record}
    stock = json.loads((ROOT / 'kernel/abi/popsicle-stock-exports.json').read_text())
    wlan = result['wlan']['module']
    gate = audit(wlan, stock)
    if gate['status'] != 'STOCK_CNSS2_IMPORTS_MATCH_ONLY' or len(gate['cnss2_imports']) != 64:
        raise ValueError('Stock CNSS2 import gate failed')
    exports = export_records(result['opairshare_wonder_provider']['path'])
    private = sorted(set(wlan['undefined']) & exports.keys())
    if private != accepted['actual_private_provider_import_CRCs_match']['qca_cld3_peach_v2']:
        raise ValueError('Private provider dependency changed')
    if any(wlan['versions'][name] != exports[name]['crc'] for name in private):
        raise ValueError('Private provider CRC mismatch')
    return result, gate


def extract_accepted(artifact, target, accepted):
    if sha(artifact) != accepted['full_artifact_sha256']:
        raise ValueError('Unexpected full artifact digest')
    wanted = {name + '.ko' for name in NAMES.values()}
    found = set()
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        entry = 'diagnostic-modules-not-for-install.tar.gz'
        if names.count(entry) != 1:
            raise ValueError('Missing or duplicate nested module archive')
        with archive.open(entry) as nested, tarfile.open(fileobj=nested, mode='r|gz') as modules:
            for member in modules:
                if member.name not in wanted:
                    continue
                if not member.isfile() or member.name in found:
                    raise ValueError('Invalid/duplicate module member')
                with (target / member.name).open('wb') as stream:
                    shutil.copyfileobj(modules.extractfile(member), stream)
                found.add(member.name)
    if found != wanted:
        raise ValueError('Accepted module is missing')


def build(modules, output, accepted=None):
    accepted = accepted or evidence()
    checked, gate = verified_inputs(modules, accepted)
    policy = json.loads((ROOT / 'kernel/abi/popsicle-pair-deployment.json').read_text())
    loader = ROOT / 'kernel/abi/popsicle-stock-loader.json'
    loader_record = json.loads(loader.read_text())
    if (sha(loader) != policy['loader_evidence_sha256']
            or loader_record['kernel_sha256'] != policy['loader_kernel_sha256']
            or loader_record['boot_sha256'] != policy['boot_sha256']):
        raise ValueError('Stock loader evidence changed')
    if output.exists():
        raise ValueError('Output already exists; no replacement')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        bundle = Path(temporary) / 'bundle'
        (bundle / 'kernel').mkdir(parents=True)
        values = {'schema': '2', 'profile': 'stock-cnss-manual', 'mode': 'diagnostic-defaults',
                  'device': policy['device'], 'firmware': policy['firmware'],
                  'kernel': policy['kernel_release'], 'boot_sha256': policy['boot_sha256'],
                  'runtime_certified': 'false', 'source_commit': accepted['build_source_commit']}
        for role, name in NAMES.items():
            source = checked[role]
            staged = bundle / 'kernel' / (name + '.ko')
            shutil.copyfile(source['path'], staged)
            if sha(staged) != source['record']['sha256']:
                raise ValueError('ELF changed during copy')
            for field in ['sha256', 'note_sha256']:
                values['candidate.' + name + '.' + field] = source['record'][field]
        for name, record in policy['stock'].items():
            for field in ['sha256', 'note_sha256']:
                values['stock.' + name + '.' + field] = record[field]
        for name in SCRIPTS:
            shutil.copyfile(ROOT / 'tools/device' / name, bundle / name)
        for name in ['action.sh', 'service.sh', 'customize.sh', 'module.prop', 'skip_mount']:
            shutil.copyfile(ROOT / 'tools/device/stock-cnss-ksu' / name, bundle / name)
        shutil.copyfile(ROOT / 'LICENSE', bundle / 'LICENSE')
        (bundle / 'deployment.tsv').write_text(''.join(key + '\t' + values[key] + '\n' for key in sorted(values)))
        (bundle / 'acceptance.json').write_text(json.dumps(accepted, indent=2) + '\n')
        (bundle / 'stock-cnss-imports.json').write_text(json.dumps(gate, indent=2) + '\n')
        (bundle / 'CHECK_FIRST.txt').write_text(
            'Experimental 0137 WLAN/provider diagnostic trial; stock CNSS2 retained.\n'
            'Not an Apple discovery/file transfer release; no RF activation parameters.\n'
            'Install/boot never starts the trial. Do not press Action before reviewing check.\n'
            'Termux root: /system/bin/sh /data/adb/modules/xairdrop17_stock_cnss/popsicle-stock-cnssctl.sh check\n'
            'The old pair transaction is preserved and blocks this profile until separately inspected/archived.\n'
            'Action explicitly calls apply once. Interrupted/failed state cannot be replayed.\n'
            'No automatic rollback; disable trial and reboot to recover original drivers.\n'
            'Logs: /data/adb/xairdrop17-stockcnss-logs; transaction: /data/adb/xairdrop17-stockcnss-transaction.\n'
            'Do not mix with the old 0131/0132 checked-pair package.\n')
        write_integrity(bundle)
        archive_path = Path(temporary) / 'package.zip'
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(p for p in bundle.rglob('*') if p.is_file()):
                name = str(path.relative_to(bundle))
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o700 if path.suffix == '.sh' else 0o600
                info.external_attr = (stat.S_IFREG | mode) << 16
                with path.open('rb') as source, archive.open(info, 'w') as destination:
                    shutil.copyfileobj(source, destination, 1024 * 1024)
        shutil.move(archive_path, output)
    return {'bundle_sha256': sha(output), 'bytes': output.stat().st_size,
            'kernel_modules': sorted(name + '.ko' for name in NAMES.values()),
            'stock_cnss2_retained': True, 'autostart': False, 'runtime_certified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--artifact', type=Path)
    inputs.add_argument('--modules', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checker-update', type=Path)
    args = parser.parse_args()
    accepted = evidence()
    if args.artifact:
        with tempfile.TemporaryDirectory() as folder:
            modules = Path(folder)
            extract_accepted(args.artifact, modules, accepted)
            report = build(modules, args.output, accepted)
    else:
        report = build(args.modules, args.output, accepted)
    if args.checker_update:
        report['checker_update'] = checker_update(args.output, args.checker_update)
        args.checker_update.with_suffix('.json').write_text(json.dumps(report['checker_update'], indent=2) + '\n')
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
