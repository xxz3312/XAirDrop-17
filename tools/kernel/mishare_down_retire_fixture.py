#!/usr/bin/env python3
"""Completed-DOWN controller/timer retirement component; runtime admission stays closed."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_active_fence_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
CASES=r'''
static void down_timer_hook(void) {
 if(down_timer_fault==1)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
 if(down_timer_fault==2)mishare_radios->start_plan.beacon_interval++;
}
static struct mishare_runtime_owner *down_completed(u32 freq,unsigned initial,bool early_start,bool early_stop) {
 reset_pe_test();radio_native_substate=initial;
 struct mishare_runtime_owner *o=queued_start_owner(freq);attach_engine(o);
 radio_early_start=early_start;radio_early_stop=early_stop;radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && "EXPECTED_DOWN_RETIRE_START");
 if(!early_start)assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);
 radio_run(false);assert(state(o).radio.phase==MISHARE_RADIO_UP && "EXPECTED_DOWN_RETIRE_UP");
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && "EXPECTED_DOWN_RETIRE_STOP");
 if(!early_stop)assert(radio_reply_stop()==QDF_STATUS_SUCCESS);
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_DOWN && !radio_q_len && !radio_timer &&
  !radio_start_pm && !radio_stop_pm && !radio_rt && timers_live && "EXPECTED_DOWN_RETIRE_ORDINARY_DOWN");
 assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==1);
 mishare_runtime_mc_stopped(&psoc);health_recovering=true;assert(!cds_post_disable());
 assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN &&
  "EXPECTED_DOWN_RETIRE_NO_RUNTIME_PERMISSION");
 return o;
}
static void down_retire_success(u32 freq,unsigned initial,bool early_start,bool early_stop,bool extra_ref) {
 struct mishare_runtime_owner *o=down_completed(freq,initial,early_start,early_stop);
 struct wlan_objmgr_vdev *v=last_vdev;
 if(extra_ref)assert(!wlan_objmgr_vdev_try_get_ref(v,1));
 struct mishare_radio_status before=state(o).radio,last={0};
 struct mishare_vdev_txn txn,after;assert(!mishare_events_snapshot(o->events,&txn));
 int refs=v->refs,alloc=allocations;unsigned cancels=recovery_timer_cancels;
 unsigned starts=radio_starts,stops=radio_stops,downs=radio_downs;
 assert(!mishare_radio_fenced_down_check(o->radio,v,o->events,o,o->pe_cookie,freq) &&
  timers_live && recovery_timer_cancels==cancels && v->refs==refs && "EXPECTED_DOWN_RETIRE_CHECK_ONLY");
 assert(!mishare_radio_fenced_down_release(&o->radio,v,o->events,o,o->pe_cookie,freq,&last) && !o->radio &&
  !mishare_radios && last.down_retired && last.down_retire_timer_attempted && last.down_retire_timer_released &&
  !last.down_retire_error && !last.ssr_cancelled_before_start &&
  last.phase==MISHARE_RADIO_BLOCKED && last.error==-ESHUTDOWN && last.host_up && last.down_accepted &&
  active_fence_equal(&before.fence,&last.fence) && "EXPECTED_DOWN_RETIRE_COMPONENT_RELEASE");
 assert(!timers_live && recovery_timer_cancels==cancels+1 && v->refs==refs-1 && allocations==alloc-1 &&
  radio_starts==starts && radio_stops==stops && radio_downs==downs && !pe_deletes && !dp_detaches &&
  !wire_deletes && !ctx_delete_calls && pe_heap_live && ctx_peer_present && objects_live && dp_objects &&
  engine_allocations==1 && "EXPECTED_DOWN_RETIRE_NATIVE_TIMER_ONLY");
 assert(!mishare_events_snapshot(o->events,&after) && after.state==txn.state && after.serial==txn.serial &&
  after.pending==txn.pending && after.submitted==txn.submitted && after.replied==txn.replied &&
  "EXPECTED_DOWN_RETIRE_TRANSACTION_UNCHANGED");
 assert(mishare_radio_validate(v->mlme,0,NULL)==QDF_STATUS_E_NOSUPPORT && "EXPECTED_DOWN_RETIRE_UNLINKED");
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o && !state(o).host_delete_accepted &&
  !pe_deletes && !dp_detaches && "EXPECTED_DOWN_RETIRE_RUNTIME_STILL_CLOSED");
 if(extra_ref)wlan_objmgr_vdev_release_ref(v,1);
 /* Remaining runtime/event/PE/peer/DP/VDEV/SM graph deliberately retained.
  * No fabricated runtime timer/retirement history or full SSR completion. */
}
static void down_retire_fault(unsigned fault) {
 struct mishare_runtime_owner *o=down_completed(5240,0,false,false);struct mishare_radio *r=o->radio;
 unsigned cancels=recovery_timer_cancels;struct mishare_radio_status last={0};
 int expected=-EUCLEAN;
 if(fault==0)r->state.fence.phase=MISHARE_RADIO_WAIT_STOP;
 if(fault==1)r->state.fence.error=-EIO;
 if(fault==2)r->state.fence.pending=1;
 if(fault==3)r->state.fence.users=1;
 if(fault==4)r->state.fence.down_accepted=false;
 if(fault==5)r->state.down_accepted=false;
 if(fault==6)radio_native_substate=WLAN_VDEV_SS_START_START_PROGRESS;
 if(fault==7)o->events->txn.serial=1;
 if(fault==8)o->events->txn.submitted=false;
 if(fault==9)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
 if(fault==10)wlan_vdev_mlme_get_des_chan(last_vdev)->ch_cfreq1+=20;
 if(fault==11)last_vdev->mlme->mgmt.generic.type=99;
 if(fault==12)response_timer.rsp_status=1;
 if(fault==13)down_timer_fault=1;
 if(fault==14)down_timer_fault=2;
 if(fault==15) {
  assert(mishare_radio_fenced_down_release(&o->radio,last_vdev,o->events,(void*)1,o->pe_cookie,5240,&last)==-EUCLEAN &&
   o->radio==r && recovery_timer_cancels==cancels && "EXPECTED_DOWN_RETIRE_FOREIGN_OWNER");return;
 }
 if(fault==16) {
  assert(mishare_radio_fenced_down_check((void*)1,last_vdev,o->events,o,o->pe_cookie,5240)==-ENOENT &&
   mishare_radio_fenced_down_check(NULL,last_vdev,o->events,o,o->pe_cookie,5240)==-EINVAL &&
   "EXPECTED_DOWN_RETIRE_UNKNOWN_TOKEN");return;
 }
 if(fault==17)r->state.down_retire_timer_attempted=true;
 int ret=mishare_radio_fenced_down_release(&o->radio,last_vdev,o->events,o,o->pe_cookie,5240,&last);
 assert(ret==expected && o->radio==r && !r->state.down_retired && !pe_deletes && !dp_detaches &&
  "EXPECTED_DOWN_RETIRE_REFUSAL");
 if(fault>=12 && fault<=14) {
  assert(r->state.down_retire_timer_attempted && r->state.down_retire_error &&
   r->state.down_retire_timer_released==(fault!=12) && "EXPECTED_DOWN_RETIRE_PARTIAL_HISTORY");
  unsigned after=recovery_timer_cancels;
  assert(mishare_radio_fenced_down_release(&o->radio,last_vdev,o->events,o,o->pe_cookie,5240,&last)==-EUCLEAN &&
   recovery_timer_cancels==after && o->radio==r && "EXPECTED_DOWN_RETIRE_NO_TIMER_RETRY");
 } else assert(recovery_timer_cancels==cancels && timers_live && "EXPECTED_DOWN_RETIRE_NO_MUTATION");
}
static void down_retire_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned initial=0;initial<2;initial++)
 for(unsigned early_start=0;early_start<2;early_start++)for(unsigned early_stop=0;early_stop<2;early_stop++)
 for(unsigned extra=0;extra<2;extra++) {
  pid_t child=fork();assert(child>=0);if(!child){down_retire_success(band?5240:2437,
   initial?WLAN_VDEV_SS_IDLE:0,!!early_start,!!early_stop,!!extra);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_DOWN_RETIRE_SUCCESS_CHILD");
 }
 for(unsigned fault=0;fault<18;fault++) {
  pid_t child=fork();assert(child>=0);if(!child){down_retire_fault(fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_DOWN_RETIRE_FAULT_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    needle='recovery_timer_cancels++;';assert source.count(needle)==1
    source=source.replace(needle,needle+'if(down_timer_fault)down_timer_hook();',1)
    # Declare the cancellation probe before the selected native timer adapter.
    needle='static unsigned recovery_flushes,recovery_buffers,recovery_timer_cancels';assert source.count(needle)==1
    source=source.replace(needle,'static unsigned down_timer_fault;\nstatic void down_timer_hook(void);\n'+needle,1)
    main=function(source,'main')
    source=source.replace(main,main.replace('int main(void)','static int previous_active_fence_main(void)',1),1)
    source+='\n'+CASES+'''\nint main(void) {
 down_retire_cases();assert(!previous_active_fence_main());return 0;
}\n'''
    return source,exits,stubbed

def controls(original):
    shape=function(original,'radio_fenced_down_shape');check=function(original,'mishare_radio_fenced_down_check')
    release=function(original,'mishare_radio_fenced_down_release');out=[]
    for body,old,new in [
      (shape,'f->phase == MISHARE_RADIO_DOWN','true'),
      (shape,'!f->error &&','true &&'),
      (shape,'!f->pending &&','true &&'),
      (shape,'r->state.down_attempted && r->state.down_accepted &&','r->state.down_attempted && true &&'),
      (shape,'!r->state.down_fence_callback_seen &&','true &&'),
      (check,'!radio_init_idle(r) ||','false ||'),
      (check,'txn.serial != 2 ||','false ||'),
      (release,'ret = mishare_ndi_reset_prepared_timer_deinit(vdev);','ret = 0;'),
      (release,'if (!ret)\n        ret = mishare_radio_fenced_down_check','if (false && !ret)\n        ret = mishare_radio_fenced_down_check'),
      (release,'r->state.down_retired = true;','r->state.down_retired = false;'),
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
            assert bad.returncode==-6 and 'EXPECTED_DOWN_RETIRE_' in bad.stderr,(index,bad.returncode,bad.stderr[-2000:])
    finally:override.unlink(missing_ok=True)

def audit(root):
    r=previous.previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_FENCED_DOWN_RETIRE_COMPONENT_PASS_ONLY',success_combinations=32,
      retained_faults=18,new_mutations=10,
      limitations='Component test only: actual raw native START/UP/STOP/DOWN, frozen origin, event STOP receipt and native synchronous response-timer release before controller reference retirement. Runtime SSR candidate/window and returned-status publication are deliberately not wired; remaining graph stays retained in child processes. Original 0177 active matrix and native baseline retained. Physical firmware/IRQ/ref/lock/PM/DP primitives remain models. No configured START bypass, full active SSR completion, public init, phone/RF/Apple proof.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
