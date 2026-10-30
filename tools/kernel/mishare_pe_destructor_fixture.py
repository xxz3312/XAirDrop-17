#!/usr/bin/env python3
"""Actions-only native PAS PE destructor under the production owner lifecycle.

Full PE allocation, cleanup callees and kernel timers remain explicit models.
This does not authorize PE destruction after MC shutdown or enable SSR recovery.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import mishare_session_fixture as pe
from mishare_recovery_fixture import function

ROOT = pe.ROOT
UTILS = 'qcacld-3.0/core/mac/src/pe/lim/lim_utils.c'
FIELDS = r'''
struct sDphHashNode {unsigned payload;};
typedef void *tpSirAssocReq;
typedef struct {struct {void *gtk,*igtk;} sha384_ft_subelem;} *tpSirAssocRsp;
typedef struct {unsigned sessionId;bool running;} TX_TIMER;
struct pe_timeout_config {struct {unsigned auth_failure_timeout;} timeouts;};
typedef u8 tSirMacAddr[6];
enum bss_type {eSIR_INFRASTRUCTURE_MODE=1,eSIR_INFRA_AP_MODE=2};
struct mgmt_beacon_probe_filter {unsigned num_sta_sessions,num_sap_sessions;tSirMacAddr sta_bssid[32];unsigned sap_channel[32];};
'''
SESSION_FIELDS = r'''
unsigned peSessionId,vdev_id,opmode,defaultAuthFailureTimeout;
unsigned bcnLen,assocReqLen,assocRspLen,user_edca_set,dfsIncludeChanSwIe;
int ap_ecsa_runtime_lock,ap_ecsa_wakelock,protection_fields_reset_timer,ap_ecsa_timer,pmf_retry_timer;
struct {bool retried;} pmf_retry_timer_info;
struct {struct {void *pHashTable;struct sDphHashNode *pDphNodeArray;unsigned size;} dphHashTable;} dph;
void *pLimStartBssReq,*lim_join_req,*pLimReAssocReq,*pLimMlmJoinReq;
void *beacon,*assoc_req,*assocRsp,**parsedAssocReq,*limAssocResponseData;
void *pLimMlmReassocRetryReq,*pLimMlmReassocReq,*pSchProbeRspTemplate;
void *pSchBeaconFrameBegin,*pSchBeaconFrameEnd,*access_policy_vendor_ie,*mac_ctx,*model_idxpool;
struct {void *probeRespData_buff,*assocRespData_buff,*probeRespBCNData_buff;
unsigned probeRespDataLen,assocRespDataLen,probeRespBCNDataLen;} add_ie_params;
'''
MODELS = r'''
#define pe_debug(...) ((void)0)
#define pe_err(...) ((void)0)
#define CFG_AUTH_FAILURE_TIMEOUT 1
#define QDF_STA_MODE 0
#define QDF_P2P_CLIENT_MODE 3
#define WLAN_MAX_VDEVS 32
#define QDF_TIMER_STATE_RUNNING 1
#define LIM_IS_AP_ROLE(s) ((s)->limSystemRole == 99)
#define INVALID_CHANNEL_NUM 0
struct scan_mbssid_info {unsigned unused;};
static void *pe_heap[64];
static unsigned pe_heap_live,pe_heap_frees,pe_cleanup_calls,pe_mbssid_calls,pe_timer_stops;
static bool pe_heap_release_probe;
static struct sDphHashNode pe_nodes[33];
static void *pe_heap_alloc(size_t size) {
 assert(pe_heap_live<64);void *p=calloc(1,size);assert(p);
 for(unsigned i=0;i<64;i++)if(!pe_heap[i]) {pe_heap[i]=p;pe_heap_live++;return p;}
 abort();
}
static void pe_heap_free(void *p) {
 if(!p)return;
 for(unsigned i=0;i<64;i++)if(pe_heap[i]==p) {pe_heap[i]=NULL;pe_heap_live--;pe_heap_frees++;free(p);return;}
 assert(!"FOREIGN_OR_DOUBLE_PE_FREE");
}
static bool cfg_in_range(int cfg,unsigned n) {assert(cfg==1);return n<=100;}
static unsigned cfg_default(int cfg) {assert(cfg==1);return 50;}
static bool tx_timer_running(TX_TIMER *t) {return t->running;}
static void tx_timer_deactivate(TX_TIMER *t) {assert(t->running);t->running=false;pe_timer_stops++;}
static void lim_sae_auth_cleanup_retry(struct mac_context *m,unsigned id) {assert(m==&pe_mac && id==7);pe_cleanup_calls++;}
static struct pe_session *lim_get_concurrent_session(struct mac_context *m,unsigned id,unsigned mode) {(void)m;(void)id;(void)mode;assert(!"OTHER_SESSION_LOOKUP_ON_PAS");return NULL;}
static void wlan_set_tpc_update_required_for_sta(struct wlan_objmgr_vdev *v,bool b) {(void)v;(void)b;assert(!"OTHER_SESSION_TPC_WRITE_ON_PAS");}
static void mlme_set_mbssid_info(struct wlan_objmgr_vdev *v,struct scan_mbssid_info *info,unsigned chan) {assert(v==last_vdev && info && !chan && v->mlme->ext_vdev_ptr);pe_mbssid_calls++;}
static void lim_ft_cleanup(struct mac_context *m,struct pe_session *s) {assert(m==&pe_mac && s==&pe_slot);pe_cleanup_calls++;}
static void lim_free_peer_idxpool(struct pe_session *s) {pe_heap_free(s->model_idxpool);s->model_idxpool=NULL;}
static void lim_free_assoc_req_frm_buf(tpSirAssocReq p) {assert(p);pe_cleanup_calls++;}
static void pe_delete_fils_info(struct pe_session *s) {assert(s==&pe_slot);pe_cleanup_calls++;}
/* AP and STA-only primitives must never execute for the owned PAS role. */
static void pe_only_runtime_lock_deinit(int *p) {(void)p;assert(!"AP_CLEANUP_ON_PAS");}
static void pe_only_wake_lock_destroy(int *p) {(void)p;assert(!"AP_CLEANUP_ON_PAS");}
static void pe_only_mc_timer_stop(int *p) {(void)p;assert(!"AP_STA_TIMER_ON_PAS");}
static void pe_only_mc_timer_destroy(int *p) {(void)p;assert(!"AP_STA_TIMER_ON_PAS");}
static int qdf_mc_timer_get_current_state(int *p) {(void)p;assert(!"STA_TIMER_ON_PAS");return 0;}
static void lim_del_pmf_sa_query_timer(struct mac_context *m,struct pe_session *s) {(void)m;(void)s;assert(0);}
static void lim_post_csa_ocv_sa_query_timer_destroy(struct pe_session *s) {(void)s;assert(0);}
static void lim_check_and_reset_protection_params(struct mac_context *m) {(void)m;assert(0);}
static void wlan_set_sap_user_config_freq(struct wlan_objmgr_vdev *v,unsigned f) {(void)v;(void)f;assert(0);}
static void pe_native_release_ref(struct wlan_objmgr_vdev *v,int id) {
 assert(id==4 && v==last_vdev && !pe_slot.valid && !pe_slot.vdev && !pe_slot.mac_ctx);
 assert(!pe_heap_live && !pe_slot.dph.dphHashTable.pHashTable && !pe_slot.dph.dphHashTable.pDphNodeArray);
 assert(!pe_slot.model_idxpool && !pe_slot.access_policy_vendor_ie);
 pe_heap_release_probe=true;wlan_objmgr_vdev_release_ref(v,id);
}
#define qdf_runtime_lock_deinit pe_only_runtime_lock_deinit
#define qdf_wake_lock_destroy pe_only_wake_lock_destroy
#define qdf_mc_timer_stop pe_only_mc_timer_stop
#define qdf_mc_timer_destroy pe_only_mc_timer_destroy
NATIVE_MBSSID
NATIVE_PMF
NATIVE_FILTER
NATIVE_POWER
#define qdf_mem_free pe_heap_free
#define wlan_objmgr_vdev_release_ref pe_native_release_ref
NATIVE_DELETE
#undef wlan_objmgr_vdev_release_ref
#undef qdf_mem_free
#undef qdf_runtime_lock_deinit
#undef qdf_wake_lock_destroy
#undef qdf_mc_timer_stop
#undef qdf_mc_timer_destroy
static void pe_delete_session(struct mac_context *m,struct pe_session *s) {
 assert(!lock_depth && m==&pe_mac && s==&pe_slot && s->valid && s->vdev==last_vdev);pe_deletes++;
 pe_heap_release_probe=false;native_pe_delete_session(m,s);assert(pe_heap_release_probe);
}
'''
HARNESS = r'''
static void fill_pe_allocations(void) {
 assert(!pe_heap_live && pe_slot.valid && pe_slot.vdev==last_vdev);
 pe_slot.mac_ctx=&pe_mac;pe_slot.opmode=QDF_PASSTHRU_MODE;pe_slot.vdev_id=7;
 pe_slot.peSessionId=0;pe_slot.defaultAuthFailureTimeout=60;pe_slot.user_edca_set=1;
 pe_slot.dph.dphHashTable.pHashTable=pe_heap_alloc(16);
 memset(pe_nodes,0x5a,sizeof(pe_nodes));pe_slot.dph.dphHashTable.pDphNodeArray=pe_nodes;pe_slot.dph.dphHashTable.size=3;
 pe_slot.model_idxpool=pe_heap_alloc(8);
 void **fields[]={&pe_slot.pLimStartBssReq,&pe_slot.lim_join_req,&pe_slot.pLimReAssocReq,&pe_slot.pLimMlmJoinReq,
 &pe_slot.beacon,&pe_slot.assoc_req,&pe_slot.assocRsp,&pe_slot.pLimMlmReassocRetryReq,&pe_slot.pLimMlmReassocReq,
 &pe_slot.pSchProbeRspTemplate,&pe_slot.pSchBeaconFrameBegin,&pe_slot.pSchBeaconFrameEnd,&pe_slot.access_policy_vendor_ie,
 &pe_slot.add_ie_params.probeRespData_buff,&pe_slot.add_ie_params.assocRespData_buff,&pe_slot.add_ie_params.probeRespBCNData_buff};
 for(unsigned i=0;i<sizeof(fields)/sizeof(*fields);i++)*fields[i]=pe_heap_alloc(8);
 pe_slot.parsedAssocReq=pe_heap_alloc(3*sizeof(void*));pe_slot.parsedAssocReq[0]=pe_heap_alloc(8);pe_slot.parsedAssocReq[2]=pe_heap_alloc(8);
 tpSirAssocRsp rsp=pe_heap_alloc(sizeof(*rsp));rsp->sha384_ft_subelem.gtk=pe_heap_alloc(8);rsp->sha384_ft_subelem.igtk=pe_heap_alloc(8);pe_slot.limAssocResponseData=rsp;
 pe_slot.bcnLen=pe_slot.assocReqLen=pe_slot.assocRspLen=5;
 pe_slot.add_ie_params.probeRespDataLen=pe_slot.add_ie_params.assocRespDataLen=pe_slot.add_ie_params.probeRespBCNDataLen=5;
}
int main(void) {
 /* All existing production owner/queue/flush/foreign-cookie regressions now
  * execute the extracted native destructor instead of the three-line stub. */
 assert(!owned_pe_regressions() && !pe_heap_live);
 for(unsigned timeout=0;timeout<3;timeout++) {
  reset_pe();struct mishare_runtime_owner *o=prepared();
  assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);run_pe(false);
  fill_pe_allocations();pe_slot.defaultAuthFailureTimeout=timeout==0?0:timeout==1?60:101;
  TX_TIMER timers[3]={{.sessionId=0,.running=true},{.sessionId=1,.running=true},{.sessionId=0,.running=false}};
  memset(&pe_mac.bcn_filter,0x5a,sizeof(pe_mac.bcn_filter));
  struct mgmt_beacon_probe_filter saved_filter=pe_mac.bcn_filter;
  pe_mac.lim.maxStation=2;pe_mac.lim.lim_timers.gpLimCnfWaitTimer=timers;
  unsigned live=pe_heap_live,frees=pe_heap_frees,refs=last_vdev->refs,stops=pe_timer_stops;
  assert(mishare_runtime_destroy(&o)==-EINPROGRESS && pe_pending.bodyptr && pe_heap_live==live);
  run_pe(false);
  assert(!pe_heap_live && pe_heap_frees-frees==live && !pe_slot.valid && !pe_slot.vdev && !pe_slot.mac_ctx);
  assert(last_vdev->refs==(int)refs-1 && pe_timer_stops==stops+1 && !timers[0].running && timers[1].running);
  assert(!memcmp(&saved_filter,&pe_mac.bcn_filter,sizeof(saved_filter)));
  assert(!pe_slot.bcnLen && !pe_slot.assocReqLen && !pe_slot.assocRspLen && !pe_slot.user_edca_set);
  assert(!pe_slot.add_ie_params.probeRespDataLen && !pe_slot.add_ie_params.assocRespDataLen && !pe_slot.add_ie_params.probeRespBCNDataLen);
  for(unsigned i=0;i<33;i++)assert(!pe_nodes[i].payload);
  assert(pe_mac.mlme_cfg->timeouts.auth_failure_timeout==(timeout==0?0:timeout==1?60:50));
  unsigned cleanup=pe_cleanup_calls,mbssid=pe_mbssid_calls;
  native_pe_delete_session(&pe_mac,&pe_slot);native_pe_delete_session(&pe_mac,NULL);
  assert(pe_cleanup_calls==cleanup && pe_mbssid_calls==mbssid && pe_heap_frees-frees==live);
  context_end(&o);assert(!o && !allocations && !objects_live && !pe_heap_live);
 }
 puts("MISHARE_NATIVE_PAS_PE_DESTRUCTOR_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    native = (root/pe.SESSION).read_text()
    src = pe.fixture(root)
    src = src.replace('struct pe_session {', FIELDS+'\nstruct pe_session {'+SESSION_FIELDS, 1)
    src = src.replace('struct mac_context {', 'struct mac_context {struct mgmt_beacon_probe_filter bcn_filter;struct pe_timeout_config *mlme_cfg;', 1)
    src = src.replace('unsigned maxBssId,max_sta_of_pe_session;', 'unsigned maxBssId,max_sta_of_pe_session,maxStation;struct {TX_TIMER *gpLimCnfWaitTimer;} lim_timers;', 1)
    old = function(src, 'pe_delete_session')
    model = MODELS.replace('NATIVE_MBSSID', function(native, 'lim_clear_mbssid_info')).replace('NATIVE_PMF', function(native, 'lim_clear_pmfcomeback_timer'))
    model = model.replace('NATIVE_FILTER', function(native, 'lim_reset_bcn_probe_filter')).replace('NATIVE_POWER', function((root/UTILS).read_text(), 'lim_cleanup_power_change'))
    model = model.replace('NATIVE_DELETE', function(native, 'pe_delete_session').replace('void pe_delete_session(', 'static void native_pe_delete_session(', 1))
    src = src.replace(old, model, 1)
    # Creation is still modeled. Initialize the real destructor's required
    # parents and identity even in the existing queue/flush regression cases.
    src = src.replace('session_ptr->valid=true;return session_ptr;', 'session_ptr->vdev_id=7;session_ptr->opmode=QDF_PASSTHRU_MODE;session_ptr->mac_ctx=m;session_ptr->valid=true;return session_ptr;', 1)
    src = src.replace('static void reset_pe(void) {', 'static struct pe_timeout_config native_pe_config;\nstatic TX_TIMER empty_pe_timer;\nstatic void reset_pe(void) {', 1)
    src = src.replace('pe_posts=pe_creates=pe_deletes=0;', 'pe_posts=pe_creates=pe_deletes=0;memset(&native_pe_config,0,sizeof(native_pe_config));pe_mac.mlme_cfg=&native_pe_config;empty_pe_timer=(TX_TIMER){0};pe_mac.lim.lim_timers.gpLimCnfWaitTimer=&empty_pe_timer;', 1)
    src = src.replace('int main(void) {', 'static int owned_pe_regressions(void) {', 1)
    src = src.replace('puts("MISHARE_OWNED_PE_SESSION_FIXTURE_PASS_ONLY");', 'return 0;', 1)
    return src+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip() != pe.PIN:
        raise ValueError('Unexpected revision')
    source = fixture(root)
    production = ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp);(d/'linux').mkdir()
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h','qdf_status.h']:
            (d/n).write_text('/* platform model */\n')
        c = d/'pe.c';exe = d/'pe'
        command = ['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(c),'-o',str(exe)]
        c.write_text(source);subprocess.run(command,check=True)
        env = {**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        out = subprocess.check_output([exe],text=True,timeout=45,env=env)
        needle = 'wlan_objmgr_vdev_release_ref(vdev, WLAN_LEGACY_MAC_ID);'
        assert source.count(needle) == 1
        # Keep the model callback referenced so -Werror cannot turn the
        # deliberate lost release into an unrelated unused-function failure.
        c.write_text(source.replace(needle, '(void)pe_native_release_ref; (void)vdev; /* negative: lost native MAC ref */', 1))
        subprocess.run(command,check=True)
        bad = subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode == -6 and 'pe_heap_release_probe' in bad.stderr
    assert out.strip() == 'MISHARE_NATIVE_PAS_PE_DESTRUCTOR_FIXTURE_PASS_ONLY'
    native = (root/pe.SESSION).read_text()
    return {'status':out.strip(),'source_commit':pe.PIN,
            'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{path:hashlib.sha256((root/path).read_bytes()).hexdigest() for path in [pe.SESSION,UTILS]},
            'native_function_sha256':{name:hashlib.sha256(function((root/path).read_text(),name).encode()).hexdigest() for path,names in [(pe.SESSION,['pe_delete_session','lim_clear_mbssid_info','lim_clear_pmfcomeback_timer','lim_reset_bcn_probe_filter']),(UTILS,['lim_cleanup_power_change'])] for name in names},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'negative_control_missing_MAC_ref_release_rejected':True,
            'checks':['existing production owner PE queue/flush/identity regressions execute native destructor',
                      'all modeled optional session allocations released exactly once; borrowed DPH array zeroed without free',
                      'native session invalidation and memory cleanup precede final MAC VDEV ref release',
                      'only matching running confirmation timers stopped; timeout zero/in-range/default branches',
                      'PAS avoids AP/STA timers, preserves STA/SAP filters and never looks up or mutates concurrent power state; invalid and NULL sessions are no-ops'],
            'limitations':'Actual native destructor, MBSSID, PMF, beacon filter and power cleanup dispatch execute with production runtime and owned MC helpers. PE allocation, remaining destructor cleanup callees, timer operations, scheduler, synchronization and object parents remain modeled. Ordinary live-MC cleanup only; no PE SSR/reset authorization, native parent lease, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
