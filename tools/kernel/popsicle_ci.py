#!/usr/bin/env python3
"""GitHub Actions input setup, diagnostic build and partial CNSS interface audit."""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from module_abi import inspect, symvers
from popsicle_modpost import write_inputs, module_report, merge_generated_exports
from btf_layout import Btf, RecordedLayouts, compare
from module_mac80211_ops import audit as audit_mac80211_ops
from popsicle_backend_audit import audited_inventory

REPO = Path(__file__).resolve().parents[2]


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def checkout(path, source, sparse=None):
    if path.exists():
        head = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if head != source['commit']:
            raise ValueError(f'Unexpected checkout at {path}: {head}')
        return
    run(['git', 'init', '-q', path])
    run(['git', '-C', path, 'remote', 'add', 'origin', source['repository']])
    if sparse:
        run(['git', '-C', path, 'sparse-checkout', 'set', sparse])
    args = ['git', '-C', path, 'fetch', '--depth=1', '--no-tags']
    if sparse:
        args.append('--filter=blob:none')
    run(args + ['origin', source['commit']])
    run(['git', '-C', path, 'checkout', '--detach', 'FETCH_HEAD'])


def download(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + '.partial')
    run(['curl', '--fail', '--location', '--retry', '3', '--retry-all-errors',
         '--connect-timeout', '30', '--max-time', '1200', '--output', partial, url])
    partial.replace(destination)


def tool_archive(path, url):
    marker = path / '.popsicle-source-url'
    if marker.exists():
        if marker.read_text() != url:
            raise ValueError(f'Toolchain cache provenance mismatch: {path}')
        return
    archive = path.parent / (path.name + '.tar.gz')
    download(url, archive)
    path.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        source.extractall(path, filter='data')
    marker.write_text(url)
    archive.unlink()


