#!/usr/bin/env python3
"""Owned retry MC completion through native prepared SSR, never START."""
import argparse
import json
from pathlib import Path
import mishare_retry_zero_reset_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
MODEL=r'''
static struct scheduler_msg retry_reset_queue;
static struct mishare_runtime_owner *retry_reset_owner;
static u8 retry_reset_data,retry_reset_mgmt;
static unsigned retry_reset_failure;
static bool retry_reset_inline,retry_reset_fence;
int mishare_retry_submit_mc(struct wlan_objmgr_vdev *v,u8 d,u8 m,struct mishare_retry_submission *r) {
 assert(v==last_vdev && state(retry_reset_owner).work_pending==1 && state(retry_reset_owner).work_users==1 &&
  d==retry_reset_data && m==retry_reset_mgmt && "EXPECTED_RETRY_PREPARED_EXECUTION");
 r->attempted=true;r->vdev_id=wlan_vdev_get_id(v);r->data_limit=d;r->mgmt_limit=m;
 for(unsigned group=0;group<2;group++) {
  u8 bit=1U<<group;
  if(!(group?m:d)){r->skipped_mask|=bit;continue;}
  r->attempted_mask|=bit;
  if(retry_reset_failure==group+1){r->first_error=-EIO;return -EIO;}
  r->submitted_mask|=bit;
 }
 r->complete=true;return 0;
}
static QDF_STATUS retry_reset_scheduler(int a,int b,int c,struct scheduler_msg *msg) {
 assert(a==QDF_MODULE_ID_HDD && b==QDF_MODULE_ID_PE && c==QDF_MODULE_ID_TARGET_IF &&
  !retry_reset_queue.bodyptr && msg->bodyptr && msg->callback && msg->flush_callback &&
  "EXPECTED_RETRY_PREPARED_POST");retry_reset_queue=*msg;
 if(retry_reset_inline)assert(!retry_reset_queue.callback(&retry_reset_queue));
 return QDF_STATUS_SUCCESS;
}
#define scheduler_post_message retry_reset_scheduler
#include "wlan_hdd_mishare_retry_work.c"
#undef scheduler_post_message
static void retry_reset_publish(struct mishare_runtime_owner *o,const struct mishare_retry_submission *r,int result) {
 mishare_runtime_retry_complete(o,r,result);
 assert(o==retry_reset_owner && state(o).retry.completed && !state(o).retry.integrity_error &&
  state(o).work_pending==1 && !state(o).work_users && "EXPECTED_RETRY_PREPARED_PUBLISH");
 if(retry_reset_fence)mark_closed(o);
 struct mishare_runtime_owner *held=o;
 assert(!mishare_runtime_retry_prepared_ssr(o) &&
  mishare_runtime_destroy(&held)==(retry_reset_fence?-EUCLEAN:-EINPROGRESS) && held==o &&
  !pe_deletes && !dp_detaches && "EXPECTED_RETRY_PREPARED_PUBLISH_RETAIN");
}
#define mishare_runtime_retry_complete retry_reset_publish
#include "wlan_hdd_mishare_runtime_retry.c"
#undef mishare_runtime_retry_complete
static struct mishare_runtime_owner *retry_prepared_ready(unsigned freq,u8 data,u8 mgmt,unsigned failure,bool inline_cb,bool fence) {
 struct mishare_runtime_owner *o=configured_rate(freq,0);
 retry_reset_owner=o;retry_reset_data=data;retry_reset_mgmt=mgmt;retry_reset_failure=failure;
 retry_reset_inline=inline_cb;retry_reset_fence=fence;retry_reset_queue=(struct scheduler_msg){0};
 assert(mishare_runtime_retry_configure(o,data,mgmt)==-EINPROGRESS && "EXPECTED_RETRY_PREPARED_CONFIGURE");
 if(!inline_cb)assert(!retry_reset_queue.callback(&retry_reset_queue));
 assert(state(o).retry.completed && state(o).retry.accepted && !state(o).retry.integrity_error &&
  state(o).retry.receipt.attempted && state(o).retry.result==(failure?-EIO:0) &&
  state(o).retry.vdev_id==wlan_vdev_get_id(last_vdev) && !state(o).work_pending && !state(o).work_users &&
  "EXPECTED_RETRY_PREPARED_RECEIPT");
 assert(mishare_runtime_retry_configure(o,0,0)==-EALREADY && "EXPECTED_RETRY_PREPARED_NO_REPLAY");
 return o;
}
'''
CASES=r'''
static void retry_prepared_cases(void) {
 const u8 pairs[][2]={{0,0},{5,0},{0,3},{5,3},{255,255}};
 for(unsigned pair=0;pair<5;pair++)for(unsigned failure=0;failure<3;failure++) {
  if((failure==1 && !pairs[pair][0]) || (failure==2 && !pairs[pair][1]))continue;
  for(unsigned mode=0;mode<32;mode++) {
   reset_pe_test();struct mishare_runtime_owner *o=retry_prepared_ready(mode&1?5240:2437,pairs[pair][0],pairs[pair][1],failure,!!(mode&2),!!(mode&4));
   struct mishare_runtime_retry_status before=state(o).retry;struct mishare_runtime_rate_status rate_before=state(o).rate;
   struct wlan_objmgr_vdev *held=last_vdev;if(mode&8)assert(!wlan_objmgr_vdev_try_get_ref(held,1));
   retry_zero_stop_recovery(o);early_dp=!!(mode&16);
   assert(mishare_runtime_retry_prepared_ssr(o) && "EXPECTED_RETRY_PREPARED_ELIGIBLE");
   assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && state(o).rate.reset_admitted &&
    !state(o).rate.reset_completed && pe_deletes==1 && dp_detaches==1 && !reset_wmi_calls && !wire_deletes &&
    "EXPECTED_RETRY_PREPARED_NATIVE_RESET");
   retry_zero_history(o,before);rate_history(o,rate_before);
   if(!(mode&16)){assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && pe_deletes==1);finish_dp();}
   if(mode&8) {
    assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).rate.reset_completed && state(o).host_delete_accepted &&
     "EXPECTED_RETRY_PREPARED_FINAL_WAIT");retry_zero_history(o,before);
    native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
    assert(!mishare_runtime_reclaim_final(&o) && !o && "EXPECTED_RETRY_PREPARED_FINAL_AFTER_CLOSE");
   } else assert(!mishare_runtime_reclaim_ndi(&o) && !o && "EXPECTED_RETRY_PREPARED_FINAL");
   assert(!allocations && !objects_live && !ctx_locks && !dp_objects && "EXPECTED_RETRY_PREPARED_BALANCE");
  }
 }
 for(unsigned fault=0;fault<16;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   reset_pe_test();struct mishare_runtime_owner *o=retry_prepared_ready(5240,5,3,1,false,false);retry_zero_stop_recovery(o);
   if(fault==0)o->state.retry.integrity_error=true;
   if(fault==1)o->state.retry.vdev_id^=1;
   if(fault==2)o->state.retry.receipt.submitted_mask=3;
   if(fault==3)o->state.retry.posted=false;
   if(fault==4)o->state.retry.completed=false;
   if(fault==5)o->state.retry.accepted=false;
   if(fault==6)o->state.quiesced=MISHARE_QUIESCE_REMOVE;
   if(fault==7)o->state.work_pending=1;
   if(fault==8)o->state.work_users=1;
   if(fault==9)o->state.work_error=-EIO;
   if(fault==10)o->state.mc_drained=false;
   if(fault==11)o->state.rate.receipt.result=-EIO;
   if(fault==12)o->state.rate.ordinary_admitted=true;
   if(fault==13)o->state.ndi.start_plan_requested=true;
   if(fault==14)native_recovery_close();
   if(fault==15)pe_slot.curr_op_freq=5180;
   if(fault<14)assert(!mishare_runtime_retry_prepared_ssr(o) && "EXPECTED_RETRY_PREPARED_BAD_EVIDENCE");
   assert(mishare_runtime_reclaim_ndi(&o)<0 && o && !state(o).rate.reset_admitted && !pe_deletes &&
    !dp_detaches && !recovery_timer_cancels && "EXPECTED_RETRY_PREPARED_FAULT_RETAIN");_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
int main(void) {assert(!previous_zero_reset_cases());retry_prepared_cases();return 0;}
'''

