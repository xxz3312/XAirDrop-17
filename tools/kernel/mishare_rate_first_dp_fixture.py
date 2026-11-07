#!/usr/bin/env python3
"""Actions-only first DP detach after ordinary DELETE reply interrupted by SSR."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_ordinary_fixture as ordinary
from mishare_recovery_fixture import function
ROOT=ordinary.ROOT
HARNESS=r'''
static bool first_dp_enabled,first_dp_batch;
static unsigned first_dp_fault;
static int first_dp_poll(struct mishare_runtime_owner **o) {
 if(!first_dp_batch)return mishare_runtime_reclaim_ndi(o);
 struct mishare_runtime_reclaim_item item={*o,77};int ret=mishare_runtime_reclaim_batch(&psoc,&item,1);*o=item.owner;return ret;
}
static void first_dp_handoff(struct mishare_runtime_owner **o) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,WLAN_HDD_ID_OBJ_MGR));
 unsigned peers=clean_peer_sends,pe=pe_deletes;int wires=wire_deletes;
 assert(state(*o).ndi.delete_replied && !state(*o).ndi.dp_detaching && !dp_detaches && stats_live);
 mark_closed(*o);assert(first_dp_poll(o)==-EINPROGRESS && "EXPECTED_FIRST_DP_MC_WAIT");
 if(!clean_peer_gone && first_dp_fault!=3)clean_peer_unmap();
 if(first_dp_fault==2)(*o)->state.ndi.create.dp_cookie++;
 if(first_dp_fault==4)dp_detach_status=QDF_STATUS_E_FAILURE;
 if(first_dp_fault==5)(*o)->state.ndi.delete_replied=false;
 if(first_dp_fault==6)(*o)->state.ndi.completion_error=-EIO;
 if(first_dp_fault==7)(*o)->state.ndi.create.stats_owned=false;
 if(first_dp_fault==8)recovery_bad_reset=true;
 if(first_dp_fault==9)(*o)->state.ndi.create.dp_cookie=0;
 health_recovering=true;assert(!cds_post_disable());
 bool qualified=!(first_dp_fault>=5);
 assert(state(*o).recovery_window==qualified && "EXPECTED_FIRST_DP_QUALIFICATION");
 if(first_dp_fault) {
  int expected=first_dp_fault==1?-ESHUTDOWN:first_dp_fault==5||first_dp_fault==7||first_dp_fault==9?-EOPNOTSUPP:first_dp_fault==8?-EINPROGRESS:-EUCLEAN;
  if(first_dp_fault==1)native_recovery_close();
  assert(first_dp_poll(o)==expected && *o && !state(*o).rate.tail_completed && !state(*o).host_delete_accepted && "EXPECTED_FIRST_DP_RETAIN");
  bool attempted=first_dp_fault>=2 && first_dp_fault<=4;
  assert(state(*o).rate.tail_dp_attempted==attempted && dp_detaches==(first_dp_fault==4?1:0) && "EXPECTED_FIRST_DP_ATTEMPT_FACT");
  assert(first_dp_poll(o)==expected && dp_detaches==(first_dp_fault==4?1:0) && "EXPECTED_FIRST_DP_NO_RETRY");
  rate_history(*o,before);_Exit(0);
 }
 assert(first_dp_poll(o)==-EINPROGRESS && state(*o).rate.tail_dp_attempted && state(*o).ndi.dp_detach_submitted &&
  dp_detaches==1 && !state(*o).rate.tail_attempted && state(*o).ndi.wma_bound && state(*o).ndi.legacy_ready && "EXPECTED_FIRST_DP_SUBMIT_RETURN");
 if(!state(*o).ndi.dp_freed) {
  assert(first_dp_poll(o)==-EINPROGRESS && dp_detaches==1 && state(*o).ndi.wma_bound && "EXPECTED_FIRST_DP_FREE_WAIT");finish_dp();
 }
 assert(state(*o).ndi.dp_freed && !dp_objects && !stats_live);
 assert(first_dp_poll(o)==-EINPROGRESS && state(*o).rate.tail_completed && state(*o).host_delete_accepted &&
  !state(*o).freed && !ctx_locks && "EXPECTED_FIRST_DP_CONTEXT_FINISH");
 rate_history(*o,before);native_recovery_close();wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);
 assert(state(*o).freed && clean_sm_destroys==1 && !mishare_runtime_reclaim_final(o) && !*o &&
  !module_refs && !allocations && !objects_live && "EXPECTED_FIRST_DP_FINAL");
 assert(pe_deletes==pe && wire_deletes==wires && clean_peer_sends==peers && dp_detaches==1 &&
  !reset_wmi_calls && !reset_force_detaches && !recovery_timer_cancels && "EXPECTED_FIRST_DP_NO_REPLAY");
}
static void first_dp_cycle(unsigned freq,unsigned failure,unsigned mode,bool batch,unsigned fault) {
 first_dp_enabled=true;first_dp_batch=batch;first_dp_fault=fault;configured_ordinary_cycle(freq,failure,mode,0);
}
static void first_dp_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<32;mode++) {
  pid_t child=fork();assert(child>=0);if(!child){first_dp_cycle(band?5240:2437,failure,mode,mode&1,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=9;fault++)for(unsigned batch=0;batch<2;batch++) {
  pid_t child=fork();assert(child>=0);if(!child){first_dp_cycle(5240,2,0,batch,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source,exits,stubbed=ordinary.fixture(root)
    source=ordinary.cleanup.owner.replace_once(source,'static void configured_clean_end(',
        'static bool first_dp_enabled;\nstatic void first_dp_handoff(struct mishare_runtime_owner **);\nstatic void configured_clean_end(')
    body=function(source,'configured_clean_end')
    needle='assert(state(*o).ndi.delete_replied && !timers_live && pm_releases==1);'
    changed=ordinary.cleanup.owner.replace_once(body,needle,needle+'\n if(first_dp_enabled){first_dp_handoff(o);return;}')
    source=ordinary.cleanup.owner.replace_once(source,body,changed)
    main=function(source,'main');source=ordinary.cleanup.owner.replace_once(source,main,HARNESS+'\n'+main.replace('engine_contract();','first_dp_cases();engine_contract();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    tail=function(runtime,'mishare_runtime_rate_tail_check')
    controls=[
        (ordinary.cleanup.owner.replace_once(runtime,'entry->state.rate.tail_dp_attempted = true;','entry->state.rate.tail_dp_attempted = false;'),0,'EXPECTED_FIRST_DP_'),
        (ordinary.cleanup.owner.replace_once(runtime,'return -EINPROGRESS; /* A real submit return precedes context release. */','/* negative: context release before DP completion */'),0,'!dp_objects && !pending_dp_cb'),
        (ordinary.cleanup.owner.replace_once(runtime,tail,ordinary.cleanup.owner.replace_once(tail,'!n->create.dp_cookie || !n->create.stats_owned','false || !n->create.stats_owned')),9,'EXPECTED_FIRST_DP_'),
    ]
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for modified,fault,marker in controls:
            target=source.replace(function(source,'main'),f'int main(void) {{first_dp_cycle(5240,2,2,false,{fault});return 0;}}',1)
            c_file.write_text(target);override.unlink(missing_ok=True)
            subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and marker in bad.stderr,(bad.returncode,bad.stderr[-2000:])
    finally:override.unlink(missing_ok=True)


def audit(root):
    r=ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r['status']='MISHARE_RATE_SSR_FIRST_DP_FIXTURE_PASS_ONLY';r['configured_combinations']=256;r['retention_cases']=18;r['native_mutations']=3
    r['limitations']='Native prepared-DP wrapper, ordinary DP completion and native SSR context finish after real modeled ordinary DELETE origin; transport/ACK/DP/peer/ref/lock primitives modeled. Caller retains parents. Earlier missing DELETE replies, configured START/UP and phone/RF/Apple proof excluded.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
