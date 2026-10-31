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
from module_cfg80211_ops import audit as audit_cfg80211_ops
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

    for header in ['mishare_raw_protocol.h', 'wma_mishare_raw_tx.h']:
        shutil.copy2(REPO / 'kernel/popsicle-hdd' / header,
                     work / 'wlan/qcacld-3.0/core/wma/inc' / header)

    shutil.copy2(REPO / 'kernel/popsicle-hdd/wlan_mishare_mgmt_diag.h',
                 work / 'wlan/qcacld-3.0/core/mac/inc/wlan_mishare_mgmt_diag.h')

    # Numeric-only cross-layer diagnostics; no HDD types in this shared header.
    for directory in ['qcacld-3.0/core/wma/src',
                      'qca-wifi-host-cmn/umac/cmn_services/mgmt_txrx/dispatcher/src']:
        shutil.copy2(REPO / 'kernel/popsicle-hdd/wlan_mishare_mgmt_diag.h',
                     work / 'wlan' / directory / 'wlan_mishare_mgmt_diag.h')

    # Dormant host helper is compiled into the real target WLAN, not a new module.
    for source, destination in [
        ('wlan_hdd_mishare_host.c', 'src'), ('wlan_hdd_mishare_host.h', 'inc'),
        ('wlan_hdd_mishare_session.h', 'inc'),
        ('wlan_hdd_mishare_mgmt_rx.c', 'src'), ('wlan_hdd_mishare_mgmt_rx.h', 'inc'),
        ('wlan_hdd_mishare_backend.c', 'src'), ('wlan_hdd_mishare_backend.h', 'inc'),
        ('mishare_raw_protocol.h', 'inc'),
        ('wlan_hdd_mishare_raw_tx.h', 'inc'),
        ('wlan_hdd_mishare_txn.c', 'src'), ('wlan_hdd_mishare_txn.h', 'inc'),
        ('wlan_hdd_mishare_events.c', 'src'), ('wlan_hdd_mishare_events.h', 'inc'),
        ('wlan_hdd_mishare_commands.c', 'src'), ('wlan_hdd_mishare_commands.h', 'inc'),
        ('wlan_hdd_mishare_runtime.c', 'src'), ('wlan_hdd_mishare_runtime.h', 'inc'),
        ('wlan_hdd_mishare_ndi.h', 'inc'),
        ('wlan_hdd_mishare_radio.c', 'src'), ('wlan_hdd_mishare_radio.h', 'inc'),
        ('wlan_hdd_mishare_radio_mlme.h', 'inc')]:
        shutil.copy2(REPO / 'kernel/popsicle-hdd' / source,
                     work / 'wlan/qcacld-3.0/core/hdd' / destination / source)

    shutil.copy2(REPO / 'kernel/provider/wondertap.h',
                 work / 'wlan/qcacld-3.0/core/hdd/inc/wlan_hdd_mishare_wonder_api.h')

    shutil.copy2(REPO / 'kernel/wonder/wondertap_managed.h',
                 work / 'wlan/qcacld-3.0/core/hdd/inc/wlan_hdd_mishare_managed.h')

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
             'mishare_wonder_host_session_step_locked',
             'hdd_mishare_host_adapter_open', 'mishare_wonder_backend_register',
             'mishare_wonder_backend_unregister', 'mishare_vdev_txn_init',
             'mishare_vdev_txn_begin', 'mishare_vdev_txn_submitted',
             'mishare_vdev_txn_response', 'mishare_vdev_txn_timeout',
             'mishare_events_bind', 'mishare_events_unbind', 'mishare_events_begin',
             'mishare_events_submitted', 'mishare_events_snapshot', 'mishare_events_notify',
             'mishare_events_begin_vdev', 'mishare_command_submit_start',
             'mishare_command_submit_stop', 'passthru_mlme_ops',
             'mishare_wonder_host_vdev_create_locked', 'mishare_wonder_host_vdev_destroy_locked',
             'mishare_runtime_create', 'mishare_runtime_destroy', 'mishare_runtime_snapshot',
             'mishare_runtime_allocated', 'mishare_runtime_prepare_free', 'mishare_runtime_freed',
             'mishare_runtime_ndi_create', 'mishare_runtime_ndi_delete_owned',
             'mishare_runtime_ndi_delete_event', 'mishare_ndi_native_create',
             'mishare_ndi_tgt_create', 'mishare_ndi_wire_create',
             'mishare_ndi_native_delete', 'mishare_ndi_native_dp_detach',
             'mishare_ndi_release_stats', 'mishare_runtime_ndi_prepare',
             'mishare_runtime_ndi_peer_event', 'mishare_ndi_legacy_prepare',
             'mishare_ndi_legacy_release', 'mishare_ndi_wma_bind',
             'mishare_ndi_wma_unbind', 'mishare_ndi_self_peer_create',
             'mishare_ndi_self_peer_delete', 'mishare_runtime_ndi_session',
             'mishare_ndi_pe_post', 'mishare_runtime_ndi_pe_event',
             'mishare_runtime_ndi_channel', 'mishare_ndi_channel_post',
             'mishare_runtime_ndi_channel_event', 'mishare_runtime_ndi_start_plan',
             'mishare_ndi_start_plan_build', 'mishare_ndi_start_plan_wma_check',
             'mishare_ndi_start_plan_post', 'mishare_runtime_ndi_start_plan_event', 'mishare_runtime_ndi_start',
             'mishare_radio_open', 'mishare_radio_snapshot', 'mishare_radio_drain',
             'mishare_ndi_radio_prepare', 'mishare_ndi_radio_start_response',
             'mishare_ndi_radio_host_up', 'mishare_ndi_radio_mark_down',
             'mishare_ndi_radio_start_pm_release']
    names += ['mishare_runtime_quiesce_psoc', 'mishare_runtime_platform_available',
              'mishare_runtime_work_allowed', 'mishare_events_quiesce_psoc',
              'mishare_radio_quiesce_psoc']
    names += ['mishare_runtime_work_get', 'mishare_runtime_work_enter',
              'mishare_runtime_work_exit', 'mishare_runtime_work_put',
              'mishare_runtime_mc_stopped', 'mishare_runtime_reclaim_host']
    names += ['mishare_runtime_recovery_candidates', 'mishare_runtime_recovery_open',
              'mishare_runtime_recovery_close', 'mishare_runtime_reclaim_ndi',
              'mishare_ndi_recovery_timer_deinit', 'mishare_ndi_recovery_dp_detach']
    names += ['mishare_runtime_reclaim_batch', 'mishare_wonder_host_psoc_busy',
              'mishare_wonder_host_reclaim_ssr_locked',
              'mishare_ndi_reset_context_release', 'mishare_ndi_reset_context_check',
              'mishare_ndi_reset_pe_check', 'mishare_ndi_reset_pe_release',
              'mishare_ndi_reset_prepared_timer_deinit', 'mishare_ndi_reset_context_finish',
              'mishare_ndi_reset_prepared_dp_detach']
    names += ['mishare_runtime_reclaim_final', 'mishare_raw_tx_sync',
              'mishare_action_tx_sync']
    names += ['mishare_radio_ssr_cancel_check', 'mishare_radio_ssr_cancel_release',
              'mishare_runtime_radio_start_flushed',
              'mishare_runtime_radio_start_refused', 'mishare_runtime_radio_start_aborted',
              'mishare_runtime_radio_prepared_aborted', 'mishare_runtime_radio_sm_entry_aborted',
              'mishare_runtime_radio_init_rejected', 'mishare_radio_native_init_rejected']
    output = subprocess.check_output([str(work / 'toolchains/clang-r536225/bin/llvm-nm'),
                                      '--defined-only', str(module)], text=True)
    defined = {line.split()[-1] for line in output.splitlines() if line.split()}
    missing = sorted(set(names) - defined)
    result = {'status': 'HOST_HELPER_SYMBOLS_PRESENT_ONLY' if not missing else 'MISSING_HOST_HELPER_SYMBOLS',
              'sha256': hashlib.sha256(module.read_bytes()).hexdigest(), 'symbols': names, 'missing': missing,
              'limitations': 'Actual linked symbol presence only; not host registration, firmware or radio validation.'}
    if module.suffix == '.ko':
        dependencies = inspect(module)['modinfo'].get('depends', [])
        result['dependencies'] = dependencies
        if not any('opairshare_wonder_provider' in value.split(',') for value in dependencies):
            raise ValueError('Missing strong private provider dependency')
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
        logged(['python3', REPO / 'tools/kernel/mishare_native_lifecycle_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-native-lifecycle-fixture.json'],
               'mishare-native-lifecycle-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_init_rejection_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-init-rejection-reset-fixture.json'],
               'mishare-init-rejection-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_sm_entry_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-sm-entry-reset-fixture.json'],
               'mishare-sm-entry-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_completed_prepare_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-completed-prepare-reset-fixture.json'],
               'mishare-completed-prepare-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_aborted_start_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-aborted-start-reset-fixture.json'],
               'mishare-aborted-start-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_refused_start_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-refused-start-reset-fixture.json'],
               'mishare-refused-start-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_rejected_start_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-rejected-start-reset-fixture.json'],
               'mishare-rejected-start-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_queued_start_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-queued-start-reset-fixture.json'],
               'mishare-queued-start-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_pre_radio_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-pre-radio-reset-fixture.json'],
               'mishare-pre-radio-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_pe_reset_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-pe-reset-fixture.json'],
               'mishare-pe-reset-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_pe_destructor_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-pe-destructor-fixture.json'],
               'mishare-pe-destructor-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_final_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-final-fixture.json'],
               'mishare-final-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_completed_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-completed-fixture.json'],
               'mishare-completed-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_completion_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-completion-fixture.json'],
               'mishare-completion-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_batch_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-batch-fixture.json'],
               'mishare-batch-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_parent_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-parent-fixture.json'],
               'mishare-parent-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_reset_context_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-reset-context-fixture.json'],
               'mishare-reset-context-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_recovery_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-recovery-fixture.json'],
               'mishare-recovery-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_work_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-work-fixture.json'],
               'mishare-work-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_shutdown_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-shutdown-fixture.json'],
               'mishare-shutdown-fixture.log')
        logged(['python3', REPO / 'tools/kernel/passthru_mode_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/passthru-mode-fixture.json'],
               'passthru-mode-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_ndi_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-ndi-fixture.json'],
               'mishare-ndi-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_create_delete_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-create-delete-fixture.json'],
               'mishare-create-delete-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_radio_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-radio-fixture.json'],
               'mishare-radio-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_start_plan_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-start-plan-fixture.json'],
               'mishare-start-plan-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_channel_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-channel-fixture.json'],
               'mishare-channel-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_session_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-session-fixture.json'],
               'mishare-session-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_context_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-context-fixture.json'],
               'mishare-context-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_firmware_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-firmware-fixture.json'],
               'mishare-firmware-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_runtime_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-runtime-fixture.json'],
               'mishare-runtime-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_ops_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-ops-fixture.json'],
               'mishare-ops-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_commands_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-commands-fixture.json'],
               'mishare-commands-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_response_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-response-fixture.json'],
               'mishare-response-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_events_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-events-fixture.json'],
               'mishare-events-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_txn_fixture.py',
                '--output', artifacts / 'reports/mishare-txn-fixture.json'],
               'mishare-txn-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_mlme_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-mlme-fixture.json'],
               'mishare-mlme-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_host_fixture.py',
                '--wlan', work / 'wlan', '--output', artifacts / 'reports/mishare-host-fixture.json'],
               'mishare-host-fixture.log')
        logged(['python3', REPO / 'tools/kernel/mishare_backend_fixture.py',
                '--output', artifacts / 'reports/mishare-backend-fixture.json'],
               'mishare-backend-fixture.log')
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
                # Use the real private exports, not unavailable GKI symbol_get.
                provider_exports = REPO / 'kernel/provider/Module.symvers'
                args = [a for a in args if not str(a).startswith('KBUILD_EXTRA_SYMBOLS=')]
                args += [f'KBUILD_EXTRA_SYMBOLS={vendor} {provider_exports}']
                args += ['POPSICLE_STOCK_MAC80211_ABI=1',
                         f'EXTRA_CFLAGS=-I{REPO}/kernel/wonder/include/wonder']
            command(args + ['modules'], f'modpost-{directory}.log')
            generated = REPO / 'kernel' / directory / 'Module.symvers'
            if generated.stat().st_size:
                merge_generated_exports(known, symvers([generated]))
            if directory == 'provider':
                required = ['opairshare_set_wonder_priv_data',
                            'opairshare_set_wonder_managed_priv_data',
                            'opairshare_wonder_managed_control']
                missing = sorted(set(required) - set(symvers([generated])))
                contract = {'status': 'PROVIDER_MANAGED_EXPORTS_PRESENT_ONLY' if not missing else 'REJECT',
                            'required': required, 'missing': missing,
                            'symvers_sha256': hashlib.sha256(generated.read_bytes()).hexdigest(),
                            'limitations': 'Export names only; no runtime binding, native parent or RF certification.'}
                (reports / 'wonder-managed-exports.json').write_text(json.dumps(contract, indent=2) + '\n')
                if missing:
                    raise ValueError('Missing private managed provider exports: ' + ', '.join(missing))
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
                    required = ['wondertap_provider_bind', 'wondertap_provider_unbind',
                                'wondertap_bind_managed_staged', 'wondertap_activate_managed',
                                'wondertap_quiesce_managed', 'wondertap_retire']
                    output = subprocess.check_output([str(work / 'toolchains/clang-r536225/bin/llvm-nm'),
                                                      '--defined-only', str(path)], text=True)
                    defined = {line.split()[-1] for line in output.splitlines() if line.split()}
                    missing = sorted(set(required) - defined)
                    contract = {'status': 'WONDER_MANAGED_ENTRIES_PRESENT_ONLY' if not missing else 'REJECT',
                                'required': required, 'missing': missing,
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                'limitations': 'Linked entry names only; not active session, native teardown or RF proof.'}
                    (reports / 'wonder-managed-module.json').write_text(json.dumps(contract, indent=2) + '\n')
                    if missing:
                        raise ValueError('Missing linked managed Wonder entries: ' + ', '.join(missing))
                    dependencies = inspect(path)['modinfo'].get('depends', [])
                    if not any('opairshare_wonder_provider' in d.split(',') for d in dependencies):
                        raise ValueError('Wonder lacks the private provider module dependency')
                    contract['dependencies'] = dependencies
                    (reports / 'wonder-managed-module.json').write_text(json.dumps(contract, indent=2) + '\n')
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
        # Add the actual newly built private provider's CRC records. No synthetic exports.
        wlan_symbols = inputs / 'wlan-providers.symvers'
        provider_symbols = REPO / 'kernel/provider/Module.symvers'
        wlan_symbols.write_text(vendor.read_text() + provider_symbols.read_text())
        env['POPSICLE_EXTRA_SYMBOLS'] = str(wlan_symbols)
        command(['bash', REPO / 'tools/kernel/popsicle_trial_build.sh', 'wlan-modules',
                 work / 'baseline', work / 'common', work / 'soc', work / 'wlan',
                 work / 'reference-modules/vendor/qcom/opensource/dataipa',
                 tools / 'clang-r536225', tools / 'rust-1.82.0.p2', host, work / 'out'],
                'modpost-wlan.log')
        path = work / 'wlan/qcacld-3.0/qca_cld3_peach_v2.ko'
        produced.append(path)
        ops_report = audit_cfg80211_ops(path)
        (reports / 'wlan-cfg80211-table.json').write_text(json.dumps(ops_report, indent=2) + '\n')
        print('WLAN ELF cfg80211 callback slots and target INI prefix verified.', flush=True)
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