def setup(work):
    lock = json.loads((REPO / 'docs/popsicle-source-lock.json').read_text())
    work.mkdir(parents=True, exist_ok=True)
    for directory, key in [('common', 'candidate_common'), ('soc', 'xiaomi_soc'),
                           ('wlan', 'xiaomi_wlan')]:
        checkout(work / directory, lock[key])
    checkout(work / 'reference-modules', lock['reference_dataipa'], lock['reference_dataipa']['path'])
    for patch in sorted((REPO / 'kernel/patches/popsicle').glob('*.patch')):
        check = ['git', '-C', str(work / 'wlan'), 'apply']
        if subprocess.run(check + ['--reverse', '--check', str(patch)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            run(check + ['--check', patch])
            run(check + [patch])

    # Dormant host helper is compiled into the real target WLAN, not a new module.
    for source, destination in [
        ('wlan_hdd_mishare_host.c', 'src'), ('wlan_hdd_mishare_host.h', 'inc')]:
        shutil.copy2(REPO / 'kernel/popsicle-hdd' / source,
                     work / 'wlan/qcacld-3.0/core/hdd' / destination / source)

    tools = lock['toolchain_record']
    for key, folder in [('clang', 'clang-r536225'), ('rust', 'rust-1.82.0.p2')]:
        url = (f"{tools[key + '_repository']}/+archive/"
               f"{tools[key + '_repository_commit']}/{tools[key + '_path']}.tar.gz")
        tool_archive(work / 'toolchains' / folder, url)
    host = work / 'toolchains/host'
    for name in ['flex', 'bison', 'm4', 'bc', 'pahole']:
        executable = shutil.which(name)
        if not executable:
            raise ValueError(f'Missing host package: {name}')
        target = host / 'usr/bin' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(executable)
    for suffix, source in [('include', '/usr/include'), ('share/bison', '/usr/share/bison'),
                           ('lib/x86_64-linux-gnu', '/usr/lib/x86_64-linux-gnu')]:
        target = host / 'usr' / suffix
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(source, target_is_directory=True)
    bindgen_url = (f"{tools['bindgen_repository']}/+/{tools['bindgen_repository_commit']}/"
                   f"{tools['bindgen_path']}?format=TEXT")
    bindgen = host / 'usr/bin/bindgen'
    bindgen_marker = bindgen.parent / '.popsicle-bindgen-source-url'
    if not (bindgen.is_file() and bindgen_marker.is_file()
            and bindgen_marker.read_text() == bindgen_url):
        bindgen_download = work / 'bindgen.b64'
        download(bindgen_url, bindgen_download)
        bindgen.write_bytes(base64.b64decode(b''.join(bindgen_download.read_bytes().split()), validate=True))
        bindgen.chmod(0o755)
        bindgen_download.unlink()
        bindgen_marker.write_text(bindgen_url)
    bindgen_version = subprocess.check_output([str(bindgen), '--version'], text=True).strip()
    if bindgen_version != f"bindgen {tools['bindgen']}":
        raise ValueError(f'Unexpected cached bindgen: {bindgen_version}')

    raw = gzip.decompress((REPO / 'kernel/configs/popsicle-stock.config.gz').read_bytes())
    expected = json.loads((REPO / 'kernel/configs/popsicle-stock.json').read_text())['config_sha256']
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Tracked kernel configuration checksum mismatch')
    baseline = work / 'baseline'
    baseline.mkdir(exist_ok=True)
    (baseline / 'kernel-config.gz').write_bytes(gzip.compress(raw, mtime=0))
    reports = work / 'artifacts/reports'
    reports.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / 'docs/popsicle-source-lock.json', reports / 'source-lock.json')
    # This inventory reports missing backend plumbing, never radio readiness.
    # Hash the actual patched working files rather than trusting HEAD alone.
    backend = audited_inventory(work / 'wlan')
    (reports / 'wlan-backend-gaps.json').write_text(json.dumps(backend, indent=2) + '\n')
    print(f"WLAN backend inventory: {backend['status']}; "
          f"{len(backend['missing_source_plumbing'])} missing source groups; "
          'firmware support unverified.', flush=True)


def check_mishare_host_symbols(work, module, report_name):
    names = ['mishare_wonder_host_create_locked', 'mishare_wonder_host_destroy_locked',
             'hdd_mishare_host_adapter_open']
    output = subprocess.check_output([str(work / 'toolchains/clang-r536225/bin/llvm-nm'),
                                      '--defined-only', str(module)], text=True)
    defined = {line.split()[-1] for line in output.splitlines() if line.split()}
    missing = sorted(set(names) - defined)
    result = {'status': 'HOST_HELPER_SYMBOLS_PRESENT_ONLY' if not missing else 'MISSING_HOST_HELPER_SYMBOLS',
              'sha256': hashlib.sha256(module.read_bytes()).hexdigest(), 'symbols': names, 'missing': missing,
              'limitations': 'Actual linked symbol presence only; not host registration, firmware or radio validation.'}
    (work / 'artifacts/reports' / report_name).write_text(json.dumps(result, indent=2) + '\n')
    if missing:
        raise ValueError('Host helper was not built: ' + ', '.join(missing))


def build(work, phase):
    artifacts = work / 'artifacts'
    logs = artifacts / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    # This narrow header was rechecked against the recorded stock caller ABI.
    env['POPSICLE_HWID_INCLUDE'] = str(REPO / 'kernel/compat/popsicle')
    tools = work / 'toolchains'
    object_phase = 'wlan-object' if phase == 'module-trial' else phase
    args = ['bash', REPO / 'tools/kernel/popsicle_trial_build.sh', object_phase,
            work / 'baseline', work / 'common', work / 'soc', work / 'wlan',
            work / 'reference-modules/vendor/qcom/opensource/dataipa',
            tools / 'clang-r536225', tools / 'rust-1.82.0.p2', tools / 'host', work / 'out']
    def logged(command, filename):
        with (logs / filename).open('w') as log:
            process = subprocess.Popen(list(map(str, command)), env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, command)

    try:
        logged(['python3', REPO / 'tools/kernel/passthru_mode_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/passthru-mode-fixture.json'],
               'passthru-mode-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_host_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-host-fixture.json'],
               'mishare-host-fixture.log')
        logged(args, 'build.log')
        if phase != 'prepare':
            check_mishare_host_symbols(work, work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.o',
                                       'mishare-host-object.json')
            host = tools / 'host'
            env['PATH'] = f"{host}/usr/bin:{tools}/rust-1.82.0.p2/bin:" + env.get('PATH', '')
            env['LD_LIBRARY_PATH'] = f'{host}/usr/lib/x86_64-linux-gnu'
            env['LIBCLANG_PATH'] = f'{tools}/clang-r536225/lib'
            env['M4'] = f'{host}/usr/bin/m4'
            env['BISON_PKGDATADIR'] = f'{host}/usr/share/bison'
            make = ['make', '-C', work / 'common', f'O={work}/out', 'ARCH=arm64',
                    f'LLVM={tools}/clang-r536225/bin/',
                    f'HOSTCFLAGS=-I{host}/usr/include',
                    f'HOSTLDFLAGS=-L{host}/usr/lib/x86_64-linux-gnu', '-j2']
            logged(make + [f'M={REPO}/kernel/popsicle-availability', 'wonder_sysctl.o'],
                   'availability.log')
            logged(make + [f'M={REPO}/kernel/provider', 'opairshare_wonder_provider.o',
                           'opairshare_route_b_probe.o'], 'provider.log')
            logged(make + [f'M={REPO}/kernel/wonder',
                           'POPSICLE_STOCK_MAC80211_ABI=1',
                           f'EXTRA_CFLAGS=-I{REPO}/kernel/wonder/include/wonder', 'wonder.o'],
                   'wonder.log')
            objects = [work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.o',
                       REPO / 'kernel/popsicle-availability/wonder_sysctl.o',
                       REPO / 'kernel/provider/opairshare_wonder_provider.o',
                       REPO / 'kernel/provider/opairshare_route_b_probe.o',
                       REPO / 'kernel/wonder/wonder.o']
            with tarfile.open(artifacts / 'diagnostic-objects.tar.gz', 'w:gz') as archive:
                for obj in objects:
                    archive.add(obj, arcname=obj.name)
    finally:
        for name in ['stock-config-delta.json', 'source-delta.txt']:
            source = work / 'out' / name
            if source.exists():
                destination = artifacts / 'reports' / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)


