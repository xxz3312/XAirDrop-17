#!/usr/bin/env python3
"""Configured native START encoder preview through ordinary/qualified SSR cleanup."""
import argparse
import json
import re
from pathlib import Path
import mishare_retry_prepared_reset_fixture as reset
import mishare_retry_native_fixture as ordinary
from mishare_recovery_fixture import function
ROOT=reset.ROOT
MODEL=r'''
static void preview_publish(struct wlan_objmgr_psoc *p,u8 id,void *token,u32 freq,int result,
                             const struct mishare_ndi_start_summary *summary) {
 mishare_runtime_ndi_start_plan_event(p,id,token,freq,result,summary);
 if(token!=preview_owner)return;
 struct mishare_runtime_owner *o=token,*held=o;
 assert(state(o).start_preview.completed && !state(o).start_preview.integrity_error &&
  state(o).work_pending==1 && !state(o).work_users && "EXPECTED_PLAN_PREVIEW_PUBLICATION");
 if(!state(o).quiesced)assert(mishare_runtime_start_preview(o,freq)==-EINPROGRESS &&
  "EXPECTED_PLAN_PREVIEW_POST_RETURN_BARRIER");
 assert(mishare_runtime_destroy(&held)<0 && held==o && !state(o).ndi.pe_delete_requested &&
  "EXPECTED_PLAN_PREVIEW_RETAIN_WORK");
}
static void preview_exercise(struct mishare_runtime_owner *o,u32 freq,unsigned origin,bool inline_cb) {
 struct mishare_runtime_rate_status rate=state(o).rate;
 struct mishare_runtime_retry_status retry=state(o).retry;
 unsigned posts=pe_posts,builds=plan_builds;
 preview_owner=o;pe_early=inline_cb;pe_queue_fail=origin==4;plan_pdev_fail=origin==3;
 int initial=mishare_runtime_start_preview(o,freq);pe_queue_fail=false;
 assert(initial==(origin==4?-EIO:-EINPROGRESS) && state(o).start_preview.requested &&
  !state(o).ndi.start_plan_requested && !state(o).ndi.radio_requested && !o->radio &&
  "EXPECTED_PLAN_PREVIEW_SUBMIT");
 if(origin!=4 && !inline_cb) {
  assert(pe_pending.bodyptr && state(o).work_pending==1 && !state(o).start_preview.completed &&
   mishare_runtime_start_preview(o,freq)==-EINPROGRESS && pe_posts==posts+1 && "EXPECTED_PLAN_PREVIEW_WAIT");
  struct wlan_objmgr_psoc foreign={9};
  mishare_runtime_ndi_start_plan_event(&foreign,7,o,freq,0,NULL);
  mishare_runtime_ndi_start_plan_event(&psoc,8,o,freq,0,NULL);
  mishare_runtime_ndi_start_plan_event(&psoc,7,(void*)1,freq,0,NULL);
  assert(!state(o).start_preview.completed && !state(o).start_preview.integrity_error &&
   "EXPECTED_PLAN_PREVIEW_FOREIGN_EVENT");
  if(origin==2)mark_closed(o);
  run_pe(origin==1);
 }
 pe_early=false;plan_pdev_fail=false;
 struct mishare_start_preview_status status=state(o).start_preview;
 assert(status.completed && !status.integrity_error && !state(o).work_pending && !state(o).work_users &&
  (origin?status.result<0:status.result==0) && "EXPECTED_PLAN_PREVIEW_COMPLETION");
 assert(origin?mishare_preview_summary_empty(&status.summary):
  (status.summary.freq==freq && status.summary.center_freq==freq && plan_builds==builds+1) &&
  "EXPECTED_PLAN_PREVIEW_NATIVE_BUILDER");
 unsigned after=pe_posts;
 for(unsigned repeat=0;repeat<3;repeat++)assert(mishare_runtime_start_preview(o,freq)==
  (state(o).quiesced?-ESHUTDOWN:status.result) && pe_posts==after && "EXPECTED_PLAN_PREVIEW_NO_REPLAY");
 assert(!mishare_runtime_preview_retire_check(o) &&
  !memcmp(&rate,&o->state.rate,sizeof(rate)) && !memcmp(&retry,&o->state.retry,sizeof(retry)) &&
  !state(o).ndi.start_plan_requested && !state(o).ndi.radio_requested && !o->radio &&
  "EXPECTED_PLAN_PREVIEW_HISTORY");
 assert(mishare_runtime_ndi_start_plan(o)==-EOPNOTSUPP && mishare_runtime_ndi_start(o)==-EOPNOTSUPP &&
  "EXPECTED_PLAN_PREVIEW_NO_RADIO_START");
 preview_owner=NULL;
}
'''
SSR=r'''
static void preview_reset_cases(void) {
 const u8 pairs[][2]={{0,0},{5,0},{0,3},{5,3}};
 for(unsigned band=0;band<2;band++)for(unsigned pair=0;pair<4;pair++)for(unsigned origin=0;origin<5;origin++)
 for(unsigned timing=0;timing<2;timing++)for(unsigned tail=0;tail<4;tail++) {
  if(timing && origin)continue;
  reset_pe_test();u32 freq=band?5240:2437;
  struct mishare_runtime_owner *o=retry_prepared_ready(freq,pairs[pair][0],pairs[pair][1],0,false,false);
  preview_exercise(o,freq,origin,!!timing);
  struct mishare_start_preview_status history=state(o).start_preview;
  struct wlan_objmgr_vdev *held=last_vdev;if(tail&1)assert(!wlan_objmgr_vdev_try_get_ref(held,1));
  retry_zero_stop_recovery(o);early_dp=!!(tail&2);
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && state(o).rate.reset_admitted &&
   !memcmp(&history,&o->state.start_preview,sizeof(history)) && "EXPECTED_PLAN_PREVIEW_SSR_BEGIN");
  if(!(tail&2))finish_dp();
  if(tail&1) {
   assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).host_delete_accepted &&
    "EXPECTED_PLAN_PREVIEW_FINAL_WAIT");
   native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
   assert(!mishare_runtime_reclaim_final(&o) && !o && "EXPECTED_PLAN_PREVIEW_FINAL_AFTER_CLOSE");
  } else assert(!mishare_runtime_reclaim_ndi(&o) && !o && "EXPECTED_PLAN_PREVIEW_SSR_FINAL");
  assert(!allocations && !objects_live && !ctx_locks && !dp_objects && !reset_wmi_calls && !wire_deletes &&
   "EXPECTED_PLAN_PREVIEW_SSR_BALANCE");
 }
 for(unsigned fault=0;fault<9;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   reset_pe_test();struct mishare_runtime_owner *o=retry_prepared_ready(5240,5,3,0,false,false);
   if(fault<4 || fault==7) {
    preview_exercise(o,5240,0,false);
    if(fault==0){struct mishare_ndi_start_summary q=state(o).start_preview.summary;mishare_runtime_ndi_start_plan_event(&psoc,7,o,5240,0,&q);}
    if(fault==1)o->state.start_preview.posted=false;
    if(fault==2)o->state.start_preview.vdev_id^=1;
    if(fault==3)o->state.start_preview.summary.freq++;
    if(fault==7){assert(mishare_runtime_start_preview(o,5180)==-EBUSY && state(o).start_preview.freq==5240 && "EXPECTED_PLAN_PREVIEW_IMMUTABLE");_Exit(0);}
   } else {
    if(fault==4)o->state.retry.receipt.submitted_mask^=1;
    if(fault==5)o->state.rate.integrity_error=true;
    if(fault==8)o->state.rate.accepted=false;
    if(fault==6){assert(!mishare_runtime_work_get(last_vdev,o));assert(mishare_runtime_start_preview(o,5240)==-EINPROGRESS && !state(o).start_preview.requested && "EXPECTED_PLAN_PREVIEW_DRAIN");_Exit(0);}
    assert(mishare_runtime_start_preview(o,5240)==-EUCLEAN && !state(o).start_preview.requested && "EXPECTED_PLAN_PREVIEW_ADMISSION");
   }
   struct mishare_runtime_owner *held=o;
   assert(mishare_runtime_destroy(&held)==-EUCLEAN && held==o && !pe_deletes && !dp_detaches &&
    "EXPECTED_PLAN_PREVIEW_BAD_RECEIPT_RETAIN");
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_PLAN_PREVIEW_FAULT_CHILD");
 }
}
'''
ORDINARY=r'''
static void preview_ordinary_cases(void) {
 const u8 pairs[][2]={{0,0},{5,0},{0,3},{5,3}};
 const unsigned modes[]={0,4,8,16};
 for(unsigned band=0;band<2;band++)for(unsigned pair=0;pair<4;pair++)for(unsigned origin=0;origin<5;origin++)
 for(unsigned timing=0;timing<2;timing++)for(unsigned tail=0;tail<4;tail++) {
  if(origin==2 || (timing && origin))continue;
  /* Native ordinary cleanup adapters are one lifecycle per process, as in
   * the underlying prestart/retry fixture; do not reuse their terminal state. */
  pid_t child=fork();assert(child>=0);if(!child) {
   preview_cycle_enabled=true;preview_cycle_origin=origin;preview_cycle_inline=!!timing;
   retry_data=pairs[pair][0];retry_mgmt=pairs[pair][1];retry_failure=retry_fault=0;retry_inline=false;
   prestart_native_cycle(band?5240:2437,0,modes[tail],false,0);
   assert(!allocations && !objects_live && !dp_objects && !module_refs && "EXPECTED_PLAN_PREVIEW_ORDINARY_BALANCE");
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_PLAN_PREVIEW_ORDINARY_CHILD");
 }
 preview_cycle_enabled=false;
}
'''

