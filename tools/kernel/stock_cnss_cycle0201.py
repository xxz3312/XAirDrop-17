#!/usr/bin/env python3
"""Same-ID scan-aware trial; preserved previous failure is never replayed."""
import argparse
import json
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile
import stock_cnss_stage0194 as prior
import stock_cnss_cycle0199 as previous
from stock_cnss_bundle import verified_inputs, extract_accepted, write_integrity, sha
ROOT=prior.ROOT
HEAD=prior.HEAD
ROLES=prior.ROLES

def completed_contract():
    return json.loads((ROOT/'docs/research/popsicle-success0200-phone-receipt.json').read_text())['completed199_contract']

def policy():
    p,a=previous.policy()
    receipt=json.loads((ROOT/'docs/research/popsicle-success0200-phone-receipt.json').read_text())
    if (receipt['status']!='COMPLETED_0199_KERNEL_EVIDENCE_AND_RESTORED_VALIDATED_WIFI_VERIFIED' or
        receipt['uploads']['xairdrop-0200-evidence.tar.gz']!='81decaddfa23391037af04cfa2ae9ef2c1619aa51ab78fbfce1bf63fc3ba66a7' or
        receipt['current_stock_note_hashes']['cnss2']!=p['stock']['cnss2']['note_sha256'] or
        receipt['current_provider_absent'] is not True or receipt['android_network_validated'] is not True or
        receipt['candidate_hal_started_in_0199'] is not False or
        completed_contract()['manifest_sha256']!='f802766c9d7120b438f8c03a315fb49549782aee955f4fdb22b27acc0168b551'):
        raise ValueError('Require exact completed diagnostic, kernel evidence and restored validated stock Wi-Fi')
    return p,a

def render(bundle,checked,accepted,gate,p,a):
    previous.render(bundle,checked,accepted,gate,p,a)
    if sha(bundle/'deployment.tsv')!=completed_contract()['manifest_sha256']:
        raise ValueError('Old failure manifest is not the independently rendered original 0199 profile')
    for f in list(bundle.iterdir()):
        if f.name in {'kernel','stage-io.sh','LICENSE','candidate-records.json','stock-cnss-imports.json','deployment.tsv'}:continue
        f.unlink()
    source_dir=ROOT/'tools/device/cycle-0201'
    expected={'cycle-engine.sh','cycle-io.sh','cyclectl.sh','action.sh','service.sh','customize.sh','module.prop','skip_mount'}
    if {x.name for x in source_dir.iterdir()}!=expected:raise ValueError('Unexpected package scope')
    for f in source_dir.iterdir():
        if f.is_symlink() or not f.is_file():raise ValueError('Unexpected package member')
        shutil.copyfile(f,bundle/f.name)
    values=dict(line.split('\t',1) for line in (bundle/'deployment.tsv').read_text().splitlines())
    values.update(schema='7',profile='stage0201-candidate-hal-cycle')
    values.update({'completed199.'+k:v for k,v in completed_contract().items()})
    (bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
    (bundle/'CHECK_FIRST.txt').write_text(
        '0201 SAME MODULE ID xairdrop17_cycle0195. Explicit diagnostic only.\n'
        'Installer/Action check only; no automatic boot loading, Apple service or init_boot write.\n'
        'archive-0199 preserves only the exact reviewed completed diagnostic by rename.\n'
        'cycle saves scan/Wi-Fi baseline, disables scan, confirms a stopped HAL interval,\n'
        'then starts candidate HAL/Wi-Fi, observes association/scans, stops HAL and restores stock.\n'
        'Every readiness gate is labelled. No native operation is retried after failure.\n'
        'Framework-only cleanup requires exact original WLAN present and provider absent.\n'
        'Otherwise disable trial/reboot, then use recover-settings; never delete failed state.\n'
        'Candidate HAL/association and scan observations remain phone-unqualified; no Apple services.\n')
    write_integrity(bundle)

def build(full,compact,output):
    if output.exists():raise ValueError('Output exists')
    p,a=policy();evidence=json.loads((ROOT/'docs/research/popsicle-candidate-0188-ci.json').read_text())
    accepted=prior.candidate_audit(full,compact,evidence,HEAD)
    if accepted!=json.loads((ROOT/'docs/research/popsicle-candidate-0188-validation.json').read_text()):
        raise ValueError('Actual immutable candidate audit changed')
    compatible={'actual_module_records':accepted['actual_module_records'],
        'actual_private_provider_import_CRCs_match':{'qca_cld3_peach_v2':accepted['actual_private_provider_imports']},
        'full_artifact_sha256':accepted['archives']['full']['sha256']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as d:
        d=Path(d);mods=d/'modules';mods.mkdir();extract_accepted(full,mods,compatible)
        checked,gate=verified_inputs(mods,compatible);bundle=d/'bundle';render(bundle,checked,accepted,gate,p,a)
        staged=d/'cycle.zip'
        with zipfile.ZipFile(staged,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for f in sorted(x for x in bundle.rglob('*') if x.is_file()):
                info=zipfile.ZipInfo(str(f.relative_to(bundle)),date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(stat.S_IFREG|(0o700 if f.suffix=='.sh' else 0o600))<<16
                with f.open('rb') as src,z.open(info,'w') as dst:shutil.copyfileobj(src,dst,1024*1024)
        shutil.move(staged,output)
    return {'stage':'0201','status':'CANDIDATE_HAL_LIFECYCLE_PHONE_PENDING','module_id':'xairdrop17_cycle0195',
            'version_code':201,'sha256':sha(output),'bytes':output.stat().st_size,'candidate_source_commit':HEAD,
            'cycle_enabled':True,'apply_enabled':False,'autostart':False,'native_failure_auto_rollback':False,
            'driver_bytes_rewritten':False,'phone_executed':False,'runtime_certified':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--full',type=Path,required=True);p.add_argument('--compact',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=build(a.full,a.compact,a.output);a.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
