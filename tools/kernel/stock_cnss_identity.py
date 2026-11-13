#!/usr/bin/env python3
"""Check 0189 read-only device evidence against captured stock; never grant loading."""
import argparse
import hashlib
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
MODULES=('cnss2','qca_cld3_peach_v2')
FOREIGN=('wonder','wonder_sysctl','opairshare_wonder_provider','opairshare_route_b_probe','oneplus13_wonder_provider')
TRANSACTIONS=('xairdrop17-pair-transaction','xairdrop17-stockcnss-transaction')
PROPS=('device','firmware','slot','boot_completed','kernel','machine','boot_id')

def parse(raw):
    if len(raw)>32768:raise ValueError('Capture too large')
    fields={}
    for line in raw.decode('ascii').splitlines():
        parts=line.split('\t')
        if len(parts)!=2 or not parts[0] or not parts[1] or parts[0] in fields:
            raise ValueError('Malformed/empty/duplicate evidence field')
        key,value=parts
        if not re.fullmatch(r'[a-z0-9_.-]+',key) or any(ord(c)<32 or ord(c)==127 for c in value):
            raise ValueError('Invalid evidence characters')
        fields[key]=value
    required={'schema','stage','uid','capture_status','boot_sha256'}
    required.update(PROPS);required.update(x+'.after' for x in PROPS)
    for m in MODULES:
        required.add(m+'.loaded')
        loaded=fields.get(m+'.loaded')
        if loaded not in ('0','1'):raise ValueError('Missing/invalid loaded state: '+m)
        if loaded=='1':required.update((m+'.initstate',m+'.note_sha256'))
        for area in ('vendor','vendor_dlkm'):
            key=f'{m}.{area}.present';required.add(key)
            if fields.get(key) not in ('0','1'):raise ValueError('Missing/invalid file presence: '+key)
            if fields[key]=='1':required.add(f'{m}.{area}.sha256')
    required.update(m+'.loaded' for m in FOREIGN)
    required.update(t+'.present' for t in TRANSACTIONS)
    if set(fields)!=required:
        raise ValueError('Missing fields: '+','.join(sorted(required-fields.keys()))+
                         '; unexpected fields: '+','.join(sorted(fields.keys()-required)))
    return fields

def evaluate(raw):
    f=parse(raw)
    profile_path=ROOT/'kernel/abi/popsicle-pair-deployment.json'
    profile=json.loads(profile_path.read_text())
    failures=[]
    def expect(key,value):
        if f[key]!=value:failures.append(key)
    for key,value in {'schema':'1','uid':'0','capture_status':'CAPTURE_COMPLETE_NOT_FOR_INSTALL',
                      'device':profile['device'],'firmware':profile['firmware'],'kernel':profile['kernel_release'],
                      'machine':'aarch64','boot_completed':'1','boot_sha256':profile['boot_sha256']}.items():
        expect(key,value)
    if f['stage'] not in ('0189','0190'):failures.append('stage')
    if f['slot'] not in ('_a','_b'):failures.append('slot')
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',f['boot_id']):failures.append('boot_id')
    for key in PROPS:expect(key+'.after',f[key])
    for m in MODULES:
        present=0
        for area in ('vendor','vendor_dlkm'):
            if f[f'{m}.{area}.present']=='1':
                present+=1;expect(f'{m}.{area}.sha256',profile['stock'][m]['sha256'])
        if not present:failures.append(m+'.stock_file_missing')
        expect(m+'.loaded','1')
        if f[m+'.loaded']=='1':
            expect(m+'.initstate','live');expect(m+'.note_sha256',profile['stock'][m]['note_sha256'])
    for m in FOREIGN:expect(m+'.loaded','0')
    for t in TRANSACTIONS:expect(t+'.present','0')
    return {'stage':f['stage'],'status':'IDENTITY_MISMATCH_BLOCKED' if failures else 'CAPTURED_STOCK_IDENTITY_MATCH_ONLY',
            'capture_sha256':hashlib.sha256(raw).hexdigest(),
            'stock_profile_sha256':hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            'mismatched_fields':failures,'observed_firmware':f['firmware'],'observed_kernel':f['kernel'],
            'boot_id':f['boot_id'],'load_authorized':False,'deployment_bundle_created':False,
            'runtime_certified':False,'phone_execution_independently_witnessed':False,
            'limitations':'User-supplied capture is not cryptographic device attestation or an unload-readiness check. '
                'Before/after observations detect changes, not arbitrary ABA races; refresh under the future executor lock. '
                'No candidate ELF, full ABI, firmware behavior, load, recovery, RF or Apple certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.capture.read_bytes()
    try:result=evaluate(raw)
    except (ValueError,UnicodeError) as error:
        result={'stage':'0190','status':'CAPTURE_INVALID_BLOCKED',
                'capture_sha256':hashlib.sha256(raw).hexdigest(),'error':str(error),
                'load_authorized':False,'runtime_certified':False,'deployment_bundle_created':False}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status']);raise SystemExit(result['status']!='CAPTURED_STOCK_IDENTITY_MATCH_ONLY')