def common(source):
    finish=function(source,'mishare_start_plan_finish')
    needle='mishare_runtime_ndi_start_plan_event(psoc, id, owner, freq, ret,'
    assert finish.count(needle)==1
    declaration='static struct mishare_runtime_owner *preview_owner;\nstatic void preview_publish(struct wlan_objmgr_psoc *,u8,void *,u32,int,const struct mishare_ndi_start_summary *);\n'
    source=source.replace(finish,declaration+finish.replace(needle,'preview_publish(psoc, id, owner, freq, ret,',1),1)
    # Assert this composition uses the actual owned MC post and native builder.
    post=function(source,'mishare_ndi_start_plan_post')
    assert 'mishare_runtime_work_get' in post and 'scheduler_post_message' in post
    assert 'vdev_mgr_start_param_update' in source
    return source

def main_body(source):
    one=re.search(r'^int main\(void\) \{[^\n]+\}',source,re.M)
    return one[0] if one else function(source,'main')

def reset_fixture(root):
    source=common(reset.fixture(root))
    prepared=re.search(r'^static struct mishare_runtime_owner \*prepared\(void\) \{.*?^\}',source,re.M|re.S)[0]
    needle='!create(&o) && !mishare_runtime_ndi_create'
    assert prepared.count(needle)==1
    source=source.replace(prepared,prepared.replace(needle,'!create(&o) && !mishare_runtime_bssid_bind(o,mac) && !mishare_runtime_ndi_create',1),1)
    main=main_body(source)
    return source.replace(main,MODEL+SSR+'\nint main(void) {preview_reset_cases();puts("MISHARE_RATE_RESET_FIXTURE_PASS_ONLY");return 0;}',1)

