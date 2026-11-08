#!/usr/bin/env python3
"""Actions-only peer-completed/no-VDEV-DELETE native SSR retirement."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_ordinary_fixture as ordinary
from mishare_recovery_fixture import function
ROOT=ordinary.ROOT
HARNESS=r'''
static bool peer_reset_enabled,peer_reset_batch,peer_reset_ack_first;
static unsigned peer_reset_fault;
static int peer_reset_poll(struct mishare_runtime_owner **o) {
 if(!peer_reset_batch)return mishare_runtime_reclaim_ndi(o);
 struct mishare_runtime_reclaim_item item={*o,77};int ret=mishare_runtime_reclaim_batch(&psoc,&item,1);*o=item.owner;return ret;
}
static void peer_reset_handoff(struct mishare_runtime_owner **o) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,WLAN_HDD_ID_OBJ_MGR));
 unsigned peers=clean_peer_sends,pe=pe_deletes;
 assert(ctx_pending && timers_live && !wire_deletes && !dp_detaches);
 if(peer_reset_ack_first && peer_reset_fault!=7)ctx_fw_origin(ctx_pending);
 if(peer_reset_fault==17)(*o)->state.ndi.blocked=true;
 if(peer_reset_fault==18)assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1);
 else mark_closed(*o);
 if(!peer_reset_ack_first && peer_reset_fault!=7)ctx_fw_origin(ctx_pending);
 if(peer_reset_fault==8)mishare_runtime_ndi_peer_event(&psoc,7,(*o)->mac,*o,true);
 if(peer_reset_fault==10)(*o)->state.ndi.create.stats_owned=false;
 if(peer_reset_fault==11)(*o)->state.rate.integrity_error=true;
 if(peer_reset_fault==9)recovery_bad_reset=true;
 if(peer_reset_fault==3)(*o)->state.ndi.create.dp_cookie++;
 if(peer_reset_fault==4)response_timer.rsp_status=1;
 if(peer_reset_fault==5)recovery_cancel_drift=true;
 if(peer_reset_fault==6)recovery_missing_timer=true;
 if(peer_reset_fault==12)dp_detach_status=QDF_STATUS_E_FAILURE;
 if(!clean_peer_gone && peer_reset_fault!=2)clean_peer_unmap();
 /* Neither an ACK nor a scalar candidate alone grants a native window. */
 int wait=peer_reset_fault==7||peer_reset_fault==10||peer_reset_fault==17||peer_reset_fault==18?-EOPNOTSUPP:
  peer_reset_fault==8||peer_reset_fault==11?-EUCLEAN:-EINPROGRESS;
 assert(peer_reset_poll(o)==wait && !recovery_timer_frees && !dp_detaches && "EXPECTED_PEER_RESET_PRE_WINDOW");
 health_recovering=true;assert(!cds_post_disable());
 bool eligible=peer_reset_fault!=7 && peer_reset_fault!=8 && peer_reset_fault!=9 &&
  peer_reset_fault!=10 && peer_reset_fault!=11 && peer_reset_fault!=17 && peer_reset_fault!=18;
 assert(state(*o).recovery_window==eligible && "EXPECTED_PEER_RESET_WINDOW");
 if(peer_reset_fault==1)native_recovery_close();
 int ret=peer_reset_poll(o);
 if(peer_reset_fault==1 || (peer_reset_fault>=4 && peer_reset_fault<=11) || peer_reset_fault>=17) {
  int expected=peer_reset_fault==1?-ESHUTDOWN:peer_reset_fault==9?-EINPROGRESS:
   peer_reset_fault==7||peer_reset_fault==10||peer_reset_fault==17||peer_reset_fault==18?-EOPNOTSUPP:-EUCLEAN;
  assert(ret==expected && *o && !recovery_timer_frees && !dp_detaches && !state(*o).host_delete_accepted &&
   "EXPECTED_PEER_RESET_EARLY_RETAIN");
  unsigned cancels=recovery_timer_cancels;
  assert(peer_reset_poll(o)==expected && recovery_timer_cancels==cancels && "EXPECTED_PEER_RESET_NO_TIMER_RETRY");
  rate_history(*o,before);_Exit(0);
 }
 assert(ret==-EINPROGRESS && state(*o).rate.peer_timer_attempted && state(*o).rate.peer_timer_released &&
  !timers_live && recovery_timer_frees==1 && recovery_rt_frees==1 && !dp_detaches &&
  !state(*o).rate.peer_dp_attempted && "EXPECTED_PEER_RESET_TIMER_RETURN");
 if(peer_reset_fault==15)native_recovery_close();
 ret=peer_reset_poll(o);
 if(peer_reset_fault==2 || peer_reset_fault==3 || peer_reset_fault==12 || peer_reset_fault==15) {
  int expected=peer_reset_fault==15?-ESHUTDOWN:-EUCLEAN;
  assert(ret==expected && !state(*o).rate.peer_reset_completed && !state(*o).host_delete_accepted &&
   dp_detaches==(peer_reset_fault==12?1:0) && "EXPECTED_PEER_RESET_DP_RETAIN");
  assert(peer_reset_poll(o)==expected && dp_detaches==(peer_reset_fault==12?1:0) &&
   recovery_timer_frees==1 && "EXPECTED_PEER_RESET_NO_DP_RETRY");_Exit(0);
 }
 assert(ret==-EINPROGRESS && state(*o).rate.peer_dp_attempted && state(*o).ndi.dp_detach_submitted &&
  dp_detaches==1 && !state(*o).rate.peer_finish_attempted && state(*o).ndi.wma_bound &&
  state(*o).ndi.legacy_ready && "EXPECTED_PEER_RESET_DP_RETURN");
 if(peer_reset_fault==16)native_recovery_close();
 if(!state(*o).ndi.dp_freed) {
  assert(peer_reset_poll(o)==(peer_reset_fault==16?-ESHUTDOWN:-EINPROGRESS) &&
   !state(*o).rate.peer_finish_attempted && "EXPECTED_PEER_RESET_DP_FREE_WAIT");finish_dp();
 }
 assert(state(*o).ndi.dp_freed && !dp_objects && !stats_live && "EXPECTED_PEER_RESET_DP_RECEIPT");
 if(peer_reset_fault==13)mishare_runtime_peer_reset_dp_freed(*o);
 if(peer_reset_fault==14)wma_context.interfaces[7].bss_status=99;
 if(peer_reset_fault==13 || peer_reset_fault==14 || peer_reset_fault==16) {
  int expected=peer_reset_fault==16?-ESHUTDOWN:-EUCLEAN;
  assert(peer_reset_poll(o)==expected && !state(*o).rate.peer_reset_completed &&
   !state(*o).host_delete_accepted && state(*o).ndi.wma_bound && state(*o).ndi.legacy_ready &&
   "EXPECTED_PEER_RESET_FINISH_RETAIN");
  assert(peer_reset_poll(o)==expected && dp_detaches==1 && "EXPECTED_PEER_RESET_NO_FINISH_RETRY");_Exit(0);
 }
 assert(peer_reset_poll(o)==-EINPROGRESS && state(*o).rate.peer_reset_completed &&
  state(*o).host_delete_accepted && !state(*o).freed && !ctx_locks && "EXPECTED_PEER_RESET_CONTEXT_FINISH");
 rate_history(*o,before);
 assert(!state(*o).ndi.delete_pending && !state(*o).ndi.delete_submitted && !state(*o).ndi.delete_replied &&
  !state(*o).rate.ordinary_completed && !state(*o).rate.reset_completed && "EXPECTED_PEER_RESET_NO_FAKE_ACK");
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);
 assert(state(*o).freed && clean_sm_destroys==1 && !peer_reset_poll(o) && !*o &&
  !module_refs && !allocations && !objects_live && "EXPECTED_PEER_RESET_FINAL");
 assert(pe_deletes==pe && clean_peer_sends==peers && !wire_deletes && dp_detaches==1 &&
  !reset_wmi_calls && !reset_force_detaches && recovery_timer_cancels==1 && "EXPECTED_PEER_RESET_NO_REPLAY");
}
static void peer_reset_cycle(unsigned freq,unsigned failure,unsigned mode,bool batch,bool ack_first,unsigned fault) {
 peer_reset_enabled=true;peer_reset_batch=batch;peer_reset_ack_first=ack_first;peer_reset_fault=fault;
 configured_ordinary_cycle(freq,failure,mode&~1U,0);
}
static void peer_reset_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<8;mode++)for(unsigned timing=0;timing<2;timing++)for(unsigned batch=0;batch<2;batch++) {
  unsigned native_mode=(mode&1?2:0)|(mode&2?4:0)|(mode&4?8:0);
  pid_t child=fork();assert(child>=0);if(!child){peer_reset_cycle(band?5240:2437,failure,native_mode,batch,timing,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=18;fault++)for(unsigned batch=0;batch<2;batch++) {
  pid_t child=fork();assert(child>=0);if(!child){peer_reset_cycle(5240,2,0,batch,false,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source,exits,stubbed=ordinary.fixture(root)
    once=ordinary.cleanup.owner.replace_once
    source=once(source,'static void configured_clean_end(',
                'static bool peer_reset_enabled;\nstatic void peer_reset_handoff(struct mishare_runtime_owner **);\nstatic void configured_clean_end(')
    body=function(source,'configured_clean_end')
    needle='assert(mishare_runtime_destroy(o)==-EINPROGRESS && !wire_deletes && !dp_detaches && "EXPECTED_PEER_ACK_BEFORE_VDEV_DELETE");'
    source=once(source,body,once(body,needle,needle+'\n  if(peer_reset_enabled){peer_reset_handoff(o);return;}'))
    main=function(source,'main')
    source=once(source,main,HARNESS+'\n'+main.replace('engine_contract();','peer_reset_cases();engine_contract();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    once=ordinary.cleanup.owner.replace_once
    body=function(runtime,'mishare_runtime_reclaim_peer_reset')
    controls=[
        (once(runtime,'entry->state.rate.peer_reset_armed = true;','entry->state.rate.peer_reset_armed = false;'),True,0,'EXPECTED_PEER_RESET_'),
        (once(runtime,'entry->state.rate.peer_timer_released = true;','entry->state.rate.peer_timer_released = false;'),False,0,'EXPECTED_PEER_RESET_'),
        (once(runtime,body,once(body,'return -EINPROGRESS; /* Peer-reset DP submit must return before finish. */',
                               '/* negative: finish before physical DP free */')),False,0,'!dp_objects && !pending_dp_cb'),
        (once(runtime,'!entry->state.rate.peer_timer_released || !entry->state.rate.peer_dp_attempted ||',
                      '!entry->state.rate.peer_timer_released || true ||'),False,0,'EXPECTED_PEER_RESET_'),
    ]
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for modified,ack_first,fault,marker in controls:
            target=once(source,function(source,'main'),f'int main(void) {{peer_reset_cycle(5240,2,0,false,{str(ack_first).lower()},{fault});return 0;}}')
            c_file.write_text(target);override.unlink(missing_ok=True)
            subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and marker in bad.stderr,(bad.returncode,bad.stderr[-2000:])
    finally:override.unlink(missing_ok=True)


def audit(root):
    r=ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_RATE_PEER_RESET_FIXTURE_PASS_ONLY',peer_reset_combinations=256,retention_cases=36,native_mutations=4)
    r['limitations']='Pre-START configured peer-completed/no-VDEV-DELETE SSR retirement with selected native timer, DP wrapper, WMA/legacy finish, SM destructor and real callback gates. Transport/ACK/physical DP/peer/ref/lock primitives modeled; native parents retained by caller. No automatic parent lease, configured START/UP or phone/RF/Apple proof.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
