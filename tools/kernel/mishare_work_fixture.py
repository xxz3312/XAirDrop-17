#!/usr/bin/env python3
"""Actions-only owned MC reservations, native stop/flush, pure-host reclaim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_shutdown_fixture as shutdown
from mishare_work_origins import remove_work_additions
ROOT=shutdown.ROOT
API=shutdown.radio.plan.API
CDS='qcacld-3.0/core/cds/src/cds_api.c'
SCHED_API='qca-wifi-host-cmn/scheduler/src/scheduler_api.c'
SCHED_CORE='qca-wifi-host-cmn/scheduler/src/scheduler_core.c'
BASE={API:'9e866026a6131f9686252b31c7c623e6aee2d3e09f3e85291f06d7e0637999d3',CDS:'ad92a10b88900e53f7cb34ec0f37dda9b270450ddec80e0738703e6eac94e933'}
MODELS=r'''
#define SCHEDULER_NUMBER_OF_MSG_QUEUE 2
#define MC_SHUTDOWN_EVENT_MASK 0
#define MC_POST_EVENT_MASK 1
#define sched_debug(...) ((void)0)
#define QDF_BUG(x) ((void)(x))
struct scheduler_mq_type {unsigned id;};
struct scheduler_ctx {void *sch_thread;unsigned sch_event_flag,sch_wait_queue,sch_shutdown;struct {struct scheduler_mq_type sch_msg_q[2];} queue_ctx;};
static struct scheduler_ctx native_sched;
static bool native_sched_missing,worker_active;
static unsigned native_phase,native_msg_frees,native_waits;
static struct scheduler_msg native_slot[2];
static pthread_t active_thread;
static pthread_mutex_t pause_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t pause_cond=PTHREAD_COND_INITIALIZER;
static bool pause_entered,pause_resume;
static struct scheduler_ctx *scheduler_get_context(void) {return native_sched_missing?NULL:&native_sched;}
static void qdf_atomic_set_bit(unsigned bit,unsigned *flags) {assert(flags==&native_sched.sch_event_flag && bit<=1);*flags|=1U<<bit;}
static void qdf_wake_up_interruptible(unsigned *queue) {assert(queue==&native_sched.sch_wait_queue && native_sched.sch_event_flag==3);native_phase=1;}
static void qdf_wait_single_event(unsigned *event,unsigned timeout) {
 assert(event==&native_sched.sch_shutdown && !timeout && native_phase==1);native_waits++;
 if(worker_active) {
  assert(!pthread_mutex_lock(&pause_lock));pause_resume=true;assert(!pthread_cond_broadcast(&pause_cond));assert(!pthread_mutex_unlock(&pause_lock));
  assert(!pthread_join(active_thread,NULL));worker_active=false;
 }
 native_phase=2;
}
static struct scheduler_msg *scheduler_mq_get(struct scheduler_mq_type *mq) {
 assert(native_phase==2 && mq->id<2);struct scheduler_msg *out=&native_slot[mq->id];
 if(mq->id==0) {if(!pe_pending.bodyptr)return NULL;*out=pe_pending;pe_pending.bodyptr=NULL;}
 else {if(!radio_q_len)return NULL;*out=radio_q[0];memmove(radio_q,radio_q+1,--radio_q_len*sizeof(*radio_q));}
 return out;
}
static void scheduler_core_msg_free(struct scheduler_msg *msg) {assert(msg && !msg->bodyptr);native_msg_frees++;}
NATIVE_SINGLE_FLUSH
NATIVE_QUEUES_FLUSH
NATIVE_SCHED_DISABLE
static void native_stop_observer(void) {
 struct wma *wma_handle=&wma_context;
 NATIVE_STOP_OBSERVER
}
static QDF_STATUS stop_mc(void) {
 QDF_STATUS status=scheduler_disable();
 if(QDF_IS_STATUS_SUCCESS(status))native_stop_observer();
 return status;
}
static void close_during_health(void) {mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR);}
static void pause_native_pe(void) {
 assert(!pthread_mutex_lock(&pause_lock));pause_entered=true;assert(!pthread_cond_broadcast(&pause_cond));
 while(!pause_resume)assert(!pthread_cond_wait(&pause_cond,&pause_lock));
 assert(!pthread_mutex_unlock(&pause_lock));
}
static void *active_pe(void *unused) {run_pe(false);return NULL;}
'''
HARNESS=r'''
static void reset_work(void) {
 reset_shutdown();assert(!worker_active);memset(&native_sched,0,sizeof(native_sched));native_sched.sch_thread=(void*)1;
 native_sched.queue_ctx.sch_msg_q[0].id=0;native_sched.queue_ctx.sch_msg_q[1].id=1;
 native_sched_missing=false;native_phase=native_msg_frees=native_waits=0;
 pause_entered=pause_resume=false;work_pause_hook=NULL;work_health_fence=NULL;work_close_at=0;
}
static void assert_counts(struct mishare_runtime_owner *o,unsigned pending,unsigned users) {
 struct mishare_runtime_status s=state(o);assert(s.work_pending==pending && s.work_users==users && !s.work_error);
}
static void mark_closed(struct mishare_runtime_owner *o) {
 assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==1);
 assert(state(o).quiesced && !state(o).mc_drained && !state(o).mc_stop_seen);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;struct wlan_objmgr_psoc other={9};
 assert(mishare_runtime_reclaim_host(NULL)==-EINVAL && !mishare_runtime_reclaim_host(&o));
 /* Native success without an owned shutdown fence is never recovery evidence. */
 reset_work();assert(!create(&o));assert(!stop_mc() && !state(o).mc_stop_seen);
 assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN);assert(!mishare_runtime_destroy(&o));
 /* Reclaim a never-wired host through actual object-manager final-free. */
 reset_work();assert(!create(&o));mark_closed(o);
 mishare_runtime_mc_stopped(&other);assert(!state(o).mc_stop_seen);
 assert(mishare_runtime_reclaim_host(&o)==-EINPROGRESS && !delete_calls);
 native_sched_missing=true;assert(stop_mc()==QDF_STATUS_E_INVAL && !state(o).mc_stop_seen);
 native_sched_missing=false;assert(!stop_mc() && native_waits==1 && state(o).mc_drained);
 assert(!mishare_runtime_reclaim_host(&o) && !o && !objects_live && !allocations && !mishare_event_owners);
 /* Deferred native final-free keeps the owner and original shutdown reason. */
 reset_work();defer_ref=1;assert(!create(&o));struct wlan_objmgr_vdev *v=last_vdev;mark_closed(o);assert(!stop_mc());
 assert(mishare_runtime_reclaim_host(&o)==-EINPROGRESS && o && state(o).host_reclaim && state(o).blocked && !state(o).freed);
 assert(state(o).quiesced==MISHARE_QUIESCE_SSR && v->refs==1 && delete_calls==1);
 assert(mishare_runtime_reclaim_host(&o)==-EINPROGRESS && delete_calls==1);
 wlan_objmgr_vdev_release_ref(v,2);assert(state(o).freed && state(o).blocked);
 assert(!mishare_runtime_reclaim_host(&o) && !o && !allocations);
 /* Native queue flushing returns every request reservation and request ref. */
 for(int kind=0;kind<4;kind++) {
  reset_work();pid_t child=fork();assert(child>=0);
  if(!child) {
   if(kind==0) {o=prepared();assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);}
   else if(kind==1) {o=with_session();assert(mishare_runtime_ndi_channel(o,2437)==-EINPROGRESS);}
   else if(kind==2) {o=with_channel(2437);assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);}
   else {o=with_plan();assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);}
   assert_counts(o,1,0);unsigned refs=last_vdev->refs;mark_closed(o);
   assert(mishare_runtime_work_get(last_vdev,o)==-ESHUTDOWN && mishare_runtime_work_enter(last_vdev,o)==-ESHUTDOWN);
   assert(!stop_mc() && native_waits==1 && native_msg_frees==1 && !pe_pending.bodyptr && !radio_q_len);
   assert_counts(o,0,0);assert(state(o).mc_drained && state(o).mc_stop_seen);
   assert(last_vdev->refs==(int)(refs-(kind==3?0:1)) && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls);
   assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && o);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* A native 'already disabled' return is not proof that pending work drained. */
 reset_work();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=prepared();assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);mark_closed(o);native_sched.sch_thread=NULL;
  assert(!stop_mc() && state(o).mc_stop_seen && !state(o).mc_drained && !native_waits && !native_msg_frees);
  assert_counts(o,1,0);assert(mishare_runtime_reclaim_host(&o)==-EINPROGRESS && !delete_calls);
  native_phase=2;scheduler_queues_flush(&native_sched);assert_counts(o,0,0);assert(state(o).mc_drained);
  assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Execute a real owned MC callback in another pthread, paused inside its PE
  * allocator boundary. Native scheduler_disable must join it before flushing. */
 reset_work();child=fork();assert(child>=0);
 if(!child) {
  o=with_plan();work_health_fence=close_during_health;work_close_at=health_queries+2;
  assert(mishare_runtime_ndi_start(o)==-ESHUTDOWN && o->radio);
  assert(state(o).quiesced && state(o).radio.phase==MISHARE_RADIO_BLOCKED && state(o).radio.closing);
  assert_counts(o,0,0);assert(!stop_mc() && state(o).mc_drained);
  assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && !radio_starts && !delete_calls);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 reset_work();child=fork();assert(child>=0);
 if(!child) {
  o=prepared();assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);work_pause_hook=pause_native_pe;worker_active=true;
  assert(!pthread_create(&active_thread,NULL,active_pe,NULL));
  assert(!pthread_mutex_lock(&pause_lock));while(!pause_entered)assert(!pthread_cond_wait(&pause_cond,&pause_lock));assert(!pthread_mutex_unlock(&pause_lock));
  assert_counts(o,1,1);mark_closed(o);assert_counts(o,1,1);
  assert(mishare_runtime_reclaim_host(&o)==-EINPROGRESS && !state(o).mc_stop_seen && !delete_calls);
  assert(!stop_mc() && native_waits==1 && !worker_active && !native_msg_frees);
  assert_counts(o,0,0);assert(state(o).mc_drained && state(o).ndi.pe_ready && state(o).blocked);
  assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls);
  _Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Identity/underflow/overflow corruption is terminal; never reset counters. */
 for(int fault=0;fault<5;fault++) {
  reset_work();child=fork();assert(child>=0);
  if(!child) {
   assert(!create(&o));v=last_vdev;
   assert(mishare_runtime_work_get(v,(void*)1)==-ESHUTDOWN && !state(o).work_error);
   mishare_runtime_work_put(v,(void*)1);assert(!state(o).work_error);
   if(fault==0)mishare_runtime_work_put(v,o);
   if(fault==1)mishare_runtime_work_exit(v,o);
   if(fault==2)assert(mishare_runtime_work_enter(v,o)==-EUCLEAN);
   if(fault==3) {o->state.work_pending=~0U;assert(mishare_runtime_work_get(v,o)==-EOVERFLOW);}
   if(fault==4) {assert(!mishare_runtime_work_get(v,o) && !mishare_runtime_work_enter(v,o));mishare_runtime_work_put(v,o);mishare_runtime_work_exit(v,o);mishare_runtime_work_put(v,o);}
   assert(state(o).work_error && state(o).blocked);mark_closed(o);assert(!stop_mc() && !state(o).mc_drained);
   assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && !delete_calls);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Unsafe reclaim candidates and native delete failure retain their owner. */
 for(int fault=0;fault<8;fault++) {
  reset_work();child=fork();assert(child>=0);
  if(!child) {
   assert(!create(&o));v=last_vdev;
   if(fault==0) {u64 t;assert(!mishare_events_begin(o->events,MISHARE_TXN_START,&t));}
   if(fault==1)v->mlme->mgmt.generic.type=7;
   if(fault==2)ch_state=1;
   if(fault==3)v->mlme->ext_vdev_ptr=(void*)1;
   if(fault==4)o->state.ndi.create.wire_attempted=true;
   if(fault==5)o->state.ndi.dp_detaching=true;
   if(fault==6)delete_fail=1;
   if(fault==7) {leak_component=1;v->vdev_comp_priv_obj[1]=malloc(1);assert(v->vdev_comp_priv_obj[1]);}
   mark_closed(o);assert(!stop_mc());
   int result=mishare_runtime_reclaim_host(&o);
   assert(result==-EUCLEAN || (fault==7 && result==-EINPROGRESS));
   assert(o && !state(o).freed && objects_live==1 && !wire_deletes && !dp_detaches);
   unsigned deletes=delete_calls;assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && delete_calls==(int)deletes);
   if(fault>=6)assert(state(o).reclaim_error);
   else assert(!delete_calls);
   _Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_work();assert(!create(&o) && !mishare_runtime_destroy(&o));
 puts("MISHARE_OWNED_MC_DRAIN_RECLAIM_FIXTURE_PASS_ONLY");return 0;
}
'''

def function(text,name):
    m=re.search(r'(?:static\s+)?(?:void|QDF_STATUS)\s+'+name+r'\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)
    if not m:raise ValueError('Missing native work function: '+name)
    return m[0]

def fixture(root):
    for path,expected in BASE.items():
        if hashlib.sha256(remove_work_additions((root/path).read_text()).encode()).hexdigest()!=expected:raise ValueError('Unbounded work source delta: '+path)
    for path in [SCHED_API,SCHED_CORE]:
        if (root/path).read_bytes()!=subprocess.check_output(['git','-C',str(root),'show','HEAD:'+path]):raise ValueError('Native scheduler source modified')
    cds=(root/CDS).read_text();post=function(cds,'cds_post_disable')
    if not post.index('scheduler_disable()')<post.index('mishare_runtime_mc_stopped')<post.index('hif_disable_isr'):raise ValueError('Incorrect MC observation origin')
    observer=re.search(r'/\* MISHARE_WORK_BEGIN:cds_mc_stopped \*/\n(.*?)/\* MISHARE_WORK_END:cds_mc_stopped \*/',cds,re.S)[1]
    src=shutdown.fixture(root)
    src=src.replace('static unsigned health_queries;',
                    'static unsigned health_queries,work_close_at;\nstatic void (*work_health_fence)(void);',1)
    needle='health_queries++;return health_missing?NULL:&health;'
    if src.count(needle)!=1:raise ValueError('Native health model boundary changed')
    src=src.replace(needle,'health_queries++;if(work_health_fence && health_queries==work_close_at)work_health_fence();return health_missing?NULL:&health;',1)
    needle='static struct pe_session *pe_create_session('
    assert src.count(needle)==1
    src=src.replace(needle,'static void (*work_pause_hook)(void);\n'+needle,1)
    pos=src.index(' {\n',src.index(needle))+len(' {\n');src=src[:pos]+' if(work_pause_hook)work_pause_hook();\n'+src[pos:]
    model=MODELS.replace('NATIVE_SINGLE_FLUSH',function((root/SCHED_CORE).read_text(),'scheduler_flush_single_queue')).replace('NATIVE_QUEUES_FLUSH',function((root/SCHED_CORE).read_text(),'scheduler_queues_flush')).replace('NATIVE_SCHED_DISABLE',function((root/SCHED_API).read_text(),'scheduler_disable')).replace('NATIVE_STOP_OBSERVER',observer)
    return src[:src.index('int main(void) {')]+model+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=shutdown.radio.plan.channel.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'work.c').write_text(source);exe=d/'work'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'work.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_OWNED_MC_DRAIN_RECLAIM_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    names=['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c']
    return {'status':out.strip(),'source_commit':shutdown.radio.plan.channel.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [API,CDS,SCHED_API,SCHED_CORE]},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},'ordinary_before_work_sha256':BASE,'checks':['real native scheduler_disable waits before real native queue flush functions','real owned PE callback paused inside modeled PE allocation is joined before MC observation','PE/channel/START-plan/radio reservations drain through native flush callbacks','already-disabled scheduler with outstanding reservations is not drain proof','missing scheduler/wrong psoc/no fence do not authorize reclaim','never-wired PAS/INIT host reclaims through native object-manager final-free','deferred physical final-free retains owner and shutdown reason until actual event','pending/active underflow, overflow and mismatched token cannot fake completion','wire history, DP/extension/SM drift and native delete failure refuse reclaim'],'limitations':'Executes production runtime/radio and real native scheduler stop/flush functions plus bounded CDS observation under ASan/UBSan. QDF thread/event/queue primitives, complete native scheduler thread and CDS shutdown, PE allocator/destructor, native SM/WMA postprocessing, IRQ/timer/DP/firmware remain models. Pthread join demonstrates ordering, not kernel scheduling certification. MC evidence applies only to tracked owned work. Recovery reclaim permits only a never-wired pure host object; NDI, firmware, DP, WMA, peer, PE and radio quarantines remain retained. Active-owner unload, module-text lifetime, psoc reuse and phone operation remain unverified. Default backend caller stays disabled.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
