#!/usr/bin/env python3
"""Actions-only actual owner/context helper execution with platform models."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_firmware_fixture as fw
from popsicle_backend_audit import PIN
ROOT=Path(__file__).resolve().parents[2]
MLME='qcacld-3.0/components/mlme/core/src/wlan_mlme_vdev_mgr_interface.c'
WMA='qcacld-3.0/core/wma/src/wma_dev_if.c'
WMH='qcacld-3.0/core/wma/inc/wma.h'
BASE={MLME:'033f335a1cb188577379367668a200c6a4ad626dd77349022ad6a2bbd6647df2',WMA:'504c7639fc3737b916200aabced43032128998a140830898f55476a3700a0709',WMH:'7b4288c535dff4fd39f100c6e969a6f3d62ec82714bb51102ae0be2104ac3d74'}

def block(s,name):
    m=re.search(r'\n/\* MISHARE_BEGIN:'+name+r' \*/\n(.*?)/\* MISHARE_END:'+name+r' \*/\n',s,re.S)
    if not m:raise ValueError('Missing owned source insertion: '+name)
    return m[1]

def source_guard(root):
    for path,h in BASE.items():
        s=(root/path).read_text()
        s=re.sub(r'\n/\* MISHARE_BEGIN:\w+ \*/\n.*?/\* MISHARE_END:\w+ \*/\n','',s,flags=re.S)
        s=s.replace('#include "wlan_hdd_mishare_ndi.h"\n','')
        if hashlib.sha256(s.encode()).hexdigest()!=h:raise ValueError('Changed legacy source outside bounded context additions: '+path)

STUBS=r'''
#define QDF_MODULE_ID_WMA 1
#define WLAN_LEGACY_WMA_ID 3
#define QDF_STATUS_E_NOMEM 6
#define WMI_PEER_TYPE_DEFAULT 0
#define WMA_BSS_STATUS_STOPPED 2
#define WMA_DELETE_STA_REQ 1
#define WMA_DELETE_STA_TIMEOUT 30
#define WMA_MISHARE_SELF_PEER_DELETE_RSP 0x12
#define QDF_TIMER_TYPE_SW 1
#define QDF_MAC_ADDR_SIZE 6
#define QDF_PEER_DELETION_TIMEDOUT 1
struct wait_for_key_timer {struct wlan_objmgr_vdev *vdev;int timer;};
struct mlme_legacy_priv {
 int bss_color_change_runtime_lock,bss_color_change_wakelock,disconnect_runtime_lock;
 int peer_set_key_rt_wakelock,peer_set_key_wakelock,set_key_wakelock_counter;
 struct wait_for_key_timer wait_key_timer;struct {void *fils_con_info;} connect_info;
};
struct wma_txrx_node {struct wlan_objmgr_vdev *vdev;int type,sub_type,pause_bitmap,bss_status;bool vdev_active,is_del_sta_deferred;void *del_staself_req;unsigned peer_count;};
struct wma {struct wlan_objmgr_psoc *psoc;unsigned max_bssid;struct wma_txrx_node interfaces[32];struct wmi_unified *wmi_handle;int wmi_cmd_rsp_wake_lock;bool fw_timeout_crash;};
typedef struct wma *tp_wma_handle;
static struct wma wma_context;
struct wlan_objmgr_peer {struct wlan_objmgr_vdev *vdev;};
static struct wlan_objmgr_peer ctx_peer;
struct wma_target_req {u8 vdev_id,type;unsigned msg_type;void *user_data;struct {u8 bytes[6];} addr;int event_timeout;};
static struct wma_target_req *ctx_pending;
static int ctx_stage,ctx_fail_at,ctx_locks,ctx_requests,ctx_create_calls,ctx_delete_calls,ctx_dp_acks,ctx_recoveries;
static bool ctx_alloc_fail,ctx_peer_present,ctx_queue_fail,ctx_early_reply,ctx_early_timeout,ctx_send_error,ctx_create_error;
static void ctx_fw_origin(struct wma_target_req *);
static void ctx_timeout_origin(struct wma_target_req *);
static QDF_STATUS ctx_step(void) {return ++ctx_stage==ctx_fail_at?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;}
static void *qdf_mem_common_alloc(size_t n) {return ctx_alloc_fail?NULL:kzalloc(n,GFP_KERNEL);}
static void qdf_mem_common_free(void *p) {kfree(p);}
static void qdf_mem_zero(void *p,size_t n) {memset(p,0,n);}
static void qdf_mem_copy(void *d,const void *s,size_t n) {memcpy(d,s,n);}
static QDF_STATUS mlme_init_rate_config(struct vdev_mlme_obj *m) {assert(m->ext_vdev_ptr);return ctx_step();}
static QDF_STATUS mlme_init_connect_chan_info_config(struct vdev_mlme_obj *m) {assert(m->ext_vdev_ptr);return ctx_step();}
static void cm_wait_for_key_time_out_handler(void *p) {(void)p;assert(0);}
static QDF_STATUS ctx_lock_init(int *p) {assert(!*p);QDF_STATUS s=ctx_step();if(!s){*p=1;ctx_locks++;}return s;}
static void ctx_lock_free(int *p) {assert(*p==1 && ctx_locks>0);*p=0;ctx_locks--;}
static QDF_STATUS qdf_mc_timer_init(int *p,int type,void (*cb)(void*),void *c) {assert(type==1 && cb && c);return ctx_lock_init(p);}
static void qdf_mc_timer_stop(int *p) {assert(*p==1);}
static void qdf_mc_timer_destroy(int *p) {ctx_lock_free(p);}
static QDF_STATUS qdf_wake_lock_create(int *p,const char *name) {assert(name);return ctx_lock_init(p);}
static void qdf_wake_lock_destroy(int *p) {ctx_lock_free(p);}
static QDF_STATUS qdf_runtime_lock_init(int *p) {return ctx_lock_init(p);}
static void qdf_runtime_lock_deinit(int *p) {ctx_lock_free(p);}
static void qdf_atomic_init(int *p) {*p=0;}
static void qdf_atomic_set(int *p,int n) {*p=n;}
static int qdf_atomic_read(int *p) {return *p;}
static void mlme_free_peer_disconnect_ies(struct wlan_objmgr_vdev *v) {assert(v && v->mlme->ext_vdev_ptr);}
static void mlme_free_sae_auth_retry(struct wlan_objmgr_vdev *v) {assert(v && v->mlme->ext_vdev_ptr);}
static void mlme_free_fils_info(void *p) {assert(p);}
static void mlme_cm_free_roam_stats_info(struct mlme_legacy_priv *p) {assert(p);}
static tp_wma_handle cds_get_context(int id) {assert(id==1);return &wma_context;}
static bool wma_mishare_pas_ndi(struct wlan_objmgr_vdev *v,unsigned type) {return v && v->mode==17 && type==7;}
static struct wlan_objmgr_peer *wlan_objmgr_get_peer_by_mac(struct wlan_objmgr_psoc *p,u8 *mac,int id) {assert(p && mac && id==3);return ctx_peer_present?&ctx_peer:NULL;}
static struct wlan_objmgr_vdev *wlan_peer_get_vdev(struct wlan_objmgr_peer *p) {return p->vdev;}
static void wlan_objmgr_peer_release_ref(struct wlan_objmgr_peer *p,int id) {assert(p && id==3);}
static QDF_STATUS wma_create_peer(tp_wma_handle w,u8 *mac,void *unused,int type,u8 id,void *mld,bool assoc) {
 assert(w==&wma_context && mac && !unused && !type && id==7 && !mld && !assoc);ctx_create_calls++;
 ctx_peer_present=true;ctx_peer.vdev=w->interfaces[id].vdev;w->interfaces[id].peer_count++;
 return ctx_create_error?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static void wma_acquire_wakelock(int *p,int time) {assert(time==30 && !*p);*p=1;}
static void wma_release_wakelock(int *p) {assert(*p==1);*p=0;}
static struct wma_target_req *wma_fill_hold_req(tp_wma_handle w,u8 id,unsigned msg,u8 type,u8 *mac,void *token,unsigned timeout) {
 assert(w==&wma_context && id==7 && msg==1 && type==0x12 && mac && token && timeout==30 && !ctx_pending);
 if(ctx_queue_fail)return NULL;
 struct wma_target_req *r=calloc(1,sizeof(*r));assert(r);ctx_requests++;r->vdev_id=id;r->msg_type=msg;r->type=type;r->user_data=token;memcpy(r->addr.bytes,mac,6);r->event_timeout=1;ctx_locks++;ctx_pending=r;return r;
}
static QDF_STATUS wma_remove_peer(tp_wma_handle w,u8 *mac,u8 id,bool nofw) {
 assert(w==&wma_context && mac && id==7 && !nofw && ctx_pending && ctx_peer_present && w->interfaces[id].peer_count==1);
 ctx_delete_calls++;ctx_peer_present=false;w->interfaces[id].peer_count--;
 if(ctx_early_reply)ctx_fw_origin(ctx_pending);
 if(ctx_early_timeout)ctx_timeout_origin(ctx_pending);
 return ctx_send_error?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static bool wma_crash_on_fw_timeout(bool enabled) {return enabled;}
static void wma_trigger_recovery_assert_on_fw_timeout(unsigned msg,int reason) {assert(msg==1 && reason==1);ctx_recoveries++;}
static void ctx_request_free(struct wma_target_req *r) {assert(r==ctx_pending && ctx_requests==1 && !r->event_timeout);ctx_pending=NULL;ctx_requests--;free(r);}
NATIVE_CONTEXT_HELPERS
NATIVE_CONTEXT_ORIGINS
'''
HARNESS=r'''
static void reset_context(void) {
 reset_transport();assert(!ctx_locks && !ctx_requests && !ctx_pending);
 memset(&wma_context,0,sizeof(wma_context));wma_context.psoc=&psoc;wma_context.max_bssid=32;wma_context.wmi_handle=&wmi;
 ctx_stage=ctx_fail_at=ctx_create_calls=ctx_delete_calls=ctx_dp_acks=ctx_recoveries=0;
 ctx_alloc_fail=ctx_peer_present=ctx_queue_fail=ctx_early_reply=ctx_early_timeout=ctx_send_error=ctx_create_error=false;
}
static void context_end(struct mishare_runtime_owner **o) {
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && ctx_delete_calls==1 && !wire_deletes && !dp_detaches);
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && ctx_delete_calls==1 && !wire_deletes);
 ctx_fw_origin(ctx_pending);assert(state(*o).ndi.peer_delete_replied && !ctx_requests && !wma_context.wmi_cmd_rsp_wake_lock);
 healthy_end(o);assert(!ctx_locks && !ctx_requests && !wma_context.interfaces[7].vdev);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_runtime_ndi_prepare(NULL)==-EINVAL);
 reset_context();assert(!create(&o));assert(mishare_runtime_ndi_prepare(o)==-EBUSY && !ctx_create_calls);assert(!mishare_runtime_destroy(&o));
 for(int fault=0;fault<=8;fault++) {
  reset_context();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));ctx_alloc_fail=fault==0;ctx_fail_at=fault;
  assert(mishare_runtime_ndi_prepare(o)<0 && !state(o).ndi.blocked && !state(o).ndi.legacy_ready && !ctx_locks && !ctx_create_calls && allocations==2 && last_vdev->refs==3);
  healthy_end(&o);
 }
 /* Occupied WMA slot is never overwritten; clean local legacy state. */
 reset_context();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));
 struct wlan_objmgr_vdev foreign={0};wma_context.interfaces[7].vdev=&foreign;
 assert(mishare_runtime_ndi_prepare(o)==-EBUSY && wma_context.interfaces[7].vdev==&foreign && !ctx_locks && !ctx_create_calls && last_vdev->refs==3);
 wma_context.interfaces[7].vdev=NULL;healthy_end(&o);
 /* Object ref failure and existing peer preflight unwind only owned context. */
 reset_context();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));fail_ref_at=ref_calls+1;
 assert(mishare_runtime_ndi_prepare(o)==-ENODEV && !ctx_locks && last_vdev->refs==3);healthy_end(&o);
 reset_context();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));ctx_peer_present=true;ctx_peer.vdev=&foreign;
 assert(mishare_runtime_ndi_prepare(o)==-EEXIST && !ctx_locks && !wma_context.interfaces[7].vdev && !ctx_create_calls);ctx_peer_present=false;healthy_end(&o);
 reset_context();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1) && !mishare_runtime_ndi_prepare(o));
 assert(state(o).ndi.legacy_ready && state(o).ndi.wma_bound && state(o).ndi.peer_created && ctx_create_calls==1 && ctx_locks==6 && allocations==3 && last_vdev->refs==4);
 assert(mishare_runtime_ndi_prepare(o)==-EBUSY && ctx_create_calls==1);
 struct wlan_objmgr_psoc wrong={2};
 mishare_runtime_ndi_peer_event(&wrong,7,mac,o,true);mishare_runtime_ndi_peer_event(&psoc,8,mac,o,true);
 mishare_runtime_ndi_peer_event(&psoc,7,mac,(void*)1,true);assert(!state(o).ndi.blocked && !state(o).ndi.peer_delete_replied);
 context_end(&o);
 reset_context();assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1) && !mishare_runtime_ndi_prepare(o));ctx_early_reply=true;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && state(o).ndi.peer_delete_submitted && state(o).ndi.peer_delete_replied && !wire_deletes);
 healthy_end(&o);assert(!ctx_locks && !ctx_requests);
 for(int fault=0;fault<6;fault++) {
  reset_context();pid_t child=fork();assert(child>=0);
  if(!child) {
   assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1));ctx_create_error=fault==0;
   if(fault==5){ctx_peer_present=true;ctx_peer.vdev=last_vdev;}
   if(fault==0 || fault==5)assert(mishare_runtime_ndi_prepare(o)==-EUCLEAN);
   else {
    assert(!mishare_runtime_ndi_prepare(o));ctx_queue_fail=fault==1;ctx_send_error=fault==2;ctx_early_timeout=fault==3;
    if(fault==3)wma_context.fw_timeout_crash=true;
    if(fault==4)mishare_runtime_ndi_peer_event(&psoc,7,mac,o,true); /* unexpected */
    if(fault==1 || fault==2 || fault==3)assert(mishare_runtime_destroy(&o)==-EUCLEAN);
    if(fault==2){assert(ctx_pending);ctx_timeout_origin(ctx_pending);}
    if(fault==3)assert(ctx_recoveries==1);
   }
   assert(mishare_runtime_destroy(&o)==-EUCLEAN && o && !wire_deletes && !dp_detaches && !delete_calls && objects_live==1 && allocations==3 && last_vdev->refs==4);
   assert(mishare_runtime_ndi_prepare(o)==-EUCLEAN);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_OWNED_CONTEXT_PEER_FIXTURE_PASS_ONLY");
}
'''

def fixture(root):
    source_guard(root);wma=(root/WMA).read_text();mlme=(root/MLME).read_text()
    funcs=block(mlme,'legacy_helpers')+block(wma,'wma_helpers')
    # These existing native destroy helpers are also executed, not substituted.
    for name,pattern in [('mlme_deinit_wait_for_key_timer',r'static\s+void'),('mlme_ext_handler_destroy',r'static\s+void')]:
        m=re.search(pattern+r'\s+'+name+r'\([^;{]+\)\s*\{.*?^\}',mlme,re.S|re.M)
        if not m:raise ValueError('Cannot extract legacy destructor '+name)
        funcs=m[0]+'\n'+funcs
    # Forward declaration is needed because the full native destructor calls it.
    funcs='static void mlme_deinit_wait_for_key_timer(struct wait_for_key_timer *);\n'+funcs
    origins='''static void ctx_fw_origin(struct wma_target_req *req_msg) {
 tp_wma_handle wma=&wma_context;
 struct {u8 vdev_id;} event_data={req_msg->vdev_id};typeof(event_data) *event=&event_data;
 u8 macaddr[6];memcpy(macaddr,req_msg->addr.bytes,6);
'''+block(wma,'peer_fw_locals')+'\n switch(req_msg->type) {\n'+block(wma,'peer_fw_case')+'''
 default:assert(0);
 }
 wma_release_wakelock(&wma->wmi_cmd_rsp_wake_lock);
 qdf_mc_timer_stop(&req_msg->event_timeout);qdf_mc_timer_destroy(&req_msg->event_timeout);
 ctx_dp_acks++;ctx_request_free(req_msg);
'''+block(wma,'peer_fw_notify')+'''}
static void ctx_timeout_origin(struct wma_target_req *tgt_req) {
 tp_wma_handle wma=&wma_context;
'''+block(wma,'peer_timeout_locals')+block(wma,'peer_timeout_case')+'''
 assert(0);
 timer_destroy:
 qdf_mc_timer_destroy(&tgt_req->event_timeout);ctx_request_free(tgt_req);
'''+block(wma,'peer_timeout_notify')+'}\n'
    # Avoid a GNU-only test declaration while retaining the native branch body.
    origins=origins.replace('struct {u8 vdev_id;} event_data={req_msg->vdev_id};typeof(event_data) *event=&event_data;','struct event_t {u8 vdev_id;} event_data={req_msg->vdev_id};struct event_t *event=&event_data;')
    real=wma[wma.index('int wma_peer_delete_handler('):wma.index('void wma_hold_req_timer(')]
    if real.index('qdf_mem_free(req_msg);')>real.index('/* MISHARE_BEGIN:peer_fw_notify */'):raise ValueError('Owned peer reply published before request free')
    src=fw.fixture(root)
    start=src.index('/* CONTEXT_TRANSPORT_STUBS */');end=src.index('/* END_CONTEXT_TRANSPORT_STUBS */',start)+len('/* END_CONTEXT_TRANSPORT_STUBS */')
    src=src[:start]+STUBS.replace('NATIVE_CONTEXT_HELPERS',funcs).replace('NATIVE_CONTEXT_ORIGINS',origins)+src[end:]
    # Keep firmware resource helpers and their reusable test functions; replace
    # its main with this independent context/lifetime harness.
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h','qdf_status.h']:(d/n).write_text('/* platform model */\n')
        (d/'owner.c').write_text(source);exe=d/'owner'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'owner.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_OWNED_CONTEXT_PEER_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in BASE},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},'legacy_sources_after_removing_bounded_additions_match':BASE,'checks':['legacy allocation and eight setup failure stages unwind only initialized resources','occupied WMA slot, ref failure and existing peer do not overwrite or delete foreign state','owned WMA reference retained through peer/vdev DELETE and DP final-free','one peer-create attempt; native error quarantines','peer request precedes native delete; real reply published only after native request cleanup','wrong token/psoc/ID ignored; unexpected matching reply quarantines','early peer reply waits for send return before VDEV DELETE','peer queue/send/timeout failures prevent VDEV DELETE and all parent cleanup','native full legacy destruction releases owned locks/timer and extension'], 'limitations':'Actual owner and extracted legacy init/full destroy/WMA bind/unbind/peer helper functions, plus bounded native peer-origin insertions. Platform primitives, WMA hold queue/timer, native wma_create_peer/wma_remove_peer and firmware/DP transports are modeled. Full WMA response/timer handlers, native IRQ/list races, firmware acceptance, native peer final-free and SSR/remove are not executed or certified. Quarantine children retain resources deliberately. No CSR/session parameter setup, START/channel/TX/RX or runtime backend caller.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