def ordinary_fixture(root):
    source,exits,stubbed=ordinary.fixture(root);source=common(source)
    cycle=function(source,'prestart_native_cycle');modified=cycle.replace('assert(!create(&o));','assert(!create(&o));\n if(preview_cycle_enabled)assert(!mishare_runtime_bssid_bind(o,mac));',1)
    needle=' struct mishare_runtime_rate_status before=state(o).rate;';assert modified.count(needle)==1
    modified=modified.replace(needle,' if(preview_cycle_enabled)preview_exercise(o,freq,preview_cycle_origin,preview_cycle_inline);\n'+needle,1)
    declarations='static bool preview_cycle_enabled,preview_cycle_inline;static unsigned preview_cycle_origin;\nstatic void preview_exercise(struct mishare_runtime_owner *,u32,unsigned,bool);\n'
    source=source.replace(cycle,declarations+modified,1)
    main=main_body(source)
    source=source.replace(main,MODEL+ORDINARY+'\nint main(void) {\n preview_ordinary_cases();engine_contract();return 0;\n}\n',1)
    return source,exits,stubbed

def mutations(original):
    out=[]
    def mutate(body,old,new):
        assert body.count(old)==1,old
        out.append(original.replace(body,body.replace(old,new,1),1))
    api=function(original,'mishare_runtime_start_preview');event=function(original,'mishare_runtime_ndi_start_plan_event')
    retirement=function(original,'mishare_runtime_preview_retire_check');rate=function(original,'mishare_runtime_rate_retire_check')
    mutate(api,'!r->accepted ||','false ||')
    mutate(api,'    p->requested = true;', '    p->requested = false;')
    mutate(api,'ret ? ret : -EINPROGRESS;', 'ret ? ret : 0;')
    mutate(event,'if (entry->state.start_preview.requested)', 'if (false && entry->state.start_preview.requested)')
    mutate(retirement,'if (entry->state.work_pending || entry->state.work_users)', 'if (false && (entry->state.work_pending || entry->state.work_users))')
    mutate(rate,'if (preview_ret)', 'if (false && preview_ret)')
    return out

def audit(root):
    r=reset.previous.previous.audit(root,fixture_builder=reset_fixture,additional_mutations=mutations,
                                  mutation_markers=('EXPECTED_PLAN_PREVIEW_',))
    engine=ordinary.previous.ordinary.cleanup.engine
    q=engine.audit(root,fixture_builder=ordinary_fixture)
    return {'status':'MISHARE_CONFIGURED_PLAN_PREVIEW_FIXTURE_PASS_ONLY','ssr_combinations':192,
            'ordinary_combinations':160,'retained_faults':9,'preview_mutations':6,'ssr_report':r,'ordinary_report':q,
            'limitations':'Production configured preview registry, actual owned MC START encoder and selected native ordinary/qualified SSR retirement. Rate WMI execution/firmware ACK, primitive scheduling/refs/IRQ/physical DP and locks remain modeled. No NDI START-plan flags, radio START/UP, public init or phone/RF/Apple certification.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
