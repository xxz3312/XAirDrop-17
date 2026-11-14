#!/usr/bin/env python3
"""Independently audit and package a one-shot diagnostic load/restore trial."""
import argparse
import json
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile
import stock_cnss_stage0194 as prior
from stock_cnss_bundle import verified_inputs, extract_accepted, write_integrity, sha
ROOT=prior.ROOT
HEAD=prior.HEAD
ROLES=prior.ROLES

def policy():
    profile,archive=prior.policy()
    receipt=json.loads((ROOT/'docs/research/popsicle-stage0194-phone-receipt.json').read_text())
    if (receipt['status']!='PHONE_REPORTED_CHECK_BACKUP_SUCCESS' or
        receipt['firmware']!=profile['firmware'] or
        receipt['receipt_sha256']!='04b2d29ae96c59dd8ad2db0be631d668b50a3b8bd47f277fc0a666974787f077' or
        receipt['source_commit']!='d91e33ed207a6c3b90927242eb7d6ad15fd61c12' or
        receipt['backup_path']!='/data/adb/xairdrop17-stage0194-backup' or
        receipt['markers']!=['STAGE0194_CHECK_PASS_ONLY','STAGE0194_BACKUP_VERIFIED_ONLY_NO_DRIVER_EFFECTS'] or
        receipt['apply_enabled'] is not False or receipt['driver_loading_observed'] is not False):
        raise ValueError('Require exact phone-returned 0194 check/backup evidence')
    return profile,archive

def render(bundle,checked,accepted,gate,profile,archive):
    # Reuse the exact 0194 evidence renderer to bind its immutable backup manifest.
    prior.render(bundle,checked,accepted,gate,profile,archive)
    old_manifest=sha(bundle/'deployment.tsv')
    for file in list(bundle.iterdir()):
        if file.name in {'stage-io.sh','kernel','LICENSE','candidate-records.json','stock-cnss-imports.json','deployment.tsv'}:continue
        file.unlink()
    source_dir=ROOT/'tools/device/cycle-0195'
    expected={'cycle-engine.sh','cycle-io.sh','cyclectl.sh','action.sh','service.sh','customize.sh','module.prop','skip_mount'}
    if {x.name for x in source_dir.iterdir()}!=expected:raise ValueError('Unexpected cycle payload')
    for source in source_dir.iterdir():
        if source.is_symlink() or not source.is_file():raise ValueError('Unexpected cycle source')
        shutil.copyfile(source,bundle/source.name)
    values=dict(line.split('\t',1) for line in (bundle/'deployment.tsv').read_text().splitlines())
    values.update(schema='4',profile='stage0195-diagnostic-cycle',cycle_enabled='true',
                  stage0194_manifest_sha256=old_manifest)
    (bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
    (bundle/'CHECK_FIRST.txt').write_text(
        '0195 MANUAL DIAGNOSTIC ROUND TRIP ONLY; NOT AIRDROP ENABLEMENT.\n'
        'Action/installer check only. Boot does nothing. Stock CNSS2 and init_boot retained.\n'
        'Explicit cycle stops Wi-Fi/HAL, replaces WLAN/provider, validates module identity,\n'
        'then removes the diagnostic pair and restores original WLAN and baseline.\n'
        'No candidate module arguments, RF/START/sysfs controls or native Apple service.\n'
        'Any failure stops; preserve state and logs, disable trial and reboot. Never retry.\n'
        'Do not delete 0194 backup or 0193 archive. No partial automatic rollback.\n')
    write_integrity(bundle)

def build(full,compact,output):
    if output.exists():raise ValueError('Output exists; refuse overwrite')
    profile,archive=policy()
    evidence=json.loads((ROOT/'docs/research/popsicle-candidate-0188-ci.json').read_text())
    accepted=prior.candidate_audit(full,compact,evidence,HEAD)
    if accepted!=json.loads((ROOT/'docs/research/popsicle-candidate-0188-validation.json').read_text()):
        raise ValueError('Actual immutable candidate audit changed')
    compatible={'actual_module_records':accepted['actual_module_records'],
        'actual_private_provider_import_CRCs_match':{'qca_cld3_peach_v2':accepted['actual_private_provider_imports']},
        'full_artifact_sha256':accepted['archives']['full']['sha256']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        tmp=Path(tmp);modules=tmp/'modules';modules.mkdir()
        extract_accepted(full,modules,compatible);checked,gate=verified_inputs(modules,compatible)
        bundle=tmp/'bundle';render(bundle,checked,accepted,gate,profile,archive)
        staged=tmp/'cycle.zip'
        with zipfile.ZipFile(staged,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for file in sorted(x for x in bundle.rglob('*') if x.is_file()):
                info=zipfile.ZipInfo(str(file.relative_to(bundle)),date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(stat.S_IFREG|(0o700 if file.suffix=='.sh' else 0o600))<<16
                with file.open('rb') as src,z.open(info,'w') as dst:shutil.copyfileobj(src,dst,1024*1024)
        shutil.move(staged,output)
    return {'stage':'0195','status':'DIAGNOSTIC_CYCLE_TRIAL_PHONE_PENDING','sha256':sha(output),
            'bytes':output.stat().st_size,'candidate_source_commit':HEAD,'cycle_enabled':True,
            'apply_enabled':False,'autostart':False,'runtime_certified':False,
            'partial_failure_live_recovery':False,'phone_executed':False,'driver_bytes_rewritten':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--full',type=Path,required=True);p.add_argument('--compact',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=build(a.full,a.compact,a.output)
    a.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
