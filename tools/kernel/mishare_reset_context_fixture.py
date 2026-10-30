#!/usr/bin/env python3
"""Actions-only pre-PE prepared SSR reclaim through actual native no-FW peer removal."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_recovery_fixture as recovery

ROOT = recovery.ROOT
WMA = recovery.work.shutdown.radio.plan.channel.pe.ctx.WMA
MODELS = r'''
static bool is_cdp_peer_detach_force_delete_supported(void *s);
static bool cdp_cfg_get_peer_unmap_conf_support(void *s);
#define WLAN_MAX_VDEVS 32
#define CDP_PEER_DELETE_NO_SPECIAL 0
#define CDP_PEER_DO_NOT_START_UNMAP_TIMER 1
#define WMI_MGMT_TID 16
#define DEBUG_PEER_DELETE_SEND 1
#define DEBUG_INVALID_PEER_ID 0
#define wmi_service_peer_delete_no_peer_flush_tids_cmd 3
#define QDF_MODULE_ID_SOC 3
#define QDF_ASSERT(x) assert(x)
#undef QDF_BUG
#define QDF_BUG(x) assert(x)
#define wma_err(...) ((void)0)
#define wma_nofl_err(...) ((void)0)
#define wma_debug(...) ((void)0)
struct peer_flush_params {uint32_t peer_tid_bitmap;uint8_t vdev_id;};
struct peer_delete_cmd_params {uint8_t vdev_id;bool is_mlo_link_switch;};
static unsigned reset_peer_ops,reset_force_detaches,reset_obj_deletes,reset_wmi_calls;
static bool reset_obj_failure,reset_slot_drift,reset_peer_delayed;
static void *reset_peer_get_context(int id) {assert(id==3);return wma_context.psoc;}
static void wma_peer_tbl_trans_add_entry(struct wlan_objmgr_peer *p,bool add,void *ctx) {assert(p==&ctx_peer && !add && !ctx && !reset_peer_ops && !timers_live);reset_peer_ops++;}
static void cdp_peer_teardown(void *s,uint8_t id,uint8_t *mac) {assert(s==wma_context.psoc && id==7 && mac && reset_peer_ops==1);reset_peer_ops++;}
static void cdp_peer_detach_force_delete(void *s,uint8_t id,uint8_t *mac) {assert(s==wma_context.psoc && id==7 && mac && reset_peer_ops==2 && !timers_live);reset_peer_ops++;reset_force_detaches++;}
static void wma_peer_unmap_conf_cb(void) {assert(0);}
static void cdp_peer_delete_sync(void *s,uint8_t id,uint8_t *mac,void (*cb)(void),uint32_t bitmap) {(void)s;(void)id;(void)mac;(void)cb;(void)bitmap;assert(0);}
static void cdp_peer_delete(void *s,uint8_t id,uint8_t *mac,uint32_t bitmap) {(void)s;(void)id;(void)mac;(void)bitmap;assert(0);}
static void wlan_roam_debug_log(uint8_t id,int reason,int peer_id,uint8_t *mac,void *p,int a,int b) {(void)id;(void)reason;(void)peer_id;(void)mac;(void)p;(void)a;(void)b;}
static bool wlan_vdev_mlme_is_mlo_link_switch_in_progress(struct wlan_objmgr_vdev *v) {(void)v;return false;}
static QDF_STATUS wmi_unified_peer_flush_tids_send(void *w,uint8_t *mac,struct peer_flush_params *p) {(void)w;(void)mac;(void)p;reset_wmi_calls++;assert(!"WMI_ON_RESET_PATH");return QDF_STATUS_E_FAILURE;}
static QDF_STATUS wmi_unified_peer_delete_send(void *w,uint8_t *mac,struct peer_delete_cmd_params *p) {(void)w;(void)mac;(void)p;reset_wmi_calls++;assert(!"WMI_ON_RESET_PATH");return QDF_STATUS_E_FAILURE;}
static void wlan_release_peer_key_wakelock(struct wlan_objmgr_vdev *v,uint8_t *mac) {assert(v==ctx_peer.vdev && mac && v->mlme->ext_vdev_ptr && reset_peer_ops==3);reset_peer_ops++;}
static struct wlan_objmgr_peer *wlan_objmgr_get_peer(struct wlan_objmgr_psoc *p,uint8_t id,uint8_t *mac,int ref) {assert(p==wma_context.psoc && !id && mac && ref==3);return ctx_peer_present?&ctx_peer:NULL;}
static QDF_STATUS wlan_objmgr_peer_obj_delete(struct wlan_objmgr_peer *p) {assert(p==&ctx_peer && reset_peer_ops==4);reset_peer_ops++;reset_obj_deletes++;if(reset_obj_failure)return QDF_STATUS_E_FAILURE;ctx_peer_present=false;if(!reset_peer_delayed)ctx_reset_peer_count--;if(reset_slot_drift)wma_context.interfaces[7].bss_status=99;return QDF_STATUS_SUCCESS;}
#define cds_get_context reset_peer_get_context
NATIVE_OBJ_PEER_REMOVE
NATIVE_PEER_REMOVE
#undef QDF_BUG
#undef cds_get_context
'''
HARNESS = r'''
static void reset_prepared_test(void) {
 reset_recovery();reset_peer_ops=reset_force_detaches=reset_obj_deletes=reset_wmi_calls=0;
 reset_obj_failure=reset_slot_drift=reset_peer_delayed=false;ctx_reset_force_supported=true;ctx_reset_unmap_conf=false;
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 for(int inline_cb=0;inline_cb<2;inline_cb++) {
  reset_prepared_test();o=prepared();stop_recovery(o);early_dp=inline_cb;
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o);
  assert(state(o).recovery_context_attempted && state(o).recovery_context_released);
  assert(!state(o).ndi.legacy_ready && !state(o).ndi.wma_bound && !state(o).ndi.peer_created);
  assert(state(o).ndi.peer_create_attempted && !state(o).ndi.peer_delete_pending && !state(o).ndi.peer_delete_submitted && !state(o).ndi.peer_delete_replied);
  assert(!ctx_peer_present && !ctx_locks && !wma_context.interfaces[7].vdev);
  assert(reset_peer_ops==5 && reset_force_detaches==1 && reset_obj_deletes==1 && !reset_wmi_calls && !ctx_requests && !ctx_delete_calls);
  assert(dp_detaches==1 && !wire_deletes && !timers_live);
  if(!inline_cb) {assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && reset_force_detaches==1);finish_dp();}
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !objects_live && !allocations && !dp_objects);
 }
 /* The actual batch dispatcher must admit the same qualified prepared owner. */
 reset_prepared_test();o=prepared();stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,77};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner && item.result==-EINPROGRESS);
 assert(reset_force_detaches==1 && state(item.owner).recovery_context_released);finish_dp();
 assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !item.result && !allocations && !objects_live);
 /* A real outstanding final-free reference keeps the original handle alive. */
 reset_prepared_test();o=prepared();struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && state(o).ndi_reclaim_ready && !state(o).freed);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
 assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !ctx_locks);
 /* Preflight failures never enter native teardown; all cases stay held. */
 for(int fault=0;fault<16;fault++) {
  reset_prepared_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=prepared();stop_recovery(o);
   struct wlan_objmgr_vdev foreign={0};
   if(fault==0)ctx_reset_force_supported=false;
   if(fault==1)ctx_reset_unmap_conf=true;
   if(fault==2)o->state.ndi.create.dp_cookie++;
   if(fault==3)wma_context.interfaces[7].vdev=&foreign;
   if(fault==4)ctx_peer.vdev=&foreign;
   if(fault==5)wma_context.interfaces[7].peer_count=2;
   if(fault==6)wma_context.interfaces[7].bss_status=99;
   if(fault==7)ch_state=3;
   if(fault==8)wmi.wmi_stopinprogress=0;
   if(fault==9)health_recovering=false;
   if(fault==10)o->state.ndi.peer_delete_pending=true;
   if(fault==11)response_timer.rsp_status=1;
   if(fault==12)recovery_cancel_drift=true;
   if(fault==13)recovery_missing_timer=true;
   if(fault==14)response_timer.rt_lock.is_lock_acquired=true;
   if(fault==15)ctx_reset_peer_count=2;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o && !reset_peer_ops && !reset_force_detaches && !dp_detaches && !recovery_timer_frees);
   assert(state(o).ndi.legacy_ready && state(o).ndi.wma_bound && state(o).ndi.peer_created);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !reset_peer_ops && !reset_wmi_calls);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* After native mutation, an error is sticky and partial facts survive. */
 for(int fault=0;fault<3;fault++) {
  reset_prepared_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=prepared();stop_recovery(o);reset_obj_failure=fault==0;reset_slot_drift=fault==1;reset_peer_delayed=fault==2;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o && state(o).recovery_error);
   assert(reset_force_detaches==1 && reset_obj_deletes==1 && !reset_wmi_calls &&  !dp_detaches && recovery_timer_frees==1);
   assert(state(o).ndi.peer_created==(fault==0) && state(o).ndi.wma_bound && state(o).ndi.legacy_ready);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && reset_force_detaches==1);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Completed-context markers cannot masquerade as a fresh timer-owned candidate. */
 reset_prepared_test();pid_t marker_child=fork();assert(marker_child>=0);
 if(!marker_child) {
  o=prepared();o->state.recovery_context_attempted=true;o->state.recovery_context_released=true;
  o->state.ndi.legacy_ready=o->state.ndi.wma_bound=o->state.ndi.peer_created=false;
  mark_closed(o);health_recovering=true;assert(!cds_post_disable());
  assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !reset_force_detaches && !recovery_timer_frees);_Exit(0);
 }
 int marker_status;assert(waitpid(marker_child,&marker_status,0)==marker_child && WIFEXITED(marker_status) && !WEXITSTATUS(marker_status));
 /* PE/radio history is outside the reset route even with force capability. */
 for(int phase=0;phase<3;phase++) {
  reset_prepared_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=phase==0?with_session():with_plan();if(phase==2)start_up(o);
   mark_closed(o);health_recovering=true;assert(!cds_post_disable());
   assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !reset_force_detaches && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_PRE_PE_PREPARED_RESET_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    text = (root/WMA).read_text()
    native = {name: recovery.function(text, name) for name in
              ['wma_remove_objmgr_peer', 'wma_remove_peer', 'mishare_ndi_reset_context_release']}
    assert 'if (no_fw_peer_delete)\n\t\tgoto peer_detach;' in native['wma_remove_peer']
    assert 'wma_remove_peer(wma, mac, id, true)' in native['mishare_ndi_reset_context_release']
    src = recovery.fixture(root)
    old = recovery.function(src, 'wma_remove_peer')
    model = MODELS.replace('NATIVE_OBJ_PEER_REMOVE', native['wma_remove_objmgr_peer']).replace('NATIVE_PEER_REMOVE', native['wma_remove_peer'])
    src = src.replace(old, model, 1)
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    pin = recovery.work.shutdown.radio.plan.channel.pe.PIN
    if subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != pin:
        raise ValueError('Unexpected revision')
    source = fixture(root)
    production = ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:
            (d/n).write_text('/* platform model declarations */\n')
        (d/'reset.c').write_text(source);exe=d/'reset'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'reset.c'),'-o',str(exe)],check=True)
        env = {**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        out = subprocess.check_output([exe], text=True, timeout=45, env=env)
        helper = 'wma_remove_peer(wma, mac, id, true)'
        assert source.count(helper) == 1
        (d/'reset.c').write_text(source.replace(helper,'wma_remove_peer(wma, mac, id, false)',1))
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'reset.c'),'-o',str(exe)],check=True)
        bad = subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode == -6 and 'WMI_ON_RESET_PATH' in bad.stderr
    assert out.strip() == 'MISHARE_PRE_PE_PREPARED_RESET_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':pin,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{WMA:hashlib.sha256((root/WMA).read_bytes()).hexdigest()},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'negative_control_no_fw_false_attempts_wmi_and_is_rejected':True,
            'checks':['actual native wma_remove_peer no-FW force-detach branch and native object-peer remove execute', 'actual batch dispatch accepts the qualified prepared owner', 'inline and deferred DP completion precede actual object final-free', 'external final-free reference retains owner beyond native window closure', '16 capability/identity/state/history/timer/physical-peer-count preflight failures retain all owned context', 'delayed physical peer destruction retains WMA/legacy context', 'partial native failure publishes resource facts, sticks error and never retries', 'PE/START/UP owners remain unsupported', 'no peer/VDEV firmware delete or ordinary DELETE ACK flag fabricated'],
            'limitations':'Production runtime and native WMA removal/helper code with modeled DP force detach, object-peer deletion, native synchronization, WMI transports and physical parents. Existing native timer/DP wrapper and object-manager final-free are included; actual peer/vdev hardware refcounts and kernel races are not certified. Only fully prepared pre-PE INIT is added. No automatic shutdown coordinator, parent lease, PE/UP reset recovery or phone/RF certification; backend stays disabled.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
