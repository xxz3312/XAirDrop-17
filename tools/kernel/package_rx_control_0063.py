#!/usr/bin/env python3
"""Repackage validated 0062 bytes with the controlled observation script."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

base = Path('base/XAirDrop-17-Mgmt-RX-0062.zip')
p = Path('out/XAirDrop-17-RX-Control-0063')
p.mkdir(parents=True)
digest = lambda b: hashlib.sha256(b).hexdigest()
with zipfile.ZipFile(base) as z:
    prefix = 'XAirDrop-17-Mgmt-RX-0062/'
    for line in z.read(prefix + 'SHA256SUMS').decode().splitlines():
        sha, name = line.split('  ', 1)
        assert digest(z.read(prefix + name)) == sha, name
    previous = json.loads(z.read(prefix + 'BUILD.json'))
    assert previous['kernel_source_commit'] == 'fde84a8b4342b7277be5d36a328cc50bd8d08202'
    assert previous['kernel_run'] == 41020407291
    assert previous['package_run'] == 41020576709
    # Verify the current source still contains every original kernel/native file.
    with tarfile.open(fileobj=io.BytesIO(z.read(prefix + 'source.tar.gz')), mode='r:gz') as t:
        for member in t.getmembers():
            name = member.name.removeprefix('XAirDrop-17/')
            if member.isfile() and name.startswith(('kernel/', 'native/')):
                assert t.extractfile(member).read() == Path(name).read_bytes(), name
    for name in ['kernel/qca_cld3_peach_v2.ko', 'kernel/opairshare_wonder_provider.ko',
                 'LICENSE', 'GPL-2.0-only.txt', 'LGPL-3.0.txt', 'tool-build.json']:
        target = p / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(prefix + name))
    (p / 'action-tx-0063').write_bytes(z.read(prefix + 'action-tx-0062'))

assert digest((p/'kernel/qca_cld3_peach_v2.ko').read_bytes()) == previous['stripped_wlan_sha256']
assert digest((p/'action-tx-0063').read_bytes()) == previous['tool_sha256']
for name in ['popsicle-wlan-trial.sh', 'popsicle-rx-control-0063.sh']:
    shutil.copy2('tools/device/' + name, p/name)
shutil.copy2('docs/POPSICLE-RX-CONTROL-0063.md', p/'README.md')
subprocess.run(['git', 'archive', '--format=tar.gz', '--prefix=XAirDrop-17/',
                '--output=' + str(p/'source.tar.gz'), 'HEAD'], check=True)
report = dict(previous)
report.update(package_revision='0063', controller_source_commit=os.environ['GITHUB_SHA'],
              package_run=int(os.environ['GITHUB_RUN_ID']), reused_package_run=41020576709,
              driver_and_tool_reused_byte_for_byte=True,
              observation_stages=['quiet', 'system_scan_request', 'optional_disconnect_rejoin', 'awdl'],
              disconnect_requires_explicit_flag=True, disconnect_max_attempts=1,
              scan_request_is_not_scan_execution_proof=True,
              counter_growth_is_not_awdl_success=True,
              controller_model_methods=7, phone_executed=False, airdrop_verified=False)
(p/'BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
(p/'SHA256SUMS').write_text(''.join(digest(f.read_bytes()) + '  ' + f.relative_to(p).as_posix() + '\n'
                                  for f in sorted(p.rglob('*')) if f.is_file() and f.name != 'SHA256SUMS'))
with zipfile.ZipFile('out/XAirDrop-17-RX-Control-0063.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(p.rglob('*')):
        if f.is_file(): z.write(f, f.relative_to(p.parent))
