#!/usr/bin/env python3
"""Actions-only shutdown admission fencing; no recovery/free certification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_radio_fixture as radio
from mishare_shutdown_origins import remove_shutdown_additions
ROOT = radio.ROOT
OPS = 'qcacld-3.0/core/hdd/src/wlan_hdd_driver_ops.c'
MAIN = 'qcacld-3.0/core/hdd/src/wlan_hdd_main.c'
BASE = {OPS:'8033a302fcf313317e931e8c46f20e793f4e1fadcabf4d397934d188d92804ef',
        MAIN:'becc33f8c7ee68b6b806d944951ebb591034e0060ee1d86f23012eeba08aa891',
        radio.plan.API:'925f135ec416f293363bd0d0e7d3f39991e15849617926f150507b2d4d6609bc'}
MODELS = r'''
#define QDF_MODULE_ID_HDD 5
#define DRIVER_MODULES_ENABLED 3
struct hdd_context {struct wlan_objmgr_psoc *psoc;int driver_status;};
static struct hdd_context health;
static bool health_missing,health_recovering,health_unloading,health_bad,health_stop;
static void *shutdown_cds_get_context(int id) {assert(id==5);return health_missing?NULL:&health;}
static bool cds_is_driver_recovering(void) {return health_recovering;}
static bool cds_is_driver_unloading(void) {return health_unloading;}
static bool cds_is_driver_in_bad_state(void) {return health_bad;}
static bool cds_is_driver_state_module_stop(void) {return health_stop;}
#define cds_get_context shutdown_cds_get_context
NATIVE_PLATFORM
#undef cds_get_context
static void shutdown_ssr(struct hdd_context *hdd_ctx) {NATIVE_SSR}
static void shutdown_remove(struct hdd_context *hdd_ctx) {NATIVE_REMOVE}
static void shutdown_module_stop(struct hdd_context *hdd_ctx) {NATIVE_MODULE_STOP}
'''
HARNESS = r'''
static void reset_shutdown(void) {
 health.psoc=&psoc;health.driver_status=3;
 health_missing=health_recovering=health_unloading=health_bad=health_stop=false;
 reset_radio();
}
static void fence(struct mishare_runtime_owner *o, enum mishare_quiesce_reason reason) {
 struct mishare_vdev_txn before,after;assert(mishare_events_snapshot(o->events,&before)==0);
 unsigned refs=last_vdev->refs;
 assert(mishare_runtime_quiesce_psoc(&psoc,reason)==1);
 assert(state(o).quiesced==reason && state(o).blocked && state(o).ndi.blocked);
 assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1 && state(o).quiesced==reason);
 assert(mishare_events_snapshot(o->events,&after)==0 && after.state==MISHARE_TXN_QUARANTINED);
 assert(before.serial==after.serial && before.pending==after.pending && before.submitted==after.submitted && before.replied==after.replied);
 assert(last_vdev->refs==(int)refs && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls);
 assert(!mishare_runtime_work_allowed(last_vdev,o) && !mishare_runtime_work_allowed(last_vdev,(void*)1));
 assert(mishare_runtime_destroy(&o)==-EUCLEAN && o);
 assert(mishare_runtime_ndi_create(o,1,1)==-EUCLEAN);
 assert(mishare_runtime_ndi_prepare(o)==-EUCLEAN);
 assert(mishare_runtime_ndi_session(o)==-EUCLEAN);
 assert(mishare_runtime_ndi_channel(o,2437)==-EUCLEAN);
 assert(mishare_runtime_ndi_start_plan(o)==-EUCLEAN);
 assert(mishare_runtime_ndi_start(o)==-EUCLEAN);
 u64 ticket=99;assert(mishare_events_begin(o->events,MISHARE_TXN_START,&ticket)==-EUCLEAN && !ticket);
 assert(mishare_events_notify(&psoc,7,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true)==-EUCLEAN);
 assert(mishare_events_notify(&psoc,7,MISHARE_TXN_STOP,MISHARE_EVENT_TIMEOUT,false)==-EUCLEAN);
 /* A reinit health reset cannot revive this owner or another MAC on its psoc. */
 struct mishare_runtime_owner *fresh=NULL;u8 other_mac[6]={2,9,8,7,6,5};
 assert(mishare_runtime_create(&pdev,other_mac,&pdev,&wdev,&fresh)==-EUCLEAN && !fresh);
}
static void *late_response(void *unused) {
 for(unsigned i=0;i<1000;i++)(void)mishare_events_notify(&psoc,7,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true);
 return NULL;
}
int main(void) {
 struct wlan_objmgr_psoc other={9};
 reset_shutdown();assert(!mishare_runtime_quiesce_psoc(NULL,MISHARE_QUIESCE_SSR));
 assert(!mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_NONE));
 assert(!mishare_runtime_quiesce_psoc(&psoc,99));
 assert(mishare_runtime_platform_available(&psoc) && !mishare_runtime_platform_available(NULL) && !mishare_runtime_platform_available(&other));
 /* Execute the native health predicate for every rejection condition. */
 for(int fault=0;fault<7;fault++) {
  reset_shutdown();health_missing=fault==0;health_recovering=fault==1;health_unloading=fault==2;
  health_bad=fault==3;health_stop=fault==4;if(fault==5)health.driver_status=0;if(fault==6)health.psoc=&other;
  struct mishare_runtime_owner *o=NULL;unsigned calls=object_calls;
  assert(!mishare_runtime_platform_available(&psoc));
  assert(mishare_runtime_create(&pdev,mac,&pdev,&wdev,&o)==-ESHUTDOWN && !o && object_calls==(int)calls);
 }
 reset_shutdown();struct mishare_runtime_owner *o=with_plan();
 assert(!mishare_runtime_quiesce_psoc(&other,MISHARE_QUIESCE_SSR) && mishare_runtime_work_allowed(last_vdev,o));
 assert(!mishare_runtime_work_allowed(NULL,o) && !mishare_runtime_work_allowed(last_vdev,(void*)1));
 start_up(o);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);radio_run(false);assert(radio_reply_stop()==QDF_STATUS_SUCCESS);radio_run(false);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);after_radio(&o);
 /* Each child deliberately retains quarantined resources; never reset refs/SM. */
 for(int stage=0;stage<14;stage++) for(int flush=0;flush<2;flush++) {
  reset_shutdown();pid_t child=fork();assert(child>=0);
  if(!child) {
   if(stage==0) {o=prepared();assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);}
   else if(stage==1) {o=with_session();assert(mishare_runtime_ndi_channel(o,2437)==-EINPROGRESS);}
   else if(stage==2) {o=with_channel(2437);assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);}
   else {
    o=with_plan();
    if(stage>=3 && stage<=5) {
     assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);
     if(stage>=4)radio_run(false);
     if(stage==5)assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);
    } else {
     start_up(o);
     if(stage>=7 && stage<=10) {
      assert(mishare_runtime_destroy(&o)==-EINPROGRESS);
      if(stage>=8)radio_run(false);
      if(stage>=9)assert(radio_reply_stop()==QDF_STATUS_SUCCESS);
      if(stage==10)radio_run(false);
     }
    }
   }
   unsigned starts=radio_starts,stops=radio_stops,downs=radio_downs;
   unsigned prepares=ch_prepares,creates=pe_creates,deletes=pe_deletes,refs=last_vdev->refs;
   unsigned expected_refs=refs-(pe_pending.bodyptr?1:0);
   /* Execute the exact native hook insertions, then check first reason. */
   enum mishare_quiesce_reason reason=stage==11?MISHARE_QUIESCE_REMOVE:stage==12?MISHARE_QUIESCE_MODULE_STOP:stage==13?MISHARE_QUIESCE_UNAVAILABLE:MISHARE_QUIESCE_SSR;
   if(stage==11)shutdown_remove(&health);
   else if(stage==12)shutdown_module_stop(&health);
   else if(stage==13) {health_recovering=true;assert(!mishare_runtime_work_allowed(last_vdev,o));health_recovering=false;}
   else shutdown_ssr(&health);
   fence(o,reason);
   while(radio_q_len)radio_run(flush);
   if(pe_pending.bodyptr)run_pe(flush);
   assert(radio_starts==starts && radio_stops==stops && radio_downs==downs);
   assert(ch_prepares==prepares && pe_creates==creates && pe_deletes==deletes);
   assert(last_vdev->refs==(int)expected_refs && !pe_request_allocs);
   assert(!ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls);
   assert(mishare_runtime_destroy(&o)==-EUCLEAN && state(o).quiesced==reason);
   /* Native free notification never clears a shutdown quarantine. */
   mishare_runtime_freed(&psoc,(unsigned long)o);assert(state(o).blocked);
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_shutdown();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=with_plan();assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);radio_run(false);
  pthread_t thread;assert(!pthread_create(&thread,NULL,late_response,NULL));
  assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==1);
  assert(!pthread_join(thread,NULL));struct mishare_vdev_txn txn;
  assert(!mishare_events_snapshot(o->events,&txn) && txn.state==MISHARE_TXN_QUARANTINED);
  assert(!radio_q_len && state(o).radio.phase==MISHARE_RADIO_BLOCKED && mishare_runtime_destroy(&o)==-EUCLEAN);
  _Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 puts("MISHARE_SHUTDOWN_ADMISSION_FIXTURE_PASS_ONLY");return 0;
}
'''

def insertion(source, tag):
    m = re.search(r'/\* MISHARE_SHUTDOWN_BEGIN:'+tag+r' \*/\n(.*?)/\* MISHARE_SHUTDOWN_END:'+tag+r' \*/', source, re.S)
    if not m: raise ValueError('Missing shutdown insertion: '+tag)
    return m[1]


def fixture(root):
    for path, expected in BASE.items():
        source = remove_shutdown_additions((root/path).read_text())
        if hashlib.sha256(source.encode()).hexdigest() != expected:
            raise ValueError('Unbounded shutdown source delta: '+path)
    ops=(root/OPS).read_text();main=(root/MAIN).read_text()
    # Hooks must precede ordinary notifier/backend/context teardown; stop hook
    # follows the native early EAGAIN return, before policy callback removal.
    for tag,body,after in [('ssr',ops,'cds_shutdown_notifier_call();'),('remove',ops,'mishare_wonder_backend_unregister(hdd_ctx);'),('module_stop',main,'hdd_deregister_policy_manager_callback(hdd_ctx->psoc);')]:
        if body.index('MISHARE_SHUTDOWN_BEGIN:'+tag)>body.index(after):raise ValueError('Late shutdown hook: '+tag)
    predicate=insertion(ops,'platform').replace('#include "wlan_hdd_mishare_runtime.h"\n','')
    models=MODELS.replace('NATIVE_PLATFORM',predicate)
    for tag in ['ssr','remove','module_stop']:models=models.replace('NATIVE_'+tag.upper(),insertion(main if tag=='module_stop' else ops,tag))
    src=radio.fixture(root)
    begin=src.index('/* PLATFORM_AVAILABLE_STUB */');end=src.index('/* END_PLATFORM_AVAILABLE_STUB */',begin)+len('/* END_PLATFORM_AVAILABLE_STUB */')
    src=src[:begin]+models+src[end:]
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=radio.plan.channel.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'shutdown.c').write_text(source);exe=d/'shutdown'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'shutdown.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_SHUTDOWN_ADMISSION_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    names=['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h','wlan_hdd_mishare_events.c','wlan_hdd_mishare_events.h']
    return {'status':out.strip(),'source_commit':radio.plan.channel.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in BASE},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},'ordinary_before_shutdown_sha256':BASE,'checks':['native health predicate rejects missing/wrong/disabled/recovery/unload/bad/module-stop context before allocation','exact SSR/remove/module-stop hooks run before native teardown callbacks','wrong PSOC and foreign opaque owner leave live owner unchanged','28 queued/native-response/radio-state and flush combinations retain owned parents and cancel queued work','first shutdown reason and quarantine survive reinit, duplicate shutdown and late free notification','transaction pending/serial/submitted/replied evidence preserved on fencing','all owner APIs and new MAC admission on fenced psoc reject','late response versus shutdown registry locking raced with pthreads'],'limitations':'Executes production owner/radio/event registry, native health predicate and exact bounded shutdown calls under ASan/UBSan. Full native shutdown functions, scheduler/IRQ/timer synchronization, native SM/WMA postprocessing and object/DP primitives remain models. A work admission check is not an in-flight execution barrier. No recovery reclaim, psoc replacement/address reuse, safe active-owner unload, module-text lifetime, concurrency/hardware-mode lease, phone loading or firmware behavior is certified. Existing quarantined owner refs remain retained. Default HDD/Wonder caller stays disabled.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
