#!/usr/bin/env python3
"""Strict actual-target CNSS2/provider/WLAN pair build; never install or load."""
import ast
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import shutil
from module_abi import inspect, symvers
from module_exports import export_records
from popsicle_modpost import write_inputs, merge_generated_exports, module_report
from popsicle_ci import REPO, download
from popsicle_transport_audit import audit as transport_audit


def check_export_surface(original, actual, required):
    missing=sorted(set(original)-actual.keys())
    changed={n:{'stock':record,'actual':actual.get(n)} for n,record in original.items()
             if n in actual and actual[n]!=record}
    extra=sorted(set(actual)-set(original)-{required})
    checked=actual.get(required)
    checked_valid=bool(checked and checked.get('export_type')=='EXPORT_SYMBOL'
                       and checked.get('namespace')=='')
    return {'match':not missing and not changed and not extra and checked_valid,
            'legacy_count':len(original),'missing':missing,'changed':changed,
            'unexpected_extra':extra,'checked_export_valid':checked_valid}


def build(work):
    work=work.resolve();tools=work/'toolchains';host=tools/'host';out=work/'out'
    reports=work/'artifacts/reports';logs=work/'artifacts/logs';abi=work/'abi'
    for p in [reports,logs,abi]:p.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ)
    for key in ['KBUILD_MODPOST_WARN','KBUILD_MODPOST_NOFINAL','KBUILD_NSDEPS']:
        if env.get(key):raise ValueError('Refusing relaxed modpost: '+key)
    env.update(PATH=f'{host}/usr/bin:{tools}/rust-1.82.0.p2/bin:'+env.get('PATH',''),
               LD_LIBRARY_PATH=f'{host}/usr/lib/x86_64-linux-gnu',LIBCLANG_PATH=f'{tools}/clang-r536225/lib',
               M4=f'{host}/usr/bin/m4',BISON_PKGDATADIR=f'{host}/usr/share/bison',
               POPSICLE_HWID_INCLUDE=str(REPO/'kernel/compat/popsicle'),
               KBUILD_GENDWARFKSYMS_STABLE='1')
    report={'status':'BUILD_STARTED','variant':'CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER=1',
            'paired_WLAN_built':False,
            'modules':{},'checked_WLAN_unresolved':[],'platform_export_crc_changes':{},
            'phone_executed':False,'radio_backend_activation_enabled':False,
            'version_generator':'gendwarfksyms','stable_kabi_mode':True,
            'new_kernel_kabi_rules_added':False,'CRC_gate_waived':False,
            'limitations':'Diagnostic paired build only. Stock CNSS2 must not remain loaded beside its replacement. No platform private layout/KCFI, module replacement procedure, actual loader/firmware, error recovery, module-exit failure or radio interoperability certification.'}
    produced=[]
    def command(args,name):
        with (logs/name).open('w') as stream:
            process=subprocess.Popen(list(map(str,args)),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in process.stdout:print(line,end='',flush=True);stream.write(line)
            if process.wait():raise subprocess.CalledProcessError(process.returncode,args)
    def trial(phase):
        command(['bash',REPO/'tools/kernel/popsicle_trial_build.sh',phase,
                 work/'baseline',work/'common',work/'soc',work/'wlan',
                 work/'reference-modules/vendor/qcom/opensource/dataipa',
                 tools/'clang-r536225',tools/'rust-1.82.0.p2',host,out],phase+'-checked.log')
    try:
        trial('prepare')
        lock=json.loads((REPO/'docs/popsicle-source-lock.json').read_text())
        core=abi/'vmlinux.symvers';download(lock['candidate_common']['actual_symvers'],core)
        vendor=abi/'stock-vendor.symvers'
        known=write_inputs(work/'common',out,core,REPO/'kernel/abi/popsicle-stock-exports.json',vendor)
        stock=json.loads((REPO/'kernel/abi/popsicle-stock-exports.json').read_text())
        original=next(m['exports'] for m in stock['modules'] if m['name']=='cnss2')
        # Exclude precisely the module being replaced, never invent an export
        # or silently use the stock provider for a missing rebuilt symbol.
        for name in original:known.pop(name)
        filtered=abi/'vendor-without-cnss2.symvers'
        filtered.write_text(''.join(line for line in vendor.read_text().splitlines(True)
                                    if line.split('\t')[2]!='cnss2'))
        report['removed_stock_provider']='cnss2';report['stock_cnss2_export_count']=len(original)
        make=['make','-C',work/'common',f'O={out}','ARCH=arm64',f'LLVM={tools}/clang-r536225/bin/',
              f'HOSTCFLAGS=-I{host}/usr/include',f'HOSTLDFLAGS=-L{host}/usr/lib/x86_64-linux-gnu','-j4','KBUILD_SYMTYPES=1','KBUILD_GENDWARFKSYMS_STABLE=1']
        command(make+[f'M={REPO}/kernel/provider',f'KBUILD_EXTRA_SYMBOLS={filtered}','modules'],'provider-checked.log')
        provider=REPO/'kernel/provider/opairshare_wonder_provider.ko';produced.append(provider)
        provider_sym=REPO/'kernel/provider/Module.symvers';merge_generated_exports(known,symvers([provider_sym]))
        # Pinned target platform configuration; do not edit the GKI .config.
        config=work/'wlan/platform/cnss2/canoe_gki_defconfig'
        settings=[line.split('=',1) for line in config.read_text().splitlines() if line.startswith('CONFIG_')]
        options=[name+'='+value for name,value in settings]
        flags=[f'-D{name}{"_MODULE" if value=="m" else ""}=1' for name,value in settings if value in ['y','m']]
        flags+=['-DCONFIG_QCOM_SOCINFO_MODULE=1','-DCONFIG_QCOM_RPROC_COMMON_MODULE=1','-DCONFIG_WCNSS_MEM_PRE_ALLOC=1','-DCONFIG_ARM_SMMU_MODULE=1','-DCONFIG_QCOM_IOMMU_UTIL_MODULE=1']
        includes=[work/'soc/include',work/'soc/drivers/soc/qcom',work/'soc/drivers/remoteproc',
                  work/'wlan/platform/inc',work/'wlan/platform/cnss_utils']
        # Real target SoC options, separate from the unmodified GKI .config.
        soc_config=work/'soc/configs/canoe_perf.bzl'
        if hashlib.sha256(soc_config.read_bytes()).hexdigest()!='efa1a94176ead2177fd3d2cde5e46885130a6fa9dc710da22c60d9ded2ae6379':
            raise ValueError('Unreviewed SoC configuration')
        source=soc_config.read_text()
        soc_values=ast.literal_eval(source[source.index('{'):])
        chosen={n:soc_values[n] for n in ['CONFIG_PCI_MSM','CONFIG_MHI_BUS',
                'CONFIG_MHI_BUS_MISC','CONFIG_IPC_LOGGING','CONFIG_QCOM_SMEM','CONFIG_QCOM_SOCINFO']}
        for n,v in chosen.items():
            options.append(n+'='+v)
            flags.append('-D'+n+('_MODULE' if v=='m' else '')+'=1')
        overlay=abi/'cnss2-include';overlay.mkdir(exist_ok=True)
        verified_headers={'include/linux/mhi.h': '8333c4d98f2403f57e96b47e18276f152315a9799ce7e40fb07af0f6b7cd9cc1', 'include/linux/mhi_misc.h': '7c379f95aaf129dae35c13d58cd1ad96efd59cb1d20663b0dfab40793a28050c'}
        for relative,digest in verified_headers.items():
            actual=work/'soc'/relative
            if hashlib.sha256(actual.read_bytes()).hexdigest()!=digest:
                raise ValueError('Unreviewed SoC header: '+relative)
            alias=overlay/('mishare_soc_'+actual.name)
            if alias.is_symlink():
                if alias.resolve()!=actual.resolve():raise ValueError('Wrong SoC header alias')
            elif alias.exists():raise ValueError('Non-symlink SoC header alias')
            else:alias.symlink_to(actual.resolve())
        flags+=['-I'+str(overlay),'-DCONFIG_MISHARE_CHECKED_CNSS2_PLATFORM=1',
                '-fno-eliminate-unused-debug-types']
        report['soc_config_sha256']='efa1a94176ead2177fd3d2cde5e46885130a6fa9dc710da22c60d9ded2ae6379'
        report['soc_selected_config']=chosen
        report['soc_header_sha256']=verified_headers
        report['platform_config_sha256']=hashlib.sha256(config.read_bytes()).hexdigest()
        platform=work/'wlan/platform/cnss2'
        command(make+[f'M={platform}',f'WLAN_PLATFORM_ROOT={work}/wlan/platform',
                      *options,'EXTRA_CFLAGS='+' '.join([*(f'-I{p}' for p in includes),*flags]),
                      f'KBUILD_EXTRA_SYMBOLS={filtered}','modules'],'cnss2-checked.log')
        platform_module=platform/'cnss2.ko';produced.append(platform_module)
        generated=symvers([platform/'Module.symvers'])
        required='cnss_wlan_unregister_driver_checked_v1'
        if required not in generated:raise ValueError('Checked CNSS2 export was not linked')
        surface=check_export_surface(original,export_records(platform_module),required)
        report['export_surface']=surface
        report['platform_export_crc_changes']=surface['changed']
        report['type_streams_requested']=True
        if not surface['match']:
            raise ValueError('Rebuilt CNSS2 export records differ from stock; inspect report')
        merge_generated_exports(known,generated)
        expected=json.loads((REPO/'kernel/abi/popsicle-stock-module-header.json').read_text())
        for name,path in [('provider',provider),('cnss2',platform_module)]:
            report['modules'][name]=module_report(path,expected,known)
            if report['modules'][name]['status'] not in ['RECORDED_LOADER_CHECKS_MATCH_ONLY','RECORDS_AND_HEADER_MATCH_ONLY']:
                raise ValueError('Recorded module checks did not pass: '+name)
        transport=transport_audit(work/'wlan/qcacld-3.0/configs/canoe_gki_peach-v2_defconfig',
                                  json.loads((REPO/'kernel/abi/popsicle-stock-transport.json').read_text()))
        report['actual_target_transport']=transport
        if transport['platform_module']!='cnss2':
            raise ValueError('Actual target is not CNSS2')
        paired=abi/'checked-wlan-providers.symvers'
        paired.write_text(filtered.read_text()+provider_sym.read_text()+(platform/'Module.symvers').read_text())
        env['POPSICLE_CHECKED_CNSS2']='1';env['POPSICLE_EXTRA_SYMBOLS']=str(paired)
        trial('wlan-object')
        obj=inspect(work/'wlan/qcacld-3.0/qca_cld3_peach_v2.o')
        report['checked_WLAN_unresolved']=sorted(set(obj['undefined'])-known.keys()-{'__this_module'})
        if required not in obj['undefined']:raise ValueError('WLAN object does not require checked CNSS2')
        if 'cnss_wlan_unregister_driver' in obj['undefined']:raise ValueError('Checked WLAN still imports legacy CNSS2 unregister')
        if report['checked_WLAN_unresolved']:raise ValueError('Missing real paired WLAN provider exports')
        trial('wlan-modules')
        wlan=work/'wlan/qcacld-3.0/qca_cld3_peach_v2.ko';produced.append(wlan)
        module=inspect(wlan);depends=','.join(module['modinfo'].get('depends',[])).split(',')
        if 'cnss2' not in depends or 'opairshare_wonder_provider' not in depends:
            raise ValueError('Checked WLAN lacks required strong paired dependencies')
        report['checked_WLAN_dependencies']=depends
        report['checked_import_crc']=module['versions'].get(required)
        if report['checked_import_crc']!=generated[required]:raise ValueError('Checked consumer import CRC mismatch')
        report['modules']['wlan']=module_report(wlan,expected,known)
        if report['modules']['wlan']['status'] not in ['RECORDED_LOADER_CHECKS_MATCH_ONLY','RECORDS_AND_HEADER_MATCH_ONLY']:
            raise ValueError('Checked WLAN recorded module checks failed')
        report['paired_WLAN_built']=True
        report['status']='CHECKED_PLATFORM_PAIR_LINK_AND_RECORDED_CHECKS_ONLY'
        return 0
    except Exception as error:
        report['status']='CHECKED_PLATFORM_PAIR_BLOCKED';report['error']=str(error);raise
    finally:
        # Preserve actual compiler/genksyms evidence even when the strict
        # public export gate refuses the candidate. Never edit a CRC/type.
        type_dir=work/'artifacts/type-inputs';type_dir.mkdir(parents=True,exist_ok=True)
        evidence=[]
        source_dir=work/'wlan/platform/cnss2'
        files=[(out/'.config','kernel.config'),
               (out/'stock-config-delta.json','stock-config-delta.json'),
               (source_dir/'Module.symvers','cnss2.Module.symvers'),
               (source_dir/'canoe_gki_defconfig','cnss2.defconfig')]
        files += [(x,x.name.lstrip('.')) for pattern in ['*.symtypes','.*.cmd'] for x in sorted(source_dir.glob(pattern))]
        for source,name in files:
            if source.is_file():
                dst=type_dir/name;shutil.copy2(source,dst)
                evidence.append({'name':name,'source':str(source.relative_to(work)),'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'size':dst.stat().st_size})
        from module_exports import load
        rule_object=source_dir/'main.o'
        if rule_object.is_file():
            raw,sections=load(rule_object)
            section=next((x for x in sections if x['name']=='.discard.gendwarfksyms.kabi_rules'),None)
            if section:
                data=raw[section['off']:section['off']+section['size']]
                dst=type_dir/'existing-kabi-rules.bin';dst.write_bytes(data)
                report['existing_kabi_rules']={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
        report['type_inputs']=evidence
        (reports/'cnss2-checked-pair.json').write_text(json.dumps(report,indent=2)+'\n')
        if produced:
            with tarfile.open(work/'artifacts/cnss2-checked-pair-diagnostic-not-for-install.tar.gz','w:gz') as bundle:
                for p in produced:bundle.add(p,arcname=p.name)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();raise SystemExit(build(args.work))
