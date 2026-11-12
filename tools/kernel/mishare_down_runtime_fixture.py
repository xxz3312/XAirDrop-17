#!/usr/bin/env python3
"""Raw completed-DOWN observation, native window and complete runtime SSR retirement."""
import argparse
import json
import re
import subprocess
from pathlib import Path
import mishare_down_retire_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
CASES=r'''
static unsigned down_runtime_sm_frees;
static void down_runtime_sm_free(struct wlan_objmgr_vdev *v) {
 if(!v->mlme->sm_hdl)return;
 struct mishare_runtime_owner *o=mishare_runtime_owners;
 assert(o && o->state.recovery_down_observed && o->state.recovery_down_released &&
  o->state.host_delete_accepted && !o->events && !o->radio && !pe_heap_live && !ctx_peer_present &&
  !dp_objects && !timers_live && !wma_context.interfaces[7].vdev && !v->mlme->ext_vdev_ptr &&
  v->mlme->sm_hdl->cur_state==WLAN_VDEV_S_INIT && "EXPECTED_DOWN_RUNTIME_NATIVE_SM_LAST");
 owner_destroy(v->mlme,v->mlme->sm_hdl);owner_expected=NULL;down_runtime_sm_frees++;
}
DOWN_RUNTIME_READY
static void down_runtime_success(u32 freq,unsigned initial,bool early_start,bool early_stop,bool inline_dp,bool held_ref) {
 struct mishare_runtime_owner *o=down_runtime_ready(freq,initial,early_start,early_stop);
 unsigned cancels=recovery_timer_cancels,starts=radio_starts,stops=radio_stops,downs=radio_downs;
 assert(!mishare_runtime_recovery_candidates(&psoc) && !state(o).recovery_down_observed &&
  "EXPECTED_DOWN_RUNTIME_NOT_ADOPTED");
 struct mishare_radio_fence_status fence=state(o).radio.fence;
 for(unsigned repeat=0;repeat<3;repeat++)assert(!mishare_runtime_fenced_down_prepare(o) &&
  state(o).recovery_down_observed && !state(o).recovery_window && o->radio && timers_live &&
  recovery_timer_cancels==cancels && "EXPECTED_DOWN_RUNTIME_OBSERVE_ONLY");
 assert(mishare_runtime_recovery_candidates(&psoc)==1 && mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS &&
  o->radio && timers_live && !pe_deletes && !dp_detaches && "EXPECTED_DOWN_RUNTIME_WINDOW_REQUIRED");
 assert(!cds_post_disable() && state(o).recovery_window && "EXPECTED_DOWN_RUNTIME_NATIVE_WINDOW");
 struct wlan_objmgr_vdev *held=last_vdev;if(held_ref)assert(!wlan_objmgr_vdev_try_get_ref(held,1));
 early_dp=inline_dp;
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && !o->radio &&
  state(o).recovery_down_released && !state(o).recovery_radio_released &&
  state(o).radio.down_retired && !state(o).radio.ssr_cancelled_before_start &&
  state(o).radio.start_attempted && state(o).radio.stop_attempted && state(o).radio.host_up &&
  state(o).radio.down_accepted && !state(o).ndi.create.timer_ready &&
  state(o).recovery_timer_attempted && state(o).recovery_timer_released &&
  !timers_live && recovery_timer_cancels==cancels+1 &&
  !pe_heap_live && !ctx_peer_present && pe_deletes==1 && dp_detaches==1 &&
  "EXPECTED_DOWN_RUNTIME_NATIVE_BEGIN");
 struct mishare_radio_status saved=state(o).radio;
 assert(active_fence_equal(&fence,&saved.fence) && radio_starts==starts && radio_stops==stops &&
  radio_downs==downs && !reset_wmi_calls && !wire_deletes && !ctx_delete_calls &&
  "EXPECTED_DOWN_RUNTIME_NO_NEW_WIRE");
 struct mishare_vdev_txn txn;assert(!mishare_events_snapshot(o->events,&txn) &&
  txn.serial==2 && txn.submitted && txn.replied && txn.pending==MISHARE_TXN_NONE &&
  txn.state==MISHARE_TXN_QUARANTINED && "EXPECTED_DOWN_RUNTIME_STOP_HISTORY");
 if(!inline_dp) {
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && wma_context.interfaces[7].vdev &&
   last_vdev->mlme->ext_vdev_ptr && "EXPECTED_DOWN_RUNTIME_DP_WAIT");
  finish_dp();
 }
 if(held_ref) {
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).host_delete_accepted &&
   !state(o).freed && !down_runtime_sm_frees && "EXPECTED_DOWN_RUNTIME_FINAL_REF_WAIT");
  native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
  assert(!mishare_runtime_reclaim_final(&o) && !o && "EXPECTED_DOWN_RUNTIME_FINAL_AFTER_WINDOW");
 } else assert(!mishare_runtime_reclaim_ndi(&o) && !o && "EXPECTED_DOWN_RUNTIME_FINAL");
 assert(!allocations && !objects_live && !mishare_radios && !mishare_event_owners && !mishare_runtime_owners &&
  !dp_objects && !ctx_locks && !pe_heap_live && !engine_allocations && down_runtime_sm_frees==1 &&
  !owner_dump_live && !owner_sm_live && !owner_mutex_live &&
  "EXPECTED_DOWN_RUNTIME_BALANCE");
}
static void down_runtime_fault(unsigned fault) {
 struct mishare_runtime_owner *o=down_runtime_ready(5240,0,false,false);
 struct mishare_radio *radio=o->radio;unsigned cancels=recovery_timer_cancels;
 assert(mishare_runtime_fenced_down_prepare((void*)1)==-ENOENT &&
  mishare_runtime_fenced_down_prepare(NULL)==-EINVAL && "EXPECTED_DOWN_RUNTIME_OPAQUE_OWNER");
 if(fault<5) {
  int expected=-EUCLEAN;
  if(fault==0){o->state.mc_drained=false;expected=-EINPROGRESS;}
  if(fault==1){o->state.quiesced=MISHARE_QUIESCE_REMOVE;expected=-ESHUTDOWN;}
  if(fault==2){o->state.rate.requested=true;expected=-EOPNOTSUPP;}
  if(fault==3)o->radio->state.fence.phase=MISHARE_RADIO_UP;
  if(fault==4)o->radio->state.fence.pending=1;
  assert(mishare_runtime_fenced_down_prepare(o)==expected && !state(o).recovery_down_observed &&
   o->radio==radio && recovery_timer_cancels==cancels && "EXPECTED_DOWN_RUNTIME_PREPARE_RETAIN");return;
 }
 assert(!mishare_runtime_fenced_down_prepare(o));
 if(fault>=5 && fault<=8) {
  if(fault==5)recovery_bad_reset=true;
  if(fault==6)recovery_cds.htc_ctx=NULL;
  if(fault==7){recovery_validates=0;recovery_bad_validate=1;}
  if(fault==8)recovery_rx_status=QDF_STATUS_E_FAILURE;
  QDF_STATUS q=cds_post_disable();assert((q!=QDF_STATUS_SUCCESS)==(fault==8));
  assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS &&
   o->radio==radio && timers_live && !pe_deletes && !dp_detaches && "EXPECTED_DOWN_RUNTIME_NATIVE_DENIAL");return;
 }
 assert(!cds_post_disable() && state(o).recovery_window);
 int expected=-EUCLEAN;
 if(fault==9){native_recovery_close();expected=-ESHUTDOWN;}
 if(fault==10)o->events->txn.serial=1;
 if(fault==11)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
 if(fault==12)pe_slot.curr_op_freq=5180;
 if(fault==13)down_timer_fault=1;
 if(fault==14)down_timer_fault=2;
 assert(mishare_runtime_reclaim_ndi(&o)==expected && o && o->radio==radio && !pe_deletes && !dp_detaches &&
  !state(o).recovery_down_released && "EXPECTED_DOWN_RUNTIME_PARTIAL_RETAIN");
 if(fault>=13)assert(state(o).recovery_timer_attempted && state(o).recovery_timer_released &&
  !state(o).ndi.create.timer_ready && state(o).recovery_error && "EXPECTED_DOWN_RUNTIME_PARTIAL_PUBLISH");
 else assert(timers_live && recovery_timer_cancels==cancels && "EXPECTED_DOWN_RUNTIME_NO_EARLY_CLEANUP");
 unsigned after=recovery_timer_cancels;
 assert(mishare_runtime_reclaim_ndi(&o)==expected && o->radio==radio && recovery_timer_cancels==after &&
  "EXPECTED_DOWN_RUNTIME_NO_RETRY");
}
static void down_runtime_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned initial=0;initial<2;initial++)
 for(unsigned start=0;start<2;start++)for(unsigned stop=0;stop<2;stop++)
 for(unsigned dp=0;dp<2;dp++)for(unsigned held=0;held<2;held++) {
  pid_t child=fork();assert(child>=0);if(!child){down_runtime_success(band?5240:2437,
   initial?WLAN_VDEV_SS_IDLE:0,!!start,!!stop,!!dp,!!held);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_DOWN_RUNTIME_CHILD");
 }
 for(unsigned fault=0;fault<15;fault++) {
  pid_t child=fork();assert(child>=0);if(!child){down_runtime_fault(fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_DOWN_RUNTIME_FAULT_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    matches=re.findall(r'^static struct mishare_runtime_owner \*down_completed\(.*?^\}',source,re.S|re.M)
    assert len(matches)==1
    ready=matches[0].replace('down_completed(', 'down_runtime_ready(',1)
    needle='mishare_runtime_mc_stopped(&psoc);health_recovering=true;assert(!cds_post_disable());'
    assert ready.count(needle)==1
    ready=ready.replace(needle,'assert(!stop_mc());health_recovering=true;',1)
    destroy=function(source,'simulated_component_destroy')
    assert destroy.count('if(v->mlme){free(v->mlme);')==1
    changed=destroy.replace('if(v->mlme){free(v->mlme);','if(v->mlme){down_runtime_sm_free(v);free(v->mlme);',1)
    source=source.replace(destroy,'static void down_runtime_sm_free(struct wlan_objmgr_vdev *);\n'+changed,1)
    main=function(source,'main')
    source=source.replace(main,CASES.replace('DOWN_RUNTIME_READY',ready,1)+'''\nint main(void) {
 down_runtime_cases();engine_contract();puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");return 0;
}\n''',1)
    return source,exits,stubbed

def controls(original):
    out=[]
    def mutate(name,old,new):
        body=function(original,name);assert body.count(old)==1,old
        out.append(original.replace(body,body.replace(old,new,1),1))
    mutate('mishare_runtime_fenced_down_prepare','e->state.recovery_down_observed = true;','e->state.recovery_down_observed = false;')
    mutate('mishare_runtime_fenced_down_prepare','if (!e->state.mc_drained ||','if ((false && !e->state.mc_drained) ||')
    mutate('mishare_runtime_fenced_down_prepare','if (e->state.rate.requested ||','if ((false && e->state.rate.requested) ||')
    mutate('mishare_runtime_ndi_recovery_candidate','no_radio || cancelled_radio || completed_down','no_radio || cancelled_radio || (false && completed_down)')
    mutate('mishare_runtime_reclaim_ndi','if (last.down_retire_timer_released)','if (false && last.down_retire_timer_released)')
    mutate('mishare_runtime_reclaim_ndi','entry->state.recovery_down_released = !ret && !entry->radio && last.down_retired;',
           'entry->state.recovery_down_released = false;')
    return out

def negative_controls(directory,c_file,command,env,source,root):
    original=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for index,changed in enumerate(controls(original)):
            override.write_text(changed);c_file.write_text(source);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and 'EXPECTED_DOWN_RUNTIME_' in bad.stderr,(index,bad.returncode,bad.stderr[-2000:])
    finally:override.unlink(missing_ok=True)

def audit(root):
    r=previous.previous.previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_DOWN_RUNTIME_SSR_FIXTURE_PASS_ONLY',raw_down_combinations=64,retained_faults=15,
      new_mutations=6,
      limitations='Explicit process-context raw completed-DOWN observation must precede the existing native CDS window qualification. Actual radio/timer/PE/peer/DP/context and native SM wrappers execute with modeled physical primitives; no configured START guard bypass. Automatic managed observation scheduling remains unconnected. No UP/WAIT/failure recovery, phone/RF/Apple certification.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
