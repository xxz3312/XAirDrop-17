#!/usr/bin/env python3
"""Actions-only completed channel/START-plan SSR retirement before any radio request."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import mishare_pe_reset_fixture as pe
from mishare_recovery_fixture import function

ROOT = pe.ROOT
HARNESS = r'''
static struct mishare_runtime_owner *ready_pre_radio(unsigned freq,bool plan) {
 struct mishare_runtime_owner *o=ready_pe_owner();last_vdev->mlme->proto.generic.nss_5g=2;
 assert(mishare_runtime_ndi_channel(o,freq)==-EINPROGRESS);run_pe(false);
 assert(state(o).ndi.channel_prepared && !state(o).ndi.channel_error);
 if(plan) {assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);run_pe(false);assert(state(o).ndi.start_plan_ready && !plan_pdev_refs);}
 return o;
}
static void assert_preparation_history(struct mishare_runtime_owner *o,struct mishare_ndi_status before) {
 struct mishare_ndi_status n=state(o).ndi;assert_reset_pe_facts(o);
 assert(n.channel_requested && n.channel_submitted && n.channel_completed && n.channel_prepared && !n.channel_error && n.channel_freq==before.channel_freq);
 assert(n.start_plan_requested==before.start_plan_requested && n.start_plan_submitted==before.start_plan_submitted && n.start_plan_completed==before.start_plan_completed && n.start_plan_ready==before.start_plan_ready);
 assert(!memcmp(&n.start_plan,&before.start_plan,sizeof(n.start_plan)) && !n.radio_requested && !o->radio);
}
int main(void) {
 assert(!pre_channel_regressions());
 struct mishare_runtime_owner *o=NULL;
 for(unsigned band=0;band<2;band++)for(unsigned plan=0;plan<2;plan++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=ready_pre_radio(band?5240:2437,plan);struct mishare_ndi_status history=state(o).ndi;
  unsigned posts=pe_posts,builds=plan_builds,prepares=ch_prepares;stop_recovery(o);early_dp=inline_cb;
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o);assert_preparation_history(o,history);
  assert(pe_posts==posts && plan_builds==builds && ch_prepares==prepares && pe_deletes==1 && dp_detaches==1 && !radio_q_len);
  assert(state(o).ndi.legacy_ready && state(o).ndi.wma_bound && !state(o).recovery_context_released);
  if(!inline_cb) {assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && pe_deletes==1);finish_dp();}
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !ctx_locks && !dp_objects);
 }
 reset_pe_test();o=ready_pre_radio(5240,true);struct mishare_ndi_status history=state(o).ndi;stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_preparation_history(item.owner,history);
 finish_dp();assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !item.result && !allocations);
 reset_pe_test();o=ready_pre_radio(5240,false);struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).ndi_reclaim_ready);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
 /* Completed preparation facts do not substitute for native geometry. */
 for(int fault=0;fault<9;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=ready_pre_radio(5240,true);stop_recovery(o);struct wlan_channel *d=last_vdev->vdev_mlme.des_chan;
   if(fault==0)pe_slot.curr_op_freq=5180;
   if(fault==1)d->ch_freq=5180;
   if(fault==2)d->ch_width=1;
   if(fault==3)d->ch_cfreq1=5260;
   if(fault==4)d->ch_cfreq2=5260;
   if(fault==5)last_vdev->vdev_mlme.des_chan=NULL;
   if(fault==6)pe_slot.ch_width=1;
   if(fault==7)pe_slot.ch_center_freq_seg1=1;
   if(fault==8) {o->state.ndi.channel_freq=5955;o->state.ndi.start_plan.freq=o->state.ndi.start_plan.center_freq=5955;pe_slot.curr_op_freq=5955;d->ch_freq=d->ch_cfreq1=5955;}
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error);
   assert(!pe_deletes && !recovery_timer_cancels && !reset_force_detaches && !dp_detaches && pe_heap_live==2);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !pe_deletes);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Snapshot frequency and native geometry must still match after timer drain. */
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=ready_pre_radio(5240,true);stop_recovery(o);reset_geometry_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_timer_released && state(o).recovery_pe_attempted && !state(o).recovery_pe_released);
  assert(!pe_deletes && pe_slot.valid && pe_heap_live==2 && !dp_detaches && !reset_force_detaches);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && recovery_timer_cancels==1);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Pending or failed preparation, malformed completion summaries and any
  * radio START request never acquire reset admission. */
 for(int fault=0;fault<17;fault++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   if(fault<=3) {
    o=ready_pe_owner();
    if(fault==0)assert(mishare_runtime_ndi_channel(o,5240)==-EINPROGRESS);
    if(fault==1) {ch_scan=true;assert(mishare_runtime_ndi_channel(o,5240)==-EINPROGRESS);run_pe(false);}
    if(fault>=2) {assert(mishare_runtime_ndi_channel(o,5240)==-EINPROGRESS);run_pe(false);if(fault==3)plan_pdev_fail=true;assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);if(fault==3)run_pe(false);}
   } else {
    o=ready_pre_radio(5240,true);
    if(fault==4)o->state.ndi.channel_submitted=false;
    if(fault==5)o->state.ndi.channel_completed=false;
    if(fault==6)o->state.ndi.channel_prepared=false;
    if(fault==7)o->state.ndi.channel_error=-EIO;
    if(fault==8)o->state.ndi.start_plan_submitted=false;
    if(fault==9)o->state.ndi.start_plan_completed=false;
    if(fault==10)o->state.ndi.start_plan_ready=false;
    if(fault==11)o->state.ndi.start_plan_error=-EIO;
    if(fault==12)o->state.ndi.start_plan.freq++;
    if(fault==13)o->state.ndi.start_plan.center_freq++;
    if(fault==14)o->state.ndi.start_plan.tx_streams=0;
    if(fault==15)o->state.ndi.start_plan.rx_streams++;
    if(fault==16)o->state.ndi.radio_requested=true;
   }
   mark_closed(o);health_recovering=true;assert(!cds_post_disable());
   assert(state(o).mc_drained && !state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !pe_deletes && !recovery_timer_cancels && !dp_detaches);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* A real submitted radio request remains unsupported even after MC flush. */
 reset_pe_test();child=fork();assert(child>=0);
 if(!child) {
  o=ready_pre_radio(5240,true);assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);
  mark_closed(o);health_recovering=true;assert(!cds_post_disable());
  assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !pe_deletes && !dp_detaches);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 puts("MISHARE_PRE_RADIO_PREPARED_RESET_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS = r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=ready_pre_radio(5240,true);stop_recovery(o);
 pe_slot.curr_op_freq=5180;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && "EXPECTED_NATIVE_FREQ_REJECTION");
 _Exit(0);
}
'''


def fixture(root):
    src=pe.fixture(root)
    src=src.replace('static bool reset_pe_drift;','static bool reset_pe_drift,reset_geometry_drift;',1)
    src=src.replace('reset_prepared_test();reset_pe_drift=false;','reset_prepared_test();reset_pe_drift=reset_geometry_drift=false;',1)
    needle='recovery_timer_cancels++;';assert src.count(needle)==1
    src=src.replace(needle,needle+'if(reset_geometry_drift)last_vdev->vdev_mlme.des_chan->ch_cfreq1+=20;',1)
    src=src.replace('int main(void) {','static int pre_channel_regressions(void) {',1)
    src=src.replace('puts("MISHARE_PRE_CHANNEL_PE_RESET_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model */\n')
        c=d/'reset.c';exe=d/'reset';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        c.write_text(source);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=45,env=env)
        main=function(source,'main');target=source.replace(main,NEGATIVE_HARNESS.strip(),1)
        c.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        guard='session->curr_op_freq != expected_freq';assert target.count(guard)==1
        c.write_text(target.replace(guard,'false /* negative: omit native PE frequency check */',1));subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_NATIVE_FREQ_REJECTION' in bad.stderr
    assert out.strip()=='MISHARE_PRE_RADIO_PREPARED_RESET_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'native_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in [pe.API,pe.destructor.pe.SESSION,pe.destructor.UTILS,pe.destructor.AUTH,pe.prepared.WMA]},
            'negative_control_missing_native_frequency_check_rejected':True,
            'checks':['all 0072 pre-channel PE regressions retained',
                      '2.4 GHz and 48-channel 5240 MHz; channel-only and completed START plan; inline/deferred DP final-free',
                      'exact batch retirement and delayed object final-free after window closure',
                      'native PE/desired-channel geometry checked before and after timer drain',
                      '9 native geometry faults and 17 incomplete/failed/malformed/radio histories reject without PE/DP cleanup',
                      'actual posted radio request remains unsupported after MC flush',
                      'channel/plan completion flags and scalar summary retained; no preparation replay, MC post or firmware ACK fabricated'],
            'limitations':'Only completed channel and optional START-plan preparation before any radio START request. Production runtime, native request/check/release/destructor and native WMA peer/parameter builder code execute with modeled regulatory/lim_pre_vdev_start, PE allocation, remaining cleanup callees, timers/scheduler/locks, DP/object-peer physical lifecycle and parents. No automatic parent/shutdown coordinator, failed/pending preparation recovery, radio START/UP recovery, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
