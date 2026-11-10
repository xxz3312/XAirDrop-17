#!/usr/bin/env python3
"""Zero-attempt retry after successful rate: native prepared SSR continuation."""
import argparse
import json
from pathlib import Path
import mishare_rate_reset_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *retry_zero_ready(unsigned freq,unsigned origin) {
 struct mishare_runtime_owner *o=configured_rate(freq,0);struct wlan_objmgr_vdev *v=NULL;
 assert(!mishare_runtime_retry_begin(o,5,3,&v) && v==last_vdev && "EXPECTED_RETRY_ZERO_BEGIN");
 if(origin<2)mishare_runtime_retry_posted(o,origin?-EIO:-ENOMEM);
 else {
  struct mishare_retry_submission receipt={0};
  assert(!wlan_objmgr_vdev_try_get_ref(v,1));assert(!mishare_runtime_work_get(v,o));
  mishare_runtime_retry_posted(o,0);
  if(origin==3) {
   mark_closed(o);mishare_runtime_mc_stopped(&psoc);
   struct mishare_runtime_owner *held=o;
   assert(!state(o).mc_drained && !mishare_runtime_retry_zero_attempt_ssr(o) &&
    mishare_runtime_reclaim_ndi(&held)==-EUCLEAN && held==o && !pe_deletes && !dp_detaches &&
    "EXPECTED_RETRY_ZERO_PENDING_RETAIN");
  }
  /* Actual wrapper publishes these zero-attempt origins while work is held;
   * its allocation/flush/entry accounting is covered separately. */
  mishare_runtime_retry_complete(o,&receipt,origin==3?-ESHUTDOWN:-ECANCELED);
  assert(state(o).retry.completed && !state(o).retry.integrity_error && state(o).work_pending==1 &&
   !mishare_runtime_retry_zero_attempt_ssr(o) && "EXPECTED_RETRY_ZERO_PUBLICATION_BARRIER");
  mishare_runtime_work_put(v,o);wlan_objmgr_vdev_release_ref(v,1);
 }
 assert(state(o).retry.completed && !state(o).retry.receipt.attempted && state(o).retry.result<0 &&
  !state(o).retry.integrity_error && "EXPECTED_RETRY_ZERO_RECEIPT");
 return o;
}
static void retry_zero_history(struct mishare_runtime_owner *o,struct mishare_runtime_retry_status before) {
 struct mishare_runtime_retry_status now=state(o).retry;
 assert(!memcmp(&now,&before,sizeof(now)) && "EXPECTED_RETRY_ZERO_HISTORY");
}
static void retry_zero_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned origin=0;origin<4;origin++)for(unsigned immediate=0;immediate<2;immediate++)for(unsigned held_ref=0;held_ref<2;held_ref++) {
  reset_pe_test();struct mishare_runtime_owner *o=retry_zero_ready(band?5240:2437,origin);
  struct mishare_runtime_retry_status retry_before=state(o).retry;struct mishare_runtime_rate_status rate_before=state(o).rate;
  struct wlan_objmgr_vdev *held=last_vdev;if(held_ref)assert(!wlan_objmgr_vdev_try_get_ref(held,1));
  retry_zero_stop_recovery(o);early_dp=immediate;
  assert(mishare_runtime_retry_zero_attempt_ssr(o) && "EXPECTED_RETRY_ZERO_ELIGIBLE");
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && state(o).rate.reset_admitted &&
   !state(o).rate.reset_completed && pe_deletes==1 && dp_detaches==1 &&
   !reset_wmi_calls && !wire_deletes && "EXPECTED_RETRY_ZERO_NATIVE_RESET_BEGIN");
  retry_zero_history(o,retry_before);rate_history(o,rate_before);
  if(!immediate){assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && pe_deletes==1);finish_dp();}
  if(held_ref) {
   assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).rate.reset_completed && state(o).host_delete_accepted &&
    "EXPECTED_RETRY_ZERO_WAIT_FINAL_FREE");retry_zero_history(o,retry_before);
   native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
   assert(!mishare_runtime_reclaim_final(&o) && !o && "EXPECTED_RETRY_ZERO_FINAL_AFTER_CLOSE");
  } else assert(!mishare_runtime_reclaim_ndi(&o) && !o && "EXPECTED_RETRY_ZERO_FINAL");
  assert(!allocations && !objects_live && !ctx_locks && !dp_objects && "EXPECTED_RETRY_ZERO_BALANCE");
 }
 for(unsigned fault=0;fault<12;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   reset_pe_test();struct mishare_runtime_owner *o=retry_zero_ready(5240,2);stop_recovery(o);
   if(fault==0)o->state.retry.integrity_error=true;
   if(fault==1)o->state.retry.receipt.attempted_mask=1;
   if(fault==2)o->state.retry.result=0;
   if(fault==3)o->state.retry.posted=false;
   if(fault==4)o->state.retry.completed=false;
   if(fault==5)o->state.quiesced=MISHARE_QUIESCE_REMOVE;
   if(fault==6)o->state.work_pending=1;
   if(fault==7)o->state.work_users=1;
   if(fault==8)o->state.work_error=-EIO;
   if(fault==9) {
    o->state.retry.receipt=(struct mishare_retry_submission){.attempted=true,.vdev_id=0,
     .data_limit=5,.mgmt_limit=3,.attempted_mask=1,.first_error=o->state.retry.result};
   }
   if(fault==10)o->state.ndi.radio_requested=true;
   if(fault==11)native_recovery_close();
   if(fault<10)assert(!mishare_runtime_retry_zero_attempt_ssr(o) && "EXPECTED_RETRY_ZERO_ELIGIBILITY_REJECT");
   assert(mishare_runtime_reclaim_ndi(&o)<0 && o && !state(o).rate.reset_admitted && !pe_deletes &&
    !dp_detaches && !recovery_timer_cancels && "EXPECTED_RETRY_ZERO_FAULT_RETAIN");_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
int main(void) {assert(!previous_rate_reset_cases());retry_zero_cases();return 0;}
'''

def fixture(root):
    source=previous.fixture(root)
    main=function(source,'main')
    stop=function(source,'stop_recovery').replace('stop_recovery(', 'retry_zero_stop_recovery(',1).replace('mark_closed(o);','if(!state(o).quiesced) {mark_closed(o);}\n ',1)
    return source.replace(main,main.replace('int main(void)','static int previous_rate_reset_cases(void)',1),1)+'\n'+stop+'\n'+HARNESS

def controls(original):
    def replace(needle,value):
        assert original.count(needle)==1,needle
        return original.replace(needle,value,1)
    return [replace('!entry->state.work_pending && !entry->state.work_users &&\n           !entry->state.work_error && r->result < 0 && !r->receipt.attempted &&',
                    '!entry->state.work_pending && !entry->state.work_users &&\n           !entry->state.work_error && r->result < 0 && true &&'),
            replace('mishare_runtime_retry_receipt_valid(r, &r->receipt, r->result, 0);',
                    'true; /* negative: omit zero-attempt evidence validation */')]

def audit(root):
    r=previous.audit(root,fixture_builder=fixture,additional_mutations=controls,mutation_markers=('EXPECTED_RATE_RESET_','EXPECTED_RETRY_ZERO_'))
    r.update(status='MISHARE_RETRY_ZERO_RESET_FIXTURE_PASS_ONLY',retry_zero_reset_combinations=32,retry_zero_retention_faults=12)
    r['limitations']='Production retry registry and rate-only prepared SSR cleanup with selected native lifecycle bodies; zero-attempt callback origins modeled with real runtime work accounting. WMI retries, firmware/IRQ/DP primitives remain modeled. Any attempted retry remains retained; no ordinary-tail/peer reset extension, parent lease, public init/START or phone/RF/Apple proof.'
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