def cnss_audit(module, table):
    required = sorted(name for name in module['undefined'] if name.startswith('cnss_'))
    missing = sorted(set(required) - table['exports'].keys())
    return {'status': 'BLOCKED' if missing else 'NAME_COVERAGE_ONLY',
            'required_cnss_symbols': len(required), 'missing': missing,
            'object_sha256': module['sha256'],
            'limitations': 'Names only; no CRC, structure layout, KCFI, full dependency, '
                          'firmware, module load or AirDrop compatibility validation.'}


def audit(work):
    table = json.loads((REPO / 'kernel/abi/popsicle-stock-cnss-exports.json').read_text())
    result = cnss_audit(inspect(work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.o'), table)
    path = work / 'artifacts/reports/cnss-interface-audit.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(path.read_text())
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write('### Popsicle diagnostic object build\n\n')
            stream.write('Object compilation completed. This is not an installable module.\n\n')
            stream.write(f"CNSS interface status: **{result['status']}**.\n\n")
            for name in result['missing']:
                stream.write(f'- Missing stock provider export: `{name}`\n')
            stream.write('\n' + result['limitations'] + '\n')
    return 2 if result['missing'] else 0


def layouts(work):
    """Derive detached type metadata without changing or installing any .ko."""
    module = work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.ko'
    original = hashlib.sha256(module.read_bytes()).hexdigest()
    btf = work / 'abi/candidate-wlan-layouts.btf'
    run(['pahole', '-j2', f'--btf_encode_detached={btf}', module])
    if hashlib.sha256(module.read_bytes()).hexdigest() != original:
        raise ValueError('Detached BTF extraction changed the candidate module')
    baseline = json.loads((REPO / 'kernel/abi/popsicle-stock-btf-layouts.json').read_text())
    result = compare(RecordedLayouts(baseline), Btf(btf.read_bytes()), list(baseline['types']))
    result['candidate_module_sha256'] = original
    (work / 'artifacts/reports/selected-layouts.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    for name, entry in result['types'].items():
        print(name, entry['status'])
    print(result['limitations'])
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write(f"\n### Selected structure layouts\n\n{result['status']}\n\n")
            stream.write('Detached metadata extraction; the module was not modified.\n\n')
            stream.write(result['limitations'] + '\n')
    return 0 if result['status'] == 'SELECTED_LAYOUTS_MATCH_ONLY' else 2


def module_stage_exit(result, link_only=False):
    """A completed link stage is distinct from the existing review gate."""
    expected = {'wonder_sysctl', 'opairshare_wonder_provider',
                'opairshare_route_b_probe', 'wonder', 'wlan'}
    complete = (set(result['modules']) == expected and not result['wlan_unresolved']
                and all(record['status'] in {'RECORDS_AND_HEADER_MATCH_ONLY',
                                             'RECORDED_LOADER_CHECKS_MATCH_ONLY',
                                             'REVIEW_KERNEL_RELEASE'}
                        for record in result['modules'].values()))
    if not complete:
        return 2
    passed = {'RECORDS_AND_HEADER_MATCH_ONLY', 'RECORDED_LOADER_CHECKS_MATCH_ONLY'}
    if result['status'] in passed and all(r['status'] in passed for r in result['modules'].values()):
        return 0
    return 0 if link_only and result['status'] == 'REVIEW_KERNEL_RELEASE' else 2


def review(work):
    result = json.loads((work / 'artifacts/reports/module-trial.json').read_text())
    code = module_stage_exit(result)
    if code:
        print(f"::error title=Module compatibility review blocked::{result['status']}. "
              'Link completion is not a compatibility pass. See module-trial.json.')
        for name, record in result['modules'].items():
            if record['status'] == 'REVIEW_KERNEL_RELEASE':
                print(f"{name}: kernel release review required; vermagic={record['vermagic']}")
        print('No binary version rewriting or compatibility checks were bypassed.')
    else:
        print('Recorded offline module checks completed; no runtime compatibility certification.')
        print('Actual stock loader evidence permits the release-prefix difference with basic CRCs.')
        print('C prototypes, remaining KCFI differences, loading and AirDrop still need validation.')
    return code


def modules(work, link_only=False):
    """Strict small-module builds, then fail closed on missing WLAN providers."""
    inputs = work / 'abi'
    inputs.mkdir(parents=True, exist_ok=True)
    lock = json.loads((REPO / 'docs/popsicle-source-lock.json').read_text())
    core = inputs / 'vmlinux.symvers'
    download(lock['candidate_common']['actual_symvers'], core)
    vendor = inputs / 'stock-vendor.symvers'
    known = write_inputs(work / 'common', work / 'out', core,
                         REPO / 'kernel/abi/popsicle-stock-exports.json', vendor)
    expected = json.loads((REPO / 'kernel/abi/popsicle-stock-module-header.json').read_text())
    artifact = work / 'artifacts'
    reports = artifact / 'reports'
    logs = artifact / 'logs'
    reports.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    result = {'status': 'IN_PROGRESS', 'modules': {}, 'wlan_unresolved': [],
              'limitations': 'Diagnostic .ko files only. No independent C type, private layout, '
                            'KCFI, BTF, GKI access, firmware, loading or AirDrop certification.'}
    tools = work / 'toolchains'
    host = tools / 'host'
    env = dict(os.environ)
    for key in ['KBUILD_MODPOST_WARN', 'KBUILD_MODPOST_NOFINAL', 'KBUILD_NSDEPS']:
        env.pop(key, None)
    env.update(PATH=f'{host}/usr/bin:{tools}/rust-1.82.0.p2/bin:' + env.get('PATH', ''),
               LD_LIBRARY_PATH=f'{host}/usr/lib/x86_64-linux-gnu',
               LIBCLANG_PATH=f'{tools}/clang-r536225/lib',
               M4=f'{host}/usr/bin/m4', BISON_PKGDATADIR=f'{host}/usr/share/bison')
    make = ['make', '-C', work / 'common', f'O={work}/out', 'ARCH=arm64',
            f'LLVM={tools}/clang-r536225/bin/', f'HOSTCFLAGS=-I{host}/usr/include',
            f'HOSTLDFLAGS=-L{host}/usr/lib/x86_64-linux-gnu', '-j2']
    produced = []

    def command(args, filename):
        with (logs / filename).open('w') as log:
            process = subprocess.Popen(list(map(str, args)), env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, args)

    try:
        for directory, names in [
            ('popsicle-availability', ['wonder_sysctl']),
            ('provider', ['opairshare_wonder_provider', 'opairshare_route_b_probe']),
            ('wonder', ['wonder']),
        ]:
            args = make + [f'M={REPO}/kernel/{directory}', f'KBUILD_EXTRA_SYMBOLS={vendor}']
            if directory == 'wonder':
                args += ['POPSICLE_STOCK_MAC80211_ABI=1',
                         f'EXTRA_CFLAGS=-I{REPO}/kernel/wonder/include/wonder']
            command(args + ['modules'], f'modpost-{directory}.log')
            generated = REPO / 'kernel' / directory / 'Module.symvers'
            if generated.stat().st_size:
                merge_generated_exports(known, symvers([generated]))
            for name in names:
                path = REPO / 'kernel' / directory / (name + '.ko')
                produced.append(path)
                if name == 'wonder':
                    # Check the actual linked table even if a compile-time
                    # assertion was accidentally put in an inactive Makefile.
                    ops_report = audit_mac80211_ops(path)
                    (reports / 'wonder-allocator-table.json').write_text(
                        json.dumps(ops_report, indent=2) + '\n')
                    print('Wonder ELF allocator callback slots verified.', flush=True)
                result['modules'][name] = module_report(path, expected, known)
                if result['modules'][name]['status'] == 'REJECT':
                    result['status'] = 'REJECT_MODULE_RECORDS_OR_HEADER'
                    return 2

        obj = inspect(work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.o')
        # __this_module is supplied by the module-generated .mod.c, not a provider.
        missing = sorted(set(obj['undefined']) - known.keys() - {'__this_module'})
        result['wlan_unresolved'] = missing
        if missing:
            result['status'] = 'BLOCKED_MISSING_WLAN_EXPORTS'
            return 2
        env['POPSICLE_HWID_INCLUDE'] = str(REPO / 'kernel/compat/popsicle')
        env['POPSICLE_EXTRA_SYMBOLS'] = str(vendor)
        command(['bash', REPO / 'tools/kernel/popsicle_trial_build.sh', 'wlan-modules',
                 work / 'baseline', work / 'common', work / 'soc', work / 'wlan',
                 work / 'reference-modules/vendor/qcom/opensource/dataipa',
                 tools / 'clang-r536225', tools / 'rust-1.82.0.p2', host, work / 'out'],
                'modpost-wlan.log')
        path = work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.ko'
        produced.append(path)
        check_mishare_host_symbols(work, path, 'mishare-host-module.json')
        merge_generated_exports(known, symvers([path.parent / 'Module.symvers']))
        result['modules']['wlan'] = module_report(path, expected, known)
        result['status'] = result['modules']['wlan']['status']
        if result['status'] != 'REJECT' and any(
                record['status'] == 'REVIEW_KERNEL_RELEASE' for record in result['modules'].values()):
            result['status'] = 'REVIEW_KERNEL_RELEASE'
        return module_stage_exit(result, link_only=link_only)
    except Exception:
        result['status'] = 'MODPOST_OR_BUILD_FAILED'
        raise
    finally:
        (reports / 'module-trial.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2), flush=True)
        if produced:
            with tarfile.open(artifact / 'diagnostic-modules-not-for-install.tar.gz', 'w:gz') as bundle:
                for path in produced:
                    bundle.add(path, arcname=path.name)
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a') as stream:
                stream.write(f"\n### Strict module trial\n\nStatus: **{result['status']}**\n\n")
                for name in result['wlan_unresolved']:
                    stream.write(f'- Missing real WLAN provider export: `{name}`\n')
                stream.write('\n' + result['limitations'] + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'build', 'audit', 'modules', 'review', 'layouts'])
    parser.add_argument('--link-only', action='store_true',
                        help='Report completed linking separately; run review as a required next step')
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'wlan-object', 'module-trial'], default='module-trial')
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == 'setup':
        setup(work)
    elif args.command == 'build':
        build(work, args.phase)
    elif args.command == 'audit':
        return audit(work)
    elif args.command == 'review':
        return review(work)
    elif args.command == 'layouts':
        return layouts(work)
    else:
        return modules(work, link_only=args.link_only)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'error: {error}', file=sys.stderr)
        sys.exit(1)
