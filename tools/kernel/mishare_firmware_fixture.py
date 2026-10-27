#!/usr/bin/env python3
"""Actions-only owned CREATE/DP/DELETE code with mocked platform boundaries.

Executes actual native owned transport helpers, full real DELETE handler and
production owner. Parameter preparation, WMI, timer primitives, DP and object
construction are models; this is not firmware or driver-load certification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_runtime_fixture as host
from mishare_ndi_origins import DELETE_TIMEOUT_HOOK, DELETE_FW_HOOK, remove_owned_delete_hooks
from popsicle_backend_audit import PIN

CORE='qca-wifi-host-cmn/umac/mlme/vdev_mgr/core/src/vdev_mgr_ops.c'
DISP='qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/src/wlan_vdev_mgr_tgt_if_tx_api.c'
TX='qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_tx_ops.c'
RX='qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_rx_ops.c'
ROOT=Path(__file__).resolve().parents[2]


def function(text,name):
    m=re.search(r'(?:static\s+)?(?:int|QDF_STATUS)\s+'+name+r'\([^;{]+\)\s*\{.*?^\}',text,re.M|re.S)
    if not m:raise ValueError('Cannot extract native function: '+name)
    return m[0]

STUBS=r'''
#define QDF_IS_STATUS_ERROR(s) ((s)!=QDF_STATUS_SUCCESS)
#define QDF_IS_STATUS_SUCCESS(s) ((s)==QDF_STATUS_SUCCESS)
#define WMI_VDEV_TYPE_NDI 7
#define QDF_STATUS_E_NOSUPPORT 5
#define CDP_INVALID_VDEV_STATS_ID 255
#define wmi_service_nan_data 1
#define wmi_service_sync_delete_cmds 2
#define WLAN_SOC_F_TESTMODE_ENABLE 1
#define DELETE_RESPONSE_BIT 1
#define DELETE_WAKELOCK 1
#define mlme_err(...) ((void)0)
#define qdf_status_to_os_return(s) ((s)==QDF_STATUS_SUCCESS?0:-EIO)
struct vdev_create_params {u8 type,subtype,vdev_id,vdev_stats_id;};
struct vdev_delete_params {u8 vdev_id;};
struct cdp_vdev_info {u8 *vdev_mac_addr;u8 vdev_id,vdev_stats_id;int op_mode,subtype,qdf_opmode;};
struct wmi_unified {int dummy;};
struct vdev_delete_response {u8 vdev_id;};
struct vdev_response_timer {int unused;};
typedef void *ol_scn_t;
typedef void *ol_txrx_soc_handle;
static struct wmi_unified wmi;
static struct vdev_response_timer response_timer;
static bool nan_cap=true,sync_cap=true,testmode,missing_dp,missing_txops;
static QDF_STATUS prepare_status,timer_status,wire_status,dp_status,delete_status,dp_detach_status,stop_status;
static int wires,timer_inits,timers_live,dp_attaches,dp_objects,stats_live,stats_resets,wire_deletes,dp_detaches,pm_releases,legacy_responses;
static bool early_delete,early_dp,delete_timeout,extract_fail;
static void (*pending_dp_cb)(void *);static void *pending_dp_ctx;
static QDF_STATUS timer_init(struct wlan_objmgr_psoc *p,u8 id) {
 assert(!lock_depth && p && id==7);timer_inits++;
 if(timer_status==QDF_STATUS_SUCCESS){assert(!timers_live);timers_live++;}
 return timer_status;
}
static void timer_deinit(struct wlan_objmgr_psoc *p,u8 id) {assert(p && id==7);assert(timers_live==1);timers_live--;}
struct wlan_lmac_if_mlme_tx_ops {
 QDF_STATUS (*psoc_vdev_rsp_timer_init)(struct wlan_objmgr_psoc*,u8);
 void (*psoc_vdev_rsp_timer_deinit)(struct wlan_objmgr_psoc*,u8);
};
static struct wlan_lmac_if_mlme_tx_ops txops={timer_init,timer_deinit};
static struct wlan_lmac_if_mlme_tx_ops *wlan_mlme_get_lmac_tx_ops(struct wlan_objmgr_psoc *p) {assert(p);return missing_txops?NULL:&txops;}
static struct wmi_unified *target_if_vdev_mgr_wmi_handle_get(struct wlan_objmgr_vdev *v) {assert(v);return &wmi;}
static bool wmi_service_enabled(struct wmi_unified *w,int cap) {assert(w==&wmi);return cap==1?nan_cap:sync_cap;}
static bool wlan_psoc_nif_feat_cap_get(struct wlan_objmgr_psoc *p,int cap) {assert(p && cap==1);return testmode;}
static void *wlan_psoc_get_dp_handle(struct wlan_objmgr_psoc *p) {assert(p);return missing_dp?NULL:p;}
static u8 wlan_objmgr_pdev_get_pdev_id(struct wlan_objmgr_pdev *p) {assert(p);return 0;}
static int wlan_util_vdev_get_cdp_txrx_opmode(struct wlan_objmgr_vdev *v) {assert(v->mode==17);return 7;}
static int wlan_util_vdev_get_cdp_txrx_subtype(struct wlan_objmgr_vdev *v) {assert(v);return 0;}
static void wlan_vdev_mgr_fill_mlo_bridge_vap_params(struct cdp_vdev_info *i,struct wlan_objmgr_vdev *v) {assert(i && v);}
static void wlan_vdev_mgr_fill_mlo_params(struct cdp_vdev_info *i,struct vdev_create_params *p) {assert(i && p);}
static QDF_STATUS vdev_mgr_create_param_update(struct vdev_mlme_obj *m,struct vdev_create_params *p) {
 assert(!lock_depth && m && p);
 if(prepare_status!=QDF_STATUS_SUCCESS)return prepare_status;
 assert(!stats_live);stats_live++;
 *p=(struct vdev_create_params){.type=m->mgmt.generic.type,.subtype=m->mgmt.generic.subtype,.vdev_id=7,.vdev_stats_id=1};
 return QDF_STATUS_SUCCESS;
}
static void vdev_mgr_reset_vdev_stats_id(struct wlan_objmgr_vdev *v,u8 id) {assert(v && id==1 && stats_live==1);stats_live--;stats_resets++;}
static QDF_STATUS wmi_unified_vdev_create_send(struct wmi_unified *w,u8 *mac,struct vdev_create_params *p) {
 assert(!lock_depth && w==&wmi && mac && p->type==7 && p->vdev_id==7 && timers_live==1);wires++;return wire_status;
}
static QDF_STATUS cdp_vdev_attach(void *soc,u8 id,struct cdp_vdev_info *i) {
 assert(!lock_depth && soc && !id && i->vdev_id==7 && i->qdf_opmode==17 && wires==1 && stats_live==1);
 dp_attaches++;dp_objects++;return dp_status; /* failure models late publication */
}
static QDF_STATUS legacy_response(struct wlan_objmgr_psoc *p,struct vdev_delete_response *r) {assert(p && r);legacy_responses++;return QDF_STATUS_SUCCESS;}
static struct vdev_response_timer *get_response_timer(struct wlan_objmgr_psoc *p,u8 id) {assert(p && id==7);return &response_timer;}
struct wlan_lmac_if_mlme_rx_ops {
 QDF_STATUS (*vdev_mgr_delete_response)(struct wlan_objmgr_psoc*,struct vdev_delete_response*);
 struct vdev_response_timer *(*psoc_get_vdev_response_timer_info)(struct wlan_objmgr_psoc*,u8);
};
static struct wlan_lmac_if_mlme_rx_ops rxops={legacy_response,get_response_timer};
static struct wlan_objmgr_psoc *target_if_get_psoc_from_scn_hdl(ol_scn_t scn) {return scn;}
static struct wlan_lmac_if_mlme_rx_ops *target_if_vdev_mgr_get_rx_ops(struct wlan_objmgr_psoc *p) {assert(p);return &rxops;}
static struct wmi_unified *get_wmi_unified_hdl_from_psoc(struct wlan_objmgr_psoc *p) {assert(p);return &wmi;}
static int wmi_extract_vdev_delete_resp(struct wmi_unified *w,u8 *data,struct vdev_delete_response *r) {assert(w && data);r->vdev_id=*data;return extract_fail;}
static void target_if_release_vdev_cmd_rt_lock(struct wlan_objmgr_psoc *p,u8 id) {assert(p && id==7);}
static QDF_STATUS target_if_vdev_mgr_rsp_timer_stop(struct wlan_objmgr_psoc *p,struct vdev_response_timer *t,int bit) {
 assert(p && t==&response_timer && bit==1);
 if(stop_status==QDF_STATUS_SUCCESS)timer_deinit(p,7);
 return stop_status;
}
static void target_if_wake_lock_timeout_release(struct wlan_objmgr_psoc *p,int lock) {assert(p && lock==1 && !timers_live);pm_releases++;}
static void target_if_vdev_mgr_handle_recovery(struct wlan_objmgr_psoc *p,u8 id,int reason,int bit) {assert(p && id==7 && reason==1 && bit==1);}
static int target_if_vdev_mgr_delete_response_handler(ol_scn_t,u8*,uint32_t);
static void timeout_origin(struct wlan_objmgr_psoc *psoc,u8 vdev_id);
static QDF_STATUS target_if_vdev_mgr_delete_send(struct wlan_objmgr_vdev *v,struct vdev_delete_params *p) {
 assert(!lock_depth && v && p->vdev_id==7 && !dp_detaches && timers_live==1);wire_deletes++;
 if(early_delete){u8 id=7;assert(!target_if_vdev_mgr_delete_response_handler(wlan_vdev_get_psoc(v),&id,1));}
 if(delete_timeout){timer_deinit(wlan_vdev_get_psoc(v),7);timeout_origin(wlan_vdev_get_psoc(v),7);}
 return delete_status;
}
static void finish_dp(void) {
 assert(pending_dp_cb && dp_objects==1);dp_objects--;void (*cb)(void*)=pending_dp_cb;void *c=pending_dp_ctx;pending_dp_cb=NULL;pending_dp_ctx=NULL;cb(c);
}
static QDF_STATUS cdp_vdev_detach(void *soc,u8 id,void (*cb)(void*),void *c) {
 assert(!lock_depth && soc && id==7 && cb && c && dp_objects==1 && !timers_live);dp_detaches++;
 if(dp_detach_status!=QDF_STATUS_SUCCESS)return dp_detach_status;
 assert(stats_live==1);stats_live--;stats_resets++;
 pending_dp_cb=cb;pending_dp_ctx=c;if(early_dp)finish_dp();return QDF_STATUS_SUCCESS;
}
NATIVE_FUNCTIONS
'''
HARNESS=r'''
static void reset_transport(void) {
 reset();assert(!timers_live && !dp_objects && !stats_live && !pending_dp_cb);
 prepare_status=timer_status=wire_status=dp_status=delete_status=dp_detach_status=stop_status=QDF_STATUS_SUCCESS;
 wires=timer_inits=dp_attaches=stats_resets=wire_deletes=dp_detaches=pm_releases=legacy_responses=0;
 early_delete=early_dp=delete_timeout=extract_fail=missing_dp=missing_txops=testmode=false;nan_cap=sync_cap=true;
}
static void reply(void) {u8 id=7;assert(!target_if_vdev_mgr_delete_response_handler(&psoc,&id,1));}
static void healthy_end(struct mishare_runtime_owner **o) {
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && wire_deletes==1 && !dp_detaches && !delete_calls);
 reply();assert(state(*o).ndi.delete_replied && pm_releases==1 && !legacy_responses && !timers_live);
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && dp_detaches==1 && !delete_calls);
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && dp_detaches==1 && !delete_calls);
 finish_dp();assert(!mishare_runtime_destroy(o) && !*o && !objects_live && !allocations && !stats_live && !dp_objects);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_runtime_ndi_create(NULL,1,1)==-EINVAL);
 reset_transport();assert(!timer_init(&psoc,7));reply();assert(legacy_responses==1 && pm_releases==1);

 /* Capability/missing context/prepare/timer failures must never issue CREATE. */
 for(int fault=0;fault<7;fault++) {
  reset_transport();assert(!create(&o));
  switch(fault){case 0:nan_cap=false;break;case 1:sync_cap=false;break;case 2:testmode=true;break;case 3:missing_txops=true;break;case 4:missing_dp=true;break;case 5:prepare_status=QDF_STATUS_E_FAILURE;break;case 6:timer_status=QDF_STATUS_E_FAILURE;break;}
  assert(mishare_runtime_ndi_create(o,1,1)<0 && !wires && !state(o).ndi.active && !stats_live && !timers_live);
  assert(last_vdev->mlme->mgmt.generic.type==9 && !last_vdev->mlme->proto.generic.nss_2g);
  assert(!mishare_runtime_destroy(&o) && !o && !objects_live && !allocations);
 }
 reset_transport();assert(!create(&o));
 assert(mishare_runtime_ndi_create(o,0,1)==-EINVAL && mishare_runtime_ndi_create(o,1,3)==-EINVAL && !wires);
 assert(!mishare_runtime_ndi_create(o,1,2) && wires==1 && dp_attaches==1 && state(o).ndi.active && state(o).ndi.create.dp_attached);
 assert(mishare_runtime_ndi_create(o,1,1)==-EBUSY && wires==1);
 struct wlan_objmgr_psoc other_psoc={2};
 assert(!mishare_runtime_ndi_delete_owned(&other_psoc,7) && !mishare_runtime_ndi_delete_owned(&psoc,8));
 mishare_runtime_ndi_delete_event(&other_psoc,7,true);assert(!state(o).ndi.delete_replied);
 healthy_end(&o);
 /* A rejected native timer gate/extract error cannot acknowledge DELETE. */
 reset_transport();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);
 u8 id=7;stop_status=QDF_STATUS_E_FAILURE;
 assert(target_if_vdev_mgr_delete_response_handler(&psoc,&id,1)<0 && !state(o).ndi.delete_replied && !dp_detaches);
 stop_status=QDF_STATUS_SUCCESS;extract_fail=true;
 assert(target_if_vdev_mgr_delete_response_handler(&psoc,&id,1)<0 && !state(o).ndi.delete_replied);
 extract_fail=false;reply();assert(mishare_runtime_destroy(&o)==-EINPROGRESS);finish_dp();assert(!mishare_runtime_destroy(&o));
 /* Early responses and inline DP callbacks still need submit return + polling. */
 reset_transport();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));early_delete=early_dp=true;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && state(o).ndi.delete_replied && !delete_calls);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && state(o).ndi.dp_freed && !delete_calls);
 assert(!mishare_runtime_destroy(&o) && !o && !objects_live && !allocations);
 /* DP completion is insufficient while another object-manager ref remains. */
 reset_transport();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);reply();
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);finish_dp();
 struct wlan_objmgr_vdev *held=last_vdev;held->refs++;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && o && !state(o).ndi.active && held->dead);
 wlan_objmgr_vdev_release_ref(held,2);assert(!mishare_runtime_destroy(&o) && !o);
 /* Unknown wire/late-DP/delete/timeout/DP-detach faults retain resources. Child
  * isolation intentionally ends retained resources without a fake recovery API. */
 for(int fault=0;fault<7;fault++) {
  reset_transport();pid_t child=fork();assert(child>=0);
  if(!child) {
   assert(!create(&o));
   if(fault==0)wire_status=QDF_STATUS_E_FAILURE;
   if(fault==1)dp_status=QDF_STATUS_E_FAILURE;
   int ret=mishare_runtime_ndi_create(o,1,1);
   if(fault==0){assert(ret==-EUCLEAN && state(o).ndi.blocked);}
   else if(fault==1){assert(ret<0 && !state(o).ndi.blocked);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);reply();}
   else {assert(!ret);if(fault==2)delete_status=QDF_STATUS_E_FAILURE;
    if(fault==3)delete_timeout=true;
    if(fault==4)dp_detach_status=QDF_STATUS_E_FAILURE;
    if(fault==5){mishare_runtime_ndi_delete_event(&psoc,7,true);}
    if(fault==6){memset(last_vdev->vdev_comp_priv_obj,0,sizeof(last_vdev->vdev_comp_priv_obj));assert(!mishare_runtime_prepare_free(last_vdev,&(unsigned long){0}));}
    if(fault==2 || fault==3)assert(mishare_runtime_destroy(&o)==-EUCLEAN);
    if(fault==4){assert(mishare_runtime_destroy(&o)==-EINPROGRESS);reply();assert(mishare_runtime_destroy(&o)==-EUCLEAN);}
   }
   assert(mishare_runtime_destroy(&o)==-EUCLEAN && o && !delete_calls && objects_live==1 && allocations==2 && last_vdev->refs==3);
   assert(mishare_runtime_ndi_create(o,1,1)==-EUCLEAN);
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 assert(!objects_live && !allocations && !timers_live && !dp_objects && !stats_live);
 puts("MISHARE_OWNED_NDI_RESOURCE_FIXTURE_PASS_ONLY");
}
'''


def fixture(root):
    rx=(root/RX).read_text();remove_owned_delete_hooks(rx)
    dp=(root/'qca-wifi-host-cmn/dp/wifi3.0/dp_main.c').read_text()
    start=dp.index('void dp_vdev_unref_delete(');end=dp.index('\n}'+ '\n',start)
    dp_free=dp[start:end]
    if dp_free.index('qdf_mem_common_free(vdev);')>dp_free.index('vdev_delete_cb(vdev_delete_context);'):
        raise ValueError('DP callback occurs before storage free')
    if rx.index('target_if_wake_lock_timeout_release',rx.index(DELETE_FW_HOOK))>rx.index('mishare_runtime_ndi_delete_event',rx.index(DELETE_FW_HOOK)):
        raise ValueError('Owned DELETE published before PM cleanup')
    funcs=''
    for path,names in [(CORE,['mishare_ndi_native_create','mishare_ndi_release_stats']),
                       (DISP,['mishare_ndi_tgt_create','mishare_ndi_native_dp_detach']),
                       (TX,['mishare_ndi_wire_create','mishare_ndi_native_delete']),
                       (RX,['target_if_vdev_mgr_delete_response_handler'])]:
        for name in names:funcs+='\n'+function((root/path).read_text(),name)+'\n'
    funcs+='\nstatic void timeout_origin(struct wlan_objmgr_psoc *psoc,u8 vdev_id) {\nint recovery_reason=1,rsp_pos=1;\n'+DELETE_TIMEOUT_HOOK+'}\n'
    # Reuse actual owner/event/transaction and native object final-free harness.
    source=host.fixture(root)
    marker='/* NDI_TRANSPORT_STUBS:';start=source.index(marker);end=source.index('/* END_NDI_TRANSPORT_STUBS */',start)+len('/* END_NDI_TRANSPORT_STUBS */')
    source=source[:start]+STUBS.replace('NATIVE_FUNCTIONS',funcs)+source[end:]
    prefix=host.HARNESS[:host.HARNESS.index('int main(void)')]
    return source.replace(host.HARNESS,prefix+HARNESS)


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected source revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h','qdf_status.h']:(d/n).write_text('/* model boundary */\n')
        (d/'owner.c').write_text(source);exe=d/'owner'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'owner.c'),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if output.strip()!='MISHARE_OWNED_NDI_RESOURCE_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':output.strip(),'source_commit':PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in [CORE,DISP,TX,RX,'qca-wifi-host-cmn/dp/wifi3.0/dp_main.c']},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'checks':['capability/context/prepare/timer failure cannot submit CREATE','response timer initialized before wire CREATE','stats retained after ambiguous CREATE or late DP error','one CREATE per owned vdev','real full DELETE handler suppresses ordinary SME/WMA completion only for owner','wrong psoc/ID exclusion and extraction/timer rejection','no DP teardown or object delete before real DELETE','DP callback/final-free and delayed object references retain owner','early real DELETE and inline DP callback wait for native return','wire ambiguity/partial DP/delete error/timeout/DP detach error retain all owner resources','unexpected response and active-resource final-free veto quarantine'],
            'limitations':'Actual production owner/event/transaction plus extracted owned native helpers and full DELETE handler. Native parameter preparation, WMI, timer/PM primitives, DP attach/detach/callback and object construction are modeled. Actual DP final-free function is not executed; callback placement is source checked. Quarantine children intentionally retain resources until process exit; no production recovery API is certified. No firmware acceptance, scheduler/IRQ concurrency, START/self-peer/legacy preparation, SSR/remove, module load or radio validation. No runtime backend caller.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
