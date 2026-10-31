#!/usr/bin/env python3
"""Actions-only SSR retirement of an explicitly scheduler-rejected START."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_queued_start_reset_fixture as queued
from mishare_recovery_fixture import function
ROOT=queued.ROOT
SCHED='qca-wifi-host-cmn/scheduler/src/scheduler_api.c'
HARNESS=r'''
static struct mishare_runtime_owner *rejected_start_owner(unsigned freq) {
 struct mishare_runtime_owner *o=ready_pre_radio(freq,true);radio_queue_fail=true;
 int err=mishare_runtime_ndi_start(o);radio_queue_fail=false;
 assert(err<0 && err!=-EINPROGRESS && o->radio && !radio_q_len);
 assert(state(o).ndi.radio_submit_error==err && o->radio->start_post_error==err && !o->radio->start_posted);
 assert(!state(o).work_pending && !state(o).work_users && !o->radio->state.pending);
 return o;
}
static void assert_rejected_facts(struct mishare_runtime_owner *o,int err) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && s.ndi.radio_submit_error==err && !s.recovery_radio_start_flushed && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(s.radio.ssr_cancelled_before_start && s.radio.ssr_start_submit_error==err && s.radio.error==err && s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.closing);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted && !s.radio.pending && !s.radio.users);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt && !radio_q_len);
}
int main(void) {
 assert(!queued_start_regressions());
 struct mishare_runtime_owner *o;
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=rejected_start_owner(band?5240:2437);int err=state(o).ndi.radio_submit_error;
  stop_recovery(o);assert(o->radio->ssr_fenced_rejected && !o->radio->ssr_fenced_new && !state(o).recovery_radio_start_flushed);
  early_dp=inline_cb;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_rejected_facts(o,err);
  if(!inline_cb)finish_dp();
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=rejected_start_owner(5240);int err=state(o).ndi.radio_submit_error;
 struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_rejected_facts(item.owner,err);finish_dp();
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner && !state(item.owner).freed);
 wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations);
 /* Metadata cannot stand in for the private, exact scheduler error. */
 for(int fault=0;fault<15;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=rejected_start_owner(5240);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->start_post_error=0;
   if(fault==1)r->start_post_error--;
   if(fault==2)r->ssr_fenced_rejected=false;
   if(fault==3)r->start_posted=true;
   if(fault==4)r->ssr_start_flushed=true;
   if(fault==5)r->start_callback_entered=true;
   if(fault==6)r->preflight=true;
   if(fault==7)r->state.pending=1;
   if(fault==8)r->state.users=1;
   if(fault==9)r->state.error--;
   if(fault==10)r->owner=(void*)1;
   if(fault==11)o->state.ndi.radio_submit_error--;
   if(fault==12)r->ssr_fenced_new=true;
   if(fault==13)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
   if(fault==14)o->state.recovery_radio_start_flushed=true;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r && !pe_deletes && !dp_detaches && !recovery_timer_cancels);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=rejected_start_owner(5240);stop_recovery(o);reset_radio_callback_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && o->radio->ssr_callback_after_fence && state(o).recovery_timer_released);
  assert(!pe_deletes && !dp_detaches && !state(o).recovery_radio_released);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Allocation/reservation failures are not scheduler rejection provenance. */
 for(int fault=0;fault<3;fault++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=ready_pre_radio(5240,true);
   if(fault==0)fail_alloc_at=alloc_calls+2;
   if(fault==1)o->state.work_pending=~0U;
   if(fault==2) {radio_queue_fail=true;}
   assert(mishare_runtime_ndi_start(o)<0 && o->radio && !o->radio->start_posted);
   fail_alloc_at=0;radio_queue_fail=false;
   if(fault==2) {assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1);}
   else mark_closed(o);
   health_recovering=true;assert(!cds_post_disable());
   assert(mishare_runtime_reclaim_ndi(&o)<0 && o->radio && !pe_deletes && !dp_detaches);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_REJECTED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=rejected_start_owner(5240);stop_recovery(o);
 o->radio->start_post_error--;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && "EXPECTED_PRIVATE_REJECTION_PROVENANCE");_Exit(0);
}
'''

def fixture(root):
    src=queued.fixture(root)
    src=src.replace('int main(void) {','static int queued_start_regressions(void) {',1)
    src=src.replace('puts("MISHARE_QUEUED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

SCHED_MODEL=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef int QDF_STATUS;
#define QDF_STATUS_SUCCESS 0
#define QDF_STATUS_E_INVAL 1
#define QDF_STATUS_E_FAILURE 2
#define QDF_STATUS_E_NOMEM 3
#define QDF_MODULE_ID_MAX 8
#define QDF_MODULE_ID_WMA 2
#define QDF_MODULE_ID_TARGET_IF 3
#define SCHEDULER_NUMBER_OF_MSG_QUEUE 2
#define SYS_MSG_COOKIE 0xface
#define MC_POST_EVENT_MASK 1
#define QDF_BUG(x) ((void)(x))
#define QDF_DEBUG_PANIC(...) ((void)0)
#define sched_err(...) ((void)0)
#define qdf_mtrace(...) ((void)0)
struct scheduler_msg {unsigned reserved,type;void *callback,*bodyptr;};
struct scheduler_mq_type {unsigned id;};
struct scheduler_ctx {void *sch_thread;unsigned sch_event_flag,sch_wait_queue;struct {unsigned scheduler_msg_qid_to_qidx[8];void *scheduler_msg_process_fn[2];struct scheduler_mq_type sch_msg_q[2];}queue_ctx;};
static struct scheduler_ctx ctx;
static unsigned puts_count,dups,frees,wakes;
static bool missing,fail_dup;
static struct scheduler_msg *queued_message;
static struct scheduler_ctx *scheduler_get_context(void) {return missing?NULL:&ctx;}
static unsigned scheduler_get_src_id(uint32_t id) {return id>>16;}
static unsigned scheduler_get_dest_id(uint32_t id) {return (id>>8)&255;}
static unsigned scheduler_get_que_id(uint32_t id) {return id&255;}
static struct scheduler_msg *scheduler_core_msg_dup(struct scheduler_msg *m) {dups++;if(fail_dup)return NULL;struct scheduler_msg *p=malloc(sizeof(*p));assert(p);*p=*m;return p;}
static void scheduler_mq_put(struct scheduler_mq_type *q,struct scheduler_msg *m) {assert(q==&ctx.queue_ctx.sch_msg_q[1] && !queued_message);queued_message=m;puts_count++;}
static void scheduler_mq_put_front(struct scheduler_mq_type *q,struct scheduler_msg *m) {scheduler_mq_put(q,m);}
static void qdf_atomic_set_bit(unsigned n,unsigned *p) {assert(n==1 && p==&ctx.sch_event_flag);*p|=1U<<n;}
static void qdf_wake_up_interruptible(unsigned *p) {assert(p==&ctx.sch_wait_queue && queued_message && puts_count==1);wakes++;}
NATIVE_POST
int main(void) {
 for(unsigned fault=0;fault<10;fault++) {
  memset(&ctx,0,sizeof(ctx));ctx.sch_thread=(void*)1;ctx.queue_ctx.scheduler_msg_qid_to_qidx[3]=1;ctx.queue_ctx.scheduler_msg_process_fn[1]=(void*)1;
  missing=fail_dup=false;puts_count=dups=frees=wakes=0;
  struct scheduler_msg m={.callback=(void*)1,.bodyptr=(void*)2};uint32_t id=(1U<<16)|(1U<<8)|3;
  if(fault==0)missing=true;
  if(fault==1)ctx.sch_thread=NULL;
  if(fault==2)m.reserved=1;
  if(fault==3)id=(8U<<16)|(1U<<8)|3;
  if(fault==4)id=(1U<<16)|(8U<<8)|3;
  if(fault==5)id=(1U<<16)|(1U<<8)|8;
  if(fault==6)ctx.queue_ctx.scheduler_msg_qid_to_qidx[3]=2;
  if(fault==7)ctx.queue_ctx.scheduler_msg_process_fn[1]=NULL;
  if(fault==8)fail_dup=true;
  QDF_STATUS s=scheduler_post_msg_by_priority(id,fault==9?NULL:&m,false);
  assert(s!=QDF_STATUS_SUCCESS && !queued_message && !puts_count && !wakes && m.bodyptr==(void*)2);
 }
 for(unsigned high=0;high<2;high++) {
  missing=fail_dup=false;puts_count=dups=wakes=0;ctx.sch_thread=(void*)1;ctx.queue_ctx.scheduler_msg_qid_to_qidx[3]=1;ctx.queue_ctx.scheduler_msg_process_fn[1]=(void*)1;
  struct scheduler_msg m={.callback=(void*)1,.bodyptr=(void*)2};
  assert(scheduler_post_msg_by_priority((1U<<16)|(1U<<8)|3,&m,high)==QDF_STATUS_SUCCESS);
  assert(puts_count==1 && dups==1 && wakes==1 && queued_message && queued_message->bodyptr==m.bodyptr);
  free(queued_message);queued_message=NULL;
 }
 puts("NATIVE_SCHEDULER_REJECTION_BEFORE_INSERT_PASS_ONLY");return 0;
}
'''

def scheduler_audit(root):
    src=(root/SCHED).read_text();native=function(src,'scheduler_post_msg_by_priority')
    source=SCHED_MODEL.replace('NATIVE_POST',native)
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);c=d/'scheduler.c';exe=d/'scheduler';c.write_text(source)
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=15,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    assert out.strip()=='NATIVE_SCHEDULER_REJECTION_BEFORE_INSERT_PASS_ONLY'
    return {'status':out.strip(),'native_sha256':hashlib.sha256(src.encode()).hexdigest(),'native_function_sha256':hashlib.sha256(native.encode()).hexdigest(),'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'error_branches':10,'success_priorities':2,'limitations':'Executes native scheduler post function with modeled queue, message duplication, context and QDF primitives; separate from the production radio transport fixture.'}

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=queued.prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    native=scheduler_audit(root)
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model */\n')
        c=d/'reset.c';exe=d/'reset';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        c.write_text(source);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=45,env=env)
        target=source.replace(function(source,'main'),NEGATIVE_HARNESS.strip(),1)
        c.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();guard='r->state.error == r->start_post_error)) &&';assert radio.count(guard)==1
        # Mutate only the copied production radio file; positive and negative
        # variants compile against the same owner, native helper and harness.
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(guard,'r->state.error != 0)) && /* negative: omit exact private error match */',1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_PRIVATE_REJECTION_PROVENANCE' in bad.stderr
    assert out.strip()=='MISHARE_REJECTED_START_SSR_CANCEL_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':queued.prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'native_scheduler_post_audit':native,'negative_control_missing_private_rejection_fact_rejected':True,
            'checks':['all 0074 regressions retained; scheduler rejected before insertion, exact private error retained',
                      '2.4/5240 MHz, inline/deferred DP, batch, delayed object final-free; actual controller unlink/ref release',
                      '15 private controller/native/callback faults reject before timer/PE/DP cleanup',
                      'callback during timer drain prevents controller retirement after users returns zero',
                      'allocation and work-reservation failures do not substitute for scheduler rejection',
                      'executed START callback, sent START, pending reply, UP and non-SSR fence stay unsupported',
                      'radio_requested, BLOCKED/original submission error and ordinary transaction history remain; no SM/WMI/PM/START/STOP/DOWN fabricated'],
            'limitations':'Only START explicitly rejected before queue insertion or accepted and actually flushed before callback execution. Original error and distinct flush/rejection histories retained. Native scheduler post is separately executed with modeled primitives; production radio rejection uses its transport model. Explicit qualified reset window and retained/serialized parents required. Production radio/runtime and native scheduler/PE/peer code execute with modeled QDF, SM dispatch, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Native MLME destroy/recovery and active START/UP are not certified. No automatic parent/shutdown coordinator, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
