#!/usr/bin/env python3
"""Actions-only prestart controller, actual rate MC ownership and native cleanup."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_ordinary_fixture as ordinary
from mishare_recovery_fixture import function
ROOT=ordinary.ROOT
MODEL=r'''
#ifndef BIT
#define BIT(n) (1U << (n))
#endif
typedef uint16_t u16;
PROVIDER_HEADER
RATE_HEADER
#include "wlan_hdd_mishare_prestart.h"
static struct mishare_prestart *prestart_control;
static struct mishare_session *prestart_session;
static struct mishare_runtime_owner *prestart_owner;
static struct wondertap_fixed_tx_rate_params prestart_params;
static u32 prestart_freq;
static struct scheduler_msg prestart_rate_queue;
static unsigned prestart_rate_posts,prestart_rate_execs,prestart_rate_replies,prestart_channel_replies;
static unsigned prestart_rate_failure;
static bool prestart_rate_inline,prestart_rate_queue_fail;
static int prestart_poll(void) {
 return mishare_prestart_step(prestart_control,prestart_session,prestart_owner,prestart_freq,1,2,&prestart_params);
}
static void prestart_channel_publish(struct wlan_objmgr_psoc *p,u8 id,void *o,u32 f,int ret) {
 mishare_runtime_ndi_channel_event(p,id,o,f,ret);
 if(prestart_owner && o==prestart_owner && !ret) {
  prestart_channel_replies++;
  assert(state(prestart_owner).work_pending==1 && !state(prestart_owner).work_users &&
   prestart_poll()==-EINPROGRESS && !prestart_control->posted && !prestart_rate_posts &&
   "EXPECTED_PRESTART_NATIVE_CHANNEL_WORK_DRAIN");
 }
}
int mishare_rate_submit_mc(struct wlan_objmgr_vdev *v,const struct wondertap_fixed_tx_rate_params *p,
                           struct mishare_rate_submission *r) {
 assert(v==last_vdev && prestart_owner && state(prestart_owner).work_pending==1 &&
  state(prestart_owner).work_users==1 && p->preamble==prestart_params.preamble &&
  p->nss==1 && p->mcs==7 && !p->reserved[0] && !r->attempted && "EXPECTED_PRESTART_NATIVE_RATE_WORK");
 prestart_rate_execs++;r->attempted=true;r->complete=!prestart_rate_failure;
 r->attempted_mask=prestart_rate_failure?(1U<<prestart_rate_failure)-1:7;
 r->submitted_mask=prestart_rate_failure?(1U<<(prestart_rate_failure-1))-1:7;
 r->first_error=prestart_rate_failure?-EIO:0;
 return r->first_error; /* WMA/WMI executor boundary remains modeled. */
}
static QDF_STATUS prestart_rate_scheduler(int from,int dest,int queue,struct scheduler_msg *m) {
 assert(from==QDF_MODULE_ID_HDD && dest==QDF_MODULE_ID_PE && queue==QDF_MODULE_ID_TARGET_IF &&
  m->bodyptr && m->callback && m->flush_callback && !prestart_rate_queue.bodyptr &&
  state(prestart_owner).work_pending==1 && !state(prestart_owner).work_users && "EXPECTED_PRESTART_NATIVE_PUBLICATION");
 prestart_rate_posts++;
 if(prestart_rate_queue_fail)return QDF_STATUS_E_FAILURE;
 prestart_rate_queue=*m;
 if(prestart_rate_inline)assert(!prestart_rate_queue.callback(&prestart_rate_queue));
 return QDF_STATUS_SUCCESS;
}
#define scheduler_post_message prestart_rate_scheduler
#include "wlan_hdd_mishare_rate_work.c"
#undef scheduler_post_message
static void prestart_rate_publish(struct mishare_runtime_owner *o,const struct mishare_runtime_rate_result *r) {
 mishare_runtime_rate_complete(o,r);prestart_rate_replies++;
 assert(o==prestart_owner && state(o).work_pending==1 && !state(o).work_users &&
  "EXPECTED_PRESTART_NATIVE_RECEIPT_OWNS_WORK");
 if(!r->result)assert(prestart_poll()==-EINPROGRESS && "EXPECTED_PRESTART_NATIVE_RATE_DRAIN");
 struct mishare_runtime_owner *held=o;
 assert(mishare_runtime_destroy(&held)==(state(o).quiesced?-EUCLEAN:-EINPROGRESS) && held==o && !state(o).ndi.pe_delete_requested &&
  "EXPECTED_PRESTART_NATIVE_RECEIPT_BLOCKS_RETIRE");
}
#define mishare_runtime_rate_complete prestart_rate_publish
#include "wlan_hdd_mishare_runtime_rate.c"
#undef mishare_runtime_rate_complete
static void prestart_history(struct mishare_runtime_owner *o,struct mishare_runtime_rate_status before) {
 struct mishare_runtime_rate_status now=state(o).rate;
 assert(now.requested && now.posted && now.completed && now.accepted==before.accepted && !now.integrity_error &&
  !memcmp(&now.request,&before.request,sizeof(now.request)) && !memcmp(&now.receipt,&before.receipt,sizeof(now.receipt)) &&
  "EXPECTED_PRESTART_NATIVE_HISTORY");
}
'''
HARNESS=r'''
static void prestart_native_cycle(unsigned freq,unsigned failure,unsigned mode,bool inline_rate,unsigned fault) {
 reset_pe_test();radio_native_substate=0;
 struct mishare_prestart control={0};struct mishare_session session={0};struct mishare_runtime_owner *o=NULL;
 assert(!create(&o));
 prestart_control=&control;prestart_session=&session;prestart_owner=o;prestart_freq=freq;
 prestart_params=(struct wondertap_fixed_tx_rate_params){.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7};
 prestart_rate_queue=(struct scheduler_msg){0};prestart_rate_posts=prestart_rate_execs=prestart_rate_replies=prestart_channel_replies=0;
 prestart_rate_failure=failure;prestart_rate_inline=inline_rate;prestart_rate_queue_fail=fault==1;
 assert(prestart_poll()==-EINPROGRESS && state(o).ndi.create.dp_attached && "EXPECTED_PRESTART_NATIVE_CREATE");
 assert(prestart_poll()==-EINPROGRESS && state(o).ndi.wma_bound && state(o).ndi.peer_created && "EXPECTED_PRESTART_NATIVE_CONTEXT");
 assert(prestart_poll()==-EINPROGRESS && pe_pending.bodyptr && !state(o).ndi.pe_completed && "EXPECTED_PRESTART_NATIVE_PE_POST");
 assert(prestart_poll()==-EINPROGRESS && !state(o).ndi.channel_requested && "EXPECTED_PRESTART_NATIVE_PE_WAIT");
 run_pe(false);
 pe_mac.lim.maxStation=2;pe_mac.lim.lim_timers.gpLimCnfWaitTimer=reset_confirm_timers;
 reset_confirm_timers[0]=(TX_TIMER){.sessionId=0};reset_confirm_timers[1]=(TX_TIMER){.sessionId=1,.running=true};reset_confirm_timers[2]=(TX_TIMER){.sessionId=0};
 pe_slot.dph.dphHashTable.pHashTable=pe_heap_alloc(16);memset(pe_nodes,0x5a,sizeof(pe_nodes));
 pe_slot.dph.dphHashTable.pDphNodeArray=pe_nodes;pe_slot.dph.dphHashTable.size=33;pe_slot.model_idxpool=pe_heap_alloc(8);
 assert(prestart_poll()==-EINPROGRESS && pe_pending.bodyptr && session.stage==MISHARE_SESSION_PLAN && "EXPECTED_PRESTART_NATIVE_CHANNEL_POST");
 assert(prestart_poll()==-EINPROGRESS && !control.posted && "EXPECTED_PRESTART_NATIVE_CHANNEL_WAIT");
 run_pe(false);assert(prestart_channel_replies==1 && state(o).ndi.channel_prepared && !state(o).work_pending);
 attach_engine(o);
 if(fault==2)fail_alloc_at=alloc_calls+1;
 if(fault==3)fail_ref_at=ref_calls+1;
 int ret=prestart_poll();
 int post_error=fault==1?-EIO:fault==2?-ENOMEM:fault==3?-ENODEV:0;
 if(post_error)assert(ret==post_error && prestart_poll()==post_error && !prestart_rate_queue.bodyptr &&
  !state(o).work_pending && !state(o).work_users && !prestart_rate_execs && "EXPECTED_PRESTART_NATIVE_POST_FAILURE");
 else {
  assert(ret==-EINPROGRESS && control.posted && prestart_rate_posts==1 && "EXPECTED_PRESTART_NATIVE_SUBMIT_RETURN");
  if(!inline_rate) {
   assert(prestart_poll()==-EINPROGRESS && state(o).work_pending==1 && !state(o).rate.completed && "EXPECTED_PRESTART_NATIVE_RATE_WAIT");
   if(fault==5)mark_closed(o);
   struct scheduler_msg m=prestart_rate_queue;prestart_rate_queue.bodyptr=NULL;
   assert(!(fault==4?m.flush_callback(&m):m.callback(&m)) && !m.bodyptr);
  }
  int expected=fault==5?-ESHUTDOWN:fault==4?-ECANCELED:failure?-EIO:0;
  assert(prestart_poll()==expected && prestart_poll()==expected && !state(o).work_pending && !state(o).work_users &&
   prestart_rate_replies==1 && prestart_rate_execs==(fault==4||fault==5?0u:1u) && "EXPECTED_PRESTART_NATIVE_READY_OR_ERROR");
 }
 assert(!state(o).ndi.start_plan_requested && !state(o).ndi.radio_requested && !radio_starts && !radio_stops && !radio_downs &&
  "EXPECTED_PRESTART_NATIVE_NEVER_START");
 if(fault==5) {
  assert(o && state(o).blocked && state(o).ndi.active && pe_slot.valid && dp_objects && timers_live && !wire_deletes && !dp_detaches &&
   "EXPECTED_PRESTART_NATIVE_SSR_PENDING_RETAIN");_Exit(0);
 }
 if(fault==6) {
  struct mishare_runtime_rate_result r=state(o).rate.receipt;mishare_runtime_rate_complete(o,&r);
  assert(state(o).rate.integrity_error && prestart_poll()==-EUCLEAN && mishare_runtime_destroy(&o)==-EUCLEAN &&
   o && !wire_deletes && !dp_detaches && "EXPECTED_PRESTART_NATIVE_DUPLICATE_RETAIN");_Exit(0);
 }
 if(!post_error && !failure && fault!=4) {
  prestart_params.mcs--;
  assert(prestart_poll()==-EBUSY && prestart_rate_posts==1 && "EXPECTED_PRESTART_NATIVE_REQUEST_FROZEN");prestart_params.mcs++;
 }
 struct mishare_runtime_rate_status before=state(o).rate;
 prestart_history(o,before);prestart_owner=NULL;prestart_control=NULL;prestart_session=NULL;
 clean_modes=mode;clean_fault=0;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && pe_pending.bodyptr && "EXPECTED_PRESTART_NATIVE_DELETE_BEGIN");
 prestart_clean_end(&o);
 assert(!o && !objects_live && !allocations && !module_refs && !engine_allocations && !dp_objects && !stats_live && !timers_live &&
  prestart_rate_posts==(fault==2||fault==3?0u:1u) && "EXPECTED_PRESTART_NATIVE_FINAL_FREE");
}
static void prestart_native_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<32;mode++)for(unsigned timing=0;timing<2;timing++) {
  pid_t child=fork();assert(child>=0);if(!child){prestart_native_cycle(band?5240:2437,failure,mode,timing,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=6;fault++)for(unsigned mode=0;mode<2;mode++) {
  pid_t child=fork();assert(child>=0);if(!child){prestart_native_cycle(5240,0,mode?8:0,false,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source,exits,stubbed=ordinary.fixture(root)
    once=ordinary.cleanup.owner.replace_once
    declaration='static void prestart_channel_publish(struct wlan_objmgr_psoc *,u8,void *,u32,int);\n'
    source=once(source,'static struct mac_context *pe_cds_get_context',declaration+'static struct mac_context *pe_cds_get_context')
    finish=function(source,'mishare_channel_finish')
    source=once(source,finish,once(finish,'mishare_runtime_ndi_channel_event(psoc, id, owner, freq, ret);',
                                  'prestart_channel_publish(psoc, id, owner, freq, ret);'))
    api=(ROOT/'kernel/provider/wondertap.h').read_text().replace('#include <linux/if_ether.h>','/* ETH_ALEN supplied by platform model */')
    rate=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_rate.h').read_text().replace('#include "wlan_hdd_mishare_wonder_api.h"','/* exact public header embedded above */')
    model=MODEL.replace('PROVIDER_HEADER',api).replace('RATE_HEADER',rate)
    cleanup=function(source,'configured_clean_end').replace('configured_clean_end(', 'prestart_clean_end(',1).replace('rate_history(*o,original_rate);','prestart_history(*o,original_rate);')
    cleanup=once(cleanup,'state(*o).rate.ordinary_completed && "EXPECTED_RATE_ORDINARY_COMPLETION"',
                 'state(*o).rate.ordinary_completed==original_rate.receipt.attempted && "EXPECTED_PRESTART_NATIVE_CLEANUP_PROVENANCE"')
    main=function(source,'main')
    source=once(source,main,model+'\n'+cleanup+'\n'+HARNESS+'\n'+main.replace('engine_contract();','prestart_native_cases();engine_contract();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    once=ordinary.cleanup.owner.replace_once
    prod=ROOT/'kernel/popsicle-hdd'
    header=(prod/'wlan_hdd_mishare_prestart.h').read_text();work=(prod/'wlan_hdd_mishare_rate_work.c').read_text()
    runtime=(prod/'wlan_hdd_mishare_runtime.c').read_text();drain=function(runtime,'mishare_runtime_ndi_drain')
    controls=[
        ('wlan_hdd_mishare_prestart.h',once(header,'if (s.work_users || s.work_pending)','if (false && (s.work_users || s.work_pending))'),0),
        ('wlan_hdd_mishare_prestart.h',once(header,'!mishare_prestart_rate_equal(&c->rate, &rate)','false'),0),
        ('wlan_hdd_mishare_rate_work.c',once(work,'    mishare_runtime_work_put(vdev, owner);\n    wlan_objmgr_vdev_release_ref(vdev, WLAN_LEGACY_MAC_ID);',
                    '    /* negative: leave the owned MC reservation live */\n    wlan_objmgr_vdev_release_ref(vdev, WLAN_LEGACY_MAC_ID);'),0),
        ('wlan_hdd_mishare_runtime.c',once(runtime,drain,once(drain,'if (!ret && (entry->state.work_pending || entry->state.work_users))',
                   'if (false && !ret && (entry->state.work_pending || entry->state.work_users))')),4),
    ]
    for name,modified,fault in controls:
        target=once(source,function(source,'main'),f'int main(void) {{prestart_native_cycle(5240,0,0,false,{fault});return 0;}}')
        c_file.write_text(target);override=directory/name;override.unlink(missing_ok=True)
        subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
        try:
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and 'EXPECTED_PRESTART_NATIVE_' in bad.stderr,(name,bad.returncode,bad.stderr[-2000:])
        finally:override.unlink(missing_ok=True)


def audit(root):
    r=ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_PRESTART_NATIVE_FIXTURE_PASS_ONLY',prestart_combinations=512,publication_and_retention_cases=12,native_mutations=4)
    r['limitations']='Production prestart/session/runtime/rate configure and owned MC work execute together with selected native CREATE/context/PE/channel/ordinary cleanup and physical VDEV/SM free bodies. WMA rate executor, scheduling, firmware ACK/DP/unmap/refs/locks remain modeled. Two SSR/duplicate classes deliberately retain objects. Caller retains parents; no automatic parent lease, managed full init, START/UP or phone/RF/Apple proof.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
