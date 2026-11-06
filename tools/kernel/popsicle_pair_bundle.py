#!/usr/bin/env python3
"""Prepare a manual runtime trial bundle from the exact accepted 0130 pair.

No download, kernel action, module rewriting/stripping, partition write or
installation occurs here. The output is experimental, not runtime-certified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
from module_exports import export_records, load
from module_abi import inspect
ROOT=Path(__file__).resolve().parents[2]
NAMES={'provider':'opairshare_wonder_provider','cnss2':'cnss2','wlan':'qca_cld3_peach_v2'}
SCRIPTS=['popsicle-pairctl.sh','popsicle-pair-engine.sh']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def note_hash(path):
    data,sections=load(path)
    notes=[s for s in sections if s['name']=='.note.gnu.build-id' and s['type']==7]
    if len(notes)!=1:raise ValueError('Missing or ambiguous loaded-identity build-id note: '+str(path))
    note=notes[0];start=note['off'];end=start+note['size']
    if start<0 or end>len(data) or end<=start:raise ValueError('Truncated build-id note')
    return hashlib.sha256(data[start:end]).hexdigest()

def verified_inputs(pair,acceptance,policy):
    if acceptance.get('phone_executed') is not False or acceptance.get('pair_result_accepted') is not True:
        raise ValueError('Requires accepted offline 0130 evidence with explicit runtime limitation')
    report=acceptance['pair_report']
    if report['status']!='CHECKED_PLATFORM_PAIR_LINK_AND_RECORDED_CHECKS_ONLY' or not report['paired_WLAN_built']:
        raise ValueError('Incomplete checked pair')
    if report['CRC_gate_waived'] or report['radio_backend_activation_enabled']:
        raise ValueError('Relaxed ABI gate or radio activation is not accepted')
    if not report['export_surface']['match'] or report['export_surface']['legacy_count']!=81:
        raise ValueError('Stock CNSS2 export records must match')
    if not acceptance.get('provider_control_parameter_owner_and_ops_relocations_verified'):
        raise ValueError('Missing verified external control parameter wiring')
    if acceptance.get('provider_control_parameter_permission')!='0200':raise ValueError('Wrong control permission')
    if policy['schema']!=1 or policy['device']!='popsicle':raise ValueError('Wrong device policy')
    loader_path=ROOT/'kernel/abi/popsicle-stock-loader.json'
    loader=json.loads(loader_path.read_text())
    if sha(loader_path)!=policy['loader_evidence_sha256'] or loader['kernel_sha256']!=policy['loader_kernel_sha256'] or loader['boot_sha256']!=policy['boot_sha256']:
        raise ValueError('Stock loader/active boot policy changed')
    result={}
    for role,name in NAMES.items():
        path=pair/'binaries'/(name+'.ko')
        if path.is_symlink() or not path.is_file():raise ValueError('Expected regular module: '+name)
        if sha(path)!=report['modules'][role]['sha256']:raise ValueError('Accepted module SHA mismatch: '+name)
        module=inspect(path)
        if module['modinfo'].get('name')!=[name]:raise ValueError('Wrong module name: '+name)
        record=report['modules'][role]
        if module['modinfo'].get('vermagic')!=record['vermagic']:raise ValueError('Candidate header changed from accepted ELF: '+name)
        if not record.get('vermagic_stock_loader_match') or record.get('stock_loader_kernel_sha256')!=policy['loader_kernel_sha256']:
            raise ValueError('Missing exact recorded stock-loader basis: '+name)
        result[role]={'path':path,'name':name,'sha256':report['modules'][role]['sha256'],'note_sha256':note_hash(path)}
    required='opairshare_wlan_live_unload_arm_v1'
    exports=export_records(result['provider']['path']);versions=inspect(result['wlan']['path'])['versions']
    if required not in exports or required not in versions or versions[required]!=exports[required]['crc']:
        raise ValueError('Strong live arm import mismatch')
    return result

def build(pair,output,acceptance=None,policy=None):
    acceptance=acceptance or json.loads((ROOT/'docs/research/popsicle-live-unload-0130-validation.json').read_text())
    policy=policy or json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
    modules=verified_inputs(pair,acceptance,policy)
    if output.exists():raise ValueError('Output already exists; no replacement')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        bundle=Path(tmp)/'pair';(bundle/'kernel').mkdir(parents=True)
        values={'schema':'1','device':policy['device'],'firmware':policy['firmware'],'kernel':policy['kernel_release'],
                'runtime_certified':'false','boot_sha256':policy['boot_sha256'],'source_commit':acceptance['source_commit']}
        for role,m in modules.items():
            copied=bundle/'kernel'/(m['name']+'.ko');shutil.copyfile(m['path'],copied)
            if sha(copied)!=m['sha256']:raise ValueError('Module changed while staging: '+m['name'])
            m['note_sha256']=note_hash(copied)
            for field in ['sha256','note_sha256']:values['candidate.'+m['name']+'.'+field]=m[field]
        for name,record in policy['stock'].items():
            for field in ['sha256','note_sha256']:values['stock.'+name+'.'+field]=record[field]
        for name in SCRIPTS:shutil.copyfile(ROOT/'tools/device'/name,bundle/name)
        (bundle/'deployment.tsv').write_text(''.join(k+'\t'+values[k]+'\n' for k in sorted(values)))
        (bundle/'acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
        (bundle/'README.txt').write_text('0131 manual runtime trial preparation. No automatic installation.\n'
            'Not a Magisk/KernelSU installer. Private ABI, native loader/sysfs/file drain and RF are not certified.\n'
            'Run check first. backup only copies audited stock files. apply changes runtime modules; restore is allowed only from a healthy ACTIVE transaction.\n'
            'Any interrupted intent or failed effect blocks replay. Never force-unload, reset references or retry an unknown graph.\n'
            'Original files/partitions/startup are untouched; reboot is the fail-stop recovery path. Preserve the transaction journal.\n'
            'A provider lifetime is one-shot: removal/recreation is required before another matched WLAN load.\n')
        paths=sorted(p for p in bundle.rglob('*') if p.is_file())
        (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(bundle).as_posix()+'\n' for p in paths))
        staged=Path(tmp)/'bundle.zip'
        with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(bundle.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(bundle).as_posix())
        # Exclusive link prevents overwriting an output created concurrently.
        import os
        os.link(staged,output)
    return {'status':'EXPERIMENTAL_MANUAL_PAIR_BUNDLE_PREPARED_ONLY','sha256':sha(output),'size':output.stat().st_size,
            'source_commit':acceptance['source_commit'],'runtime_certified':False,'phone_executed':False}



def write_checker_update(bundle_path,output_dir,baseline=None,policy=None):
    """Stage only the two changed files and their complete checksum list.

    Any change to a retained file, kernel module or other manifest identity
    rejects this small update. The user keeps the original audited drivers.
    """
    baseline=baseline or json.loads((ROOT/'kernel/abi/popsicle-checker-base-0131.json').read_text())
    policy=policy or json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
    allowed={'popsicle-pairctl.sh','deployment.tsv'}
    with zipfile.ZipFile(bundle_path) as z:
        names=[n.filename for n in z.infolist()]
        if len(names)!=len(set(names)) or set(names)!=set(baseline['files'])|{'SHA256SUMS'}:
            raise ValueError('Unexpected update bundle members')
        checks={}
        for line in z.read('SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            if name in checks or len(digest)!=64:raise ValueError('Invalid checksum list')
            checks[name]=digest
        if set(checks)!=set(baseline['files']):raise ValueError('Incomplete update checksums')
        for name,digest in checks.items():
            h=hashlib.sha256()
            with z.open(name) as f:
                while data:=f.read(1024*1024):h.update(data)
            if h.hexdigest()!=digest:raise ValueError('Corrupt update member: '+name)
            if name not in allowed and digest!=baseline['files'][name]:
                raise ValueError('Small update would change retained file: '+name)
        rows=[line.split('\t',1) for line in z.read('deployment.tsv').decode().splitlines()]
        manifest=dict(rows)
        if len(rows)!=len(manifest):raise ValueError('Duplicate update manifest keys')
        expected=dict(baseline['manifest']);expected['kernel']=policy['kernel_release']
        if manifest!=expected:raise ValueError('Small update changed non-kernel-release identity')
        if z.read('popsicle-pairctl.sh')!=(ROOT/'tools/device/popsicle-pairctl.sh').read_bytes():
            raise ValueError('Checker does not match current source')
        output_dir.mkdir(parents=True,exist_ok=False)
        for name in sorted(allowed|{'SHA256SUMS'}):(output_dir/name).write_bytes(z.read(name))
    return {'status':'CHECKER_DATA_ONLY_UPDATE','files':sorted(allowed|{'SHA256SUMS'}),'retained_module_bytes_changed':False,'base_bundle_sha256':baseline['bundle_sha256']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pair',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--checker-update',type=Path)
    a=p.parse_args();result=build(a.pair,a.output)
    if a.checker_update:result['checker_update']=write_checker_update(a.output,a.checker_update)
    print(json.dumps(result,indent=2))
