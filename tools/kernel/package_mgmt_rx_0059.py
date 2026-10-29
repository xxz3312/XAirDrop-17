#!/usr/bin/env python3
"""Assemble already-compiled CI inputs; never build or load kernel code here."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

p=Path('out/XAirDrop-17-Mgmt-RX-0059')
(p/'kernel').mkdir(parents=True,exist_ok=True)
ndk=Path('.xos-ndk/ndk')/os.environ['NDK_VERSION']/'toolchains/llvm/prebuilt/linux-x86_64/bin'
build=json.loads(Path('tool/build.json').read_text())
assert build['commit']==os.environ['GITHUB_SHA']
hashfile=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert hashfile('tool/action-tx')==build['binary_sha256']
original={}
for name in ['qca_cld3_peach_v2.ko','opairshare_wonder_provider.ko']:
    original[name]=hashfile('extracted/'+name)
    subprocess.run([str(ndk/'llvm-strip'),'--strip-debug','extracted/'+name,'-o',str(p/'kernel'/name)],check=True)
    # Load-relevant version and module metadata bytes must survive stripping.
    for section in ['.modinfo','__versions']:
        before=Path('extracted')/(name+section+'.before')
        after=Path('extracted')/(name+section+'.after')
        subprocess.run([str(ndk/'llvm-objcopy'),'--dump-section',section+'='+str(before),'extracted/'+name],check=True)
        subprocess.run([str(ndk/'llvm-objcopy'),'--dump-section',section+'='+str(after),str(p/'kernel'/name)],check=True)
        assert before.read_bytes()==after.read_bytes()
info=subprocess.check_output([str(ndk/'llvm-readelf'),'-p','.modinfo',str(p/'kernel/qca_cld3_peach_v2.ko')],text=True)
assert 'parm=mishare_mgmt_rx_diag:' in info and 'parm=mishare_mgmt_rx:' in info and 'name=qca_cld3_peach_v2' in info
Path('out/module-info.txt').write_text(info)
symbols=subprocess.check_output([str(ndk/'llvm-nm'),'--defined-only',str(p/'kernel/qca_cld3_peach_v2.ko')],text=True)
for name in ['mishare_mgmt_rx_register','mishare_mgmt_rx_unregister','mishare_mgmt_rx_route']:
    assert any(line.endswith(' T '+name) for line in symbols.splitlines())
for name in ['popsicle-wlan-trial.sh','popsicle-mgmt-rx-test.sh']:
    shutil.copy2('tools/device/'+name,p/name)
shutil.copy2('tool/action-tx',p/'action-tx-0059')
shutil.copy2('tool/build.json',p/'tool-build.json')
shutil.copy2('docs/POPSICLE-FULL-MGMT-RX-0059.md',p/'README.md')
for source in ['LICENSE','LICENSES/GPL-2.0-only.txt','LICENSES/LGPL-3.0.txt']:
    shutil.copy2(source,p/Path(source).name)
subprocess.run(['git','archive','--format=tar.gz','--prefix=XAirDrop-17/','--output='+str(p/'source.tar.gz'),'HEAD'],check=True)
module=p/'kernel/qca_cld3_peach_v2.ko'
assert module.read_bytes()[:4]==b'\x7fELF' and module.stat().st_size<50*1024*1024
report={'controller_tool_source_commit':os.environ['GITHUB_SHA'],'kernel_source_commit':os.environ['KERNEL_COMMIT'],'kernel_run':int(os.environ['KERNEL_RUN']),'tool_run':int(os.environ['TOOL_RUN']),'package_run':int(os.environ['GITHUB_RUN_ID']),'original_module_sha256':original,'stripped_wlan_sha256':hashfile(module),'stripped_wlan_bytes':module.stat().st_size,'stripped_provider_sha256':hashfile(p/'kernel/opairshare_wonder_provider.ko'),'tool_sha256':build['binary_sha256'],'strip':'NDK 27.2.12479018 llvm-strip --strip-debug; .modinfo/__versions byte comparison passed','diagnostic_stages':True,'diagnostic_snapshot_is_atomic':False,'default_mgmt_rx':False,'manual_opt_in':'popsicle-wlan-trial.sh run-mgmt-rx','host_registration_is_sme_pe_submission_only':True,'firmware_full_rx_verified':False,'phone_executed':False,'airdrop_verified':False}
(p/'BUILD.json').write_text(json.dumps(report,indent=2)+'\n')
(p/'SHA256SUMS').write_text(''.join(hashfile(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS'))
with zipfile.ZipFile('out/XAirDrop-17-Mgmt-RX-0059.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(p.rglob('*')):
        if f.is_file():z.write(f,f.relative_to(p.parent))
