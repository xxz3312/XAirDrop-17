#!/usr/bin/env python3
"""Actions-only owned START planning and actual native parameter-builder fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_channel_fixture as channel
from mishare_firmware_fixture import CORE, function
ROOT=channel.ROOT
WMA=channel.pe.ctx.WMA
API=channel.API
BASE={'qca-wifi-host-cmn/umac/mlme/vdev_mgr/core/src/vdev_mgr_ops.c': 'bac42c7a0839f2bab80329a70beeac14fc3d090ada87ce00a5c3be499a0a7fd3', 'qcacld-3.0/core/wma/src/wma_dev_if.c': '3f197045d42f27c5c165bd2e56c2ccc122ba1bb989536d5d06bdeb108e473028', 'qcacld-3.0/core/mac/src/pe/lim/lim_api.c': '96cafddb540845d75e576e2f1c10d8662b09d705a18b7622036ee46651785f07'}

STUBS=r'''
#define MOBILE_DFS_SUPPORT 1
#define WLAN_FEATURE_11BE_MLO 1
#define WLAN_PEER_SELF 1
#define WLAN_MLME_SB_ID 9
#define WLAN_VDEV_MLME_TYPE_AP 1
#define WMI_HOST_MODE_11NG_HT20 5
#define WMI_HOST_MODE_11NA_HT20 4
enum QDF_OPMODE {QDF_STA_MODE=1,QDF_SAP_MODE=2,QDF_P2P_GO_MODE=3};
struct wlan_ssid {u8 ssid[32],length;};
struct mlme_channel_param {uint32_t mhz,cfreq1,cfreq2,chan_id,pwr,phy_mode,maxpower,minpower,maxregpower,regpower,antennamax,reg_class_id;bool dfs_set,dfs_set_cfreq2,is_stadfs_en,is_chan_passive,allow_ht,allow_vht,half_rate,quarter_rate;};
struct vdev_start_params {u8 vdev_id;uint32_t beacon_interval,dtim_period,disable_hw_ack,preferred_rx_streams,preferred_tx_streams,regdomain,he_ops,bcn_tx_rate_code,ldpc_rx_enabled,mbssid_flags,mbssid_multi_group_flag,mbssid_multi_group_id,vdevid_trans,cac_duration_ms;bool is_restart,hidden_ssid;struct mlme_channel_param channel;struct wlan_ssid ssid;struct {bool mlo_enabled;} mlo_flags;};
static bool plan_pdev_fail,plan_bad_output,plan_mlo,plan_wrong_peer_type;
static unsigned plan_pdev_refs,plan_builds;
static int wlan_peer_get_peer_type(struct wlan_objmgr_peer *p) {assert(p==&ctx_peer);return plan_wrong_peer_type?2:1;}
NATIVE_WMA_CHECK
static QDF_STATUS wlan_objmgr_pdev_try_get_ref(struct wlan_objmgr_pdev *p,int id) {assert(!lock_depth && p==&pdev && id==9);if(plan_pdev_fail)return QDF_STATUS_E_FAILURE;plan_pdev_refs++;return QDF_STATUS_SUCCESS;}
static void wlan_objmgr_pdev_release_ref(struct wlan_objmgr_pdev *p,int id) {assert(p==&pdev && id==9 && plan_pdev_refs==1);plan_pdev_refs--;}
static bool vdev_mgr_is_sta_max_phy_enabled(enum QDF_OPMODE mode,struct wlan_objmgr_pdev *p) {assert((int)mode==17 && p==&pdev);return false;}
static bool vdev_mgr_is_opmode_sap_or_p2p_go(enum QDF_OPMODE mode) {return mode==QDF_SAP_MODE || mode==QDF_P2P_GO_MODE;}
static bool vdev_mgr_is_49G_5G_chan_freq(uint16_t freq) {return freq>=4900;}
static void vdev_mgr_set_cur_chan_punc_bitmap(struct wlan_channel *d,uint16_t *p) {(void)d;(void)p;assert(0);}
static void tgt_dfs_set_current_channel_for_freq(struct wlan_objmgr_pdev *p,unsigned f,unsigned a,unsigned b,unsigned c,unsigned d,unsigned e,unsigned g,unsigned h,unsigned i,bool *updated) {(void)p;(void)f;(void)a;(void)b;(void)c;(void)d;(void)e;(void)g;(void)h;(void)i;(void)updated;assert(0);}
static bool utils_is_dfs_cfreq2_ch(struct wlan_objmgr_pdev *p) {(void)p;assert(0);return false;}
#define DFS_AGILE_SM_EV_AGILE_STOP 1
static void utils_dfs_agile_sm_deliver_evt(struct wlan_objmgr_pdev *p,int ev) {(void)p;(void)ev;assert(0);}
static bool tgt_dfs_is_stadfs_enabled(struct wlan_objmgr_pdev *p) {assert(p==&pdev);return false;}
static void wlan_reg_get_dfs_region(struct wlan_objmgr_pdev *p,uint32_t *r) {assert(p==&pdev);*r=1;}
static bool utils_is_dfs_chan_for_freq(struct wlan_objmgr_pdev *p,uint32_t f) {assert(p==&pdev && f);return false;}
static void vdev_mgr_start_param_update_11be(struct vdev_mlme_obj *m,struct vdev_start_params *p,struct wlan_channel *d) {assert(m && d && p);}
static void vdev_mgr_start_param_update_mlo(struct vdev_mlme_obj *m,struct vdev_start_params *p) {assert(m && p);p->mlo_flags.mlo_enabled=plan_mlo;}
static unsigned vdev_mgr_fetch_ratecode(struct vdev_mlme_obj *m) {assert(m);return 0;}
static void vdev_mgr_start_param_update_cac_ms(struct wlan_objmgr_vdev *v,struct vdev_start_params *p) {(void)v;(void)p;assert(0);}
static void wlan_vdev_mlme_get_ssid(struct wlan_objmgr_vdev *v,u8 *ssid,u8 *len) {assert(v && ssid);*len=0;plan_builds++;if(plan_bad_output)v->mlme->mgmt.generic.maxregpower++;}
#define mlme_err(...) ((void)0)
NATIVE_START_PARAM_UPDATE
NATIVE_START_PLAN_BUILD
#undef MOBILE_DFS_SUPPORT
#define mishare_ndi_start_plan_build mishare_ndi_start_plan_nonmobile
NATIVE_START_PLAN_BUILD
#undef mishare_ndi_start_plan_build
#define MOBILE_DFS_SUPPORT 1
#define cds_get_context pe_cds_get_context
#define qdf_mem_free pe_qdf_mem_free
NATIVE_START_PLAN_REQUEST
#undef qdf_mem_free
#undef cds_get_context
'''
HARNESS=r'''
static void reset_plan(void) {
 reset_channel();plan_pdev_fail=plan_bad_output=plan_mlo=plan_wrong_peer_type=false;plan_pdev_refs=plan_builds=0;
}
static struct mishare_runtime_owner *with_channel(uint32_t freq) {
 struct mishare_runtime_owner *o=with_session();last_vdev->mlme->proto.generic.nss_5g=2;
 assert(mishare_runtime_ndi_channel(o,freq)==-EINPROGRESS);run_pe(false);assert(state(o).ndi.channel_prepared);return o;
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_runtime_ndi_start_plan(NULL)==-EINVAL);
 assert(mishare_ndi_start_plan_nonmobile(NULL,0,NULL)==-EOPNOTSUPP && !plan_builds && !plan_pdev_refs);
 reset_plan();o=with_session();assert(mishare_runtime_ndi_start_plan(o)==-EBUSY && !pe_pending.bodyptr);channel_end(&o);
 for(int band=0;band<2;band++) {
  reset_plan();unsigned freq=band?5745:2437;o=with_channel(freq);int peer_creates=ctx_create_calls;
  assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS && !state(o).ndi.start_plan_completed && last_vdev->refs==6);
  assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !state(o).ndi.pe_delete_requested && !ctx_delete_calls);
  struct wlan_objmgr_psoc wrong={9};
  mishare_runtime_ndi_start_plan_event(&wrong,7,o,freq,0,NULL);
  mishare_runtime_ndi_start_plan_event(&psoc,8,o,freq,0,NULL);
  mishare_runtime_ndi_start_plan_event(&psoc,7,(void*)1,freq,0,NULL);
  assert(!state(o).ndi.blocked && !state(o).ndi.start_plan_completed);
  run_pe(false);struct mishare_ndi_status n=state(o).ndi;
  assert(n.start_plan_submitted && n.start_plan_completed && n.start_plan_ready && !n.blocked);
  assert(n.start_plan.freq==freq && n.start_plan.center_freq==freq && n.start_plan.phy_mode==(unsigned)(band?4:5));
  assert(n.start_plan.tx_streams==(unsigned)(band?2:1) && n.start_plan.rx_streams==n.start_plan.tx_streams);
  assert(plan_builds==1 && !plan_pdev_refs && ctx_create_calls==peer_creates && ch_prepares==2 && last_vdev->refs==5);
  assert(mishare_runtime_ndi_start_plan(o)==-EBUSY);channel_end(&o);
 }
 /* Host PHY enums must never be compared as firmware PHY mode values. */
 reset_plan();o=with_channel(2437);last_vdev->mlme->mgmt.generic.phy_mode=6;
 struct mishare_ndi_start_summary wrong_phy={0};
 assert(mishare_ndi_start_plan_build(last_vdev->mlme,2437,&wrong_phy)==-EUCLEAN && !plan_builds && !plan_pdev_refs);
 channel_end(&o);
 /* Posting is one-shot; queue/allocation/ref failure is proven before MC execution. */
 for(int fault=0;fault<4;fault++) {
  reset_plan();o=with_channel(2437);pe_alloc_fail=fault==0;pe_queue_fail=fault==1;
  if(fault==2)fail_ref_at=ref_calls+1;
  int ret=mishare_runtime_ndi_start_plan(o);
  if(fault<3)assert(ret<0 && ret!=-EINPROGRESS && !pe_pending.bodyptr);
  else {assert(ret==-EINPROGRESS);run_pe(true);}
  assert(state(o).ndi.start_plan_completed && !state(o).ndi.start_plan_ready && !state(o).ndi.blocked && !plan_builds && !plan_pdev_refs && last_vdev->refs==5);
  pe_alloc_fail=pe_queue_fail=false;channel_end(&o);
 }
 /* Re-check live regulatory/concurrency/capabilities; rejection cannot reuse an old plan. */
 for(int fault=0;fault<6;fault++) {
  reset_plan();o=with_channel(2437);ch_scan=fault==0;ch_connections=fault==1;ch_passive=fault==2;ch_dfs=fault==3;
  nan_cap=fault!=4;sync_cap=fault!=5;
  assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);run_pe(false);
  assert(state(o).ndi.start_plan_completed && !state(o).ndi.start_plan_ready && !state(o).ndi.blocked && !plan_builds && ch_prepares==1 && last_vdev->refs==5);
  ch_scan=ch_passive=ch_dfs=false;ch_connections=0;nan_cap=sync_cap=true;channel_end(&o);
 }
 reset_plan();o=with_channel(2437);pe_early=true;
 assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS && state(o).ndi.start_plan_submitted && state(o).ndi.start_plan_ready && !pe_pending.bodyptr);
 pe_early=false;channel_end(&o);
 /* Ambiguous native state/partial preparation must retain the complete owner. */
 for(int fault=0;fault<15;fault++) {
  reset_plan();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=with_channel(2437);
   plan_pdev_fail=fault==0;plan_bad_output=fault==1;plan_mlo=fault==2;plan_wrong_peer_type=fault==3;
   if(fault==4)ctx_peer.vdev=NULL;
   if(fault==5)wma_context.interfaces[7].peer_count=2;
   if(fault==6)wma_context.interfaces[7].bss_status=9;
   if(fault==7)pe_slot.mishare_owner=(void*)1;
   if(fault==8)ch_prepare_status=QDF_STATUS_E_FAILURE;
   if(fault==9)ch_bad_des=true;
   if(fault==13)wma_context.wmi_handle=NULL;
   if(fault==14)wma_context.interfaces=NULL;
   assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);
   if(fault==10)mishare_runtime_ndi_start_plan_event(&psoc,7,o,5745,0,NULL);
   if(fault==11)mishare_runtime_ndi_start_plan_event(&psoc,7,o,2437,0,NULL);
   run_pe(false);
   if(fault==12) {struct mishare_ndi_start_summary copy=state(o).ndi.start_plan;mishare_runtime_ndi_start_plan_event(&psoc,7,o,2437,0,&copy);}
   assert(state(o).ndi.blocked && mishare_runtime_destroy(&o)==-EUCLEAN && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls && !plan_pdev_refs && last_vdev->refs==5 && !pe_pending.bodyptr);
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_OWNED_START_PLAN_FIXTURE_PASS_ONLY");
}
'''


def fixture(root):
    for path,h in BASE.items():
        s=(root/path).read_text()
        s=re.sub(r'\n/\* MISHARE_BEGIN:start_plan_\w+ \*/\n.*?/\* MISHARE_END:start_plan_\w+ \*/\n','',s,flags=re.S)
        if hashlib.sha256(s.encode()).hexdigest()!=h:
            raise ValueError('START plan changed existing native source: '+path)
    param=(root/'qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h').read_text()
    for name,value in [('WMI_HOST_MODE_11NG_HT20',5),('WMI_HOST_MODE_11NA_HT20',4)]:
        if not re.search(r'\b'+name+r'\s*=\s*'+str(value)+r'\b',param):
            raise ValueError('Review changed firmware PHY mode: '+name)
    src=channel.fixture(root)
    src=src.replace('struct wma_txrx_node interfaces[32];','struct wma_txrx_node *interfaces;')
    src=src.replace('static struct wma wma_context;', 'static struct wma_txrx_node plan_interfaces[32];\nstatic struct wma wma_context;')
    src=src.replace('memset(&wma_context,0,sizeof(wma_context));', 'memset(plan_interfaces,0,sizeof(plan_interfaces));memset(&wma_context,0,sizeof(wma_context));wma_context.interfaces=plan_interfaces;')
    # Extend only platform layouts exercised by the real native builder.
    src=src.replace('struct wlan_channel {uint32_t ch_freq,ch_cfreq1,ch_cfreq2;int ch_width;};','struct wlan_channel {uint32_t ch_freq,ch_cfreq1,ch_cfreq2,ch_ieee,ch_flags,ch_flagext,ch_freq_seg1,ch_freq_seg2;int ch_width;};')
    src=src.replace('struct vdev_mlme_obj {', 'struct vdev_mlme_mbss_11ax {unsigned mbssid_flags,is_multi_mbssid,grp_id,vdevid_trans;};\nstruct vdev_mlme_obj {', 1)
    src=src.replace('struct { struct { u8 type,subtype; } generic; } mgmt; struct {struct {u8 nss_2g,nss_5g;} generic;} proto;',
        'struct { struct { u8 type,subtype;unsigned phy_mode,maxregpower,disable_hw_ack,tx_power,maxpower,minpower,antennamax,reg_class_id; } generic;struct {unsigned num_rx_chain,num_tx_chain;} chainmask_info;struct {bool half_rate,quarter_rate;} rate_info;struct vdev_mlme_mbss_11ax mbss_11ax;struct {bool hidden_ssid;} ap; } mgmt; struct {struct {u8 nss_2g,nss_5g;unsigned beacon_interval,dtim_period,ldpc;} generic;struct {bool allow_ht;} ht_info;struct {bool allow_vht;} vht_info;struct {unsigned he_ops;} he_ops_info;} proto;')
    src=src.replace('ch_prepares++;struct wlan_channel *d=',
        'o->proto.ht_info.allow_ht=true;o->proto.vht_info.allow_vht=false;o->mgmt.generic.maxregpower=s->maxTxPower;o->mgmt.generic.phy_mode=s->curr_op_freq<3000?5:4;o->mgmt.chainmask_info.num_rx_chain=s->nss;o->mgmt.chainmask_info.num_tx_chain=s->nss;ch_prepares++;struct wlan_channel *d=')
    start=src.index('/* START_PLAN_TRANSPORT_STUBS */');end=src.index('/* END_START_PLAN_TRANSPORT_STUBS */',start)+len('/* END_START_PLAN_TRANSPORT_STUBS */')
    src=src[:start]+src[end:]
    wma=channel.pe.ctx.block((root/WMA).read_text(),'start_plan_wma')
    builder=channel.pe.ctx.block((root/CORE).read_text(),'start_plan_builder').replace('#include <wmi_unified_param.h>\n','')
    request=channel.pe.ctx.block((root/API).read_text(),'start_plan_request')
    native_update=function((root/CORE).read_text(),'vdev_mgr_start_param_update')
    code=STUBS.replace('NATIVE_WMA_CHECK',wma).replace('NATIVE_START_PARAM_UPDATE',native_update).replace('NATIVE_START_PLAN_BUILD',builder).replace('NATIVE_START_PLAN_REQUEST',request)
    return src[:src.index('int main(void) {')]+code+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=channel.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h','qdf_status.h']:(d/n).write_text('/* platform model */\n')
        (d/'owner.c').write_text(source);exe=d/'owner'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'owner.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_OWNED_START_PLAN_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':channel.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in BASE},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},'ordinary_native_source_sha256':BASE,'checks':['actual complete target START parameter builder executes for owned PAS/NDI HT20','MC/flush VDEV reference and owner destruction ordering','fresh regulatory/scan/connection/capability checks before planning','existing exact self-peer validated without a second create','foreign peer/bad WMA slot/partial preparation quarantines','builder pdev reference failure/output drift/MLO rejection retains owner','post allocation/ref/queue rejection and early completion','duplicate/wrong frequency/missing summary matching reply quarantines','no target-if START/STOP/UP/DOWN, timer, PM or WMI call'],'limitations':'Production owner, native owned WMA checker, full native START parameter builder and owned MC/flush helpers execute. Native lim_pre_vdev_start, PE allocation/destruction, scheduler, regulatory/policy, WMI/DP/object primitives and MLO/11be subhelpers remain models. MOBILE_DFS_SUPPORT is selected and the native AP predicate is modeled for PAS; non-mobile configuration fails closed in production. No native MLME transition, radio command, hardware-mode lease, firmware acceptance, SSR/remove or runtime caller.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
