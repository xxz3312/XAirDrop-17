#!/usr/bin/env python3
"""Build a separate candidate check/backup KSU package; no driver loading route."""
import argparse
import json
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile
from stock_cnss_candidate_audit import audit as candidate_audit
from stock_cnss_bundle import verified_inputs, extract_accepted, write_integrity, sha
ROOT=Path(__file__).resolve().parents[2]
HEAD='a4b9404257efe395cf3cf865a806bff5daba6f4b'
ROLES={'wlan':'qca_cld3_peach_v2','opairshare_wonder_provider':'opairshare_wonder_provider'}

def policy():
    p=json.loads((ROOT/'docs/research/popsicle-stock-4.0.6-0193.json').read_text())
    receipt=json.loads((ROOT/'docs/research/popsicle-0193-archive-receipt.json').read_text())
    old=json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
    if (p['status']!='ARCHIVE_RECORD_PROFILE_ONLY' or p['firmware']!='OS4.0.6.0.XPBCNXM' or
        p['boot_sha256']!='84e5aded3a181265b4a53132d3e4aafa29a8946112b166b8bc78f0724da390e8' or
        p['kernel_sha256']!=old['loader_kernel_sha256'] or p['kernel_release']!=old['kernel_release'] or
        p['stock']!=old['stock'] or p['device']!=old['device'] or
        p['boot_comparison']['status']!='KERNEL_PAYLOAD_MATCH_ONLY' or
        p['boot_comparison']['kernel_payload_matches_old_capture'] is not True or
        p['boot_comparison']['boot_sha256']!=p['boot_sha256'] or
        p['boot_comparison']['kernel_sha256']!=p['kernel_sha256'] or
        p['deployment_load_qualified'] is not False or p['runtime_certified'] is not False or
        receipt['status']!='PHONE_REPORTED_ARCHIVE_SUCCESS' or
        receipt['load_authorized'] is not False or receipt['runtime_certified'] is not False or
        receipt['receipt_sha256']!='823ba96ecfef655b76e2b222b5aab3b3f657f42c1b1b0776807c8e4ddb502475' or
        receipt['archive_path']!='/data/adb/xairdrop17-stockcnss-transaction.previous.0193.'+p['expected_record']['boot_id']):
        raise ValueError('Exact current component/archive evidence required; no old profile retarget')
    return p,receipt

def render(bundle,checked,accepted,gate,p,receipt):
    (bundle/'kernel').mkdir(parents=True)
    values={'schema':'3','profile':'stage0194-check-backup','mode':'diagnostic-defaults',
            'device':p['device'],'firmware':p['firmware'],'kernel':p['kernel_release'],
            'boot_sha256':p['boot_sha256'],'runtime_certified':'false','apply_enabled':'false',
            'source_commit':HEAD,'prior_archive_path':receipt['archive_path'],
            'prior_boot_id':p['expected_record']['boot_id'],
            'prior_manifest_sha256':p['expected_record']['manifest_sha256']}
    for role,name in ROLES.items():
        item=checked[role];target=bundle/'kernel'/(name+'.ko');shutil.copyfile(item['path'],target)
        if sha(target)!=item['record']['sha256']:raise ValueError('Raw ELF changed while staging')
        for field in ('sha256','note_sha256'):values[f'candidate.{name}.{field}']=item['record'][field]
    for name,record in p['stock'].items():
        for field in ('sha256','note_sha256'):values[f'stock.{name}.{field}']=record[field]
    source_dir=ROOT/'tools/device/stage-0194'
    if {x.name for x in source_dir.iterdir()}!={'stagectl.sh','stage-io.sh','action.sh','service.sh','customize.sh','module.prop','skip_mount'}:
        raise ValueError('Unexpected installer/boot payload scope')
    for source in source_dir.iterdir():
        if not source.is_file() or source.is_symlink():raise ValueError('Unexpected stage source')
        shutil.copyfile(source,bundle/source.name)
    shutil.copyfile(ROOT/'LICENSE',bundle/'LICENSE')
    (bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
    (bundle/'candidate-records.json').write_text(json.dumps(accepted,indent=2)+'\n')
    (bundle/'stock-cnss-imports.json').write_text(json.dumps(gate,indent=2)+'\n')
    (bundle/'CHECK_FIRST.txt').write_text('0194 CHECK/BACKUP ONLY. No driver loading entry point.\n'
        'Action checks only; installation and boot perform no Wi-Fi/module/service changes.\n'
        'Raw WLAN/provider files retained byte-for-byte for staging identity checks.\n'
        'Old profiles and archived backup are preserved. No init_boot writes.\n'
        'Backup controller: /data/adb/modules/xairdrop17_stage0194/stagectl.sh backup\n'
        'Driver loading and Apple discovery/handshake/transfer are NOT enabled/certified.\n')
    write_integrity(bundle)

def build(full,compact,output):
    if output.exists():raise ValueError('Output exists; refuse overwrite')
    p,receipt=policy()
    evidence=json.loads((ROOT/'docs/research/popsicle-candidate-0188-ci.json').read_text())
    accepted=candidate_audit(full,compact,evidence,HEAD)
    if accepted!=json.loads((ROOT/'docs/research/popsicle-candidate-0188-validation.json').read_text()):
        raise ValueError('Actual candidate audit differs from independently committed result')
    compatible={'actual_module_records':accepted['actual_module_records'],
        'actual_private_provider_import_CRCs_match':{'qca_cld3_peach_v2':accepted['actual_private_provider_imports']},
        'full_artifact_sha256':accepted['archives']['full']['sha256']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        tmp=Path(tmp);modules=tmp/'modules';modules.mkdir()
        extract_accepted(full,modules,compatible)
        checked,gate=verified_inputs(modules,compatible)
        bundle=tmp/'bundle';render(bundle,checked,accepted,gate,p,receipt)
        staged=tmp/'stage.zip'
        with zipfile.ZipFile(staged,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for file in sorted(x for x in bundle.rglob('*') if x.is_file()):
                info=zipfile.ZipInfo(str(file.relative_to(bundle)),date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(stat.S_IFREG|(0o700 if file.suffix=='.sh' else 0o600))<<16
                with file.open('rb') as src,z.open(info,'w') as dst:shutil.copyfileobj(src,dst,1024*1024)
        shutil.move(staged,output)
    return {'stage':'0194','status':'CANDIDATE_CHECK_BACKUP_PACKAGE_ONLY','sha256':sha(output),'bytes':output.stat().st_size,
            'candidate_source_commit':HEAD,'kernel_modules':sorted(n+'.ko' for n in ROLES.values()),
            'apply_enabled':False,'autostart':False,'runtime_certified':False,'old_profile_retargeted':False,
            'phone_installed_or_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full',type=Path,required=True)
    p.add_argument('--compact',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=build(a.full,a.compact,a.output);a.output.with_suffix('.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
