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
import stock_cnss_cycle0203 as previous
from stock_cnss_bundle import verified_inputs, extract_accepted, write_integrity, sha
ROOT=prior.ROOT
HEAD=prior.HEAD
ROLES=prior.ROLES

def reviewed_contract():
    return json.loads((ROOT/'docs/research/popsicle-evidence0204-phone-receipt.json').read_text())['completed203_contract']

def policy():
    p,a=previous.policy()
    receipt=json.loads((ROOT/'docs/research/popsicle-evidence0204-phone-receipt.json').read_text())
    if (receipt['status']!='CANDIDATE_HAL_NETWORK_VALIDATION_AND_STOCK_RECOVERY_CORROBORATED_EXPLICIT_SCAN_FAILED_AT_TEARDOWN' or
        receipt['uploads']['xairdrop-0204-evidence.tar.gz']!='ff793f479466f4e9ce9c9da04adaad335e939a97d9f9bb74de907897dfd73276' or
        receipt['current_stock_cnss2_wlan_notes_match'] is not True or receipt['current_provider_absent'] is not True or
        receipt['current_android_validated'] is not True or receipt['explicit_scan_success_certified'] is not False or
        reviewed_contract()['manifest_sha256']!='dac59a7c2ec97c849cf3094e4aee4c7482b4832b2412818ca309ecf95a8caa7e'):
        raise ValueError('Require reviewed203 roundtrip, current stock recovery and request-specific teardown evidence')
    return p,a

def render(bundle,checked,accepted,gate,p,a):
    previous.render(bundle,checked,accepted,gate,p,a)
    if sha(bundle/'deployment.tsv')!=reviewed_contract()['manifest_sha256']:
        raise ValueError('Reviewed203 manifest differs from independently rendered historical profile')
    for f in list(bundle.iterdir()):
        if f.name in {'kernel','stage-io.sh','LICENSE','candidate-records.json','stock-cnss-imports.json','deployment.tsv'}:continue
        f.unlink()
    source_dir=ROOT/'tools/device/cycle-0205'
    expected={'cycle-engine.sh','scan-io.sh','cycle-io.sh','cyclectl.sh','action.sh','service.sh','customize.sh','module.prop','skip_mount'}
    if {x.name for x in source_dir.iterdir()}!=expected:raise ValueError('Unexpected package scope')
    for f in source_dir.iterdir():
        if f.is_symlink() or not f.is_file():raise ValueError('Unexpected package member')
        shutil.copyfile(f,bundle/f.name)
    values=dict(line.split('\t',1) for line in (bundle/'deployment.tsv').read_text().splitlines())
    values.update(schema='9',profile='stage0205-scan-completion-cycle')
    values.update({'reviewed203.'+k:v for k,v in reviewed_contract().items()})
    (bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
    (bundle/'CHECK_FIRST.txt').write_text(
        '0205 SAME MODULE ID xairdrop17_cycle0195. Explicit diagnostic only.\n'
        'Installer/Action check only; no automatic boot loading, Apple service or init_boot write.\n'
        'archive-0203 preserves the exact reviewed HAL roundtrip record by rename.\n'
        'cycle saves scan/Wi-Fi baseline, disables scan, confirms a stopped HAL interval,\n'
        'then starts candidate HAL/Wi-Fi, waits for one uniquely correlated scan result, stops HAL and restores stock.\n'
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
    return {'stage':'0205','status':'REQUEST_CORRELATED_SCAN_PHONE_PENDING','module_id':'xairdrop17_cycle0195',
            'version_code':205,'sha256':sha(output),'bytes':output.stat().st_size,'candidate_source_commit':HEAD,
            'cycle_enabled':True,'apply_enabled':False,'autostart':False,'native_failure_auto_rollback':False,
            'driver_bytes_rewritten':False,'phone_executed':False,'runtime_certified':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--full',type=Path,required=True);p.add_argument('--compact',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=build(a.full,a.compact,a.output);a.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
