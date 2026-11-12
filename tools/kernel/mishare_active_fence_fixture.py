#!/usr/bin/env python3
"""Native active START/UP/STOP/DOWN fence observations; recovery stays closed."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_native_wma_start_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.engine.ROOT
CASES=r'''
static bool active_fence_matches(const struct mishare_radio_fence_status *f,
                                  const struct mishare_radio_status *s,
                                  const struct mishare_radio *r) {
 return f->recorded && f->phase==s->phase && f->error==s->error && f->closing==s->closing &&
  f->start_attempted==s->start_attempted && f->stop_attempted==s->stop_attempted && f->host_up==s->host_up &&
  f->down_attempted==s->down_attempted && f->down_accepted==s->down_accepted && f->pending==s->pending && f->users==s->users &&
  f->start_sm_entered==r->start_sm_entered && f->start_sm_call_active==r->start_sm_call_active &&
  f->start_reply_queued==r->start_reply_queued && f->stop_reply_queued==r->stop_reply_queued &&
  f->applying_start_reply==r->applying_start_reply && f->applying_stop_reply==r->applying_stop_reply;
}
static bool active_fence_equal(const struct mishare_radio_fence_status *a,
                                const struct mishare_radio_fence_status *b) {
 return a->recorded==b->recorded && a->phase==b->phase && a->error==b->error && a->closing==b->closing &&
  a->start_attempted==b->start_attempted && a->stop_attempted==b->stop_attempted && a->host_up==b->host_up &&
  a->down_attempted==b->down_attempted && a->down_accepted==b->down_accepted && a->pending==b->pending && a->users==b->users &&
  a->start_sm_entered==b->start_sm_entered && a->start_sm_call_active==b->start_sm_call_active &&
  a->start_reply_queued==b->start_reply_queued && a->stop_reply_queued==b->stop_reply_queued &&
  a->applying_start_reply==b->applying_start_reply && a->applying_stop_reply==b->applying_stop_reply;
}
/* Cut 0 WAIT_START; 1 START reply queued; 2 UP; 3 STOP queued;
 * 4 WAIT_STOP; 5 STOP reply queued; 6 DOWN; 7 START send failure;
 * 8 native WMA failure after UP; 9 STOP send failure; 10 DOWN send failure. */
static void active_fence_cycle(u32 freq,unsigned initial,unsigned cut,bool late,enum mishare_quiesce_reason reason) {
 reset_pe_test();radio_native_substate=initial;
 struct mishare_runtime_owner *o=queued_start_owner(freq);struct wlan_sm *sm=attach_engine(o);
 if(cut==7)radio_start_fail=true;
 radio_run(false);
 if(cut!=7) {
  assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && radio_starts==1 &&
   "EXPECTED_ACTIVE_FENCE_WAIT_START");
  if(cut>=1) {
   if(cut==8){post_mlme.cfg.ratemask_cfg.type=WLAN_MLME_RATEMASK_TYPE_HT;post_invalid_wmi=true;}
   assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);
   if(cut!=1)radio_run(false);
  }
  if(cut!=8 && cut>=2) {
   assert(state(o).radio.phase==MISHARE_RADIO_UP && state(o).radio.host_up &&
    ch_state==WLAN_VDEV_S_UP && sm->cur_state==WLAN_VDEV_SS_UP_ACTIVE && "EXPECTED_ACTIVE_FENCE_UP");
   if(cut>=3) {
    assert(mishare_runtime_destroy(&o)==-EINPROGRESS && o->radio && radio_q_len==1 &&
     "EXPECTED_ACTIVE_FENCE_STOP_QUEUED");
    if(cut==9)radio_stop_fail=true;
    if(cut!=3)radio_run(false);
    if(cut!=9 && cut>=4) {
     assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && radio_stops==1 && "EXPECTED_ACTIVE_FENCE_WAIT_STOP");
     if(cut>=5) {
      assert(radio_reply_stop()==QDF_STATUS_SUCCESS);
      if(cut==10)radio_down_fail=true;
      if(cut!=5)radio_run(false);
     }
    }
   }
  }
 }
 struct mishare_radio *radio=o->radio;struct mishare_radio_status before=state(o).radio;
 assert(radio && before.start_attempted && !before.fence.recorded && !pe_deletes && !dp_detaches &&
  !wire_deletes && !ctx_delete_calls && "EXPECTED_ACTIVE_FENCE_RETAINED_SETUP");
 if(cut==7 || cut==8 || cut==9 || cut==10)assert(before.phase==MISHARE_RADIO_BLOCKED && before.error &&
  "EXPECTED_ACTIVE_FENCE_ORIGINAL_ERROR");
 if(cut==6)assert(before.phase==MISHARE_RADIO_DOWN && before.down_accepted && "EXPECTED_ACTIVE_FENCE_DOWN");
 struct wlan_objmgr_psoc foreign={9};
 assert(!mishare_runtime_quiesce_psoc(&foreign,reason) && !state(o).radio.fence.recorded &&
  state(o).radio.phase==before.phase && "EXPECTED_ACTIVE_FENCE_FOREIGN_PSOC");
 unsigned starts=radio_starts,stops=radio_stops,downs=radio_downs,builds=plan_builds;
 assert(mishare_runtime_quiesce_psoc(&psoc,reason)==1 && "EXPECTED_ACTIVE_FENCE_OWNER");
 struct mishare_radio_status fenced=state(o).radio;
 assert(active_fence_matches(&fenced.fence,&before,radio) && fenced.phase==MISHARE_RADIO_BLOCKED && fenced.closing &&
  fenced.error==(before.error?before.error:-ESHUTDOWN) && state(o).quiesced==reason &&
  "EXPECTED_ACTIVE_FENCE_CAPTURE");
 struct mishare_radio_fence_status origin=fenced.fence;
 /* Queue reservations may drain, native IRQ-response handling may release
  * response/PM state. None of those facts rewrites the original fence. */
 if(late && radio_timer==START_RESPONSE_BIT)(void)radio_reply_start(0);
 if(late && radio_timer==STOP_RESPONSE_BIT)(void)radio_reply_stop();
 while(radio_q_len)radio_run(!late);
 for(unsigned repeat=0;repeat<3;repeat++) {
  assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1 && state(o).quiesced==reason &&
   "EXPECTED_ACTIVE_FENCE_FIRST_REASON");
  struct mishare_radio_status now=state(o).radio;
  assert(active_fence_equal(&origin,&now.fence) && now.phase==MISHARE_RADIO_BLOCKED &&
   radio_starts==starts && radio_stops==stops && radio_downs==downs && plan_builds==builds &&
   "EXPECTED_ACTIVE_FENCE_IMMUTABLE");
 }
 mishare_runtime_mc_stopped(&psoc);
 health_recovering=reason==MISHARE_QUIESCE_SSR;
 if(reason==MISHARE_QUIESCE_SSR)assert(!cds_post_disable());
 assert(!mishare_runtime_recovery_candidates(&psoc) && !state(o).recovery_window &&
  "EXPECTED_ACTIVE_FENCE_NO_WINDOW");
 unsigned heap=pe_heap_live;int refs=last_vdev->refs,alloc=allocations;
 assert(mishare_radio_ssr_cancel_check(radio,last_vdev,o->events,o,o->pe_cookie,freq)==-EUCLEAN &&
  "EXPECTED_ACTIVE_FENCE_NO_PRESTART_ADOPTION");
 struct mishare_radio_status last={0};struct mishare_radio *held_radio=radio;
 assert(mishare_radio_drain(&held_radio,&last)==-EUCLEAN && held_radio==radio &&
  active_fence_equal(&origin,&last.fence) && "EXPECTED_ACTIVE_FENCE_NO_ORDINARY_RELEASE");
 assert(mishare_runtime_destroy(&o)==-EUCLEAN && o && o->radio==radio &&
  mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o && o->radio==radio &&
  last_vdev->refs==refs && allocations==alloc && pe_heap_live==heap && pe_heap_live &&
  ctx_peer_present && objects_live && dp_objects && engine_allocations==1 &&
  !pe_deletes && !dp_detaches && !wire_deletes && !ctx_delete_calls &&
  !state(o).host_delete_accepted && !state(o).recovery_timer_attempted &&
  "EXPECTED_ACTIVE_FENCE_NATIVE_RESOURCES_RETAINED");
 /* Deliberate retained native graph: this child exits without synthetic SM
  * reset, timer/peer cleanup, host deletion, or a claim of leak-free teardown. */
}
static struct mishare_radio_fence_status active_send_origin;
static void active_send_fence(void) {
 struct mishare_runtime_owner *o=mishare_runtime_owners;
 struct mishare_radio_status before=state(o).radio;
 assert(before.phase==MISHARE_RADIO_STARTING && before.start_attempted && before.pending==1 && before.users==1 &&
  o->radio->start_sm_call_active && "EXPECTED_ACTIVE_FENCE_NATIVE_ENTRY");
 assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==1);
 struct mishare_radio_status after=state(o).radio;
 assert(active_fence_matches(&after.fence,&before,o->radio) && "EXPECTED_ACTIVE_FENCE_NATIVE_CAPTURE");
 active_send_origin=after.fence;
}
static void active_send_case(u32 freq,unsigned initial) {
 reset_pe_test();radio_native_substate=initial;
 struct mishare_runtime_owner *o=queued_start_owner(freq);attach_engine(o);
 active_send_fence_enabled=true;radio_run(false);active_send_fence_enabled=false;
 assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && radio_starts==1 &&
  !o->radio->start_sm_call_active && !state(o).radio.users && !state(o).radio.pending &&
  "EXPECTED_ACTIVE_FENCE_NATIVE_RETURN");
 for(unsigned repeat=0;repeat<3;repeat++) {
  assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==1);
  struct mishare_radio_status now=state(o).radio;
  assert(active_fence_equal(&active_send_origin,&now.fence) && now.fence.start_sm_call_active &&
   now.fence.users==1 && now.fence.pending==1 && "EXPECTED_ACTIVE_FENCE_NATIVE_IMMUTABLE");
 }
 mishare_runtime_mc_stopped(&psoc);health_recovering=true;assert(!cds_post_disable());
 assert(!mishare_runtime_recovery_candidates(&psoc) && !state(o).recovery_window &&
  mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches &&
  "EXPECTED_ACTIVE_FENCE_NATIVE_RETAIN");
}
static void active_fence_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned initial=0;initial<2;initial++)
 for(unsigned cut=0;cut<11;cut++)for(unsigned late=0;late<2;late++) {
  pid_t child=fork();assert(child>=0);if(!child){active_fence_cycle(band?5240:2437,
   initial?WLAN_VDEV_SS_IDLE:0,cut,!!late,MISHARE_QUIESCE_SSR);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_ACTIVE_FENCE_CHILD");
 }
 for(unsigned band=0;band<2;band++)for(unsigned initial=0;initial<2;initial++) {
  pid_t child=fork();assert(child>=0);if(!child){active_send_case(band?5240:2437,initial?WLAN_VDEV_SS_IDLE:0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_ACTIVE_FENCE_NATIVE_CHILD");
 }
 for(unsigned band=0;band<2;band++)for(unsigned initial=0;initial<2;initial++)for(unsigned reason=0;reason<2;reason++) {
  pid_t child=fork();assert(child>=0);if(!child){active_fence_cycle(band?5240:2437,
   initial?WLAN_VDEV_SS_IDLE:0,2,true,reason?MISHARE_QUIESCE_MODULE_STOP:MISHARE_QUIESCE_REMOVE);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_ACTIVE_FENCE_NON_SSR_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    sender=function(source,'wmi_unified_vdev_start_send')
    assert sender.count('radio_starts++;')==1
    changed=sender.replace('radio_starts++;','radio_starts++;if(active_send_fence_enabled)active_send_fence();',1)
    source=source.replace(sender,'static bool active_send_fence_enabled;\nstatic void active_send_fence(void);\n'+changed,1)
    old=function(source,'main')
    source=source.replace(old,old.replace('int main(void)','static int active_native_baseline(void)',1),1)
    source+='\n'+CASES+'''\nint main(void) {
 active_fence_cases();assert(!active_native_baseline());return 0;
}\n'''
    return source,exits,stubbed

def controls(original):
    capture=function(original,'radio_capture_fence_locked')
    quiesce=function(original,'mishare_radio_quiesce_psoc')
    out=[]
    for body,old,new in [
      (quiesce,'        radio_capture_fence_locked(r);','        /* omitted capture */'),
      (capture,'if (f->recorded)','if (false && f->recorded)'),
      (capture,'f->phase = r->state.phase;','f->phase = MISHARE_RADIO_BLOCKED;'),
      (capture,'f->start_attempted = r->state.start_attempted;','f->start_attempted = false;'),
      (capture,'f->host_up = r->state.host_up;','f->host_up = false;'),
      (capture,'f->error = r->state.error;','f->error = 0;'),
      (capture,'f->pending = r->state.pending;','f->pending = 0;'),
      (capture,'f->start_sm_entered = r->start_sm_entered;','f->start_sm_entered = false;'),
      (capture,'f->start_sm_call_active = r->start_sm_call_active;','f->start_sm_call_active = false;'),
      (capture,'f->users = r->state.users;','f->users = 0;'),
      (quiesce,'if (wlan_vdev_get_psoc(r->vdev) != psoc)','if (false && wlan_vdev_get_psoc(r->vdev) != psoc)'),
    ]:
        assert body.count(old)==1,old
        out.append(original.replace(body,body.replace(old,new,1),1))
    return out

def negative_controls(directory,c_file,command,env,source,root):
    original=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_radio.c').read_text()
    override=directory/'wlan_hdd_mishare_radio.c'
    try:
        for index,changed in enumerate(controls(original)):
            override.write_text(changed);c_file.write_text(source);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and 'EXPECTED_ACTIVE_FENCE_' in bad.stderr,(index,bad.returncode,bad.stderr[-2000:])
    finally:
        override.unlink(missing_ok=True)

def audit(root):
    r=previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_ACTIVE_RADIO_FENCE_FIXTURE_PASS_ONLY',active_ssr_combinations=88,
      non_ssr_combinations=8,native_entry_combinations=4,fence_mutations=11,
      limitations='Production radio/runtime/event registries, actual native generic SM/table/selected PAS callbacks and native START-response WMA bodies. Raw unconfigured native lifecycle only; no configured START guard bypass. Controller-local first-fence evidence, not a cross-lock SM/native/IRQ barrier. Work/ref/lock/timer/PM/DP/firmware endpoints remain models. Active cases intentionally retain resources in child processes; no active SSR recovery, leak-free cleanup, backend enable, phone/RF/Apple proof.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
