#!/usr/bin/env python3
"""Actions-only typed PCIe boundary with pinned native WLAN callbacks.

CNSS2 slots below are a model. Production native registration is deliberately
unchanged until checked CNSS2 removal and its callers have been integrated.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from mishare_execution_fixture import COMMON, extract

ROOT = Path(__file__).resolve().parents[2]
PCIE = 'qcacld-3.0/core/pld/src/pld_pcie.c'
BODY = r'''
struct pci_dev {struct device dev;};
struct pci_device_id {int id;};
#include "execution.c"
#define PLD_BUS_TYPE_PCIE 77
struct pld_ops {
 int (*reinit)(struct device *,int,void *,void *);
 void (*shutdown)(struct device *,int);
 int (*idle_restart)(struct device *,int);
 int (*idle_shutdown)(struct device *,int);
};
struct pld_context {struct pld_ops *ops;};
static struct pci_dev pdev={{9}};
static const struct pci_device_id device_id={11};
static int calls,private_refs,result;
static bool missing,blocking,entered,allow_return;
static pthread_mutex_t block_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t block_cond=PTHREAD_COND_INITIALIZER;
static void vendor_body(void) {
 in_wlan=true;calls++;
 assert(atomic_load(&wlan_module.refs)==private_refs+1 && "EXPECTED_PCIE_PIN");
 if(private_refs){module_put(THIS_MODULE);private_refs=0;assert(atomic_load(&wlan_module.refs)==1 && "EXPECTED_PCIE_PIN");}
 if(blocking){
  pthread_mutex_lock(&block_lock);entered=true;pthread_cond_broadcast(&block_cond);
  while(!allow_return)pthread_cond_wait(&block_cond,&block_lock);
  pthread_mutex_unlock(&block_lock);
 }
 callback_returned=true;in_wlan=false;
}
static int vendor_reinit(struct device *d,int bus,void *bdev,void *bid) {
 assert(d==&pdev.dev && bus==77 && bdev==&pdev && bid==&device_id && "EXPECTED_PCIE_ID");vendor_body();return result;
}
static void vendor_shutdown(struct device *d,int bus){assert(d==&pdev.dev && bus==77);vendor_body();}
static int vendor_idle(struct device *d,int bus){assert(d==&pdev.dev && bus==77);vendor_body();return result;}
static struct pld_ops native_ops={vendor_reinit,vendor_shutdown,vendor_idle,vendor_idle};
static struct pld_context context={&native_ops};
static struct pld_context *pld_get_global_context(void){return missing?NULL:&context;}
NATIVE_CALLBACKS
/* Model the CNSS2 callback slot types, not the CNSS2 scheduler or registration. */
struct cnss_slots {
 int (*reinit)(struct pci_dev *,const struct pci_device_id *);
 void (*shutdown)(struct pci_dev *);
 int (*idle_restart)(struct pci_dev *,const struct pci_device_id *);
 int (*idle_shutdown)(struct pci_dev *);
};
static const struct cnss_slots slots={
 opairshare_wlan_execution_pcie_reinit,opairshare_wlan_execution_pcie_shutdown,
 opairshare_wlan_execution_pcie_idle_restart,opairshare_wlan_execution_pcie_idle_shutdown
};
static const struct mishare_wlan_pcie_execution_ops descriptor={
 THIS_MODULE,pld_pcie_reinit,pld_pcie_shutdown,pld_pcie_idle_restart_cb,pld_pcie_idle_shutdown_cb
};
static int invoke(int kind,bool expected){
 expect_final_return=expected;callback_returned=false;int ret=0;
 switch(kind){
 case 0:ret=slots.reinit(&pdev,&device_id);break;
 case 1:slots.shutdown(&pdev);break;
 case 2:ret=slots.idle_restart(&pdev,&device_id);break;
 case 3:ret=slots.idle_shutdown(&pdev);break;
 default:assert(false);
 }
 expect_final_return=false;return ret;
}
static void reset(void){
 assert(!execution_ops.owner && !execution_pcie_ops.owner && !execution_active && !atomic_load(&wlan_module.refs) && "EXPECTED_PCIE_CLEAR");
 missing=false;context.ops=&native_ops;native_ops=(struct pld_ops){vendor_reinit,vendor_shutdown,vendor_idle,vendor_idle};
 result=-EIO;calls=private_refs=0;blocking=entered=allow_return=false;atomic_store(&wlan_module.deny,false);
}
static int thread_kind;
static void *callback_thread(void *unused){(void)unused;int ret=invoke(thread_kind,true);assert(ret==(thread_kind==1?0:-EIO));return NULL;}
static int v2_reinit(struct device *d){(void)d;return 0;}
static void v2_shutdown(struct device *d){(void)d;}
static void admission_cases(void){
 reset();
 assert(slots.reinit(NULL,&device_id)==-EINVAL);
 assert(slots.idle_restart(NULL,&device_id)==-EINVAL);
 assert(slots.idle_shutdown(NULL)==-EINVAL);slots.shutdown(NULL);
 assert(slots.reinit(&pdev,&device_id)==-ENODEV);
 assert(opairshare_wlan_execution_register_pcie_v3(NULL)==-EINVAL);
 struct mishare_wlan_pcie_execution_ops invalid=descriptor;
 invalid.idle_shutdown=NULL;assert(opairshare_wlan_execution_register_pcie_v3(&invalid)==-EINVAL);
 assert(!opairshare_wlan_execution_register_pcie_v3(&descriptor));
 assert(opairshare_wlan_execution_register_pcie_v3(&descriptor)==-EALREADY);
 invalid=descriptor;invalid.owner=&foreign_module;
 assert(opairshare_wlan_execution_register_pcie_v3(&invalid)==-EBUSY);
 assert(opairshare_wlan_execution_reinit(&pdev.dev)==-EPROTOTYPE && "EXPECTED_BUS_REFUSAL");
 int before=atomic_load(&execution_get_count);
 atomic_store(&wlan_module.deny,true);
 assert(slots.reinit(&pdev,&device_id)==-ESHUTDOWN && !calls);
 assert(atomic_load(&execution_get_count)==before+1);
 assert(!opairshare_wlan_execution_unregister(THIS_MODULE));
 reset();
 struct mishare_wlan_execution_ops v2={THIS_MODULE,v2_reinit,v2_shutdown,v2_reinit,v2_reinit};
 assert(!opairshare_wlan_execution_register_v2(&v2));
 assert(opairshare_wlan_execution_register_pcie_v3(&descriptor)==-EBUSY);
 assert(slots.reinit(&pdev,&device_id)==-EPROTOTYPE && "EXPECTED_BUS_REFUSAL");
 assert(!opairshare_wlan_execution_unregister(THIS_MODULE));
 reset();assert(!opairshare_wlan_execution_register_pcie_v3(&descriptor));
 assert(opairshare_wlan_execution_register_v2(&v2)==-EBUSY);
 assert(!opairshare_wlan_execution_unregister_begin(THIS_MODULE,false));
 assert(!opairshare_wlan_execution_unregister_end(THIS_MODULE,0));
 reset();
}
int main(void){
 admission_cases();
 for(int kind=0;kind<4;kind++){
  reset();
  struct mishare_wlan_pcie_execution_ops copied=descriptor;
  assert(!opairshare_wlan_execution_register_pcie_v3(&copied));
  memset(&copied,0,sizeof(copied));
  atomic_store(&wlan_module.refs,1);private_refs=1;
  assert(invoke(kind,true)==(kind==1?0:-EIO));
  assert(calls==1 && !atomic_load(&wlan_module.refs) && "EXPECTED_PCIE_RELEASE");
  assert(opairshare_wlan_execution_close(&foreign_module)==-EBUSY);
  assert(!opairshare_wlan_execution_unregister(THIS_MODULE));
  reset();assert(!opairshare_wlan_execution_register_pcie_v3(&descriptor));
  missing=true;assert(invoke(kind,false)==(kind==1?0:-ENODEV) && !calls);
  missing=false;context.ops=NULL;assert(invoke(kind,false)==(kind==1?0:-ENODEV) && !calls);
  context.ops=&native_ops;
  if(kind==3){native_ops.shutdown=NULL;assert(invoke(kind,true)==-EIO && "EXPECTED_PCIE_IDLE_GUARD");native_ops.shutdown=vendor_shutdown;native_ops.idle_shutdown=NULL;assert(invoke(kind,false)==-ENODEV && "EXPECTED_PCIE_IDLE_GUARD");}
  assert(!opairshare_wlan_execution_unregister(THIS_MODULE));
  reset();assert(!opairshare_wlan_execution_register_pcie_v3(&descriptor));
  thread_kind=kind;blocking=true;pthread_t thread;
  assert(!pthread_create(&thread,NULL,callback_thread,NULL));
  pthread_mutex_lock(&block_lock);while(!entered)pthread_cond_wait(&block_cond,&block_lock);pthread_mutex_unlock(&block_lock);
  assert(opairshare_wlan_execution_close(THIS_MODULE)==-EBUSY && "EXPECTED_PCIE_DRAIN");
  assert(opairshare_wlan_execution_unregister(THIS_MODULE)==-EBUSY && execution_pcie_ops.owner && "EXPECTED_PCIE_RETAIN");
  assert(slots.idle_shutdown(&pdev)==-ESHUTDOWN && calls==1 && "EXPECTED_PCIE_CLOSED");
  pthread_mutex_lock(&block_lock);allow_return=true;pthread_cond_broadcast(&block_cond);pthread_mutex_unlock(&block_lock);
  assert(!pthread_join(thread,NULL));assert(!opairshare_wlan_execution_unregister(THIS_MODULE));
 }
 reset();puts("MISHARE_PCIE_EXECUTION_FIXTURE_PASS_ONLY");return 0;
}
'''


def assemble(wlan):
    native=(wlan/PCIE).read_text()
    original=subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+PCIE],text=True)
    fragments={}
    for name in ['pld_pcie_reinit','pld_pcie_shutdown','pld_pcie_idle_restart_cb','pld_pcie_idle_shutdown_cb']:
        pattern=r'^static (?:int|void) '+name+r'\([^;{]+?\)\s*\{.*?^\}'
        fragment=extract(native,pattern)
        restored=fragment.replace('\tif (!pld_context || !pld_context->ops)\n\t\t'+('return;' if name=='pld_pcie_shutdown' else 'return -ENODEV;')+'\n','',1)
        if name=='pld_pcie_idle_shutdown_cb':restored=restored.replace('if (pld_context->ops->idle_shutdown)','if (pld_context->ops->shutdown)',1)
        if restored!=extract(original,pattern):raise ValueError('Unreviewed PCIe callback change: '+name)
        fragments[name]=fragment
    return COMMON+BODY.replace('NATIVE_CALLBACKS','\n'.join(fragments.values())),fragments,native


def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,fragments,native=assemble(wlan)
    provider=(ROOT/'kernel/provider/execution.c').read_text()
    header=(ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['module.h','mutex.h','string.h']:(d/'linux'/name).write_text('/* modeled module API */\n')
        (d/'mishare_wlan_execution.h').write_bytes(header)
        source=d/'test.c';exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        def execute(p,c):
            (d/'execution.c').write_text(p);source.write_text(c);subprocess.run(command,check=True)
            return subprocess.run([exe],capture_output=True,text=True,env=env,timeout=30)
        good=execute(provider,code)
        if good.returncode:raise ValueError(good.stderr)
        mutations=[
            (provider.replace('else if (!try_module_get(execution_ops.owner))','else if (false && !try_module_get(execution_ops.owner))',1),code,'EXPECTED_PCIE_PIN'),
            (provider.replace('ret = ops.reinit(pdev, id);\n    execution_leave(base.owner);','execution_leave(base.owner);\n    ret = ops.reinit(pdev, id);',1),code,'EXPECTED_PCIE_PIN'),
            (provider,code.replace('slots.reinit(&pdev,&device_id)','slots.reinit(&pdev,NULL)'),'EXPECTED_PCIE_ID'),
            (provider.replace('ret = -EPROTOTYPE;', 'ret = -ENODEV;',1),code,'EXPECTED_BUS_REFUSAL'),
            (provider.replace('if (execution_active)\n            ret = -EBUSY;','if (false && execution_active)\n            ret = -EBUSY;'),code,'EXPECTED_PCIE_DRAIN'),
            (provider,code.replace('if (pld_context->ops->idle_shutdown)','if (pld_context->ops->shutdown)',1),'EXPECTED_EXTERNAL_RETURN'),
        ]
        for changed,changed_code,marker in mutations:
            assert changed!=provider or changed_code!=code
            bad=execute(changed,changed_code)
            if bad.returncode!=-6 or marker not in bad.stderr:raise ValueError((marker,bad.returncode,bad.stderr[:1800]))
    report={'status':'MISHARE_PCIE_EXECUTION_FIXTURE_PASS_ONLY','fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'execution_header_sha256':hashlib.sha256(header).hexdigest(),'native_pcie_sha256':hashlib.sha256(native.encode()).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in fragments.items()},'callbacks':4,'concurrent_close_cases':4,'negative_controls_rejected':len(mutations),'sanitizers':['address','undefined','leak detection'],'production_CNSS2_slots_connected':False,'checked_CNSS2_unregister_integrated':False,'phone_executed':False,'limitations':'Real provider and four native PCIe callback bodies; modeled CNSS2 slots, module API and upper WLAN bodies. No CNSS2 scheduler, real registration, checked remove, loader, KCFI or radio certification. Production PCIe slots remain native until checked lifecycle integration.'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(good.stdout,end='')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
