#!/usr/bin/env python3
"""Actions-only production registry/transaction C and extracted native origin hooks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from popsicle_backend_audit import PIN
ROOT=Path(__file__).resolve().parents[2]
RX='qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_rx_ops.c'
TXDEFS='qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/inc/wlan_vdev_mgr_tgt_if_tx_defs.h'
RXDEFS='qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/inc/wlan_vdev_mgr_tgt_if_rx_defs.h'
COMMON=r'''
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "wlan_hdd_mishare_events.h"
#define QDF_STATUS_SUCCESS 0
#define QDF_PASSTHRU_MODE 17
#define WLAN_HDD_ID_OBJ_MGR 1
#define GFP_KERNEL 0
#define WARN_ON(x) (x)
#define DEFINE_SPINLOCK(name) pthread_mutex_t name=PTHREAD_MUTEX_INITIALIZER
static _Thread_local int lock_depth;
#define spin_lock_irqsave(lock,flags) do { (flags)=0; assert(!lock_depth); assert(!pthread_mutex_lock(lock));lock_depth++; } while(0)
#define spin_unlock_irqrestore(lock,flags) do { (void)(flags);assert(lock_depth==1);lock_depth--;assert(!pthread_mutex_unlock(lock)); } while(0)
struct wlan_objmgr_psoc { int id; };
struct wlan_objmgr_vdev { struct wlan_objmgr_psoc *psoc; u8 id; int mode,refs,dead; };
static int fail_alloc, allocations, releases, release_reenter, legacy_calls;
static void *kzalloc(size_t n,int gfp) { (void)gfp;assert(!lock_depth);if(fail_alloc)return NULL;allocations++;return calloc(1,n); }
static void kfree(void *p) { assert(!lock_depth);if(p)allocations--;free(p); }
static int wlan_objmgr_vdev_try_get_ref(struct wlan_objmgr_vdev *v,int id) {
 assert(!lock_depth && id==WLAN_HDD_ID_OBJ_MGR);if(v->dead)return -1;v->refs++;return 0;
}
static void wlan_objmgr_vdev_release_ref(struct wlan_objmgr_vdev *v,int id) {
 assert(!lock_depth && id==WLAN_HDD_ID_OBJ_MGR && v->refs>0);v->refs--;releases++;
 if(release_reenter) assert(mishare_events_notify(v->psoc,v->id,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true)==-ENOENT);
}
static int wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { assert(v->refs>0);return v->mode; }
static struct wlan_objmgr_psoc *wlan_vdev_get_psoc(struct wlan_objmgr_vdev *v) { assert(v->refs>0);return v->psoc; }
static u8 wlan_vdev_get_id(struct wlan_objmgr_vdev *v) { assert(v->refs>0);return v->id; }
#include "wlan_hdd_mishare_txn.c"
#include "wlan_hdd_mishare_events.c"
'''
HARNESS=r'''
static struct mishare_vdev_txn snapshot(struct mishare_event_owner *o) {
 struct mishare_vdev_txn s;assert(!mishare_events_snapshot(o,&s));return s;
}
struct stress_context { struct wlan_objmgr_psoc *psoc; u8 id; atomic_int quit,seen,missing; };
static void *notifier_thread(void *data) {
 struct stress_context *ctx=data;
 while(!atomic_load(&ctx->quit)) {
  int ret=mishare_events_notify(ctx->psoc,ctx->id,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true);
  if(ret==-EALREADY) atomic_fetch_add(&ctx->seen,1);
  else { assert(ret==-ENOENT);atomic_fetch_add(&ctx->missing,1); }
 }
 return NULL;
}
int main(void) {
 struct wlan_objmgr_psoc p={1},q={2};
 struct wlan_objmgr_vdev v={.psoc=&p,.id=7,.mode=17};
 struct mishare_event_owner *a=NULL,*b=NULL;
 struct mishare_vdev_txn s;u64 ticket,stop;
 assert(mishare_events_bind(NULL,&a)==-EINVAL);
 assert(mishare_events_bind(&v,NULL)==-EINVAL);
 assert(mishare_events_begin(NULL,MISHARE_TXN_START,&ticket)==-EINVAL && !ticket);
 assert(mishare_events_submitted(NULL,1,MISHARE_TXN_ACCEPTED)==-EINVAL);
 assert(mishare_events_snapshot(NULL,&s)==-EINVAL);
 assert(mishare_events_notify(NULL,7,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true)==-EINVAL);
 mishare_events_unbind(NULL);mishare_events_unbind(&a);
 v.dead=1;assert(mishare_events_bind(&v,&a)==-ENODEV && !a && !v.refs);v.dead=0;
 v.mode=0;assert(mishare_events_bind(&v,&a)==-EOPNOTSUPP && !a && !v.refs);v.mode=17;
 v.psoc=NULL;assert(mishare_events_bind(&v,&a)==-ENODEV && !a && !v.refs);v.psoc=&p;
 fail_alloc=1;assert(mishare_events_bind(&v,&a)==-ENOMEM && !a && !v.refs);fail_alloc=0;
 origin_stop_fw(&p,7);assert(legacy_calls==1);
 assert(!mishare_events_bind(&v,&a) && a && v.refs==1 && allocations==1);
 assert(mishare_events_bind(&v,&a)==-EBUSY && v.refs==1);
 assert(mishare_events_bind(&v,&b)==-EEXIST && !b && v.refs==1 && allocations==1);
 struct wlan_objmgr_vdev other={.psoc=&q,.id=7,.mode=17};
 assert(!mishare_events_bind(&other,&b) && other.refs==1);
 assert(!mishare_events_begin(a,MISHARE_TXN_START,&ticket));
 assert(mishare_events_notify(&p,8,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true)==-ENOENT);
 origin_start_fw(&q,7,WMI_HOST_VDEV_START_RESP_EVENT,WLAN_MLME_HOST_VDEV_START_OK);
 assert(snapshot(a).pending==MISHARE_TXN_START && !snapshot(a).replied);
 /* Native RESTART origin must not complete a one-shot START transaction. */
 origin_start_fw(&p,7,WMI_HOST_VDEV_RESTART_RESP_EVENT,WLAN_MLME_HOST_VDEV_START_OK);
 origin_start_timeout(&p,7,WMI_HOST_VDEV_RESTART_RESP_EVENT);
 assert(!snapshot(a).replied && snapshot(a).state==MISHARE_TXN_COLD);
 origin_start_fw(&p,7,WMI_HOST_VDEV_START_RESP_EVENT,WLAN_MLME_HOST_VDEV_START_OK);
 assert(snapshot(a).replied && !snapshot(a).submitted && snapshot(a).state==MISHARE_TXN_COLD);
 assert(!mishare_events_submitted(a,ticket,MISHARE_TXN_ACCEPTED));
 assert(snapshot(a).state==MISHARE_TXN_STARTED);
 assert(!mishare_events_begin(a,MISHARE_TXN_STOP,&stop));
 assert(!mishare_events_submitted(a,stop,MISHARE_TXN_ACCEPTED));
 /* A stale START timeout cannot affect the pending STOP. */
 origin_start_timeout(&p,7,WMI_HOST_VDEV_START_RESP_EVENT);
 assert(snapshot(a).pending==MISHARE_TXN_STOP && snapshot(a).state==MISHARE_TXN_STARTED);
 int prior_legacy=legacy_calls;
 origin_stop_timeout(&p,7);
 assert(legacy_calls==prior_legacy+1 && snapshot(a).state==MISHARE_TXN_QUARANTINED);
 origin_stop_fw(&p,7);assert(snapshot(a).state==MISHARE_TXN_QUARANTINED);
 assert(v.refs==1 && allocations==2); /* No automatic free on timeout. */
 release_reenter=1;mishare_events_unbind(&a);release_reenter=0;
 assert(!a && !v.refs && allocations==1);
 mishare_events_unbind(&a);mishare_events_unbind(&b);assert(!other.refs && !allocations);
 /* Negative START firmware response quarantines. */
 v.id=8;assert(!mishare_events_bind(&v,&a));
 assert(!mishare_events_begin(a,MISHARE_TXN_START,&ticket));
 assert(!mishare_events_submitted(a,ticket,MISHARE_TXN_ACCEPTED));
 origin_start_fw(&p,8,WMI_HOST_VDEV_START_RESP_EVENT,WLAN_MLME_HOST_VDEV_START_CHAN_INVALID);
 assert(snapshot(a).state==MISHARE_TXN_QUARANTINED);mishare_events_unbind(&a);
 /* Real STOP response completes; later synthetic timeout does not undo it. */
 v.id=9;assert(!mishare_events_bind(&v,&a));
 assert(!mishare_events_begin(a,MISHARE_TXN_START,&ticket));
 assert(!mishare_events_submitted(a,ticket,MISHARE_TXN_ACCEPTED));
 origin_start_fw(&p,9,WMI_HOST_VDEV_START_RESP_EVENT,WLAN_MLME_HOST_VDEV_START_OK);
 assert(!mishare_events_begin(a,MISHARE_TXN_STOP,&stop));
 assert(!mishare_events_submitted(a,stop,MISHARE_TXN_ACCEPTED));
 origin_stop_fw(&p,9);assert(snapshot(a).state==MISHARE_TXN_STOPPED);
 origin_stop_timeout(&p,9);assert(snapshot(a).state==MISHARE_TXN_STOPPED);
 mishare_events_unbind(&a);
 /* Native START timeout is distinct, even if a later real response arrives. */
 v.id=10;assert(!mishare_events_bind(&v,&a));
 assert(!mishare_events_begin(a,MISHARE_TXN_START,&ticket));
 origin_start_timeout(&p,10,WMI_HOST_VDEV_START_RESP_EVENT);
 origin_start_fw(&p,10,WMI_HOST_VDEV_START_RESP_EVENT,WLAN_MLME_HOST_VDEV_START_OK);
 assert(snapshot(a).state==MISHARE_TXN_QUARANTINED);mishare_events_unbind(&a);
 /* Notifications carry keys only. Concurrent removal/free leaves no owner pointer
  * in the notifier. Fake pthread lock verifies this host model, not kernel IRQs.
  */
 v.id=11;assert(!mishare_events_bind(&v,&a));
 struct stress_context ctx={.psoc=&p,.id=11};pthread_t thread;
 assert(!pthread_create(&thread,NULL,notifier_thread,&ctx));
 while(atomic_load(&ctx.seen)<100) sched_yield();
 mishare_events_unbind(&a);
 while(atomic_load(&ctx.missing)<100) sched_yield();
 atomic_store(&ctx.quit,1);assert(!pthread_join(thread,NULL));
 assert(!a && !allocations && !v.refs && !mishare_event_owners && releases>0);
 puts("MISHARE_NATIVE_EVENT_ORIGIN_FIXTURE_PASS_ONLY");return 0;
}
'''


def extract_hooks(root):
    after=(root/RX).read_text()
    patterns={
      'start_timeout':r'\t\t/\* Preserve timeout origin before recovery/common callback\. \*/\n\t\tif \(start_rsp\.resp_type == WMI_HOST_VDEV_START_RESP_EVENT\)\n\t\t\tmishare_events_notify\(psoc, vdev_id, MISHARE_TXN_START,\s+MISHARE_EVENT_TIMEOUT, false\);\n',
      'stop_timeout':r'\t\tmishare_events_notify\(psoc, vdev_id, MISHARE_TXN_STOP,\s+MISHARE_EVENT_TIMEOUT, false\);\n',
      'start_fw':r'\t/\* The transport validated/stopped the matching response timer above\. \*/\n\tif \(vdev_start_resp\.resp_type == WMI_HOST_VDEV_START_RESP_EVENT\)\n\t\tmishare_events_notify\(psoc, vdev_id, MISHARE_TXN_START,\s+MISHARE_EVENT_FIRMWARE,\s+vdev_start_resp\.status == WLAN_MLME_HOST_VDEV_START_OK\);\n',
      'stop_fw':r'\tmishare_events_notify\(psoc, vdev_id, MISHARE_TXN_STOP,\s+MISHARE_EVENT_FIRMWARE, true\);\n',
    }
    hooks={}
    restored=after.replace('#include <wlan_hdd_mishare_events.h>\n','')
    for name,pattern in patterns.items():
        matches=list(re.finditer(pattern,after))
        if len(matches)!=1:raise ValueError('Native hook extraction failed: '+name)
        m=matches[0];hooks[name]=m[0];restored=restored.replace(m[0],'')
        if name.endswith('timeout'):
            end=after.index('target_if_vdev_mgr_handle_recovery',m.end())
            stop=after.rfind('target_if_vdev_mgr_rsp_timer_stop',0,m.start())
            if not (stop<m.start()<m.end()<=end):raise ValueError('Timeout provenance moved')
        else:
            gate=after.rfind('if (QDF_IS_STATUS_ERROR(status))',0,m.start())
            exit_gate=after.index('goto err;',gate)
            if not gate<exit_gate<m.start():raise ValueError('Response timer gate moved')
    before=subprocess.check_output(['git','-C',str(root),'show','HEAD:'+RX],text=True)
    from mishare_ndi_origins import remove_owned_delete_hooks, remove_stop_id_guard
    restored=remove_stop_id_guard(remove_owned_delete_hooks(restored))
    if restored!=before:raise ValueError('Native RX change exceeds origin-only insertions')
    # Public response layouts must remain byte-identical to the locked source.
    for path in [TXDEFS,RXDEFS]:
        if (root/path).read_text()!=subprocess.check_output(['git','-C',str(root),'show','HEAD:'+path],text=True):
            raise ValueError('Unexpected public response definition change')
    return hooks


def fixture(root):
    hooks=extract_hooks(root)
    wmi=(root/'qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h').read_text()
    event=re.search(r'typedef enum \{\s*/\* Event response of START CMD \*/.*?\} WMI_HOST_START_EVENT_PARAM;',wmi,re.S)[0]
    status=re.search(r'enum wlan_mlme_host_vdev_start_status\s*\{.*?\};',(root/TXDEFS).read_text(),re.S)[0]
    code=COMMON+'\n'+event+'\n'+status+'\n'
    code+='struct start_response { unsigned int resp_type,status; };\n'
    code+='static void origin_start_fw(struct wlan_objmgr_psoc *psoc,u8 vdev_id,unsigned int type,unsigned int status) {\nstruct start_response vdev_start_resp={type,status};\n'+hooks['start_fw']+'legacy_calls++;\n}\n'
    code+='static void origin_start_timeout(struct wlan_objmgr_psoc *psoc,u8 vdev_id,unsigned int type) {\nstruct start_response start_rsp={type,WLAN_MLME_HOST_VDEV_START_TIMEOUT};\n'+hooks['start_timeout']+'legacy_calls++;\n}\n'
    for name in ['stop_fw','stop_timeout']:
        code+='static void origin_'+name+'(struct wlan_objmgr_psoc *psoc,u8 vdev_id) {\n'+hooks[name]+'legacy_calls++;\n}\n'
    return code+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected source commit')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;\ntypedef uint64_t u64;\n')
        for n in ['linux/bug.h','linux/slab.h','linux/spinlock.h','wlan_objmgr_vdev_obj.h']:(d/n).write_text('/* supplied by fixture */\n')
        (d/'test.c').write_text(source);exe=d/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'test.c'),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if output.strip()!='MISHARE_NATIVE_EVENT_ORIGIN_FIXTURE_PASS_ONLY':raise ValueError('Unexpected output')
    return {'status':'MISHARE_NATIVE_EVENT_ORIGIN_FIXTURE_PASS_ONLY','source_commit':PIN,
      'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
      'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_events.c','wlan_hdd_mishare_events.h','wlan_hdd_mishare_txn.c','wlan_hdd_mishare_txn.h']},
      'native_rx_sha256':hashlib.sha256((root/RX).read_bytes()).hexdigest(),'native_rx_origin_insertions_only':False,'native_rx_origin_insertions_and_stop_id_guard_only':True,'public_response_definitions_unchanged':True,
      'checks':['no owner leaves legacy flow','PASSTHRU-only bind','vdev reference and allocation failure rollback','duplicate key and owner rejection','same vdev ID across psocs','early real response','restart exclusion','wrong-command timeout exclusion','real start failure','native start/stop timeout quarantine','late firmware response remains quarantined','real stop completes','late timeout after completion ignored','unbind removes before reference release','concurrent key notification versus unregister/free'],
      'limitations':'Production registry/transaction C with simulated object manager and pthread lock, plus extracted actual origin insertions. Not full native handler/timer execution, real IRQ locking, vdev/event draining, WMI, kernel teardown or AirDrop certification. No runtime owner binds yet.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
