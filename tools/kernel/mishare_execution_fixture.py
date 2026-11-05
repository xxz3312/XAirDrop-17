#!/usr/bin/env python3
"""Actions-only external provider return boundary and native IPCI registration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_ssr_stop_origins import remove_ssr_stop_additions

ROOT = Path(__file__).resolve().parents[2]
IPCI = 'qcacld-3.0/core/pld/src/pld_ipci.c'
COMMON = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
struct module {atomic_int refs;atomic_bool deny;};
static struct module wlan_module,foreign_module;
#define THIS_MODULE (&wlan_module)
struct device {int id;};
struct mutex {pthread_mutex_t value;};
#define DEFINE_MUTEX(n) struct mutex n={PTHREAD_MUTEX_INITIALIZER}
static void mutex_lock(struct mutex *m) {assert(!pthread_mutex_lock(&m->value));}
static void mutex_unlock(struct mutex *m) {assert(!pthread_mutex_unlock(&m->value));}
static _Thread_local bool in_wlan,expect_final_return,callback_returned;
static atomic_int gets,puts;
static bool try_module_get(struct module *m) {
 assert(m);atomic_fetch_add(&gets,1);if(atomic_load(&m->deny))return false;
 atomic_fetch_add(&m->refs,1);return true;
}
static void module_put(struct module *m) {
 int previous=atomic_fetch_sub(&m->refs,1);assert(previous>0 && "EXPECTED_EXEC_PUT_BALANCE");
 if(previous==1 && expect_final_return)assert(!in_wlan && callback_returned && "EXPECTED_EXTERNAL_RETURN");
 atomic_fetch_add(&puts,1);
}
#define EXPORT_SYMBOL(x)
#define pr_err(...) ((void)0)
#include "mishare_wlan_execution.h"
'''
HARNESS = r'''
#include "execution.c"
#define PLD_BUS_TYPE_IPCI 42
struct pld_ops {int (*reinit)(struct device *,int,void *,void *);void (*shutdown)(struct device *,int);};
struct pld_context {struct pld_ops *ops;};
static struct device dev={1};
static int callback_result,private_refs,callback_calls;
static bool blocking,entered,allow_return;
static pthread_mutex_t block_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t block_cond=PTHREAD_COND_INITIALIZER;
static void vendor_body(void) {
 in_wlan=true;callback_calls++;
 assert(atomic_load(&wlan_module.refs)==private_refs+1 && "EXPECTED_EXEC_PIN");
 if(private_refs){module_put(&wlan_module);private_refs=0;assert(atomic_load(&wlan_module.refs)==1 && "EXPECTED_EXEC_PIN");}
 if(blocking) {
  assert(!pthread_mutex_lock(&block_lock));entered=true;pthread_cond_broadcast(&block_cond);
  while(!allow_return)assert(!pthread_cond_wait(&block_cond,&block_lock));
  assert(!pthread_mutex_unlock(&block_lock));
 }
 callback_returned=true;in_wlan=false;
}
static int vendor_reinit(struct device *d,int bus,void *bdev,void *bid) {
 assert(d==&dev && bus==42 && !bdev && !bid);vendor_body();return callback_result;
}
static void vendor_shutdown(struct device *d,int bus) {assert(d==&dev && bus==42);vendor_body();}
static struct pld_ops native_ops={vendor_reinit,vendor_shutdown};
static struct pld_context native_context={&native_ops};
static struct pld_context *pld_get_global_context(void) {return &native_context;}
NATIVE_REINIT
NATIVE_SHUTDOWN
struct icnss_driver_ops {void (*shutdown)(struct device *);int (*reinit)(struct device *);};
static struct icnss_driver_ops pld_ipci_ops={NATIVE_SLOTS};
static int native_register_result,native_registers,native_unregisters;
static int icnss_register_driver(struct icnss_driver_ops *ops) {
 assert(ops==&pld_ipci_ops && ops->shutdown==opairshare_wlan_execution_shutdown && ops->reinit==opairshare_wlan_execution_reinit && "EXPECTED_EXTERNAL_SLOTS");
 native_registers++;return native_register_result;
}
static void icnss_unregister_driver(struct icnss_driver_ops *ops) {assert(ops==&pld_ipci_ops && !execution_active && "EXPECTED_UNREGISTER_DRAIN");native_unregisters++;}
NATIVE_DESCRIPTOR
NATIVE_REGISTER
NATIVE_UNREGISTER
static void prepare(int private_count) {
 assert(!execution_ops.owner && !execution_active && !atomic_load(&wlan_module.refs));
 private_refs=private_count;atomic_store(&wlan_module.refs,private_count);atomic_store(&wlan_module.deny,false);
 expect_final_return=false;callback_returned=false;in_wlan=false;blocking=entered=allow_return=false;callback_calls=0;callback_result=0;native_register_result=0;
}
static void invoke_shutdown(void) {expect_final_return=true;callback_returned=false;pld_ipci_ops.shutdown(&dev);expect_final_return=false;}
static int invoke_reinit(void) {expect_final_return=true;callback_returned=false;int ret=pld_ipci_ops.reinit(&dev);expect_final_return=false;return ret;}
static void *run_callback(void *unused) {(void)unused;assert(invoke_reinit()==-EIO);return NULL;}
int main(void) {
 assert(opairshare_wlan_execution_register(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_close(NULL)==-EINVAL && opairshare_wlan_execution_unregister(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_reinit(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_reinit(&dev)==-ENODEV);opairshare_wlan_execution_shutdown(NULL);opairshare_wlan_execution_shutdown(&dev);
 prepare(0);struct mishare_wlan_execution_ops bad=pld_ipci_execution;bad.reinit=NULL;
 assert(opairshare_wlan_execution_register(&bad)==-EINVAL);
 assert(!pld_ipci_register_driver());int registrations=native_registers;
 assert(pld_ipci_register_driver()==-EALREADY && native_registers==registrations && "EXPECTED_REGISTER_OWNERSHIP");
 bad=pld_ipci_execution;bad.owner=&foreign_module;assert(opairshare_wlan_execution_register(&bad)==-EBUSY);
 assert(opairshare_wlan_execution_close(&foreign_module)==-EBUSY && !execution_closing);
 assert(opairshare_wlan_execution_unregister(&foreign_module)==-EBUSY && !execution_closing);
 assert(invoke_reinit()==0 && callback_calls==1 && !atomic_load(&wlan_module.refs) && "EXPECTED_EXTERNAL_RETURN");
 pld_ipci_unregister_driver();assert(!execution_ops.owner);
 prepare(1);assert(!pld_ipci_register_driver());invoke_shutdown();assert(!atomic_load(&wlan_module.refs) && !private_refs && callback_calls==1 && "EXPECTED_EXTERNAL_RETURN");pld_ipci_unregister_driver();
 prepare(1);assert(!pld_ipci_register_driver());callback_result=-EIO;assert(invoke_reinit()==-EIO && !atomic_load(&wlan_module.refs) && !execution_active);pld_ipci_unregister_driver();
 prepare(0);assert(!pld_ipci_register_driver());atomic_store(&wlan_module.deny,true);
 assert(invoke_reinit()==-ESHUTDOWN);invoke_shutdown();assert(!callback_calls && !execution_active && !atomic_load(&wlan_module.refs) && "EXPECTED_EXEC_REFUSAL");atomic_store(&wlan_module.deny,false);pld_ipci_unregister_driver();
 prepare(0);assert(!pld_ipci_register_driver());assert(!opairshare_wlan_execution_close(&wlan_module));
 assert(invoke_reinit()==-ESHUTDOWN && "EXPECTED_CLOSING_REFUSAL");invoke_shutdown();assert(!callback_calls && "EXPECTED_CLOSING_REFUSAL");
 assert(opairshare_wlan_execution_register(&pld_ipci_execution)==-ESHUTDOWN);pld_ipci_unregister_driver();
 prepare(0);native_register_result=-EIO;assert(pld_ipci_register_driver()==-EIO && !execution_ops.owner && "EXPECTED_REGISTER_ROLLBACK");
 prepare(0);struct mishare_wlan_execution_ops copy=pld_ipci_execution;assert(!opairshare_wlan_execution_register(&copy));memset(&copy,0,sizeof(copy));
 assert(invoke_reinit()==0 && callback_calls==1 && "EXPECTED_DESCRIPTOR_COPY");assert(!opairshare_wlan_execution_unregister(&wlan_module));
 prepare(1);assert(!pld_ipci_register_driver());blocking=true;callback_result=-EIO;
 pthread_t thread;assert(!pthread_create(&thread,NULL,run_callback,NULL));
 assert(!pthread_mutex_lock(&block_lock));while(!entered)assert(!pthread_cond_wait(&block_cond,&block_lock));assert(!pthread_mutex_unlock(&block_lock));
 assert(opairshare_wlan_execution_close(&wlan_module)==-EBUSY && "EXPECTED_CLOSE_DRAIN");
 int before=native_unregisters;pld_ipci_unregister_driver();assert(native_unregisters==before && execution_ops.owner && "EXPECTED_UNREGISTER_DRAIN");
 assert(opairshare_wlan_execution_unregister(&wlan_module)==-EBUSY && execution_ops.owner && "EXPECTED_UNREGISTER_DRAIN");
 assert(invoke_reinit()==-ESHUTDOWN && "EXPECTED_CLOSING_REFUSAL");
 assert(!pthread_mutex_lock(&block_lock));allow_return=true;pthread_cond_broadcast(&block_cond);assert(!pthread_mutex_unlock(&block_lock));
 assert(!pthread_join(thread,NULL));assert(!atomic_load(&wlan_module.refs) && !execution_active);
 pld_ipci_unregister_driver();assert(native_unregisters==before+1 && !execution_ops.owner);
 assert(!opairshare_wlan_execution_unregister(&wlan_module));
 assert(!atomic_load(&foreign_module.refs));
 puts("MISHARE_EXTERNAL_EXECUTION_FIXTURE_PASS_ONLY");return 0;
}
'''

def extract(text, pattern):
    match=re.search(pattern,text,re.M|re.S)
    if not match:raise ValueError('Changed native execution source: '+pattern)
    return match[0]

def assemble(wlan):
    native=(wlan/IPCI).read_text()
    assert remove_ssr_stop_additions(native)==subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+IPCI],text=True)
    fragments={
        'NATIVE_REINIT':extract(native,r'^static int pld_ipci_reinit\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_SHUTDOWN':extract(native,r'^static void pld_ipci_shutdown\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_REGISTER':extract(native,r'^int pld_ipci_register_driver\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_UNREGISTER':extract(native,r'^void pld_ipci_unregister_driver\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_DESCRIPTOR':extract(native,r'^static const struct mishare_wlan_execution_ops pld_ipci_execution\s*=\s*\{.*?^\};'),
        'NATIVE_SLOTS':extract(native,r'/\* MISHARE_SSR_STOP_BEGIN:execution_slots \*/.*?/\* MISHARE_SSR_STOP_END:execution_slots \*/'),
    }
    code=HARNESS
    for key,value in fragments.items():code=code.replace(key,value)
    return COMMON+code,fragments,native

def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,fragments,native=assemble(wlan)
    provider=(ROOT/'kernel/provider/execution.c').read_text()
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['module.h','mutex.h','errno.h','string.h']:(d/'linux'/name).write_text('/* boundary models */\n')
        (d/'execution.c').write_text(provider)
        (d/'mishare_wlan_execution.h').write_text((ROOT/'kernel/provider/mishare_wlan_execution.h').read_text())
        source=d/'test.c';source.write_text(code);exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(source),'-o',str(exe)]
        subprocess.run(command,check=True)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        out=subprocess.check_output([exe],text=True,env=env,timeout=20)
        mutations=[
            (provider.replace('else if (!try_module_get(execution_ops.owner))','else if (false && !try_module_get(execution_ops.owner))',1),code,'EXPECTED_EXEC_PIN'),
            (provider.replace('module_put(owner);','if (false) module_put(owner);',1),code,'EXPECTED_EXTERNAL_RETURN'),
            (provider.replace('ret = ops.reinit(dev);\n    execution_leave(ops.owner);','execution_leave(ops.owner);\n    ret = ops.reinit(dev);',1),code,'EXPECTED_EXTERNAL_RETURN'),
            (provider.replace('else if (execution_closing)\n        ret = -ESHUTDOWN;','else if (false && execution_closing)\n        ret = -ESHUTDOWN;',1),code,'EXPECTED_CLOSING_REFUSAL'),
            (provider.replace('if (execution_active)\n            ret = -EBUSY;','if (false && execution_active)\n            ret = -EBUSY;'),code,'EXPECTED_CLOSE_DRAIN'),
        ]
        for changed,changed_code,marker in mutations:
            assert changed!=provider
            (d/'execution.c').write_text(changed);source.write_text(changed_code);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=20)
            assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[:2000])
    report={'status':'MISHARE_EXTERNAL_EXECUTION_FIXTURE_PASS_ONLY','source_commit':subprocess.check_output(['git','-C',str(wlan),'rev-parse','HEAD'],text=True).strip(),'fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'execution_header_sha256':hashlib.sha256((ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes()).hexdigest(),'native_ipci_sha256':hashlib.sha256(native.encode()).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in fragments.items()},'negative_controls_rejected':len(mutations),'sanitizers':['address','undefined','leak detection'],'limitations':'Production external provider and full native IPCI register/unregister/reinit/shutdown functions execute with modeled module loader, ICNSS registration and vendor callbacks. Real pthread close versus callback overlap is exercised; native DSC, firmware, real rmmod and ICNSS unregister/error-path drain contracts are not executed. Only SSR shutdown/reinit slots use this boundary; remove, crash shutdown, other native callback types and managed metadata self-detach remain outside certification. A void unregister refusal still needs its upper caller to honor preflight; no hot-unplug or forced-unload safety.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(out,end='')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
