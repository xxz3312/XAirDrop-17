#!/usr/bin/env python3
"""Package the declaration-only KernelSU module. No vendor binaries or boot scripts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = 'system/vendor/etc/vintf/manifest/manifest_xairdrop17_xos.xml'
ALLOWED = {'module.prop', 'customize.sh', 'action.sh', FRAGMENT}


def validated_files(source):
    paths = {p.relative_to(source).as_posix(): p for p in source.rglob('*') if p.is_file()}
    if set(paths) != ALLOWED or any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('Unexpected module content; only the declaration and manual scripts are allowed')
    data = {name: path.read_bytes() for name, path in paths.items()}
    manifest = ET.fromstring(data[FRAGMENT])
    hal = manifest.find('hal')
    if (manifest.attrib != {'version': '2.0', 'type': 'device'} or len(manifest) != 1 or hal is None or
        hal.attrib != {'format': 'aidl'} or len(hal) != 3 or hal.findtext('name') != 'com.domestic.xoscomm' or
        hal.findtext('version') != '1' or hal.findtext('fqname') != 'IDomesticXOsComm/default'):
        raise ValueError('Unexpected XOS AIDL declaration')
    action = data['action.sh'].decode()
    if action.count('@MANIFEST_SHA256@') != 1:
        raise ValueError('Manifest verification placeholder missing or duplicated')
    data['action.sh'] = action.replace('@MANIFEST_SHA256@', hashlib.sha256(data[FRAGMENT]).hexdigest()).encode()
    return data


def package(output):
    data = validated_files(ROOT / 'modules/xos-vintf')
    data['service-smoke.sh'] = (ROOT / 'tools/device/popsicle-xos-service-smoke.sh').read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'XAirDrop-17-XOS-VINTF-0.1.zip'
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(data.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 26, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            z.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
    record = {'status': 'PACKAGED_NOT_DEVICE_TESTED', 'commit': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'bytes': path.stat().st_size, 'entries': sorted(data),
              'scope': 'One systemless VINTF declaration, installer checks and manual registration test. No boot service, native ELF, kernel modules, SELinux rules or APKs.'}
    (output / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    package(p.parse_args().output)
