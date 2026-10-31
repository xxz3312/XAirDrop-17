#!/usr/bin/env python3
"""Actions-only owned radio lifecycle with real native transport/response functions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_start_plan_fixture as plan
from mishare_firmware_fixture import function, TX, RX
from mishare_events_fixture import RXDEFS, TXDEFS
ROOT=plan.ROOT
MLME=plan.channel.pe.ctx.MLME
UTIL='qcacld-3.0/core/wma/src/wma_utils.c'
SM='qca-wifi-host-cmn/umac/mlme/vdev_mgr/core/src/vdev_mlme_sm.c'

STUBS=r'''
#define GFP_ATOMIC 1
#define wma_err(...) ((void)0)
#define QDF_STATUS_E_CANCELED 7
#define WMA_BSS_STATUS_STARTED 3
#define START_RESPONSE_TIMER 10
#define STOP_RESPONSE_TIMER 11
#define START_RESPONSE_BIT 2
#define RESTART_RESPONSE_BIT 3
#define STOP_RESPONSE_BIT 4
#define START_WAKELOCK 2
#define STOP_WAKELOCK 3
#define QDF_MONITOR_MODE 4
#define QDF_MAX_NO_OF_MODE 0
#define WLAN_VDEV_TARGET_IF_ID WLAN_HDD_ID_OBJ_MGR
#define WLAN_VDEV_SS_IDLE 0
#define WLAN_VDEV_SS_START_START_PROGRESS 101
#define WLAN_VDEV_SS_STOP_STOP_PROGRESS 102
static unsigned radio_native_substate;
static unsigned wlan_vdev_mlme_get_substate(struct wlan_objmgr_vdev *v) {assert(v);return radio_native_substate;}
#define WLAN_VDEV_S_START 1
#define WLAN_VDEV_S_UP 2
#define WLAN_VDEV_S_SUSPEND 3
#define WLAN_VDEV_S_STOP 4
enum wlan_vdev_sm_evt {WLAN_VDEV_SM_EV_START=1,WLAN_VDEV_SM_EV_START_RESP,WLAN_VDEV_SM_EV_START_SUCCESS,WLAN_VDEV_SM_EV_DOWN,WLAN_VDEV_SM_EV_DISCONNECT_COMPLETE,WLAN_VDEV_SM_EV_STOP_RESP,WLAN_VDEV_SM_EV_MLME_DOWN_REQ,WLAN_VDEV_SM_EV_DOWN_COMPLETE};
enum beacon_update_op {BEACON_INIT,BEACON_REINIT,BEACON_UPDATE,BEACON_CSA,BEACON_FREE};
NATIVE_RESPONSE_DEFS
NATIVE_RESPONSE_ENUMS
struct vdev_stop_params {u8 vdev_id;bool is_mlo_link_switch;};
struct vdev_down_params {u8 vdev_id;};
static unsigned radio_starts,radio_stops,radio_downs,radio_timer,radio_start_pm,radio_stop_pm,radio_rt,sm_depth;
static bool radio_start_fail,radio_stop_fail,radio_down_fail,radio_early_start,radio_early_stop,radio_queue_fail,radio_apply_fail;
static unsigned radio_q_len;
static struct scheduler_msg radio_q[8];
static QDF_STATUS radio_sched_post(int src,int dst,int queue,struct scheduler_msg *msg) {
 assert(!lock_depth && src==QDF_MODULE_ID_HDD && dst==QDF_MODULE_ID_PE && queue==QDF_MODULE_ID_TARGET_IF && msg->callback && msg->flush_callback);
 if(radio_queue_fail)return QDF_STATUS_E_FAILURE;
 assert(radio_q_len<8);radio_q[radio_q_len++]=*msg;return QDF_STATUS_SUCCESS;
}
static void radio_run(bool flush) {
 assert(radio_q_len);struct scheduler_msg msg=radio_q[0];memmove(radio_q,radio_q+1,--radio_q_len*sizeof(*radio_q));
 assert((flush?msg.flush_callback(&msg):msg.callback(&msg))==QDF_STATUS_SUCCESS && !msg.bodyptr);
}
static QDF_STATUS radio_sm_dispatch(struct wlan_objmgr_vdev*,enum wlan_vdev_sm_evt);
static QDF_STATUS wlan_vdev_mlme_sm_deliver_evt(struct wlan_objmgr_vdev *v,enum wlan_vdev_sm_evt e,uint16_t n,void *p) {
 assert(!sm_depth && !lock_depth && !n && !p);sm_depth++;QDF_STATUS s=radio_sm_dispatch(v,e);sm_depth--;return s;
}
static QDF_STATUS wlan_vdev_mlme_sm_deliver_evt_sync(struct wlan_objmgr_vdev *v,enum wlan_vdev_sm_evt e,uint16_t n,void *p) {
 assert(sm_depth==1 && !lock_depth && !n && !p);return radio_sm_dispatch(v,e);
}
static void radio_pm_wake_acquire(struct wlan_objmgr_psoc *p,int kind) {assert(p==&psoc);if(kind==2) {assert(!radio_start_pm);radio_start_pm=1;} else {assert(kind==3 && !radio_stop_pm);radio_stop_pm=1;}}
static void radio_pm_wake_release(struct wlan_objmgr_psoc *p,int kind) {assert(p==&psoc);if(kind==2)radio_start_pm=0;else {assert(kind==3);radio_stop_pm=0;}}
static void radio_pm_rt_acquire(struct vdev_response_timer *t) {assert(t==&response_timer && !radio_rt);radio_rt=1;}
static void radio_pm_rt_release(struct wlan_objmgr_psoc *p,u8 id) {assert(p==&psoc && id==7);radio_rt=0;}
static void radio_timer_start(struct wlan_objmgr_psoc *p,struct vdev_response_timer *t,unsigned bit) {assert(p==&psoc && t==&response_timer && !radio_timer && timers_live);radio_timer=bit;}
static QDF_STATUS radio_timer_stop(struct wlan_objmgr_psoc *p,struct vdev_response_timer *t,unsigned bit) {assert(p==&psoc && t==&response_timer);if(radio_timer!=bit)return QDF_STATUS_E_FAILURE;radio_timer=0;return QDF_STATUS_SUCCESS;}
static void target_if_vdev_start_link_handler(struct wlan_objmgr_vdev *v,bool restart) {assert(v==last_vdev && !restart);}
static void target_if_vdev_stop_link_handler(struct wlan_objmgr_vdev *v) {assert(v==last_vdev);}
static int target_if_vdev_mgr_start_response_handler(ol_scn_t,u8*,uint32_t);
static int target_if_vdev_mgr_stop_response_handler(ol_scn_t,u8*,uint32_t);
static QDF_STATUS radio_reply_start(unsigned status) {
 struct vdev_start_response rsp={.vdev_id=7,.resp_type=WMI_HOST_VDEV_START_RESP_EVENT,.status=status};
 return target_if_vdev_mgr_start_response_handler(&psoc,(u8*)&rsp,sizeof(rsp))?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static QDF_STATUS radio_reply_stop(void) {u32 id=7;return target_if_vdev_mgr_stop_response_handler(&psoc,(u8*)&id,sizeof(id))?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;}
static QDF_STATUS wmi_unified_vdev_start_send(struct wmi_unified *w,struct vdev_start_params *p) {
 assert(w==&wmi && p->vdev_id==7 && !p->is_restart && radio_timer==2 && radio_start_pm && radio_rt);radio_starts++;
 if(radio_early_start)assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);
 return radio_start_fail?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static QDF_STATUS wmi_unified_vdev_stop_send(struct wmi_unified *w,struct vdev_stop_params *p) {
 assert(w==&wmi && p->vdev_id==7 && radio_timer==4 && radio_stop_pm && radio_rt && !ctx_delete_calls && !wire_deletes);radio_stops++;
 if(radio_early_stop)assert(radio_reply_stop()==QDF_STATUS_SUCCESS);
 return radio_stop_fail?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static QDF_STATUS wmi_unified_vdev_down_send(struct wmi_unified *w,u8 id) {
 assert(w==&wmi && id==7 && !radio_timer && radio_stop_pm && radio_rt && !ctx_delete_calls && !wire_deletes);radio_downs++;
 return radio_down_fail?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static struct wlan_objmgr_vdev *wlan_objmgr_get_vdev_by_id_from_psoc(struct wlan_objmgr_psoc *p,u8 id,int ref) {assert(p==&psoc && ref==1);if(id!=7)return NULL;last_vdev->refs++;return last_vdev;}
#define wlan_psoc_get_id(p) ((p)->id)
static int wmi_extract_vdev_start_resp(struct wmi_unified *w,u8 *data,struct vdev_start_response *r) {assert(w==&wmi && data);*r=*(struct vdev_start_response*)data;return 0;}
static int wmi_extract_vdev_stopped_param(struct wmi_unified *w,u8 *data,u32 *id) {assert(w==&wmi && data);*id=*(u32*)data;return 0;}
#define target_if_wake_lock_timeout_acquire radio_pm_wake_acquire
#define target_if_wake_lock_timeout_release radio_pm_wake_release
#define target_if_acquire_vdev_cmd_rt_lock radio_pm_rt_acquire
#define target_if_release_vdev_cmd_rt_lock radio_pm_rt_release
#define target_if_vdev_mgr_rsp_timer_start radio_timer_start
#define target_if_vdev_mgr_rsp_timer_stop radio_timer_stop
NATIVE_TX_FUNCTIONS
NATIVE_RX_FUNCTIONS
NATIVE_PM_RELEASE
#undef target_if_wake_lock_timeout_acquire
#undef target_if_wake_lock_timeout_release
#undef target_if_acquire_vdev_cmd_rt_lock
#undef target_if_release_vdev_cmd_rt_lock
#undef target_if_vdev_mgr_rsp_timer_start
#undef target_if_vdev_mgr_rsp_timer_stop
static QDF_STATUS vdev_mgr_start_send(struct vdev_mlme_obj *m,bool restart) {
 struct vdev_start_params p={0};QDF_STATUS s=vdev_mgr_start_param_update(m,&p);if(s)return s;p.is_restart=restart;
 return target_if_vdev_mgr_start_send(m->vdev,&p);
}
static QDF_STATUS vdev_mgr_stop_send(struct vdev_mlme_obj *m) {struct vdev_stop_params p={7,false};return target_if_vdev_mgr_stop_send(m->vdev,&p);}
static QDF_STATUS vdev_mgr_down_send(struct vdev_mlme_obj *m) {struct vdev_down_params p={7};return target_if_vdev_mgr_down_send(m->vdev,&p);}
static QDF_STATUS vdev_mgr_up_send(struct vdev_mlme_obj *m) {(void)m;assert(0);return QDF_STATUS_E_FAILURE;}
NATIVE_MON_UP
/* Full WMA START response processing remains an explicit boundary; its owned
 * wrapper and the real native target-if RX/TX/PM functions execute below. */
static QDF_STATUS wma_vdev_start_resp_handler(struct vdev_mlme_obj *m,struct vdev_start_response *rsp) {
 assert(m->vdev==last_vdev && rsp->vdev_id==7 && !rsp->status && !sm_depth);
 if(radio_apply_fail)return QDF_STATUS_E_FAILURE;
 return wlan_vdev_mlme_sm_deliver_evt(m->vdev,WLAN_VDEV_SM_EV_START_RESP,0,NULL);
}
NATIVE_WMA_HELPERS
NATIVE_PREPARE
#define scheduler_post_message radio_sched_post
#include "wlan_hdd_mishare_radio.c"
#undef scheduler_post_message
NATIVE_FALLBACK_WRAPPERS
/* Bounded SM model follows the pinned native cases. The full native SM and
 * WMA post-START path are compiled by WLAN, not executed in this host model. */
static QDF_STATUS radio_sm_dispatch(struct wlan_objmgr_vdev *v,enum wlan_vdev_sm_evt e) {
 struct vdev_mlme_obj *m=v->mlme;QDF_STATUS s;
 assert(v==last_vdev && sm_depth==1);
 switch(e) {
 case WLAN_VDEV_SM_EV_START:
  assert(ch_state==WLAN_VDEV_S_INIT);
  s=mishare_radio_validate(m,0,NULL);if(s)return s;ch_state=WLAN_VDEV_S_START;
  radio_native_substate=WLAN_VDEV_SS_START_START_PROGRESS;return mishare_radio_start_send(m,0,NULL);
 case WLAN_VDEV_SM_EV_START_RESP:
  assert(ch_state==WLAN_VDEV_S_START);return mishare_radio_start_continue(m,0,NULL);
 case WLAN_VDEV_SM_EV_START_SUCCESS:
  assert(ch_state==WLAN_VDEV_S_START);ch_state=WLAN_VDEV_S_UP;
  (void)passthru_radio_beacon(m,BEACON_INIT,0,NULL);
  s=mishare_radio_up_send(m,0,NULL);
  if(s) {ch_state=WLAN_VDEV_S_SUSPEND;(void)passthru_radio_disconnect(m,0,NULL,false);return s;}
  return mishare_radio_up_complete(m,0,NULL);
 case WLAN_VDEV_SM_EV_DOWN:
  assert(ch_state==WLAN_VDEV_S_UP);ch_state=WLAN_VDEV_S_SUSPEND;
  return passthru_radio_disconnect(m,0,NULL,false);
 case WLAN_VDEV_SM_EV_DISCONNECT_COMPLETE:
  assert(ch_state==WLAN_VDEV_S_SUSPEND);ch_state=WLAN_VDEV_S_STOP;radio_native_substate=WLAN_VDEV_SS_STOP_STOP_PROGRESS;
  return mishare_radio_stop_send(m,0,NULL);
 case WLAN_VDEV_SM_EV_STOP_RESP:
  assert(ch_state==WLAN_VDEV_S_STOP);return mishare_radio_stop_continue(m,0,NULL);
 case WLAN_VDEV_SM_EV_MLME_DOWN_REQ:
  assert(ch_state==WLAN_VDEV_S_STOP);return mishare_radio_down_send(m,0,NULL);
 case WLAN_VDEV_SM_EV_DOWN_COMPLETE:
  assert(ch_state==WLAN_VDEV_S_STOP);ch_state=WLAN_VDEV_S_INIT;radio_native_substate=WLAN_VDEV_SS_IDLE;
  return mishare_radio_down_complete(m,0,NULL);
 }
 assert(0);return QDF_STATUS_E_FAILURE;
}
static QDF_STATUS radio_dispatch_start(struct wlan_objmgr_psoc *p,struct vdev_start_response *r) {assert(p==&psoc);return passthru_radio_start_rsp(last_vdev->mlme,r);}
static QDF_STATUS radio_dispatch_stop(struct wlan_objmgr_psoc *p,struct vdev_stop_response *r) {assert(p==&psoc);return passthru_radio_stop_rsp(last_vdev->mlme,r);}
'''
HARNESS=r'''
static void reset_radio(void) {
 reset_plan();assert(!radio_q_len && !mishare_radios);radio_native_substate=0;
 radio_starts=radio_stops=radio_downs=radio_timer=radio_start_pm=radio_stop_pm=radio_rt=sm_depth=0;
 radio_start_fail=radio_stop_fail=radio_down_fail=radio_early_start=radio_early_stop=radio_queue_fail=radio_apply_fail=false;
 rxops.vdev_mgr_start_response=radio_dispatch_start;rxops.vdev_mgr_stop_response=radio_dispatch_stop;
}
static struct mishare_runtime_owner *with_plan(void) {
 struct mishare_runtime_owner *o=with_channel(2437);
 assert(mishare_runtime_ndi_start_plan(o)==-EINPROGRESS);run_pe(false);assert(state(o).ndi.start_plan_ready);return o;
}
static void after_radio(struct mishare_runtime_owner **o) {
 assert(!radio_q_len && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt && !mishare_radios);
 assert(state(*o).radio.phase==MISHARE_RADIO_DOWN || state(*o).radio.phase==MISHARE_RADIO_CANCELLED);
 assert(!ctx_delete_calls && !wire_deletes);run_pe(false);context_end(o);
}
static void start_up(struct mishare_runtime_owner *o) {
 assert(mishare_runtime_ndi_start(o)==-EINPROGRESS && radio_q_len==1 && last_vdev->refs==6);
 assert(mishare_runtime_ndi_start(o)==-EBUSY);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && radio_starts==1 && !state(o).radio.host_up && radio_start_pm && radio_rt && !ctx_delete_calls);
 assert(radio_reply_start(0)==QDF_STATUS_SUCCESS && !radio_timer && radio_q_len==1);
 radio_run(false);assert(state(o).radio.phase==MISHARE_RADIO_UP && state(o).radio.host_up && !radio_start_pm && !radio_rt);
}
int main(void) {
 assert(mishare_runtime_ndi_start(NULL)==-EINVAL);
 assert(mishare_radio_validate(NULL,0,NULL)==QDF_STATUS_E_NOSUPPORT);
 assert(passthru_radio_start_rsp(NULL,NULL)==QDF_STATUS_E_NOSUPPORT);
 assert(passthru_radio_stop_rsp(NULL,NULL)==QDF_STATUS_E_NOSUPPORT);
 assert(passthru_radio_beacon(NULL,BEACON_INIT,0,NULL)==QDF_STATUS_E_NOSUPPORT);
 assert(passthru_radio_disconnect(NULL,0,NULL,false)==QDF_STATUS_E_NOSUPPORT);
 reset_radio();struct mishare_runtime_owner *o=with_channel(2437);
 assert(mishare_runtime_ndi_start(o)==-EBUSY && !radio_q_len);channel_end(&o);
 /* Actual native TX/RX and PM ordering, owner teardown waits at every phase. */
 reset_radio();o=with_plan();start_up(o);
 assert(radio_reply_start(0)!=QDF_STATUS_SUCCESS && state(o).radio.phase==MISHARE_RADIO_UP); /* native timer rejects duplicate */
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !ctx_delete_calls && radio_q_len==1);
 radio_run(false);assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && radio_stops==1 && radio_stop_pm && radio_rt && !ctx_delete_calls);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !ctx_delete_calls && !radio_downs);
 assert(radio_reply_stop()==QDF_STATUS_SUCCESS && !radio_timer && radio_q_len==1);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !ctx_delete_calls);
 radio_run(false);assert(state(o).radio.phase==MISHARE_RADIO_DOWN && state(o).radio.down_accepted && radio_downs==1 && ch_state==0 && !radio_stop_pm && !radio_rt);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !o->radio && pe_pending.bodyptr && last_vdev->refs==6); /* PE-delete request ref, radio ref gone */
 after_radio(&o);
 /* Replies before send returns are buffered by the real transaction registry. */
 reset_radio();o=with_plan();radio_early_start=radio_early_stop=true;
 assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && radio_q_len==1);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_UP);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && radio_q_len==1);radio_run(false);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);after_radio(&o);
 /* Closing/flush before initial work performs no START or STOP. */
 for(int flush=0;flush<2;flush++) {
  reset_radio();o=with_plan();assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);
  if(!flush)assert(mishare_runtime_destroy(&o)==-EINPROGRESS);
  radio_run(flush);assert(state(o).radio.phase==MISHARE_RADIO_CANCELLED && !radio_starts && !radio_stops && !radio_downs);
  assert(mishare_runtime_destroy(&o)==-EINPROGRESS);after_radio(&o);
 }
 /* Proven pre-post allocation/ref/queue rejection permits only normal unstarted cleanup. */
 for(int fault=0;fault<4;fault++) {
  reset_radio();o=with_plan();
  if(fault==0)fail_alloc_at=alloc_calls+1;
  if(fault==1)fail_ref_at=ref_calls+1;
  if(fault==2)fail_alloc_at=alloc_calls+2;
  radio_queue_fail=fault==3;
  assert(mishare_runtime_ndi_start(o)<0 && !radio_q_len && !radio_starts);
  fail_alloc_at=fail_ref_at=0;radio_queue_fail=false;
  if(o->radio) {assert(state(o).radio.phase==MISHARE_RADIO_CANCELLED);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);after_radio(&o);}
  else channel_end(&o);
 }
 /* All ambiguous wire/host/queue/timeout failures retain PE, peer, VDEV and DP. */
 for(int fault=0;fault<15;fault++) {
  reset_radio();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=with_plan();assert(mishare_runtime_ndi_start(o)==-EINPROGRESS);
   radio_start_fail=fault==0;radio_early_start=fault==1;
   if(fault==1)radio_start_fail=true; /* early ACK plus generic submit error */
   if(fault==2)ch_scan=true; /* fresh preflight rejection, no fabricated INIT completion */
   radio_run(false);
   if(fault>=3) {
    if(fault==3) {mishare_events_notify(&psoc,7,MISHARE_TXN_START,MISHARE_EVENT_TIMEOUT,false);struct vdev_start_response rsp={.vdev_id=7,.resp_type=WMI_HOST_VDEV_START_RESP_EVENT,.status=1};assert(passthru_radio_start_rsp(last_vdev->mlme,&rsp)!=QDF_STATUS_SUCCESS);}
    else if(fault==4)assert(radio_reply_start(1)!=QDF_STATUS_SUCCESS);
    else {
     if(fault==5)fail_alloc_at=alloc_calls+1;
     assert((radio_reply_start(0)==QDF_STATUS_SUCCESS)==(fault!=5));
     if(fault>=6) {
      radio_apply_fail=fault==6;
      if(fault==7)nan_cap=false;
      radio_run(fault==8); /* flush real START response */
      if(fault>=9) {
       assert(state(o).radio.phase==MISHARE_RADIO_UP);
       radio_queue_fail=fault==9;
       int ret=mishare_runtime_destroy(&o);assert(ret==(fault==9?-EUCLEAN:-EINPROGRESS));
       if(fault>=10) {
        radio_stop_fail=fault==10;radio_run(fault==11);
        if(fault>=12) {
         if(fault==12) {mishare_events_notify(&psoc,7,MISHARE_TXN_STOP,MISHARE_EVENT_TIMEOUT,false);struct vdev_stop_response rsp={7};assert(passthru_radio_stop_rsp(last_vdev->mlme,&rsp)!=QDF_STATUS_SUCCESS);}
         else {assert(radio_reply_stop()==QDF_STATUS_SUCCESS);radio_down_fail=fault==13;radio_run(fault==14);}
        }
       }
      }
     }
    }
   }
   while(radio_q_len)radio_run(false);
   assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && mishare_runtime_destroy(&o)==-EUCLEAN && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls && last_vdev->refs==6);
   if(fault==13)assert(!state(o).radio.down_accepted && ch_state==WLAN_VDEV_S_STOP);
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_OWNED_RADIO_LIFECYCLE_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    src=plan.fixture(root)
    # Replace only the older dormant radio API stubs with real production C.
    start=src.index('/* RADIO_TRANSPORT_STUBS */');end=src.index('/* END_RADIO_TRANSPORT_STUBS */',start)+len('/* END_RADIO_TRANSPORT_STUBS */')
    src=src[:start]+src[end:]
    src=src.replace('struct vdev_response_timer {int unused;};','struct vdev_response_timer {int expire_time,timer_status;};')
    src=src.replace('struct wlan_lmac_if_mlme_rx_ops {','struct vdev_start_response;struct vdev_stop_response;\nstruct wlan_lmac_if_mlme_rx_ops {')
    src=src.replace('struct vdev_response_timer *(*psoc_get_vdev_response_timer_info)(struct wlan_objmgr_psoc*,u8);','struct vdev_response_timer *(*psoc_get_vdev_response_timer_info)(struct wlan_objmgr_psoc*,u8);\n QDF_STATUS (*vdev_mgr_start_response)(struct wlan_objmgr_psoc*,struct vdev_start_response*);\n QDF_STATUS (*vdev_mgr_stop_response)(struct wlan_objmgr_psoc*,struct vdev_stop_response*);')
    src=src.replace('rxops={legacy_response,get_response_timer};','rxops={.vdev_mgr_delete_response=legacy_response,.psoc_get_vdev_response_timer_info=get_response_timer};')
    src=src.replace('assert(p && id==7);return &response_timer;','assert(p);return id==7?&response_timer:NULL;')
    src=src.replace('struct {unsigned he_ops;} he_ops_info;} proto;','struct {unsigned he_ops;} he_ops_info;struct {unsigned assoc_id;} sta;} proto;')
    defs=(root/RXDEFS).read_text();param=(root/'qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h').read_text()
    structs='\n'.join(re.search(r'struct '+n+r'\s*\{.*?\};',defs,re.S)[0] for n in ['vdev_start_response','vdev_stop_response'])
    enums=re.search(r'typedef enum \{\s*/\* Event response of START CMD \*/.*?\} WMI_HOST_START_EVENT_PARAM;',param,re.S)[0]
    enums+=re.search(r'enum wlan_mlme_host_vdev_start_status\s*\{.*?\};',(root/TXDEFS).read_text(),re.S)[0]
    tx=(root/TX).read_text();rx=(root/RX).read_text();mlme=(root/MLME).read_text()
    native_tx='\n'.join(function(tx,n) for n in ['target_if_vdev_mgr_start_send','target_if_vdev_mgr_stop_send','target_if_vdev_mgr_down_send'])
    native_rx='\n'.join(function(rx,n) for n in ['target_if_vdev_mgr_start_response_handler','target_if_vdev_mgr_stop_response_handler'])
    pm=plan.channel.pe.ctx.block(tx,'radio_pm')
    pm=pm.replace('#include "wlan_hdd_mishare_ndi.h"\n','').replace('#include <wlan_vdev_mlme_api.h>\n','')
    fallback='\n'.join(function(mlme,n) for n in ['passthru_mlme_reject_2','passthru_mlme_reject_3','passthru_mlme_reject_4','passthru_mlme_reject_5'])
    fallback+='\n'+plan.channel.pe.ctx.block(mlme,'radio_wrappers')
    native=STUBS.replace('NATIVE_RESPONSE_DEFS',structs).replace('NATIVE_RESPONSE_ENUMS',enums).replace('NATIVE_TX_FUNCTIONS',native_tx).replace('NATIVE_RX_FUNCTIONS',native_rx).replace('NATIVE_PM_RELEASE',pm).replace('NATIVE_MON_UP',function((root/UTIL).read_text(),'wma_mon_mlme_vdev_up_send')).replace('NATIVE_WMA_HELPERS',plan.channel.pe.ctx.block((root/plan.WMA).read_text(),'radio_wma')).replace('NATIVE_PREPARE',plan.channel.pe.ctx.block((root/plan.API).read_text(),'radio_prepare')).replace('NATIVE_FALLBACK_WRAPPERS',fallback)
    return src[:src.index('int main(void) {')]+native+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=plan.channel.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'radio.c').write_text(source);exe=d/'radio'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'radio.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_OWNED_RADIO_LIFECYCLE_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    names=['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h','wlan_hdd_mishare_radio_mlme.h','wlan_hdd_mishare_events.c','wlan_hdd_mishare_txn.c']
    return {'status':out.strip(),'source_commit':plan.channel.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [TX,RX,MLME,plan.WMA,plan.API,UTIL]},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},'native_sm_source_sha256':hashlib.sha256((root/SM).read_bytes()).hexdigest(),'checks':['runtime START requires completed owned plan and binds an extra VDEV reference','complete native target-if START/STOP/DOWN TX and START/STOP response handlers execute','real registry handles early replies before submission returns','native NDI host-only UP validates exact context and releases START PM without WMI UP','STOP response alone never permits PE/peer/VDEV/DP deletion','accepted DOWN and native PM release precede final INIT and teardown','MC request flush/cancel/queue/allocation/reference failures','START/STOP timeout and generic native send error quarantine','DOWN send failure publishes no DOWN_COMPLETE','response copy/queue/worker references prevent early parent release','native nested callbacks use the non-locking SM API only while model SM lock is held','unbound dedicated callbacks remain unsupported'],'limitations':'Production runtime/radio/registry/transaction, complete native target-if TX/RX functions, owned WMA wrappers, native monitor NDI UP helper and native PM helper execute under ASan/UBSan. Native vdev core send wrappers, scheduler/SM/IRQ primitives, full WMA START postprocessing, TLV extraction, policy/regulatory, object manager and DP are models. The full native SM is compiled in WLAN, not executed here. Real radio, concurrency reservation, firmware acceptance, data queues, SSR/remove recovery and phone loading are unverified. No default HDD/Wonder runtime caller is enabled.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
