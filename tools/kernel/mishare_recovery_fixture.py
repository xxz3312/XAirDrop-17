#!/usr/bin/env python3
"""Actions-only pre-context NDI reset reclaim; full radio recovery excluded."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import mishare_work_fixture as work
from mishare_recovery_origins import remove_recovery_additions
ROOT=work.ROOT
CDS=work.CDS
TIMER='qca-wifi-host-cmn/target_if/mlme/psoc/src/target_if_psoc_timer_tx_ops.c'
DISP='qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/src/wlan_vdev_mgr_tgt_if_tx_api.c'
WMA='qcacld-3.0/core/wma/src/wma_main.c'
WMI='qca-wifi-host-cmn/wmi/src/wmi_unified.c'
DP='qca-wifi-host-cmn/dp/wifi3.0/dp_main.c'
BASE={CDS:'6d3d5066c16ad68f23a80247ada0aca2149c83b7b0cdc30810bb83f2a3584d84',TIMER:'de9ae1bee934653e908c504b57b9e5a94da37e0b1b6f5fbee03b92c1834b86a0',DISP:'5eb7b61812b8f4f4a4977691b6b433ff953cb47fba74291498d3848d52b10079'}
MODELS=r'''
#define QDF_MODULE_ID_HIF 2
#define QDF_MODULE_ID_SOC 3
#define TARGET_STATUS_RESET 4
#define WLAN_UMAC_PSOC_MAX_VDEVS 32
#define QDF_TRACE(...) ((void)0)
#define wma_debug(...) ((void)0)
#define cds_debug(...) ((void)0)
#define cds_err(...) ((void)0)
#define mlme_err(...) ((void)0)
typedef struct wmi_unified *wmi_unified_t;
struct hif_opaque_softc {int status;};
struct cds_context {void *htc_ctx;};
static struct cds_context recovery_cds;
static struct cds_context *gp_cds_context=&recovery_cds;
static struct hif_opaque_softc recovery_hif;
static bool recovery_isr_off,recovery_htc_off,recovery_rx_off,recovery_bad_reset,recovery_missing_timer,recovery_cancel_drift;
static QDF_STATUS recovery_rx_status;
static unsigned recovery_flushes,recovery_buffers,recovery_timer_cancels,recovery_timer_frees,recovery_rt_frees,recovery_validates,recovery_bad_validate;
static struct mishare_runtime_owner *recovery_subject;
static void *recovery_get_context(int id) {if(id==1)return &wma_context;if(id==2)return &recovery_hif;if(id==3)return &psoc;assert(0);return NULL;}
static int wmi_validate_handle(struct wmi_unified *w) {recovery_validates++;return !w || (recovery_bad_validate && recovery_validates==recovery_bad_validate);}
static void hif_disable_isr(struct hif_opaque_softc *h) {assert(h==&recovery_hif);recovery_isr_off=true;}
static void hif_reset_soc(struct hif_opaque_softc *h) {assert(h==&recovery_hif && recovery_isr_off);h->status=recovery_bad_reset?0:4;}
static int hif_get_target_status(struct hif_opaque_softc *h) {assert(h==&recovery_hif);return h->status;}
static bool cds_should_suspend_target(void) {return false;}
static void cds_suspend_target(tp_wma_handle w) {(void)w;assert(0);}
static void htc_stop(void *h) {assert(h==(void*)1 && recovery_isr_off);recovery_htc_off=true;}
static QDF_STATUS cds_close_rx_thread(void) {if(!recovery_rx_status)recovery_rx_off=true;return recovery_rx_status;}
static void cdp_pdev_pre_detach(void *soc,int id,int force) {assert(soc==&psoc && !id && force==1 && recovery_rx_off);}
#define OL_TXRX_PDEV_ID 0
static void recovery_event_lock(int *p) {assert(!*p);*p=1;}
static void recovery_event_unlock(int *p) {assert(*p);*p=0;}
static void qdf_flush_workqueue(int unused,int queue) {
 assert(!unused && (queue==1 || queue==2) && recovery_isr_off && recovery_htc_off && recovery_rx_off && wmi.wmi_stopinprogress);
 if(recovery_subject) {assert(!state(recovery_subject).recovery_window);assert(mishare_runtime_reclaim_ndi(&recovery_subject)==-EINPROGRESS);}
 recovery_flushes++;
}
typedef void *wmi_buf_t;
static wmi_buf_t qdf_nbuf_queue_remove(unsigned *n) {if(!*n)return NULL;(*n)--;return (void*)1;}
static void recovery_nbuf_free(void *b) {assert(b==(void*)1);recovery_buffers++;}
#define qdf_spin_lock_bh recovery_event_lock
#define qdf_spin_unlock_bh recovery_event_unlock
#define qdf_nbuf_free recovery_nbuf_free
NATIVE_WMI_REMOVE
#undef qdf_spin_lock_bh
#undef qdf_spin_unlock_bh
#undef qdf_nbuf_free
NATIVE_WMI_STOP
NATIVE_WMI_BLOCKED
#define cds_get_context recovery_get_context
NATIVE_RESET_CHECK
NATIVE_RESET_CONTEXT
NATIVE_WMA_STOP
NATIVE_WMA_WORK_CLOSE
NATIVE_CDS_HELPER
NATIVE_CDS_POST
#undef cds_get_context
static void native_recovery_close(void) {struct wlan_objmgr_psoc *psoc=health.psoc;NATIVE_CDS_CLOSE}
static struct wlan_lmac_if_mlme_rx_ops *recovery_rx_ops(struct wlan_objmgr_psoc *p) {assert(p==&psoc);return recovery_missing_timer?NULL:&rxops;}
static bool qdf_timer_sync_cancel(int *timer) {assert(timer==&response_timer.rsp_timer && *timer==1);recovery_timer_cancels++;if(recovery_cancel_drift)response_timer.rsp_status=1;return false;}
static void qdf_timer_free(int *timer) {assert(timer==&response_timer.rsp_timer && *timer==1 && timers_live==1 && recovery_timer_cancels);*timer=0;timers_live--;recovery_timer_frees++;}
static void recovery_runtime_deinit(int *lock) {assert(lock==&response_timer.rt_lock.vdev_cmd_rt_lock && *lock==1);*lock=0;recovery_rt_frees++;}
#define target_if_vdev_mgr_get_rx_ops recovery_rx_ops
#define qdf_runtime_lock_deinit recovery_runtime_deinit
NATIVE_TIMER_DEINIT
NATIVE_TIMER_HELPER
NATIVE_PREPARED_TIMER
#undef qdf_runtime_lock_deinit
#undef target_if_vdev_mgr_get_rx_ops
NATIVE_DP_HELPER
'''
HARNESS=r'''
static void reset_recovery(void) {
 reset_work();memset(&response_timer,0,sizeof(response_timer));
 recovery_cds.htc_ctx=(void*)1;recovery_hif.status=0;
 recovery_isr_off=recovery_htc_off=recovery_rx_off=recovery_bad_reset=recovery_missing_timer=recovery_cancel_drift=false;
 recovery_rx_status=QDF_STATUS_SUCCESS;recovery_flushes=recovery_buffers=recovery_timer_cancels=recovery_timer_frees=recovery_rt_frees=recovery_validates=recovery_bad_validate=0;
 recovery_subject=NULL;wmi.wmi_stopinprogress=0;wmi.wmi_rx_work_queue=1;wmi.wmi_rx_diag_work_queue=2;
 wmi.event_queue=3;wmi.diag_event_queue=2;wmi.eventq_lock=wmi.diag_eventq_lock=0;
 rxops.psoc_get_vdev_response_timer_info=get_response_timer;
}
static struct mishare_runtime_owner *early_ndi(void) {struct mishare_runtime_owner *o=NULL;assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));assert(state(o).ndi.create.dp_cookie==(unsigned long)&psoc);return o;}
static void stop_recovery(struct mishare_runtime_owner *o) {
 mark_closed(o);health_recovering=true;recovery_subject=o;
 assert(!cds_post_disable() && state(o).mc_drained && state(o).recovery_window);
 assert(recovery_flushes==2 && recovery_buffers==5 && recovery_isr_off && recovery_htc_off && recovery_rx_off);
 recovery_subject=NULL;
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_runtime_reclaim_ndi(NULL)==-EINVAL && !mishare_runtime_reclaim_ndi(&o));
 reset_recovery();health_recovering=true;assert(!cds_post_disable() && !recovery_flushes); /* no owned candidate, ordinary path */
 for(int inline_cb=0;inline_cb<2;inline_cb++) {
  reset_recovery();o=early_ndi();assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);
  stop_recovery(o);early_dp=inline_cb;
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && !timers_live && !stats_live && !wire_deletes && !delete_calls);
  assert(recovery_timer_frees==1 && recovery_rt_frees==1 && dp_detaches==1 && !state(o).ndi.delete_replied);
  if(!inline_cb) {assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !delete_calls);finish_dp();}
  void *old_token=o;
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !objects_live && !allocations && !dp_objects && !stats_live && !timers_live);
  mishare_runtime_recovery_dp_freed(old_token); /* ignored without dereferencing a freed token */
 }
 reset_recovery();defer_ref=1;o=early_ndi();struct wlan_objmgr_vdev *held=last_vdev;stop_recovery(o);
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && state(o).ndi_reclaim_ready && !state(o).ndi.active && held->refs==1);
 assert(state(o).ndi.create.wire_attempted && state(o).ndi.create.wire_accepted && !state(o).ndi.delete_submitted && !state(o).ndi.delete_replied && !state(o).ndi.dp_freed);
 assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && state(o).blocked);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,2);
 assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
 /* Missing native transport conditions never open a recovery window. */
 for(int fault=0;fault<6;fault++) {
  reset_recovery();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=early_ndi();mark_closed(o);health_recovering=fault!=0;
   recovery_bad_reset=fault==1;if(fault==2)recovery_cds.htc_ctx=NULL;
   recovery_rx_status=fault==3?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
   recovery_bad_validate=fault==4?1:fault==5?3:0;
   QDF_STATUS s=cds_post_disable();assert((s!=QDF_STATUS_SUCCESS)==(fault==3));
   assert(!state(o).recovery_window && state(o).mc_drained && !recovery_timer_frees && !dp_detaches);
   assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !wire_deletes && !delete_calls);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Bad timer identity/status and post-cancel drift retain DP, no forced ACK. */
 for(int fault=0;fault<10;fault++) {
  reset_recovery();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=early_ndi();stop_recovery(o);
   if(fault==0) {response_timer.psoc=NULL;}
   if(fault==1) {response_timer.vdev_id=8;}
   if(fault==2) {response_timer.rsp_timer_inuse=0;}
   if(fault==3) {response_timer.rsp_status=1;}
   if(fault==4)response_timer.rt_lock.is_lock_acquired=true;
   recovery_missing_timer=fault==5;recovery_cancel_drift=fault==6;
   if(fault==7)o->state.ndi.create.dp_cookie++;
   missing_dp=fault==8;dp_detach_status=fault==9?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error && o && dp_objects==1);
   unsigned detaches=dp_detaches,cancels=recovery_timer_cancels;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && dp_detaches==(int)detaches && recovery_timer_cancels==cancels);
   assert(!wire_deletes && !delete_calls && !state(o).ndi.delete_replied);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Real window closure cannot be reversed, even if the DP callback is late. */
 reset_recovery();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=early_ndi();stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);
  native_recovery_close();finish_dp();mishare_runtime_recovery_open(&psoc);
  assert(state(o).recovery_window_closed && !state(o).recovery_window && state(o).recovery_dp_freed);
  assert(mishare_runtime_reclaim_ndi(&o)==-ESHUTDOWN && !delete_calls && last_vdev->mlme->mgmt.generic.type==7);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Context/peer/PE/radio, DELETE history, partial attach and duplicate DP events
  * are deliberately quarantined instead of entering this narrow reclaim. */
 for(int fault=0;fault<8;fault++) {
  reset_recovery();child=fork();assert(child>=0);
  if(!child) {
   if(fault==0)o=prepared();else if(fault==1)o=with_session();else if(fault==2)o=with_plan();
   else {o=early_ndi();if(fault==3)o->state.ndi.delete_pending=true;if(fault==4)o->state.ndi.create.dp_attached=false;if(fault==5)o->state.ndi.context_error=-EIO;}
   if(fault<=5) {
    mark_closed(o);health_recovering=true;assert(!cds_post_disable());
    assert(state(o).recovery_window==(fault==0) && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !dp_detaches && !recovery_timer_frees);
   } else {
    stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
    if(fault==6) {mishare_runtime_recovery_dp_freed(o);assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error);}
    else {delete_fail=1;assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).reclaim_error);unsigned deletes=delete_calls;assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && delete_calls==(int)deletes);}
   }
   assert(o && !wire_deletes && !state(o).ndi.delete_replied);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_recovery();assert(!create(&o) && !mishare_runtime_destroy(&o));
 puts("MISHARE_EARLY_NDI_RESET_RECLAIM_FIXTURE_PASS_ONLY");return 0;
}
'''
def function(text,name):
    m=re.search(r'(?:static\s+)?(?:void|int|bool|QDF_STATUS)\s+'+name+r'\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)
    if not m:raise ValueError('Missing recovery native function: '+name)
    return m[0]
def bounded(text,tag):
    return re.search(r'/\* MISHARE_RECOVERY_BEGIN:'+tag+r' \*/\n(.*?)/\* MISHARE_RECOVERY_END:'+tag+r' \*/',text,re.S)[1]
def fixture(root):
    for p,h in BASE.items():
        if hashlib.sha256(remove_recovery_additions((root/p).read_text()).encode()).hexdigest()!=h:raise ValueError('Unbounded recovery delta: '+p)
    cds=(root/CDS).read_text();post=function(cds,'cds_post_disable');close=function(cds,'cds_close')
    assert post.index('htc_stop(')<post.index('cds_close_rx_thread()')<post.index('mishare_cds_recovery_window(')<post.index('cdp_pdev_pre_detach(')
    assert close.index('mishare_runtime_recovery_close(')<close.index('dispatcher_psoc_close(')
    dp=(root/DP).read_text();native=function(dp,'dp_vdev_unref_delete');assert native.index('qdf_mem_common_free(vdev);')<native.index('vdev_delete_cb(vdev_delete_context);')
    src=work.fixture(root);a=src.index('/* RECOVERY_TRANSPORT_STUBS */');b=src.index('/* END_RECOVERY_TRANSPORT_STUBS */',a)+len('/* END_RECOVERY_TRANSPORT_STUBS */');src=src[:a]+src[b:]
    src=src.replace('struct wmi_unified {int dummy;};','struct wmi_unified {int dummy,wmi_stopinprogress,wmi_rx_work_queue,wmi_rx_diag_work_queue,eventq_lock,diag_eventq_lock;unsigned event_queue,diag_event_queue;};',1)
    src=src.replace('struct vdev_response_timer {int expire_time,timer_status;};','struct vdev_response_timer {int expire_time,timer_status,rsp_timer,rsp_timer_inuse;unsigned long rsp_status;struct wlan_objmgr_psoc *psoc;u8 vdev_id;struct {bool is_lock_acquired;int vdev_cmd_rt_lock;} rt_lock;};',1)
    needle='assert(!timers_live);timers_live++;';assert src.count(needle)==1;src=src.replace(needle,needle+'response_timer.psoc=p;response_timer.vdev_id=id;response_timer.rsp_timer=1;response_timer.rsp_timer_inuse=1;response_timer.rsp_status=0;response_timer.rt_lock.is_lock_acquired=false;response_timer.rt_lock.vdev_cmd_rt_lock=1;',1)
    replacements={'NATIVE_PREPARED_TIMER':function((root/TIMER).read_text(),'mishare_ndi_reset_prepared_timer_deinit'),'NATIVE_RESET_CHECK':function((root/work.shutdown.radio.plan.channel.pe.ctx.WMA).read_text(),'mishare_ndi_reset_context_check'),'NATIVE_RESET_CONTEXT':function((root/work.shutdown.radio.plan.channel.pe.ctx.WMA).read_text(),'mishare_ndi_reset_context_release'),'NATIVE_WMI_REMOVE':function((root/WMI).read_text(),'wmi_unified_remove_work'),'NATIVE_WMI_STOP':function((root/WMI).read_text(),'wmi_stop'),'NATIVE_WMI_BLOCKED':function((root/WMI).read_text(),'wmi_is_blocked'),'NATIVE_WMA_STOP':function((root/WMA).read_text(),'wma_wmi_stop'),'NATIVE_WMA_WORK_CLOSE':function((root/WMA).read_text(),'wma_wmi_work_close'),'NATIVE_CDS_HELPER':bounded(cds,'cds_helper').replace('#include "wmi_unified_api.h"\n',''),'NATIVE_CDS_POST':post,'NATIVE_CDS_CLOSE':bounded(cds,'cds_close'),'NATIVE_TIMER_DEINIT':function((root/TIMER).read_text(),'target_if_psoc_vdev_rsp_timer_deinit'),'NATIVE_TIMER_HELPER':function((root/TIMER).read_text(),'mishare_ndi_recovery_timer_deinit'),'NATIVE_DP_HELPER':function((root/DISP).read_text(),'mishare_ndi_recovery_dp_detach')}
    model=MODELS
    for k,v in replacements.items():model=model.replace(k,v)
    return src[:src.index('int main(void) {')]+model+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=work.shutdown.radio.plan.channel.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'recovery.c').write_text(source);exe=d/'recovery'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'recovery.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_EARLY_NDI_RESET_RECLAIM_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    names=['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']
    return {'status':out.strip(),'source_commit':work.shutdown.radio.plan.channel.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [CDS,TIMER,DISP,WMI,WMA,DP]},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},'ordinary_before_recovery_sha256':BASE,'checks':['complete native cds_post_disable orders MC/ISR/HIF/HTC/RX before qualified window','native WMI stop/blocked/work_close/remove_work flush both independent event queues before window open','native timer sync cancellation plus complete deinit validates exact owner and inactive response/PM state','attach-time DP soc cookie must match exact live parent before native detach wrapper','actual DP final-free callback required; no DELETE submission/reply flags fabricated','inline and delayed DP callbacks require submit return before native host deletion','deferred object final-free keeps original wire history, quarantine and owner until real notification','CDS close irrevocably closes window; late DP callback cannot reopen or delete native host','context/peer/PE/plan/history/partial attach and failure cases remain isolated'],'limitations':'Executes production recovery controller, full native CDS post-disable and WMI stop/work-flush functions, full native timer deinit, owned DP wrapper and object-manager final-free under ASan/UBSan. HIF/HTC reset/stop, QDF scheduler/thread/IRQ/timer/workqueue primitives, DP detach/storage free and component destructors remain models. Real DP callback source ordering is audited, not the full DP detach executed. Target reset status is a native-driver qualification, not physical firmware acceptance. No automatic recovery caller is enabled; caller must retain exact parents and prevent CDS destruction across polls. Prepared/STARTed NDI, WMA/peer/PE/PM recovery, active-owner unload, psoc reuse and phone operation remain unverified.'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
