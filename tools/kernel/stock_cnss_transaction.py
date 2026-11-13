#!/usr/bin/env python3
"""Classify read-only retained state; never authorize archive, replay or loading."""
import argparse
import hashlib
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
SMALL=('boot-id','phase','manifest.sha256','wifi.before','phase.new','phase.after')
OPS=r'(wifi-off|hals-stop|remove-wlan|insert-provider|insert-wlan|hals-start|wifi-restore)'
PHASE=r'(backup-only|prepared|active|intent:'+OPS+r'|done:'+OPS+r'|returned:'+OPS+r':[0-9]+)'


def parent_signature_allowed(value,android_data=False):
    if android_data and value in ('1000:1000:771','1000:1000:0771'):return True
    match=re.fullmatch(r'0:[0-9]+:([0-7]{3,4})',value)
    return bool(match and not (int(match[1],8)&0o022))

def classify(raw):
    if len(raw)>16384:raise ValueError('Oversized capture')
    f={}
    for line in raw.decode('ascii').splitlines():
        p=line.split('\t')
        if len(p)!=2 or not all(p) or p[0] in f or any(ord(c)<32 or ord(c)==127 for c in line.replace('\t','')):
            raise ValueError('Malformed/ambiguous fields')
        f[p[0]]=p[1]
    base={'schema','stage','uid','boot_id','boot_id.after','transaction.present','capture_status'}
    if f.get('stage')=='0192':base.update(('parent.data.meta','parent.adb.meta'))
    if f.get('transaction.present') not in ('0','1','UNKNOWN'):raise ValueError('Invalid transaction presence')
    if f['transaction.present']=='1':
        if 'transaction.access' in f:base.add('transaction.access')
        else:
            base.update(('transaction.identity','transaction.identity.after'))
            base.update(k+'.'+s for k in SMALL for s in ('status','value'))
            base.update(k+'.'+s for k in ('backup','hals') for s in ('status','sha256'))
    if set(f)!=base:raise ValueError('Missing/unexpected fields')
    reasons=[]
    for k,v in {'schema':'1','uid':'0','capture_status':'CAPTURE_COMPLETE_RECORD_ONLY'}.items():
        if f[k]!=v:reasons.append(k)
    if f['stage'] not in ('0191','0192'):reasons.append('stage')
    if f['stage']=='0192':
        for key,android_data in [('parent.data.meta',True),('parent.adb.meta',False)]:
            if not parent_signature_allowed(f[key],android_data):reasons.append(key)
    if not re.fullmatch(UUID,f['boot_id']) or f['boot_id.after']!=f['boot_id']:reasons.append('boot_changed_or_invalid')
    status='TRANSACTION_RECORD_BLOCKED'
    if f['transaction.present']=='UNKNOWN':reasons.append('transaction_presence_unverified')
    elif f['transaction.present']=='0':
        if not reasons:status='NO_TRANSACTION_RECORDED'
    elif 'transaction.access' in f:reasons.append('transaction_access_rejected')
    else:
        if not re.fullmatch(r'[0-9]+:[0-9]+',f['transaction.identity']) or f['transaction.identity.after']!=f['transaction.identity']:
            reasons.append('transaction_directory_changed')
        for k in SMALL:
            if k=='phase.new':
                if (f[k+'.status'],f[k+'.value'])!=('MISSING','-'):reasons.append('unfinished_journal_preserved')
            elif f[k+'.status']!='OK':reasons.append(k+'.unreadable')
        if not re.fullmatch(UUID,f['boot-id.value']):reasons.append('invalid_recorded_boot')
        if not re.fullmatch(PHASE,f['phase.value']):reasons.append('unknown_phase')
        if f['phase.after.value']!=f['phase.value']:reasons.append('phase_changed')
        if f['wifi.before.value'] not in ('0','1'):reasons.append('invalid_wifi_baseline')
        checker=json.loads((ROOT/'kernel/abi/popsicle-stock-cnss-checker-base-0136.json').read_text())
        profile=json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
        if f['manifest.sha256.value']!=checker['files']['deployment.tsv']:reasons.append('unknown_manifest')
        if f['backup.status']!='OK' or f['backup.sha256']!=profile['stock']['qca_cld3_peach_v2']['sha256']:
            reasons.append('stock_backup_mismatch')
        if f['hals.status']!='OK' or not re.fullmatch(r'[0-9a-f]{64}',f['hals.sha256']):reasons.append('hals_record_unreadable')
        if not reasons:
            status='SAME_BOOT_TRANSACTION_PRESERVED' if f['boot-id.value']==f['boot_id'] else 'PRIOR_BOOT_RECORD_ONLY'
    return {'stage':f['stage'],'status':status,'reasons':reasons,'capture_sha256':hashlib.sha256(raw).hexdigest(),
            'archive_authorized':False,'replay_authorized':False,'load_authorized':False,'runtime_certified':False,
            'limitations':'User-supplied observations are not device attestation or serialization. '
                'Even prior-boot matching records require fresh qualified stock identity and an independently '
                'qualified executor before any archival operation. Firmware 4.0.6.0 is not qualified by this record.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=a.capture.read_bytes()
    try:r=classify(raw)
    except (ValueError,UnicodeError) as e:
        r={'stage':'0191','status':'TRANSACTION_CAPTURE_INVALID','error':str(e),
           'archive_authorized':False,'replay_authorized':False,'load_authorized':False}
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
    raise SystemExit(r['status'] in ('TRANSACTION_CAPTURE_INVALID','TRANSACTION_RECORD_BLOCKED'))
