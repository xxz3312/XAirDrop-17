#!/usr/bin/env python3
"""Compare a freshly captured boot payload; never update accepted identities."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from stock_cnss_identity import parse
from popsicle_modpost import stock_loader_evidence
ROOT=Path(__file__).resolve().parents[2]

def compare(raw,capture,reviewed):
    f=parse(capture)
    if (f['uid']!='0' or f['capture_status']!='CAPTURE_COMPLETE_NOT_FOR_INSTALL' or
        f['stage'] not in ('0189','0190') or f['slot'] not in ('_a','_b') or
        f['boot_completed']!='1' or f['machine']!='aarch64' or f['device']!='popsicle' or
        not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',f['boot_id']) or
        not re.fullmatch(r'[0-9a-f]{64}',f['boot_sha256']) or
        any(f[k]!=f[k+'.after'] for k in ('boot_id','slot','firmware','kernel','device','machine','boot_completed'))):
        raise ValueError('Incomplete or changed identity observation')
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=f['boot_sha256']:raise ValueError('Boot bytes do not match uploaded phone capture')
    if len(raw)<4096 or raw[:8]!=b'ANDROID!':raise ValueError('Truncated/non-Android boot')
    size,ramdisk_size=struct.unpack_from('<II',raw,8)
    header_size=struct.unpack_from('<I',raw,20)[0]
    version=struct.unpack_from('<I',raw,40)[0]
    if version!=4 or header_size!=1584 or not size or 4096+size>len(raw):
        raise ValueError('Unsupported/truncated boot v4 kernel/header')
    ramdisk_offset=4096+((size+4095)//4096)*4096
    if ramdisk_offset+ramdisk_size>len(raw):raise ValueError('Truncated boot ramdisk')
    kernel=raw[4096:4096+size];kernel_sha=hashlib.sha256(kernel).hexdigest()
    same=kernel_sha==reviewed['kernel_sha256']
    return {'stage':'0192','status':'KERNEL_PAYLOAD_MATCH_ONLY' if same else 'KERNEL_PAYLOAD_CHANGED_REVIEW_REQUIRED',
            'boot_sha256':digest,'identity_capture_sha256':hashlib.sha256(capture).hexdigest(),
            'kernel_sha256':kernel_sha,'reviewed_kernel_sha256':reviewed['kernel_sha256'],
            'kernel_bytes':size,'ramdisk_bytes':ramdisk_size,'boot_header_version':version,
            'boot_matches_old_capture':digest==reviewed['boot_sha256'],
            'kernel_payload_matches_old_capture':same,'observed_firmware':f['firmware'],
            'load_authorized':False,'runtime_certified':False,'accepted_profile_updated':False,
            'limitations':'Whole kernel payload identity comparison only. A different boot can contain the same '
                'kernel payload; version strings alone cannot establish that. No running-memory attestation, '
                'new firmware qualification, candidate ABI/load/unload/recovery/RF/Apple certificate.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--boot',type=Path,required=True)
    p.add_argument('--identity',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    expected=json.loads((ROOT/'kernel/abi/popsicle-stock-module-header.json').read_text())
    reviewed=stock_loader_evidence(expected)
    if reviewed is None:raise ValueError('Missing authenticated reviewed loader evidence')
    result=compare(a.boot.read_bytes(),a.identity.read_bytes(),reviewed)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
