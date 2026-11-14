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
import stock_cnss_cycle0195 as previous
from stock_cnss_bundle import verified_inputs, extract_accepted, write_integrity, sha
ROOT=prior.ROOT
HEAD=prior.HEAD
ROLES=prior.ROLES

def legacy_contract():
    return {'boot_id':'1ec1a3c5-b1af-4896-b625-3bb7b63a4ff2',
            'manifest_sha256':'46a964d7a416c8b56034bfe0df37ec641ff090710cc2623da4272ca69e751853',
            'commands.log.sha256':'f05c474a242f4baa56e93f87e6a4240ef81c4d14dcfc1d5a017ce36324bf14cc',
            'kernel.before.log.sha256':'50b878dbca8468e48d6cea22d01ea63c563837a162da1cd0f984120d9eacaa75',
            'kernel.after.log.sha256':'88f2136296db5cf230a80cad61e7da502e461eadbffba7b1d8cd94779fa12801'}

def policy():
    p,a=previous.policy()
    receipt=json.loads((ROOT/'docs/research/popsicle-hal-probe0196-phone-receipt.json').read_text())
    incident=json.loads((ROOT/'docs/research/popsicle-hal-restart-0196.json').read_text())
    if (receipt['status']!='PHONE_REPORTED_STOCK_HAL_STABILITY_AND_BASELINE_RESTORE_PASS' or
        receipt['receipt_sha256']!='8ea503274a4e014cc56e6f39e015182c54ef1506908b30bb9cac54dd63f4b8a7' or
        receipt['stopped_samples']!=10 or receipt['sample_indices']!=list(range(10)) or
        receipt['stable_marker_observed'] is not True or receipt['restoration_marker_observed'] is not True or
        receipt['old_0195_cycle_retry_authorized'] is not False or
        incident['evidence_sha256']!='c634f1e87047e9720800af0eda00f19db7fe345979c52de2040de1e43c4d4f82' or
        incident['transaction_manifest_sha256']!=legacy_contract()['manifest_sha256'] or
        incident['last_phase']!='returned:insert-provider:1' or
        incident['native_load_restore_certified'] is not False):
        raise ValueError('Require exact failure evidence and phone-returned stock-only HAL interval')
    return p,a

def render(bundle,checked,accepted,gate,p,a):
    previous.render(bundle,checked,accepted,gate,p,a)
    if sha(bundle/'deployment.tsv')!=legacy_contract()['manifest_sha256']:
        raise ValueError('Old failure manifest is not the independently rendered original 0195 profile')
    for f in list(bundle.iterdir()):
        if f.name in {'kernel','stage-io.sh','LICENSE','candidate-records.json','stock-cnss-imports.json','deployment.tsv'}:continue
        f.unlink()
    source_dir=ROOT/'tools/device/cycle-0197'
    expected={'cycle-engine.sh','cycle-io.sh','cyclectl.sh','action.sh','service.sh','customize.sh','module.prop','skip_mount'}
    if {x.name for x in source_dir.iterdir()}!=expected:raise ValueError('Unexpected package scope')
    for f in source_dir.iterdir():
        if f.is_symlink() or not f.is_file():raise ValueError('Unexpected package member')
        shutil.copyfile(f,bundle/f.name)
    values=dict(line.split('\t',1) for line in (bundle/'deployment.tsv').read_text().splitlines())
    values.update(schema='5',profile='stage0197-scan-guard-cycle')
    values.update({'legacy195.'+k:v for k,v in legacy_contract().items()})
    (bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
    (bundle/'CHECK_FIRST.txt').write_text(
        '0197 SAME MODULE ID xairdrop17_cycle0195. Explicit diagnostic only.\n'
        'Installer/Action check only; no automatic boot loading, Apple service or init_boot write.\n'
        'archive-0195 preserves only the exact reviewed prior-boot failed record by rename.\n'
        'cycle saves scan/Wi-Fi baseline, disables scan, confirms a stopped HAL interval,\n'
        'then performs a fixed diagnostic WLAN/provider round trip retaining stock CNSS2.\n'
        'Every readiness gate is labelled. No native operation is retried after failure.\n'
        'Framework-only cleanup requires exact original WLAN present and provider absent.\n'
        'Otherwise disable trial/reboot, then use recover-settings; never delete failed state.\n'
        'New driver loading/restoration and Apple transfer remain phone-unqualified.\n')
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
    return {'stage':'0197','status':'SCAN_GUARDED_DIAGNOSTIC_PHONE_PENDING','module_id':'xairdrop17_cycle0195',
            'version_code':197,'sha256':sha(output),'bytes':output.stat().st_size,'candidate_source_commit':HEAD,
            'cycle_enabled':True,'apply_enabled':False,'autostart':False,'native_failure_auto_rollback':False,
            'driver_bytes_rewritten':False,'phone_executed':False,'runtime_certified':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--full',type=Path,required=True);p.add_argument('--compact',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=build(a.full,a.compact,a.output);a.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
