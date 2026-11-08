#!/usr/bin/env python3
"""Actions-only native self-peer reply after the original SSR fence; observation only."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_ordinary_fixture as ordinary
from mishare_recovery_fixture import function
ROOT=ordinary.ROOT
HARNESS=r'''
static bool late_peer_mode,late_peer_stop_first;
static unsigned late_peer_fault;
static void late_peer_observe(struct mishare_runtime_owner **o) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 assert(ctx_pending && ctx_requests==1 && state(*o).ndi.peer_delete_submitted && !state(*o).ndi.peer_delete_replied &&
  !wire_deletes && !dp_detaches && !state(*o).ndi.delete_pending && timers_live);
 if(late_peer_fault==1)(*o)->state.ndi.blocked=true;
 if(late_peer_fault==3)(*o)->state.ndi.peer_delete_submitted=false;
 if(late_peer_fault==9)(*o)->state.rate.integrity_error=true;
 if(late_peer_fault==2)assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1);
 else mark_closed(*o);
 bool armed=late_peer_fault!=1 && late_peer_fault!=2 && late_peer_fault!=3 && late_peer_fault!=9;
 assert(state(*o).rate.late_peer_armed==armed && !state(*o).rate.late_peer_reply &&
  !state(*o).rate.late_delete_armed && "EXPECTED_LATE_PEER_ARM");
 if(late_peer_stop_first)assert(!stop_mc());
 if(late_peer_fault==12)native_recovery_close();
 if(late_peer_fault==11)mishare_runtime_ndi_delete_event(&psoc,7,false); /* Unexpected matching VDEV notification. */
 if(late_peer_fault==4)ctx_timeout_origin(ctx_pending);
 else if(late_peer_fault==6)mishare_runtime_ndi_peer_event(&psoc,7,(*o)->mac,(void*)1,true);
 else if(late_peer_fault==7){u8 mac[6];memcpy(mac,(*o)->mac,6);mac[0]^=1;mishare_runtime_ndi_peer_event(&psoc,7,mac,*o,true);}
 else if(late_peer_fault==10)mishare_runtime_ndi_peer_event(&psoc,8,(*o)->mac,*o,true);
 else if(late_peer_fault!=8)ctx_fw_origin(ctx_pending); /* Actual selected native request/timer/wake-lock cleanup origin. */
 if(late_peer_fault==5)mishare_runtime_ndi_peer_event(&psoc,7,(*o)->mac,*o,true);
 if(!late_peer_stop_first)assert(!stop_mc());
 bool received=late_peer_fault==0 || late_peer_fault==5 || late_peer_fault==12;
 assert(state(*o).ndi.peer_delete_replied==received && state(*o).rate.late_peer_reply==received &&
  state(*o).blocked && state(*o).ndi.blocked && "EXPECTED_LATE_PEER_NATIVE_REPLY");
 bool pending=late_peer_fault==6 || late_peer_fault==7 || late_peer_fault==8 || late_peer_fault==10;
 assert(ctx_requests==(pending?1:0) && !!ctx_pending==pending &&
  !!wma_context.wmi_cmd_rsp_wake_lock==pending && "EXPECTED_LATE_PEER_NATIVE_REQUEST_CLEANUP");
 if(late_peer_fault==4 || late_peer_fault==5 || late_peer_fault==11)assert(state(*o).ndi.completion_error);
 int destroy_expected=late_peer_fault==9?-EUCLEAN:-EOPNOTSUPP;
 int expected=late_peer_fault==0?-EINPROGRESS:late_peer_fault==12?-ESHUTDOWN:late_peer_fault==5||late_peer_fault==9?-EUCLEAN:-EOPNOTSUPP;
 assert(mishare_runtime_destroy(o)==destroy_expected && mishare_runtime_reclaim_ndi(o)==expected && "EXPECTED_LATE_PEER_NO_VDEV_DELETE");
 struct mishare_runtime_reclaim_item item={*o,77};
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==expected && item.owner==*o && "EXPECTED_LATE_PEER_BATCH_RETAIN");
 assert(mishare_runtime_recovery_candidates(&psoc)==(late_peer_fault==0?1u:0u) && !state(*o).recovery_window && "EXPECTED_LATE_PEER_NO_WINDOW");
 assert(mishare_runtime_work_get(last_vdev,*o)==-ESHUTDOWN && "EXPECTED_LATE_PEER_NO_WORK_ADMISSION");
 assert(*o && (*o)->vdev==last_vdev && (*o)->referenced && (*o)->events && state(*o).ndi.active &&
  state(*o).ndi.legacy_ready && state(*o).ndi.wma_bound && module_refs==1 && objects_live && dp_objects && stats_live &&
  timers_live && !wire_deletes && !dp_detaches && !delete_calls && !state(*o).host_delete_accepted &&
  !state(*o).rate.ordinary_completed && !state(*o).rate.tail_dp_attempted && "EXPECTED_LATE_PEER_RESOURCE_RETAIN");
 assert(state(*o).rate.receipt.result==before.receipt.result && state(*o).rate.receipt.attempted_mask==before.receipt.attempted_mask);
 _Exit(0); /* Owner/native resources intentionally remain quarantined in every case. */
}
static void late_peer_cycle(unsigned freq,unsigned failure,unsigned mode,bool stop_first,unsigned fault) {
 late_peer_mode=true;late_peer_stop_first=stop_first;late_peer_fault=fault;
 configured_ordinary_cycle(freq,failure,mode&~1U,0);
}
static void late_peer_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<4;mode++)for(unsigned timing=0;timing<2;timing++) {
  unsigned native_mode=(mode&1?2:0)|(mode&2?8:0);
  pid_t child=fork();assert(child>=0);if(!child){late_peer_cycle(band?5240:2437,failure,native_mode,timing,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=12;fault++)for(unsigned timing=0;timing<2;timing++) {
  pid_t child=fork();assert(child>=0);if(!child){late_peer_cycle(5240,2,0,timing,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source,exits,stubbed=ordinary.fixture(root)
    source=ordinary.cleanup.owner.replace_once(source,'static void configured_clean_end(',
        'static bool late_peer_mode;\nstatic void late_peer_observe(struct mishare_runtime_owner **);\nstatic void configured_clean_end(')
    body=function(source,'configured_clean_end')
    needle='assert(mishare_runtime_destroy(o)==-EINPROGRESS && !wire_deletes && !dp_detaches && "EXPECTED_PEER_ACK_BEFORE_VDEV_DELETE");'
    changed=ordinary.cleanup.owner.replace_once(body,needle,needle+'\n  if(late_peer_mode){late_peer_observe(o);return;}')
    source=ordinary.cleanup.owner.replace_once(source,body,changed)
    main=function(source,'main');source=ordinary.cleanup.owner.replace_once(source,main,HARNESS+'\n'+main.replace('engine_contract();','late_peer_cases();engine_contract();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text();once=ordinary.cleanup.owner.replace_once
    controls=[
        (once(runtime,'entry->state.rate.late_peer_armed = true;','entry->state.rate.late_peer_armed = false;'),0),
        (once(runtime,'else if (entry->state.rate.late_peer_armed &&','else if (false && entry->state.rate.late_peer_armed &&'),0),
        (once(runtime,'!entry->state.ndi.blocked && mishare_runtime_rate_peer_inflight(entry)','true && mishare_runtime_rate_peer_inflight(entry)'),1),
    ]
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for modified,fault in controls:
            target=source.replace(function(source,'main'),f'int main(void) {{late_peer_cycle(5240,2,0,false,{fault});return 0;}}',1)
            c_file.write_text(target);override.unlink(missing_ok=True)
            subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and 'EXPECTED_LATE_PEER_' in bad.stderr,(bad.returncode,bad.stderr[-2000:])
    finally:override.unlink(missing_ok=True)


def audit(root):
    r=ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r['status']='MISHARE_RATE_LATE_PEER_OBSERVATION_FIXTURE_PASS_ONLY';r['late_peer_combinations']=64;r['retention_cases']=24;r['native_mutations']=3
    r['limitations']='Observation only: selected native self-peer hold-request/timer/wake-lock completion origin after healthy original SSR fence. All matching owners/native VDEV/DP/WMA/legacy remain quarantined, no VDEV DELETE admission or retirement. Transport/ACK/DP/peer/ref/locks modeled; caller retains parents. No full recovery, configured START/UP or phone/RF/Apple proof.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
