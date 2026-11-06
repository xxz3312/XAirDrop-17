#!/usr/bin/env python3
from mishare_live_origins import restore_live_additions
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
#include <unistd.h>
#include <sys/wait.h>
struct module {atomic_int refs;atomic_bool deny,coming;};
static struct module wlan_module,foreign_module;
#define THIS_MODULE (&wlan_module)
struct device {int id;};
struct mutex {pthread_mutex_t value;};
#define DEFINE_MUTEX(n) struct mutex n={PTHREAD_MUTEX_INITIALIZER}
static void mutex_lock(struct mutex *m) {assert(!pthread_mutex_lock(&m->value));}
static void mutex_unlock(struct mutex *m) {assert(!pthread_mutex_unlock(&m->value));}
static _Thread_local bool in_wlan,expect_final_return,callback_returned;
static atomic_int execution_get_count,execution_put_count;
static bool try_module_get(struct module *m) {
 assert(m);atomic_fetch_add(&execution_get_count,1);if(atomic_load(&m->deny))return false;
 atomic_fetch_add(&m->refs,1);return true;
}
static inline bool module_is_coming(struct module *m) {return atomic_load(&m->coming);}
static bool module_is_live(struct module *m) {return !atomic_load(&m->deny);}
static void module_put(struct module *m) {
 int previous=atomic_fetch_sub(&m->refs,1);assert(previous>0 && "EXPECTED_EXEC_PUT_BALANCE");
 if(previous==1 && expect_final_return)assert(!in_wlan && callback_returned && "EXPECTED_EXTERNAL_RETURN");
 atomic_fetch_add(&execution_put_count,1);
}
#define EXPORT_SYMBOL(x)
#define pr_err(...) ((void)0)
#include "mishare_wlan_execution.h"
'''
HARNESS = r'''
#include "execution.c"
#define PLD_BUS_TYPE_IPCI 42
#define PLD_BUS_TYPE_SNOC 43
struct pld_ops {void (*remove)(struct device *,int);int (*reinit)(struct device *,int,void *,void *);void (*shutdown)(struct device *,int);int (*idle_restart)(struct device *,int);int (*idle_shutdown)(struct device *,int);};
struct pld_context {struct pld_ops *ops;int pld_driver_state;};
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
static int vendor_idle_restart(struct device *d,int bus) {assert(d==&dev && bus==42);vendor_body();return callback_result;}
static int vendor_idle_shutdown(struct device *d,int bus) {assert(d==&dev && bus==42);vendor_body();return callback_result;}
static struct pld_ops native_ops={.reinit=vendor_reinit,.shutdown=vendor_shutdown,.idle_restart=vendor_idle_restart,.idle_shutdown=vendor_idle_shutdown};
static struct pld_context native_context={.ops=&native_ops};
static bool context_missing;
static struct pld_context *pld_get_global_context(void) {return context_missing?NULL:&native_context;}
static int remove_result,remove_trans_result,removed,sync_destroyed;
struct osif_psoc_sync {int active;};
static struct osif_psoc_sync remove_sync;
static void cds_set_driver_loaded(bool x) {(void)x;}
static void cds_set_unload_in_progress(bool x) {(void)x;}
static int osif_psoc_sync_trans_start_wait(struct device *d,struct osif_psoc_sync **s) {assert(d==&dev);*s=&remove_sync;return remove_trans_result;}
static void osif_psoc_sync_wait_for_ops(struct osif_psoc_sync *s) {assert(s==&remove_sync);}
static int hdd_mishare_remove_prepare(struct device *d) {assert(d==&dev);return remove_result;}
static void osif_psoc_sync_unregister(struct device *d) {assert(d==&dev);}
static void pld_del_dev(struct pld_context *c,struct device *d) {assert(c==&native_context && d==&dev);}
static void osif_psoc_sync_trans_stop(struct osif_psoc_sync *s) {assert(s==&remove_sync);}
static void osif_psoc_sync_destroy(struct osif_psoc_sync *s) {assert(s==&remove_sync);sync_destroyed++;}
static void vendor_remove(struct device *d,int bus) {assert(d==&dev && bus==43);removed++;}
NATIVE_REMOVE
NATIVE_REINIT
NATIVE_SHUTDOWN
NATIVE_IDLE_RESTART
NATIVE_IDLE_SHUTDOWN
struct icnss_driver_ops {void (*shutdown)(struct device *);int (*reinit)(struct device *);int (*idle_restart)(struct device *);int (*idle_shutdown)(struct device *);};
static struct icnss_driver_ops pld_ipci_ops={NATIVE_SLOTS NATIVE_IDLE_SLOTS};
static int native_register_result,native_registers,native_unregisters,native_unregister_result;
static bool native_remove_enabled;
static int icnss_register_driver(struct icnss_driver_ops *ops) {
 assert(ops==&pld_ipci_ops && ops->shutdown==opairshare_wlan_execution_shutdown && ops->reinit==opairshare_wlan_execution_reinit && ops->idle_restart==opairshare_wlan_execution_idle_restart && ops->idle_shutdown==opairshare_wlan_execution_idle_shutdown && "EXPECTED_EXTERNAL_SLOTS");
 native_registers++;return native_register_result;
}
static int icnss_unregister_driver(struct icnss_driver_ops *ops) {assert(ops==&pld_ipci_ops && !execution_active && "EXPECTED_UNREGISTER_DRAIN");native_unregisters++;if(native_remove_enabled && !native_unregister_result)pld_ipci_remove(&dev);return native_unregister_result;}
NATIVE_DESCRIPTOR
NATIVE_REGISTER
NATIVE_CHECKED
NATIVE_UNREGISTER
static int other_bus_calls;
static void pld_pcie_unregister_driver(void) {other_bus_calls++;}
static void pld_snoc_fw_sim_unregister_driver(void) {other_bus_calls++;}
static void pld_pcie_fw_sim_unregister_driver(void) {other_bus_calls++;}
static void pld_snoc_unregister_driver(void) {other_bus_calls++;}
static void pld_sdio_unregister_driver(void) {other_bus_calls++;}
static void pld_usb_unregister_driver(void) {other_bus_calls++;}
NATIVE_COMMON_CHECKED
NATIVE_HDD_CHECKED
#define hdd_err(...) ((void)0)
static int component_deinits;
static void native_late_unload(void) {
 int mishare_ret;int *private_result=NULL;
NATIVE_LATE_GUARD
 component_deinits++;
}
static int thread_kind;
static void prepare(int private_count) {
 assert(!execution_ops.owner && !execution_active && !atomic_load(&wlan_module.refs));
 native_unregister_result=0;native_remove_enabled=false;native_context.ops=&native_ops;native_context.pld_driver_state=1;native_ops.remove=vendor_remove;remove_result=remove_trans_result=removed=sync_destroyed=other_bus_calls=0;
 thread_kind=0;context_missing=false;private_refs=private_count;atomic_store(&wlan_module.refs,private_count);atomic_store(&wlan_module.deny,false);
 expect_final_return=false;callback_returned=false;in_wlan=false;blocking=entered=allow_return=false;callback_calls=0;callback_result=0;native_register_result=0;
}
static void invoke_shutdown(void) {expect_final_return=true;callback_returned=false;pld_ipci_ops.shutdown(&dev);expect_final_return=false;}
static int invoke_reinit(void) {expect_final_return=true;callback_returned=false;int ret=pld_ipci_ops.reinit(&dev);expect_final_return=false;return ret;}
static int invoke_idle(bool shutdown,bool vendor_expected) {
 expect_final_return=vendor_expected;callback_returned=false;
 int ret=shutdown?pld_ipci_ops.idle_shutdown(&dev):pld_ipci_ops.idle_restart(&dev);
 expect_final_return=false;return ret;
}
static void *run_callback(void *unused) {(void)unused;int ret=thread_kind?invoke_idle(thread_kind==1,true):invoke_reinit();assert(ret==-EIO);return NULL;}
static void unregister_failure_case(int kind) {
 prepare(0);assert(!pld_ipci_register_driver());native_remove_enabled=true;
 if(kind==0)remove_result=-EINPROGRESS;
 if(kind==1)remove_result=-EUCLEAN;
 if(kind==2)remove_trans_result=-EBUSY;
 if(kind==3)context_missing=true;
 if(kind==4)native_unregister_result=-ENOMEM;
 if(kind<3 || kind==4) {
  component_deinits=0;native_late_unload();assert(!component_deinits && "EXPECTED_LATE_UNLOAD_RETAINED");
  int expected=kind==0?-EINPROGRESS:kind==1?-EUCLEAN:kind==4?-ENOMEM:-EBUSY;
  assert(wlan_hdd_unregister_driver_checked()==expected && "EXPECTED_CHECKED_REMOVE_ERROR");
  assert(!other_bus_calls && native_context.ops && native_context.pld_driver_state==1 && !removed && !sync_destroyed && "EXPECTED_GLOBAL_RETAINED");
  assert(unregister_scope && atomic_load(&wlan_module.refs)==1 && "EXPECTED_FAILED_SCOPE_PIN");
  int before=native_unregisters;assert(wlan_hdd_unregister_driver_checked()==expected && native_unregisters==before && "EXPECTED_FAILED_NO_REPLAY");
  assert(opairshare_wlan_execution_unregister(THIS_MODULE)==expected && execution_ops.owner && "EXPECTED_FAILED_SCOPE_RETAINED");
 } else {
  assert(!opairshare_wlan_execution_unregister_begin(THIS_MODULE,false));
  pld_ipci_remove(&dev);
  assert(opairshare_wlan_execution_unregister_end(THIS_MODULE,0)==-ENODEV && !removed && sync_destroyed==1 && "EXPECTED_REMOVE_CONTEXT_ERROR");
 }
}
static void unregister_cases(void) {
 for(int k=0;k<5;k++) {
  pid_t child=fork();assert(child>=0);if(!child){unregister_failure_case(k);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_REMOVE_FAILURE_CHILD");
 }
 prepare(0);assert(!pld_ipci_register_driver());native_remove_enabled=true;
 assert(!wlan_hdd_unregister_driver_checked() && removed==1 && sync_destroyed==1 && other_bus_calls==6 && !native_context.ops && !native_context.pld_driver_state && !execution_ops.owner && !atomic_load(&wlan_module.refs) && "EXPECTED_CHECKED_REMOVE_SUCCESS");
 prepare(0);assert(!pld_ipci_register_driver());atomic_store(&wlan_module.deny,true);int gets=atomic_load(&execution_get_count);
 assert(!pld_ipci_unregister_driver_checked() && !execution_ops.owner && atomic_load(&execution_get_count)==gets && "EXPECTED_BORROWED_EXIT");
 prepare(0);assert(!pld_ipci_register_driver());
 assert(opairshare_wlan_execution_unregister_begin(&foreign_module,false)==-EBUSY);
 assert(opairshare_wlan_execution_unregister_begin(THIS_MODULE,true)==-EINVAL);
 assert(!opairshare_wlan_execution_unregister_begin(THIS_MODULE,false));bool recorded=false;
 assert(!opairshare_wlan_execution_remove_begin(THIS_MODULE,&dev,&recorded) && recorded);
 assert(opairshare_wlan_execution_unregister_end(THIS_MODULE,0)==-EINPROGRESS && "EXPECTED_PENDING_RECEIPT");
 assert(opairshare_wlan_execution_unregister(THIS_MODULE)==-EBUSY && execution_ops.owner);
 assert(!opairshare_wlan_execution_remove_end(THIS_MODULE,&dev,0));
 assert(!opairshare_wlan_execution_unregister_end(THIS_MODULE,0) && !execution_ops.owner && !atomic_load(&wlan_module.refs));
 for(int kind=0;kind<2;kind++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   prepare(0);assert(!pld_ipci_register_driver());assert(!opairshare_wlan_execution_unregister_begin(THIS_MODULE,false));
   bool rec=false;assert(!opairshare_wlan_execution_remove_begin(THIS_MODULE,&dev,&rec) && rec);
   if(kind==0){struct device wrong={2};assert(opairshare_wlan_execution_remove_end(THIS_MODULE,&wrong,0)==-EUCLEAN);}
   else assert(opairshare_wlan_execution_remove_begin(THIS_MODULE,&dev,&rec)==-EBUSY && !rec);
   assert(!(!opairshare_wlan_execution_unregister_end(THIS_MODULE,0)) && execution_ops.owner && atomic_load(&wlan_module.refs)==1 && "EXPECTED_RECEIPT_FAIL_CLOSED");_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
int main(void) {
 unregister_cases();
 assert(opairshare_wlan_execution_register_v2(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_close(NULL)==-EINVAL && opairshare_wlan_execution_unregister(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_reinit(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_reinit(&dev)==-ENODEV);opairshare_wlan_execution_shutdown(NULL);opairshare_wlan_execution_shutdown(&dev);
 prepare(0);struct mishare_wlan_execution_ops bad=pld_ipci_execution;bad.reinit=NULL;
 assert(opairshare_wlan_execution_register_v2(&bad)==-EINVAL);
 bad=pld_ipci_execution;bad.idle_shutdown=NULL;assert(opairshare_wlan_execution_register_v2(&bad)==-EINVAL);
 bad=pld_ipci_execution;bad.idle_restart=NULL;assert(opairshare_wlan_execution_register_v2(&bad)==-EINVAL);
 assert(!pld_ipci_register_driver());int registrations=native_registers;
 assert(pld_ipci_register_driver()==-EALREADY && native_registers==registrations && "EXPECTED_REGISTER_OWNERSHIP");
 bad=pld_ipci_execution;bad.owner=&foreign_module;assert(opairshare_wlan_execution_register_v2(&bad)==-EBUSY);
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
 assert(opairshare_wlan_execution_register_v2(&pld_ipci_execution)==-ESHUTDOWN);pld_ipci_unregister_driver();
 prepare(0);native_register_result=-EIO;assert(pld_ipci_register_driver()==-EIO && !execution_ops.owner && "EXPECTED_REGISTER_ROLLBACK");
 prepare(0);struct mishare_wlan_execution_ops copy=pld_ipci_execution;assert(!opairshare_wlan_execution_register_v2(&copy));memset(&copy,0,sizeof(copy));
 assert(invoke_reinit()==0 && callback_calls==1 && "EXPECTED_DESCRIPTOR_COPY");assert(!opairshare_wlan_execution_unregister(&wlan_module));

 for(int kind=0;kind<2;kind++) {
  prepare(1);assert(!pld_ipci_register_driver());callback_result=kind?-EINPROGRESS:-EAGAIN;
  assert(invoke_idle(kind==0,true)==callback_result && callback_calls==1 && !private_refs && !atomic_load(&wlan_module.refs) && "EXPECTED_IDLE_RETURN");
  pld_ipci_unregister_driver();
 }
 prepare(0);assert(!pld_ipci_register_driver());callback_result=-EIO;native_ops.shutdown=NULL;
 assert(invoke_idle(true,false)==-EIO && callback_calls==1 && !atomic_load(&wlan_module.refs) && "EXPECTED_IDLE_GUARD");native_ops.shutdown=vendor_shutdown;
 native_ops.idle_shutdown=NULL;assert(invoke_idle(true,false)==-ENODEV && "EXPECTED_IDLE_MISSING_CALLBACK");native_ops.idle_shutdown=vendor_idle_shutdown;
 native_ops.idle_restart=NULL;assert(invoke_idle(false,false)==-ENODEV);native_ops.idle_restart=vendor_idle_restart;
 context_missing=true;assert(invoke_idle(true,false)==-EINVAL && invoke_idle(false,false)==-EINVAL);context_missing=false;
 assert(opairshare_wlan_execution_idle_restart(NULL)==-EINVAL && opairshare_wlan_execution_idle_shutdown(NULL)==-EINVAL);
 atomic_store(&wlan_module.deny,true);assert(invoke_idle(true,false)==-ESHUTDOWN && invoke_idle(false,false)==-ESHUTDOWN);atomic_store(&wlan_module.deny,false);
 assert(!opairshare_wlan_execution_close(&wlan_module));assert(invoke_idle(true,false)==-ESHUTDOWN && invoke_idle(false,false)==-ESHUTDOWN && "EXPECTED_IDLE_CLOSING");
 assert(callback_calls==1 && !atomic_load(&wlan_module.refs));pld_ipci_unregister_driver();
 for(int kind=0;kind<3;kind++) {
 prepare(1);assert(!pld_ipci_register_driver());thread_kind=kind;blocking=true;callback_result=-EIO;
 pthread_t thread;assert(!pthread_create(&thread,NULL,run_callback,NULL));
 assert(!pthread_mutex_lock(&block_lock));while(!entered)assert(!pthread_cond_wait(&block_cond,&block_lock));assert(!pthread_mutex_unlock(&block_lock));
 assert(opairshare_wlan_execution_close(&wlan_module)==-EBUSY && "EXPECTED_CLOSE_DRAIN");
 int before=native_unregisters;pld_ipci_unregister_driver();assert(native_unregisters==before && execution_ops.owner && "EXPECTED_UNREGISTER_DRAIN");
 assert(opairshare_wlan_execution_unregister(&wlan_module)==-EBUSY && execution_ops.owner && "EXPECTED_UNREGISTER_DRAIN");
 assert(invoke_reinit()==-ESHUTDOWN && "EXPECTED_CLOSING_REFUSAL");
 assert(!pthread_mutex_lock(&block_lock));allow_return=true;pthread_cond_broadcast(&block_cond);assert(!pthread_mutex_unlock(&block_lock));
 assert(!pthread_join(thread,NULL));assert(!atomic_load(&wlan_module.refs) && !execution_active);
 pld_ipci_unregister_driver();assert(native_unregisters==before+1 && !execution_ops.owner);
 }
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
        'NATIVE_IDLE_RESTART':extract(native,r'^static int pld_ipci_idle_restart_cb\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_IDLE_SHUTDOWN':extract(native,r'^static int pld_ipci_idle_shutdown_cb\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_IDLE_SLOTS':extract(native,r'/\* MISHARE_SSR_STOP_BEGIN:execution_idle_slots \*/.*?/\* MISHARE_SSR_STOP_END:execution_idle_slots \*/'),
        'NATIVE_REGISTER':extract(native,r'^int pld_ipci_register_driver\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_REMOVE':extract(native,r'^static void pld_ipci_remove\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_CHECKED':extract(native,r'^int pld_ipci_unregister_driver_checked\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_LATE_GUARD':extract(restore_live_additions((wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_main.c').read_text()),r'/\* MISHARE_SSR_STOP_BEGIN:unload_checked_unregister \*/.*?/\* MISHARE_SSR_STOP_END:unload_checked_unregister \*/'),
        'NATIVE_COMMON_CHECKED':extract((wlan/'qcacld-3.0/core/pld/src/pld_common.c').read_text(),r'^int pld_unregister_driver_checked\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_HDD_CHECKED':extract((wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_driver_ops.c').read_text(),r'^int wlan_hdd_unregister_driver_checked\([^;{]+?\)\s*\{.*?^\}'),
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
    assert 'EXPORT_SYMBOL(opairshare_wlan_execution_register);' not in provider
    assert 'EXPORT_SYMBOL(opairshare_wlan_execution_register_v2);' in provider
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['module.h','mutex.h','string.h']:(d/'linux'/name).write_text('/* boundary models */\n')
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
        mutations += [
            (provider.replace('ret = ops.idle_shutdown(dev);\n    execution_leave(ops.owner);','execution_leave(ops.owner);\n    ret = ops.idle_shutdown(dev);',1),code,'EXPECTED_EXEC_PIN'),
            (provider,code.replace(fragments['NATIVE_IDLE_SLOTS'],fragments['NATIVE_IDLE_SLOTS'].replace('opairshare_wlan_execution_idle_shutdown','pld_ipci_idle_shutdown_cb',1),1),'EXPECTED_EXTERNAL_SLOTS'),
            (provider,code.replace(fragments['NATIVE_IDLE_SHUTDOWN'],fragments['NATIVE_IDLE_SHUTDOWN'].replace('if (pld_context->ops->idle_shutdown)','if (pld_context->ops->shutdown)',1),1),'EXPECTED_IDLE_GUARD'),
        ]
        mutations += [
            (provider.replace('if (result && !unregister_error)','if (false && result && !unregister_error)',1),code,'EXPECTED_LATE_UNLOAD_RETAINED'),
            (provider.replace('if (unregister_remove_dev || execution_active)','if (false && (unregister_remove_dev || execution_active))',1),code,'EXPECTED_PENDING_RECEIPT'),
            (provider.replace('release = unregister_pin;','release = false;',1),code,'EXPECTED_CHECKED_REMOVE_SUCCESS'),
            (provider,code.replace(fragments['NATIVE_COMMON_CHECKED'],fragments['NATIVE_COMMON_CHECKED'].replace('if (ret)\n\t\treturn ret;','if (false && ret)\n\t\treturn ret;',1),1),'EXPECTED_LATE_UNLOAD_RETAINED'),
            (provider,code.replace(fragments['NATIVE_LATE_GUARD'],fragments['NATIVE_LATE_GUARD'].replace('if (mishare_ret)','if (false && mishare_ret)',1),1),'EXPECTED_LATE_UNLOAD_RETAINED'),
        ]
        mutations.append((provider,code.replace('opairshare_wlan_execution_unregister_end(THIS_MODULE, ret)','opairshare_wlan_execution_unregister_end(THIS_MODULE, 0)',1),'EXPECTED_LATE_UNLOAD_RETAINED'))
        for changed,changed_code,marker in mutations:
            assert changed!=provider or changed_code!=code
            (d/'execution.c').write_text(changed);source.write_text(changed_code);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=20)
            assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[:2000])
    report={'status':'MISHARE_EXTERNAL_EXECUTION_FIXTURE_PASS_ONLY','source_commit':subprocess.check_output(['git','-C',str(wlan),'rev-parse','HEAD'],text=True).strip(),'fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'execution_header_sha256':hashlib.sha256((ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes()).hexdigest(),'native_ipci_sha256':hashlib.sha256(native.encode()).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in fragments.items()},'negative_controls_rejected':len(mutations),'idle_specific_controls_rejected':3,'unregister_receipt_scenarios':12,'retained_failure_child_universes':7,'concurrent_callback_kinds':['SSR reinit','idle shutdown','idle restart'],'registration_export':'opairshare_wlan_execution_register_v2','registration_v1_alias_exported':False,'sanitizers':['address','undefined','leak detection'],'limitations':'Production external provider and full native IPCI register/unregister/reinit/shutdown functions execute with modeled module loader, ICNSS registration and vendor callbacks. Real pthread close versus callback overlap is exercised; native DSC, firmware, real rmmod and ICNSS unregister/error-path drain contracts are not executed. SSR shutdown/reinit and idle shutdown/restart slots use this boundary; physical remove outside unregister, crash shutdown, other native callback types and managed metadata self-detach remain outside certification. Checked IPCI/PLD/HDD unregister now propagates receipts before global clearing; native module-exit cannot veto loader unload; no hot-unplug or forced-unload safety.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(out,end='')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
