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

from module_abi import inspect

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
    bindgen_download = work / 'bindgen.b64'
    download(bindgen_url, bindgen_download)
    bindgen = host / 'usr/bin/bindgen'
    bindgen.write_bytes(base64.b64decode(b''.join(bindgen_download.read_bytes().split()), validate=True))
    bindgen.chmod(0o755)
    bindgen_download.unlink()

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


def build(work, phase):
    artifacts = work / 'artifacts'
    logs = artifacts / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    # This narrow header was rechecked against the recorded stock caller ABI.
    env['POPSICLE_HWID_INCLUDE'] = str(REPO / 'kernel/compat/popsicle')
    tools = work / 'toolchains'
    args = ['bash', REPO / 'tools/kernel/popsicle_trial_build.sh', phase,
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
        logged(args, 'build.log')
        if phase == 'wlan-object':
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'build', 'audit'])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'wlan-object'], default='wlan-object')
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == 'setup':
        setup(work)
    elif args.command == 'build':
        build(work, args.phase)
    else:
        return audit(work)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'error: {error}', file=sys.stderr)
        sys.exit(1)
