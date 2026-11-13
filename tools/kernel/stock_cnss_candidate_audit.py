#!/usr/bin/env python3
"""Verify immutable CI archives/raw ELF records; never authorize or package a load."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import zipfile
from module_abi import inspect
from module_exports import export_records
from popsicle_modpost import header_layout, stock_loader_evidence
from popsicle_pair_bundle import note_hash
from stock_cnss_audit import audit as cnss_audit
ROOT=Path(__file__).resolve().parents[2]
ROLES={'wonder_sysctl':'wonder_sysctl','opairshare_wonder_provider':'opairshare_wonder_provider',
       'opairshare_route_b_probe':'opairshare_route_b_probe','wonder':'wonder','wlan':'qca_cld3_peach_v2'}
REQUIRED={'transport-stop','ce-stop','htt-callbacks','ce-buffers','diagnostic',
          'stop-admission','bridge-controller','parent-peer-composite'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def verify_ci(evidence,head):
    run=evidence['run']
    if (evidence['repository']!='xxz3312/XAirDrop-17' or run['head_sha']!=head or
        len(head)!=40 or any(c not in '0123456789abcdef' for c in head) or
        run['path']!='.github/workflows/popsicle-build.yml' or
        run['status']!='completed' or run['conclusion']!='success'):
        raise ValueError('Unaccepted source/workflow result')
    jobs=evidence['jobs']
    for name in REQUIRED:
        found=[j for j in jobs if j['name']==name]
        if len(found)!=1 or found[0]['status']!='completed' or found[0]['conclusion']!='success':
            raise ValueError('Missing/ambiguous/failed required job: '+name)
    return run


def verify_archive(path,evidence,kind):
    run=evidence['run'];name=f'popsicle-{kind}-{run["id"]}-{run["run_attempt"]}'
    found=[a for a in evidence['artifacts'] if a['name']==name]
    if len(found)!=1:raise ValueError('Missing/ambiguous artifact: '+name)
    a=found[0]
    if (a['expired'] or a['workflow_run']['id']!=run['id'] or
        a['workflow_run']['head_sha']!=run['head_sha'] or a['size_in_bytes']!=path.stat().st_size or
        a['digest']!='sha256:'+sha(path)):
        raise ValueError('Artifact identity/size/GitHub digest mismatch: '+name)
    return {'id':a['id'],'name':name,'sha256':sha(path),'bytes':path.stat().st_size}


def members(archive):
    names=archive.namelist()
    if len(names)!=len(set(names)) or any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n for n in names):
        raise ValueError('Ambiguous or unsafe ZIP member')
    return names


def verify_record(actual,claimed,role):
    if (claimed['status']!='RECORDED_LOADER_CHECKS_MATCH_ONLY' or
        actual['sha256']!=claimed['sha256'] or
        actual['modinfo'].get('name')!=[ROLES[role]] or
        actual['modinfo'].get('vermagic')!=claimed['vermagic'] or
        len(actual['versions'])!=claimed['version_records'] or
        set(actual['undefined'])-actual['versions'].keys() or
        claimed['version_record_mismatches'] or claimed['undefined_without_version'] or
        not claimed['vermagic_stock_loader_match']):
        raise ValueError('Actual ELF disagrees with accepted CI record: '+role)


def audit(full,compact,evidence,head):
    run=verify_ci(evidence,head)
    archives={'full':verify_archive(full,evidence,'diagnostics'),
              'compact':verify_archive(compact,evidence,'validation')}
    with zipfile.ZipFile(full) as f,zipfile.ZipFile(compact) as c,tempfile.TemporaryDirectory() as tmp:
        fn=members(f);cn=members(c);reports={}
        full_json={n.removeprefix('reports/') for n in fn if n.startswith('reports/') and n.endswith('.json')}
        compact_json={n for n in cn if n.endswith('.json')}
        if full_json!=compact_json:raise ValueError('Full/compact JSON scope differs')
        for n in sorted(compact_json):
            a=f.read('reports/'+n);b=c.read(n)
            if a!=b:raise ValueError('Full/compact JSON bytes differ: '+n)
            reports[n]=json.loads(a)
        trial=reports['module-trial.json'];stock_report=reports['stock-cnss-imports.json']
        if (trial['status']!='RECORDED_LOADER_CHECKS_MATCH_ONLY' or trial['wlan_unresolved'] or
            set(trial['modules'])!=set(ROLES)):
            raise ValueError('Unaccepted module-trial scope/result')
        paths={};want={name+'.ko':role for role,name in ROLES.items()}
        with f.open('diagnostic-modules-not-for-install.tar.gz') as stream,tarfile.open(fileobj=stream,mode='r|gz') as t:
            for m in t:
                if m.name not in want or not m.isfile() or m.name in paths:
                    raise ValueError('Unexpected/duplicate/nonregular raw ELF: '+m.name)
                p=Path(tmp)/m.name
                with t.extractfile(m) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst)
                paths[m.name]=p
        if set(paths)!=set(want):raise ValueError('Incomplete raw module archive')
        header=json.loads((ROOT/'kernel/abi/popsicle-stock-module-header.json').read_text())
        stock=json.loads((ROOT/'kernel/abi/popsicle-stock-exports.json').read_text())
        loader=stock_loader_evidence(header)
        records={};modules={}
        for role,name in ROLES.items():
            path=paths[name+'.ko'];m=inspect(path);claim=trial['modules'][role]
            verify_record(m,claim,role)
            if header_layout(path)!=header['layout'] or claim['layout']!=header['layout']:
                raise ValueError('Actual module header differs from captured stock: '+role)
            if claim['stock_loader_kernel_sha256']!=loader['kernel_sha256']:
                raise ValueError('Loader report not bound to captured kernel: '+role)
            records[role]={'sha256':m['sha256'],'note_sha256':note_hash(path),'bytes':path.stat().st_size,
                'version_records':len(m['versions']),'dependencies':m['modinfo'].get('depends',[]),
                'vermagic':m['modinfo']['vermagic'],'vermagic_exact_match':claim['vermagic_exact_match'],
                'header_layout':header_layout(path)}
            modules[role]=m
        gate=cnss_audit(modules['wlan'],stock)
        if gate!=stock_report or gate['status']!='STOCK_CNSS2_IMPORTS_MATCH_ONLY':
            raise ValueError('Independent stock CNSS2 import audit differs/rejects')
        provider=export_records(paths[ROLES['opairshare_wonder_provider']+'.ko'])
        private=sorted(set(modules['wlan']['undefined']) & provider.keys())
        if not private or any(modules['wlan']['versions'][n]!=provider[n]['crc'] for n in private):
            raise ValueError('Actual private provider imports/CRCs disagree')
        layouts=reports['selected-layouts.json']
        if (set(layouts['types'])!={'module','net_device','wiphy','wireless_dev','sk_buff','cfg80211_chan_def','ieee80211_channel'} or
            layouts['status']!='SELECTED_LAYOUTS_MATCH_ONLY' or
            layouts['candidate_module_sha256']!=modules['wlan']['sha256'] or
            any(x['status']!='MATCH' for x in layouts['types'].values())):
            raise ValueError('Selected-layout report is not bound to this WLAN')
    return {'stage':'0188','status':'CANDIDATE_RECORDS_VERIFIED_NOT_FOR_INSTALL',
        'source_commit':head,'workflow_run':run['id'],'required_jobs_success':len(REQUIRED),
        'archives':archives,'identical_json_reports':len(reports),'actual_module_records':records,
        'cnss2_import_count':len(gate['cnss2_imports']),'cnss2_crc_mismatches':gate['crc_errors'],
        'forbidden_checked_or_live_imports':gate['forbidden_checked_or_live_imports'],
        'actual_private_provider_imports':private,'captured_firmware':stock['firmware'],
        'selected_layout_report_types':sorted(layouts['types']),
        'runtime_certified':False,'phone_executed':False,'load_authorized':False,
        'deployment_bundle_created':False,'old_0135_bundle_retargeted':False,
        'remaining':['Fresh phone/kernel/firmware/CNSS2 identity must match the captured target.',
          'A new independently qualified deployment profile/executor is required; old bundle remains pinned.',
          'Native unload/load and reboot recovery still require staged device acceptance.'],
        'limitations':'Actual archive digests, raw ELF identities/notes/version coverage/module header, '
          'stock CNSS2 imports and private provider CRCs independently checked. Full kernel CRC comparisons '
          'and selected private layouts are retained CI evidence, not independently rederived here. '
          'No C declaration/KCFI/full ABI/firmware/unload/load/RF/Apple compatibility certification.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full',type=Path,required=True)
    p.add_argument('--compact',type=Path,required=True);p.add_argument('--ci-evidence',type=Path,required=True)
    p.add_argument('--source-commit',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.full,a.compact,json.loads(a.ci_evidence.read_text()),a.source_commit)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status']);print('Raw ELF records:',len(result['actual_module_records']))
