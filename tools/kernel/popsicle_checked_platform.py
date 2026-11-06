#!/usr/bin/env python3
"""Strict opt-in ICNSS/provider/WLAN pair build; never install or load modules."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
from module_abi import inspect, symvers
from popsicle_modpost import write_inputs, merge_generated_exports, module_report
from popsicle_ci import REPO, download


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
               POPSICLE_HWID_INCLUDE=str(REPO/'kernel/compat/popsicle'))
    report={'status':'BUILD_STARTED','variant':'CONFIG_MISHARE_CHECKED_ICNSS_UNREGISTER=1',
            'modules':{},'checked_WLAN_unresolved':[],'platform_export_crc_changes':{},
            'phone_executed':False,'radio_backend_activation_enabled':False,
            'limitations':'Diagnostic paired build only. Stock ICNSS must not remain loaded beside its replacement. No platform private layout/KCFI, module replacement procedure, actual loader/firmware, error recovery, module-exit failure or radio interoperability certification.'}
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
        original=next(m['exports'] for m in stock['modules'] if m['name']=='icnss2')
        # Exclude precisely the module being replaced, never invent an export
        # or silently use the stock provider for a missing rebuilt symbol.
        for name in original:known.pop(name)
        filtered=abi/'vendor-without-icnss.symvers'
        filtered.write_text(''.join(line for line in vendor.read_text().splitlines(True)
                                    if line.split('\t')[2]!='icnss2'))
        report['removed_stock_provider']='icnss2';report['stock_icnss_export_count']=len(original)
        make=['make','-C',work/'common',f'O={out}','ARCH=arm64',f'LLVM={tools}/clang-r536225/bin/',
              f'HOSTCFLAGS=-I{host}/usr/include',f'HOSTLDFLAGS=-L{host}/usr/lib/x86_64-linux-gnu','-j4']
        command(make+[f'M={REPO}/kernel/provider',f'KBUILD_EXTRA_SYMBOLS={filtered}','modules'],'provider-checked.log')
        provider=REPO/'kernel/provider/opairshare_wonder_provider.ko';produced.append(provider)
        provider_sym=REPO/'kernel/provider/Module.symvers';merge_generated_exports(known,symvers([provider_sym]))
        # Pinned target platform configuration; do not edit the GKI .config.
        config=work/'wlan/platform/icnss2/canoe_gki_defconfig'
        settings=[line.split('=',1) for line in config.read_text().splitlines() if line.startswith('CONFIG_')]
        options=[name+'='+value for name,value in settings]
        flags=[f'-D{name}{"_MODULE" if value=="m" else ""}=1' for name,value in settings if value in ['y','m']]
        flags+=['-DCONFIG_QCOM_SOCINFO_MODULE=1','-DCONFIG_QCOM_RPROC_COMMON_MODULE=1','-DCONFIG_WCNSS_MEM_PRE_ALLOC=1','-DCONFIG_ARM_SMMU_MODULE=1','-DCONFIG_QCOM_IOMMU_UTIL_MODULE=1']
        includes=[work/'soc/include',work/'soc/drivers/soc/qcom',work/'soc/drivers/remoteproc',
                  work/'wlan/platform/inc',work/'wlan/platform/cnss_utils']
        # DDK dependencies use the SoC remoteproc header, which extends the
        # common GKI declaration set. Select the real pinned header only
        # after checking the shared guard; never reconstruct declarations.
        rproc=work/'soc/include/linux/remoteproc/qcom_rproc.h'
        common_rproc=work/'common/include/linux/remoteproc/qcom_rproc.h'
        digest=hashlib.sha256(rproc.read_bytes()).hexdigest()
        if digest!='d9462a7424185a48125a412889d25077bdbe9013dc31d0d0038767cd305eb31c':
            raise ValueError('Unreviewed SoC remoteproc header')
        for header in [rproc,common_rproc]:
            if '#ifndef __QCOM_RPROC_H__' not in header.read_text():
                raise ValueError('Remoteproc header guard contract changed')
        overlay=abi/'icnss-include';overlay.mkdir(exist_ok=True)
        alias=overlay/'mishare_soc_qcom_rproc.h'
        if alias.is_symlink():
            if alias.resolve()!=rproc.resolve():raise ValueError('Unexpected SoC header alias')
        elif alias.exists():raise ValueError('Refusing non-symlink SoC header alias')
        else:alias.symlink_to(rproc.resolve())
        # Include at the native source position, after pr_fmt is defined.
        # Forcing this header before the source would initialize printk early.
        flags+=['-I'+str(overlay),'-DCONFIG_MISHARE_CHECKED_ICNSS_PLATFORM=1']
        report['soc_remoteproc_header_sha256']=digest
        report['platform_soc_dependency_defines']=['CONFIG_QCOM_SOCINFO_MODULE=1','CONFIG_QCOM_RPROC_COMMON_MODULE=1']
        report['platform_config_sha256']=hashlib.sha256(config.read_bytes()).hexdigest()
        platform=work/'wlan/platform/icnss2'
        command(make+[f'M={platform}',f'WLAN_PLATFORM_ROOT={work}/wlan/platform',
                      *options,'EXTRA_CFLAGS='+' '.join([*(f'-I{p}' for p in includes),*flags]),
                      f'KBUILD_EXTRA_SYMBOLS={filtered}','modules'],'icnss-checked.log')
        platform_module=platform/'icnss2.ko';produced.append(platform_module)
        generated=symvers([platform/'Module.symvers'])
        required='icnss_unregister_driver_checked_v1'
        if required not in generated:raise ValueError('Checked ICNSS export was not linked')
        missing=sorted(set(original)-generated.keys());report['missing_legacy_platform_exports']=missing
        changes={name:{'stock':record['crc'],'generated':generated.get(name)}
                 for name,record in original.items() if generated.get(name)!=record['crc']}
        report['platform_export_crc_changes']=changes
        if missing or changes:raise ValueError('Rebuilt ICNSS legacy export surface differs from stock; inspect report')
        merge_generated_exports(known,generated)
        expected=json.loads((REPO/'kernel/abi/popsicle-stock-module-header.json').read_text())
        for name,path in [('provider',provider),('icnss2',platform_module)]:
            report['modules'][name]=module_report(path,expected,known)
            if report['modules'][name]['status'] not in ['RECORDED_LOADER_CHECKS_MATCH_ONLY','RECORDS_AND_HEADER_MATCH_ONLY']:
                raise ValueError('Recorded module checks did not pass: '+name)
        paired=abi/'checked-wlan-providers.symvers'
        paired.write_text(filtered.read_text()+provider_sym.read_text()+(platform/'Module.symvers').read_text())
        env['POPSICLE_CHECKED_ICNSS']='1';env['POPSICLE_EXTRA_SYMBOLS']=str(paired)
        trial('wlan-object')
        obj=inspect(work/'wlan/qcacld-3.0/qca_cld3_peach_v2.o')
        report['checked_WLAN_unresolved']=sorted(set(obj['undefined'])-known.keys()-{'__this_module'})
        if required not in obj['undefined']:raise ValueError('WLAN object does not require checked ICNSS')
        if 'icnss_unregister_driver' in obj['undefined']:raise ValueError('Checked WLAN still imports legacy ICNSS unregister')
        if report['checked_WLAN_unresolved']:raise ValueError('Missing real paired WLAN provider exports')
        trial('wlan-modules')
        wlan=work/'wlan/qcacld-3.0/qca_cld3_peach_v2.ko';produced.append(wlan)
        module=inspect(wlan);depends=','.join(module['modinfo'].get('depends',[])).split(',')
        if 'icnss2' not in depends or 'opairshare_wonder_provider' not in depends:
            raise ValueError('Checked WLAN lacks required strong paired dependencies')
        report['checked_WLAN_dependencies']=depends
        report['checked_import_crc']=module['versions'].get(required)
        if report['checked_import_crc']!=generated[required]:raise ValueError('Checked consumer import CRC mismatch')
        report['modules']['wlan']=module_report(wlan,expected,known)
        if report['modules']['wlan']['status'] not in ['RECORDED_LOADER_CHECKS_MATCH_ONLY','RECORDS_AND_HEADER_MATCH_ONLY']:
            raise ValueError('Checked WLAN recorded module checks failed')
        report['status']='CHECKED_PLATFORM_PAIR_LINK_AND_RECORDED_CHECKS_ONLY'
        return 0
    except Exception as error:
        report['status']='CHECKED_PLATFORM_PAIR_BLOCKED';report['error']=str(error);raise
    finally:
        (reports/'checked-platform-pair.json').write_text(json.dumps(report,indent=2)+'\n')
        if produced:
            with tarfile.open(work/'artifacts/checked-pair-diagnostic-not-for-install.tar.gz','w:gz') as bundle:
                for p in produced:bundle.add(p,arcname=p.name)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();raise SystemExit(build(args.work))