def fixture(root):
    s=previous.fixture(root)
    main='int main(void) {assert(!previous_rate_reset_cases());retry_zero_cases();return 0;}'
    assert s.count(main)==1
    return s.replace(main,main.replace('int main(void)','static int previous_zero_reset_cases(void)',1),1)+MODEL+CASES

def controls(original):
    def change(needle,value):
        assert original.count(needle)==1,needle
        return original.replace(needle,value,1)
    return previous.controls(original)+[
        change('entry->state.quiesced == MISHARE_QUIESCE_SSR && entry->state.mc_drained &&',
               'entry->state.quiesced == MISHARE_QUIESCE_SSR && true &&'),
        change('mishare_runtime_retry_receipt_valid(r, &r->receipt, r->result, r->vdev_id);',
               'true; /* negative: ignore frozen retry receipt/ID */'),
        change('!rate->ordinary_admitted && !rate->ordinary_completed &&',
               'true && !rate->ordinary_completed &&')]

def audit(root):
    r=previous.previous.audit(root,fixture_builder=fixture,additional_mutations=controls,
            mutation_markers=('EXPECTED_RATE_RESET_','EXPECTED_RETRY_ZERO_','EXPECTED_RETRY_PREPARED_'))
    r.update(status='MISHARE_RETRY_PREPARED_RESET_FIXTURE_PASS_ONLY',retry_prepared_combinations=352,retry_prepared_retention_faults=16,retry_zero_reset_combinations=32,retry_zero_retention_faults=12)
    r['limitations']='Production retry work/configure/registry with modeled WMI executor, selected native prepared SSR/timer/PE/DP/VDEV/free and actual native recovery qualification bodies. No ordinary-tail/peer-reset extension, firmware ACK, IRQ/DP/ref physical concurrency, automatic parent lease, public init/START or phone/RF/Apple proof.'
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
