#!/usr/bin/env python3
"""Actions-only ASan/UBSan execution of the actual dormant HDD host helper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_idle_origins import remove_idle_additions
from mishare_parent_origins import remove_parent_additions
from mishare_ssr_stop_origins import remove_ssr_stop_additions

ROOT = Path(__file__).resolve().parents[2]
COMMON = r'''
#ifndef FIXTURE_H
#define FIXTURE_H
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sys/wait.h>
#include <unistd.h>
/* Kernel sources use errno as a local variable, unlike libc. */
#undef errno
typedef uint8_t u8;
typedef uint32_t u32;
typedef u8 tSirMacAddr[6];
#define ETH_ALEN 6
#define GFP_KERNEL 0
#define QDF_PASSTHRU_MODE 17
#define NET_NAME_UNKNOWN 0
#define DEVICE_IFACE_OPENED 1
#define SME_SESSION_OPENED 2
#define ASSERT_RTNL() assert(rtnl_owned)
#define WARN_ON(x) (x)
#define hdd_err(...) ((void)0)
#define hdd_info(...) ((void)0)
#define hdd_err_rl(...) ((void)0)
#define hdd_enter() ((void)0)
#define hdd_exit() ((void)0)
#define DEFINE_SPINLOCK(n) pthread_mutex_t n = PTHREAD_MUTEX_INITIALIZER
#define spin_lock_irqsave(n, f) do { (f)=0;assert(!pthread_mutex_lock(n)); } while(0)
#define spin_unlock_irqrestore(n, f) do { (void)(f);assert(!pthread_mutex_unlock(n)); } while(0)
struct device { int refs; };
struct wlan_objmgr_psoc { int refs; };
struct wireless_dev { int dummy; };
struct net_device { bool running; struct wireless_dev *ieee80211_ptr; };
struct link_info { unsigned long link_flags[1]; };
struct qdf_mac_addr { u8 bytes[6]; };
struct wlan_objmgr_pdev { int refs; struct wlan_objmgr_psoc *psoc; };
struct hdd_context { struct device *parent_dev; struct wlan_objmgr_psoc *psoc; struct wlan_objmgr_pdev *pdev; bool is_scheduler_suspended,is_wiphy_suspended,hdd_wlan_suspended; int driver_status; };
bool mishare_wonder_host_psoc_busy(struct wlan_objmgr_psoc *psoc);
struct hdd_adapter { struct net_device *dev; struct link_info *deflink; unsigned long event_flags; int device_mode; struct qdf_mac_addr mac_addr; unsigned long pause_map; };
struct hdd_adapter_create_param { int num_sessions; };
struct osif_vdev_sync { int id; };
static bool rtnl_owned=true, parent_owned=true, identity_refusal_expected;
static bool rtnl_contended, native_idle_active, idle_retirement_expected;
static int rtnl_attempts;
static struct wlan_objmgr_psoc *expected_psoc;
static int failure, validations, closed, dp_destroyed;
static int device_pins, psoc_pins, pdev_pins, runtime_tokens;
#define WLAN_HDD_ID_OBJ_MGR 9
#define QDF_STATUS_SUCCESS 0
static void pins_live(void) { assert(device_pins==1 && psoc_pins==1 && pdev_pins==1 && "EXPECTED_PARENT_PINS"); }
static void pins_empty(void) { assert(!device_pins && !psoc_pins && !pdev_pins && "EXPECTED_PARENT_UNPIN"); }
static char trace[256];
static struct hdd_adapter *active;
static struct osif_vdev_sync *registered;
bool mishare_wonder_host_adapter_owned(struct hdd_adapter *adapter);
static const u8 mac[6]={2,3,4,5,6,7};
static void event(char c) { size_t n=strlen(trace);assert(n+1<sizeof(trace));trace[n]=c;trace[n+1]=0; }
static void reset(int fail) { assert(!runtime_tokens);pins_empty();assert(!active && !registered);assert(!expected_psoc || !mishare_wonder_host_psoc_busy(expected_psoc));failure=fail;trace[0]=0; }
static struct device *get_device(struct device *d) { assert(d);event('G');if(failure==6)return NULL;d->refs++;device_pins++;return d; }
static void put_device(struct device *d) { assert(d && d->refs==1 && !psoc_pins && !pdev_pins && "EXPECTED_PARENT_RELEASE_ORDER");event('g');d->refs--;device_pins--; }
static int wlan_objmgr_psoc_try_get_ref(struct wlan_objmgr_psoc *p,int id) { assert(p && id==9 && device_pins==1);event('Q');if(failure==7)return 1;p->refs++;psoc_pins++;return 0; }
static void wlan_objmgr_psoc_release_ref(struct wlan_objmgr_psoc *p,int id) { assert(p && p->refs==1 && id==9 && !pdev_pins && device_pins==1 && "EXPECTED_PARENT_RELEASE_ORDER");event('q');p->refs--;psoc_pins--; }
static int wlan_objmgr_pdev_try_get_ref(struct wlan_objmgr_pdev *p,int id) { assert(p && id==9 && device_pins==1 && psoc_pins==1);event('B');if(failure==8)return 1;p->refs++;pdev_pins++;return 0; }
static void wlan_objmgr_pdev_release_ref(struct wlan_objmgr_pdev *p,int id) { pins_live();assert(p && p->refs==1 && id==9);event('b');p->refs--;pdev_pins--; }
static struct wlan_objmgr_psoc *wlan_pdev_get_psoc(struct wlan_objmgr_pdev *p) { pins_live();return failure==9?NULL:p->psoc; }
static bool is_valid_ether_addr(const u8 *a) { u8 v=0;for(int i=0;i<6;i++)v|=a[i];return v && !(a[0]&1); }
static void ether_addr_copy(u8 *d,const u8 *s) { memcpy(d,s,6); }
static void *kzalloc(size_t n,int flags) { (void)flags;event('A');return failure==1?NULL:calloc(1,n); }
static void kfree(void *p) { pins_empty();event('F');free(p); }
static bool test_bit(unsigned n,const unsigned long *p) { return !!(*p & (1UL<<n)); }
static bool netif_running(struct net_device *d) { return d->running; }
static void osif_psoc_sync_assert_trans_protected(struct device *d) { assert(d && parent_owned);event('P'); }
static bool rtnl_trylock(void) { assert(parent_owned);rtnl_attempts++;if(rtnl_contended || rtnl_owned)return false;rtnl_owned=true;return true; }
static void rtnl_unlock(void) { assert(parent_owned && rtnl_owned);rtnl_owned=false; }
static void idle_cleanup_boundary(void) { assert((!native_idle_active || idle_retirement_expected) && "EXPECTED_IDLE_OWNERSHIP"); }
static int wlan_hdd_validate_context(struct hdd_context *h) { assert(h && !identity_refusal_expected && "EXPECTED_PARENT_IDENTITY");validations++;event('V');return failure==4?-ENODEV:0; }
static struct hdd_adapter *hdd_get_adapter(struct hdd_context *h,int mode) { assert(h && mode==17);event('L');return failure==5?(struct hdd_adapter*)1:active; }
static int osif_vdev_sync_create(struct device *d,struct osif_vdev_sync **s) { assert(d && parent_owned && mishare_wonder_host_psoc_busy(expected_psoc));pins_live();assert(!mishare_wonder_host_adapter_owned(NULL) && "EXPECTED_NULL_ADAPTER_QUERY");event('S');if(failure==2)return -ENOMEM;*s=calloc(1,sizeof(**s));return 0; }
static void osif_vdev_sync_destroy(struct osif_vdev_sync *s) { assert(s && s!=registered && mishare_wonder_host_psoc_busy(expected_psoc));pins_live();event('D');free(s); }
static void osif_vdev_sync_register(struct net_device *d,struct osif_vdev_sync *s) { assert(d && s && !registered);registered=s;event('R'); }
static struct osif_vdev_sync *osif_vdev_sync_unregister(struct net_device *d) { assert(d);struct osif_vdev_sync *s=registered;registered=NULL;pins_live();event('U');return s; }
static void osif_vdev_sync_wait_for_ops(struct osif_vdev_sync *s) { assert(s && !registered);pins_live();event('W'); }
static void hdd_close_adapter(struct hdd_context *h,struct hdd_adapter *a,bool locked) { assert(h && a==active && locked && rtnl_owned);assert(!expected_psoc || mishare_wonder_host_psoc_busy(h->psoc));if(expected_psoc)pins_live();event('C');free(a->dev);free(a->deflink);free(a);active=NULL;closed++; }
static void hdd_cleanup_adapter(struct hdd_context *h,struct hdd_adapter *a,bool locked) { hdd_close_adapter(h,a,locked); }
static void qdf_copy_macaddr(struct qdf_mac_addr *d,const struct qdf_mac_addr *s) { memcpy(d,s,sizeof(*d)); }
static void ucfg_dp_destroy_intf(void *p,struct qdf_mac_addr *a) { assert(p && !memcmp(a->bytes,mac,6));event('X');dp_destroyed++; }
#include "wlan_hdd_mishare_runtime.h"
struct mishare_runtime_owner { int dummy; };
static int runtime_busy,runtime_closed,runtime_error;
static struct wlan_objmgr_psoc *runtime_registry_psoc;
bool mishare_runtime_psoc_busy(struct wlan_objmgr_psoc *p) {assert(parent_owned);return p && p==runtime_registry_psoc;}
static bool runtime_ssr,batch_extra;
static int batch_rc,batch_calls;
static bool cds_is_driver_recovering(void) { return runtime_ssr; }
int mishare_runtime_reclaim_batch(struct wlan_objmgr_psoc *psoc,struct mishare_runtime_reclaim_item *items,unsigned count) {
 if(active)pins_live();else pins_empty();assert(psoc==expected_psoc && parent_owned && rtnl_owned && runtime_ssr && "EXPECTED_HANDOFF_SSR_ADMISSION");
 assert(count<=1 && (count ? items && items[0].owner : !items));batch_calls++;
 if(batch_extra || (!count && (runtime_tokens || runtime_registry_psoc==psoc)))return -EBUSY;
 if(batch_rc) {if(count)items[0].result=batch_rc;return batch_rc;}
 if(count) {assert(runtime_tokens==1);runtime_tokens--;free(items[0].owner);items[0].owner=NULL;items[0].result=0;runtime_closed++;}
 return 0;
}
int mishare_runtime_create(struct wlan_objmgr_pdev *pdev,const u8 *address,void *osif,struct wireless_dev *wdev,struct mishare_runtime_owner **owner) { pins_live();assert(pdev && pdev->refs==1 && address && osif && wdev);if(*owner)return -EBUSY;*owner=calloc(1,sizeof(**owner));runtime_tokens++;return 0; }
int mishare_runtime_destroy(struct mishare_runtime_owner **owner) { idle_cleanup_boundary();pins_live();if(!*owner)return 0;if(runtime_ssr)return -EUCLEAN;if(runtime_error)return runtime_error;if(runtime_busy)return -EINPROGRESS;assert(runtime_tokens==1);runtime_tokens--;free(*owner);*owner=NULL;runtime_closed++;return 0; }
int mishare_runtime_snapshot(struct mishare_runtime_owner *o,struct mishare_runtime_status *s) { (void)o;(void)s;return -EOPNOTSUPP; }
int mishare_runtime_ndi_create(struct mishare_runtime_owner *o,u8 a,u8 b) { (void)o;(void)a;(void)b;return -EOPNOTSUPP; }
int mishare_runtime_ndi_prepare(struct mishare_runtime_owner *o) { (void)o;return -EOPNOTSUPP; }
int mishare_runtime_ndi_session(struct mishare_runtime_owner *o) { (void)o;return -EOPNOTSUPP; }
int mishare_runtime_ndi_channel(struct mishare_runtime_owner *o,u32 f) { (void)o;(void)f;return -EOPNOTSUPP; }
int mishare_runtime_ndi_start_plan(struct mishare_runtime_owner *o) { (void)o;return -EOPNOTSUPP; }
int mishare_runtime_ndi_start(struct mishare_runtime_owner *o) { (void)o;return -EOPNOTSUPP; }
static struct hdd_adapter *__hdd_open_adapter(struct hdd_context *,uint8_t,const char *,tSirMacAddr,unsigned char,bool,struct hdd_adapter_create_param *,bool);
#endif
'''
IDLE_MODELS = r'''
struct osif_psoc_sync { int dummy; };
static struct osif_psoc_sync idle_sync;
static char idle_trace[64];
static bool idle_trans_failure, idle_open;
static int idle_stop_result;
static struct hdd_context *mode_context;
static bool is_mode_change_psoc_idle_shutdown, mode_ftm;
enum QDF_GLOBAL_MODE {MODE_CURRENT,MODE_REQUESTED};
struct bbm_params {int token;};
static bool is_con_mode_valid(enum QDF_GLOBAL_MODE mode) {return mode==MODE_CURRENT || mode==MODE_REQUESTED;}
static enum QDF_GLOBAL_MODE hdd_get_conparam(void) {return MODE_CURRENT;}
#define QDF_MODULE_ID_HDD 11
static void *cds_get_context(int id) {assert(id==QDF_MODULE_ID_HDD);return mode_context;}
#define QCA_WLAN_IDLE_SHUTDOWN_STARTED 1
#define QCA_WLAN_IDLE_SHUTDOWN_COMPLETED 2
static void idle_event(char c) {size_t n=strlen(idle_trace);assert(n+1<sizeof(idle_trace));idle_trace[n]=c;idle_trace[n+1]=0;}
static void hdd_reg_wait_for_country_change(struct hdd_context *h) {assert(h);idle_event('C');}
static void wlan_hdd_send_idle_shutdown_event(struct hdd_context *h,int e) {assert(h);idle_event(e==1?'B':'E');}
static int osif_psoc_sync_trans_start(struct device *d,struct osif_psoc_sync **s) {assert(d && !parent_owned);idle_event('S');if(idle_trans_failure)return -EBUSY;parent_owned=true;*s=&idle_sync;return 0;}
static void osif_psoc_sync_wait_for_ops(struct osif_psoc_sync *s) {assert(s==&idle_sync && parent_owned);idle_event('W');}
static void osif_psoc_sync_trans_stop(struct osif_psoc_sync *s) {assert(s==&idle_sync && parent_owned);idle_event('T');parent_owned=false;}
static bool hdd_is_any_interface_open(struct hdd_context *h) {assert(h && parent_owned);idle_event('I');return idle_open;}
static int hdd_wlan_stop_modules(struct hdd_context *h,bool ftm) {assert(h && parent_owned && !mishare_wonder_host_psoc_busy(h->psoc) && !mishare_runtime_psoc_busy(h->psoc) && "EXPECTED_STOP_ADMISSION");mode_ftm=ftm;idle_event('M');return idle_stop_result;}
NATIVE_IDLE
static void idle_check(struct hdd_context *h,int rc,const char *trace) {
 assert(parent_owned && rtnl_owned);parent_owned=false;rtnl_owned=false;idle_trace[0]=0;
 native_idle_active=true;
 int actual=__hdd_psoc_idle_shutdown(h);native_idle_active=false;
 assert(!rtnl_owned && "EXPECTED_IDLE_UNLOCK");
 assert(actual==rc && !parent_owned && !strcmp(idle_trace,trace) && "EXPECTED_IDLE_RESULT");
 parent_owned=true;rtnl_owned=true;
}
'''

RESET_MODELS = r'''
static int handoff_from_temporary(struct mishare_wonder_host **owner);
#undef QDF_STATUS_SUCCESS
NATIVE_QDF_STATUS
#define hdd_debug(...) ((void)0)
#define QDF_STA_MODE 0
#define QDF_P2P_CLIENT_MODE 1
#define QDF_SAP_MODE 2
#define WMM_INIT_DONE 3
#define WLAN_DATA_FLOW_CONTROL 4
#define WLAN_CONTROL_PATH 5
#define WLAN_STOP_ALL_NETIF_QUEUE 20
#define WLAN_STOP_ALL_NETIF_QUEUE_N_CARRIER 21
#define WLAN_START_ALL_NETIF_QUEUE 22
#define WLAN_OSIF_TDLS_ID 23
#define NET_DEV_HOLD_RESET_ALL_ADAPTERS 31
#define wlan_hdd_link_info link_info
struct wlan_objmgr_vdev {int dummy;};
static struct wlan_objmgr_vdev reset_vdev;
static struct hdd_adapter *reset_slots[5],*reset_current;
static int reset_refs[5],reset_stops[5],reset_index,reset_holds,reset_puts;
static int reset_vdev_refs,reset_vdev_gets,reset_tdls,reset_twt,reset_stop_only,reset_stop_carrier,reset_start_queue;
static bool reset_sap_restart,reset_vdev_present;
static int reset_slot(struct hdd_adapter *a) {for(int i=0;i<5;i++)if(reset_slots[i]==a)return i;abort();}
static void reset_hold(struct hdd_adapter *a) {if(a){int i=reset_slot(a);assert(!reset_refs[i]);reset_refs[i]++;reset_holds++;}}
static void reset_begin(struct hdd_context *h,struct hdd_adapter **a,struct hdd_adapter **n,int id) {
 assert(h && parent_owned && id==31);reset_index=0;*a=reset_slots[0];*n=reset_slots[1];reset_hold(*a);reset_hold(*n);
}
static void reset_advance(struct hdd_adapter **a,struct hdd_adapter **n,int id) {
 assert(id==31 && !reset_refs[reset_slot(*a)] && "EXPECTED_RESET_ITERATOR_BALANCE");
 *a=*n;reset_index++;*n=reset_index+1<5?reset_slots[reset_index+1]:NULL;reset_hold(*n);
}
static void hdd_adapter_dev_put_debug(struct hdd_adapter *a,int id) {int i=reset_slot(a);assert(id==31 && reset_refs[i]==1 && "EXPECTED_RESET_ITERATOR_BALANCE");reset_refs[i]--;reset_puts++;}
#define hdd_for_each_adapter_dev_held_safe(h,a,n,id) for(reset_begin(h,&(a),&(n),id);(a);reset_advance(&(a),&(n),id))
#define hdd_adapter_for_each_active_link_info(a,l) for((l)=(a)->deflink;(l);(l)=NULL)
static void ucfg_mlme_get_sap_internal_restart(struct wlan_objmgr_psoc *p,bool *v) {assert(p==expected_psoc);*v=reset_sap_restart;}
static void hdd_adapter_abort_tx_flow(struct hdd_adapter *a) {assert(!mishare_wonder_host_adapter_owned(a) && "EXPECTED_PRIVATE_RESET_SKIP");reset_current=a;}
static void hdd_send_twt_del_all_sessions_to_userspace(struct link_info *l) {assert(l==reset_current->deflink);reset_twt++;}
static struct wlan_objmgr_vdev *hdd_objmgr_get_vdev_by_user(struct link_info *l,int id) {assert(l==reset_current->deflink && id==23);reset_vdev_gets++;if(!reset_vdev_present)return NULL;reset_vdev_refs++;return &reset_vdev;}
static void hdd_notify_tdls_reset_adapter(struct wlan_objmgr_vdev *v) {assert(v==&reset_vdev && reset_vdev_refs==1);reset_tdls++;}
static void hdd_objmgr_put_vdev_by_user(struct wlan_objmgr_vdev *v,int id) {assert(v==&reset_vdev && id==23 && reset_vdev_refs==1);reset_vdev_refs--;}
static void hdd_medium_assess_ssr_enable_flag(void) {assert(reset_current->device_mode==2 && reset_sap_restart);}
static void wlan_hdd_netif_queue_control(struct hdd_adapter *a,int op,int reason) {
 assert(a==reset_current && !mishare_wonder_host_adapter_owned(a));
 if(op==22){assert(reason==4);reset_start_queue++;}
 else {assert(reason==5);if(op==20)reset_stop_only++;else{assert(op==21);reset_stop_carrier++;}}
}
static void hdd_reset_scan_operation(struct link_info *l) {assert(l==reset_current->deflink);}
static void hdd_wmm_adapter_close(struct hdd_adapter *a) {assert(a==reset_current);}
static void clear_bit(unsigned bit,unsigned long *flags) {*flags &= ~(1UL<<bit);}
static void hdd_stop_adapter(struct hdd_context *h,struct hdd_adapter *a) {assert(h && a==reset_current);reset_stops[reset_slot(a)]++;}
NATIVE_RESET
#undef hdd_for_each_adapter_dev_held_safe
#undef hdd_adapter_for_each_active_link_info
#undef wlan_hdd_link_info

static void reset_matrix_one(struct hdd_context *h,struct hdd_adapter *private,int position,bool restart,bool vdev,bool owned)
{
 struct hdd_adapter ordinary[4]={0};struct net_device netdev[4]={0};struct link_info links[4]={0};
 int modes[4]={QDF_STA_MODE,QDF_P2P_CLIENT_MODE,QDF_SAP_MODE,QDF_PASSTHRU_MODE};
 assert(private && mishare_wonder_host_adapter_owned(private)==owned && "EXPECTED_ADAPTER_OWNER_QUERY");
 for(int i=0;i<4;i++) {ordinary[i].dev=&netdev[i];ordinary[i].deflink=&links[i];ordinary[i].device_mode=modes[i];ordinary[i].event_flags=(1UL<<WMM_INIT_DONE)|0x100;ordinary[i].pause_map=1UL<<WLAN_DATA_FLOW_CONTROL;}
 memcpy(ordinary[3].mac_addr.bytes,private->mac_addr.bytes,6);
 assert(!mishare_wonder_host_adapter_owned(&ordinary[3]) && "EXPECTED_ADAPTER_OWNER_QUERY");
 for(int i=0,j=0;i<5;i++)reset_slots[i]=i==position?private:&ordinary[j++];
 memset(reset_refs,0,sizeof(reset_refs));memset(reset_stops,0,sizeof(reset_stops));
 reset_holds=reset_puts=reset_vdev_refs=reset_vdev_gets=reset_tdls=reset_twt=reset_stop_only=reset_stop_carrier=reset_start_queue=0;
 reset_sap_restart=restart;reset_vdev_present=vdev;unsigned long flags=private->event_flags;
 assert(parent_owned && rtnl_owned);rtnl_owned=false;
 assert(hdd_reset_all_adapters(h)==QDF_STATUS_SUCCESS);rtnl_owned=true;
 for(int i=0;i<5;i++) {
  assert(!reset_refs[i] && "EXPECTED_RESET_ITERATOR_BALANCE");
  if(i==position && owned)assert(!reset_stops[i] && private->event_flags==flags && "EXPECTED_PRIVATE_RESET_SKIP");
  else assert(reset_stops[i]==1 && reset_slots[i]->event_flags==0x100 && "EXPECTED_UNOWNED_RESET");
 }
 assert(reset_holds==5 && reset_puts==5 && !reset_vdev_refs && "EXPECTED_RESET_ITERATOR_BALANCE");
 assert(reset_vdev_gets==2 && reset_tdls==(vdev?2:0) && reset_twt==2 && reset_stop_only==(restart?1:0) && reset_stop_carrier==((owned?4:5)-(restart?1:0)) && reset_start_queue==(owned?4:5) && "EXPECTED_UNOWNED_RESET");
 reset_current=NULL;memset(reset_slots,0,sizeof(reset_slots));
}
static void reset_owned_cases(struct hdd_context *h,struct wireless_dev *wdev)
{
 assert(!mishare_wonder_host_adapter_owned(NULL) && "EXPECTED_NULL_ADAPTER_QUERY");
 for(int state=0;state<4;state++) {
  struct mishare_wonder_host *owner=NULL;reset(0);assert(!mishare_wonder_host_create_locked(h,mac,&owner));
  active->dev->ieee80211_ptr=wdev;
  if(state)assert(!mishare_wonder_host_vdev_create_locked(owner));
  if(state==2){runtime_busy=1;assert(mishare_wonder_host_destroy_locked(&owner)==-EINPROGRESS);runtime_busy=0;}
  bool handed=state==3;if(handed)assert(!handoff_from_temporary(&owner));
  struct hdd_adapter *private=active;
  if(state==1) {
   pid_t child=fork();assert(child>=0);
   if(!child){runtime_error=-EUCLEAN;assert(mishare_wonder_host_destroy_locked(&owner)==-EUCLEAN);runtime_ssr=true;reset_matrix_one(h,private,2,true,true,true);pins_live();_Exit(0);}
   int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
  }
  runtime_ssr=true;
  if(handed){batch_rc=-EINPROGRESS;assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EINPROGRESS);batch_rc=0;}
  for(int pos=0;pos<3;pos++)for(int sap=0;sap<2;sap++)for(int v=0;v<2;v++) {trace[0]=0;reset_matrix_one(h,private,pos*2,sap,v,true);pins_live();}
  trace[0]=0;if(handed)assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));else assert(!mishare_wonder_host_reclaim_ssr_locked(&owner));
  runtime_ssr=false;assert(!active && !registered);pins_empty();
 }
 /* With an empty host registry all adapters, including PAS, keep native reset. */
 struct net_device dev={0};struct link_info link={0};struct hdd_adapter unowned={.dev=&dev,.deflink=&link,.device_mode=QDF_PASSTHRU_MODE,.pause_map=1UL<<WLAN_DATA_FLOW_CONTROL};
 runtime_ssr=true;
 for(int pos=0;pos<3;pos++)for(int sap=0;sap<2;sap++)for(int v=0;v<2;v++) {unowned.event_flags=(1UL<<WMM_INIT_DONE)|0x100;reset_matrix_one(h,&unowned,pos*2,sap,v,false);}
 reset_holds=reset_puts=0;rtnl_owned=false;assert(!hdd_reset_all_adapters(h));rtnl_owned=true;
 assert(!reset_holds && !reset_puts);runtime_ssr=false;
}
'''

SSR_STOP_MODELS = r'''
#ifndef ERESTARTSYS
#define ERESTARTSYS 512
#endif
#define DRIVER_MODULES_CLOSED 2
#define QDF_IS_STATUS_SUCCESS(s) ((s)==QDF_STATUS_SUCCESS)
#define QDF_MODULE_ID_SOC 70
#define QDF_MODULE_ID_HIF 71
#define QDF_MONITOR_MODE 36
#define QDF_SYSTEM_SUSPEND 1
#define OL_TXRX_PDEV_ID 0
#define PACKET_CAPTURE_MODE_DISABLE 0
#define WLAN_OSIF_POWER_ID 24
NATIVE_QDF_FROM_OS
NATIVE_SSR_STATE
NATIVE_MODULE_STATE
static struct hdd_context *ssr_ctx;
static int ssr_soc_cookie,ssr_hif_cookie;
static bool ssr_hif_missing,ssr_soc_present,ssr_epping,ssr_ipa,ssr_capture,ssr_monitor_present,ssr_vdev_present;
static bool ssr_qualification_ready,ssr_unloading,ssr_lookup_missing,ssr_resume_tail_expected;
static struct device *ssr_transition_dev;
static int ssr_smmu_completions;
static QDF_STATUS ssr_post_status;
static int ssr_stop_force,ssr_after_retire_force,ssr_last_stop_error,ssr_qualified_wait,ssr_module_prefixes;
static int ssr_post_calls,ssr_parent_closes,ssr_tail,ssr_asserts,ssr_masks,ssr_isr_stops,ssr_cleanup_calls;
static int ssr_inner_reinits,ssr_inner_result,ssr_start_status,ssr_start_calls,ssr_resume_calls;
static int ssr_ipa_forces,ssr_scheduler_resumes,ssr_capture_resumes,ssr_power_vdev_refs;
static int is_recovery_cleanup_done;
static struct hdd_adapter ssr_monitor;
static struct link_info ssr_monitor_link;
struct hif_bus_id {int dummy;};
enum qdf_bus_type {SSR_IPCI=1};
#define QDF_BUG(x) do {if(!(x))ssr_asserts++;} while(0)
#define QDF_ASSERT(x) do {if(!(x))ssr_asserts++;} while(0)
#define QDF_IS_EPPING_ENABLED(x) (x)
static void *ssr_get_context(int id) {if(id==11)return ssr_lookup_missing?NULL:ssr_ctx;if(id==70)return ssr_soc_present?&ssr_soc_cookie:NULL;assert(id==71);return ssr_hif_missing?NULL:&ssr_hif_cookie;}
static bool ucfg_ipa_is_enabled(void) {return ssr_ipa;}
static void ucfg_ipa_uc_force_pipe_shutdown(struct wlan_objmgr_pdev *p) {assert(p==ssr_ctx->pdev);ssr_ipa_forces++;}
static bool pld_is_fw_rejuvenate(struct device *d) {assert(d==ssr_ctx->parent_dev);return true;}
static bool pld_is_pdr(struct device *d) {assert(d==ssr_ctx->parent_dev);return false;}
static void ucfg_ipa_fw_rejuvenate_send_msg(struct wlan_objmgr_pdev *p) {assert(p==ssr_ctx->pdev);}
static void hdd_set_connection_in_progress(bool value) {assert(!value);}
static void wlan_deregister_txrx_packetdump(int id) {assert(!id);}
static void scheduler_resume(void) {ssr_scheduler_resumes++;}
static void ucfg_pmo_resume_all_components(struct wlan_objmgr_psoc *p,int why) {assert(p==ssr_ctx->psoc && why==1);}
static void wlan_hdd_rx_thread_resume(struct hdd_context *h) {assert(h==ssr_ctx);}
static int ucfg_pkt_capture_get_mode(struct wlan_objmgr_psoc *p) {assert(p==ssr_ctx->psoc);return ssr_capture;}
static struct hdd_adapter *ssr_monitor_get(struct hdd_context *h,int mode) {assert(h==ssr_ctx && mode==36);return ssr_monitor_present?&ssr_monitor:NULL;}
static struct wlan_objmgr_vdev *ssr_power_vdev_get(struct link_info *l,int id) {assert(l==&ssr_monitor_link && id==24);if(!ssr_vdev_present)return NULL;ssr_power_vdev_refs++;return &reset_vdev;}
static void ssr_power_vdev_put(struct wlan_objmgr_vdev *v,int id) {assert(v==&reset_vdev && id==24 && ssr_power_vdev_refs==1);ssr_power_vdev_refs--;}
static void ucfg_pkt_capture_resume_mon_thread(struct wlan_objmgr_vdev *v) {assert(v==&reset_vdev && ssr_power_vdev_refs==1);ssr_capture_resumes++;}
static void ucfg_ipa_uc_ssr_cleanup(struct wlan_objmgr_pdev *p) {assert(p==ssr_ctx->pdev);}
static void cdp_flush_cache_rx_queue(void *soc) {assert(soc==&ssr_soc_cookie);}
static void hdd_deregister_cb(struct hdd_context *h) {assert(h==ssr_ctx);}
static void hdd_lpass_notify_stop(struct hdd_context *h) {assert(h==ssr_ctx);if(ssr_resume_tail_expected)assert(mishare_module_stop.phase==MISHARE_SSR_STOP_EMPTY && mishare_ssr_stop_blocked && parent_owned && !rtnl_owned && "EXPECTED_POWER_ACK_ORDER");ssr_tail++;}
static void qdf_set_smmu_fault_state(bool value) {assert(!value);ssr_smmu_completions++;}
static QDF_STATUS cds_post_disable(void) {
 ssr_post_calls++;
 /* Qualification is a boundary result here; production post-disable now
  * invokes the real host wrapper and bridge rather than this stub retiring it. */
 batch_rc=QDF_IS_STATUS_SUCCESS(ssr_post_status)?(ssr_qualification_ready?ssr_qualified_wait:-EUCLEAN):-ESHUTDOWN;
 return ssr_post_status;
}
#define QDF_GLOBAL_MISSION_MODE MODE_CURRENT
static int ssr_module_mode(void) {return ssr_epping?MODE_REQUESTED:MODE_CURRENT;}
#define hdd_get_conparam ssr_module_mode
static int ssr_stop_section(struct hdd_context *hdd_ctx,bool ftm_mode,bool mishare_resume) {
 bool is_recovery_stop=runtime_ssr;
 QDF_STATUS qdf_status;int ret=0;
 bool mishare_tracked;int mishare_gate;
 NATIVE_MODULE_BEGIN
 ssr_module_prefixes++;
 NATIVE_POST_DISABLE
 if(ssr_after_retire_force)return mishare_ssr_stop_finish_locked(&mishare_module_stop,hdd_ctx,ssr_after_retire_force,false,mishare_tracked);
 assert((!is_recovery_stop || !mishare_wonder_host_stop_ready_locked(hdd_ctx)) && "EXPECTED_PARENT_BOUNDARY");
 ssr_parent_closes++;hdd_ctx->driver_status=DRIVER_MODULES_CLOSED; /* modeled parent-close boundary */
 NATIVE_MODULE_FINISH
 return ret;
}
#undef hdd_get_conparam
#define hdd_mishare_stop_modules ssr_stop_section
NATIVE_MODULE_RESUME
#undef hdd_mishare_stop_modules
static int ssr_stop_model(struct hdd_context *h,bool ftm) {assert(h==ssr_ctx && !ftm);ssr_last_stop_error=ssr_stop_force?ssr_stop_force:ssr_stop_section(h,false,false);return ssr_last_stop_error;}
#define cds_get_context ssr_get_context
#define hdd_get_adapter ssr_monitor_get
#define hdd_objmgr_get_vdev_by_user ssr_power_vdev_get
#define hdd_objmgr_put_vdev_by_user ssr_power_vdev_put
#define hdd_wlan_stop_modules ssr_stop_model
NATIVE_POWER_COMPLETION
NATIVE_POWER_SHUTDOWN
#undef hdd_wlan_stop_modules
#undef hdd_get_adapter
#undef hdd_objmgr_get_vdev_by_user
#undef hdd_objmgr_put_vdev_by_user
static int qdf_atomic_read(int *p) {return *p;}
static void qdf_atomic_set(int *p,int v) {*p=v;}
static void hdd_soc_recovery_cleanup(void) {ssr_cleanup_calls++;}
static bool hdd_wait_for_debugfs_threads_completion(void) {return true;}
static void hif_mask_interrupt_call(void *p) {assert(p==&ssr_hif_cookie);ssr_masks++;}
static void hif_disable_isr(void *p) {assert(p==&ssr_hif_cookie);ssr_isr_stops++;}
static bool cds_get_conparam(void) {return ssr_epping;}
NATIVE_SOC_SHUTDOWN
static bool qdf_is_driver_unloading(void) {return ssr_unloading;}
static int osif_psoc_sync_trans_resume(struct device *d,struct osif_psoc_sync **s) {assert(d==(ssr_transition_dev?ssr_transition_dev:ssr_ctx->parent_dev) && parent_owned && !rtnl_owned);ssr_resume_calls++;*s=&idle_sync;return 0;}
static int __hdd_soc_recovery_reinit(struct device *dev,void *bdev,const struct hif_bus_id *bid,enum qdf_bus_type bus) {
 (void)bdev;(void)bid;assert(dev==ssr_ctx->parent_dev && "EXPECTED_CALLBACK_DEVICE");assert(bus==SSR_IPCI && parent_owned);
 if(ssr_resume_tail_expected)assert(ssr_tail==1 && ssr_smmu_completions==1 && "EXPECTED_UPPER_ACK_REQUIRED");
 assert(!mishare_ssr_stop_blocked && "EXPECTED_NO_PRIVATE_REINIT");ssr_inner_reinits++;return ssr_inner_result;
}
static void hdd_start_complete(int status) {ssr_start_status=status;ssr_start_calls++;}
NATIVE_SOC_REINIT
#undef cds_get_context
#undef QDF_BUG
#undef QDF_ASSERT

static void ssr_stop_case(struct hdd_context *h,struct wireless_dev *wdev,int kind)
{
 bool owned=(kind>=2 && kind<=8) || kind==12 || kind==13;
 bool missing=kind==5 || kind==10 || kind==13,epping=kind==6 || kind==11;
 bool retire=kind==7 || kind==8,blocked=owned && kind!=7;
 struct mishare_wonder_host *owner=NULL;
 reset(0);batch_rc=0;ssr_ctx=h;mishare_ssr_stop_blocked=false;mishare_module_stop=(struct mishare_ssr_stop_checkpoint){0};
 ssr_hif_missing=missing;ssr_soc_present=kind%2;ssr_epping=epping;
 ssr_ipa=ssr_capture=ssr_monitor_present=ssr_vdev_present=kind==12;
 h->is_scheduler_suspended=h->is_wiphy_suspended=h->hdd_wlan_suspended=kind==12;
 ssr_monitor.deflink=&ssr_monitor_link;
 ssr_qualification_ready=retire;ssr_unloading=ssr_lookup_missing=ssr_resume_tail_expected=false;ssr_transition_dev=NULL;ssr_smmu_completions=0;ssr_qualified_wait=ssr_module_prefixes=0;
 ssr_post_status=(kind==1 || kind==3)?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
 ssr_stop_force=(kind==4 || kind==9)?-EINPROGRESS:0;ssr_after_retire_force=kind==8?-EINPROGRESS:0;
 ssr_inner_result=kind==14?-EIO:0;
 ssr_post_calls=ssr_parent_closes=ssr_tail=ssr_asserts=ssr_masks=ssr_isr_stops=ssr_cleanup_calls=0;
 ssr_inner_reinits=ssr_start_calls=ssr_resume_calls=ssr_ipa_forces=ssr_scheduler_resumes=ssr_capture_resumes=ssr_power_vdev_refs=0;
 ssr_start_status=12345;is_recovery_cleanup_done=kind==13;
 if(owned){assert(!mishare_wonder_host_create_locked(h,mac,&owner));active->dev->ieee80211_ptr=wdev;assert(!mishare_wonder_host_vdev_create_locked(owner));assert(!handoff_from_temporary(&owner));}
 memset(reset_slots,0,sizeof(reset_slots));memset(reset_refs,0,sizeof(reset_refs));reset_holds=reset_puts=0;reset_slots[0]=active;
 runtime_ssr=true;rtnl_owned=false;trace[0]=0;__hdd_soc_recovery_shutdown();
 assert(parent_owned && !rtnl_owned);
 if(kind==3)assert(ssr_last_stop_error==-EINVAL && !ssr_asserts && "EXPECTED_POST_DISABLE_ERROR");
 if(kind==7)assert(!active && !mishare_ssr_stop_blocked && ssr_parent_closes==1 && "EXPECTED_NATIVE_SSR_RETIRE");
 if(kind==8)assert(mishare_ssr_stop_blocked && !ssr_parent_closes && !ssr_tail && !active && "EXPECTED_OWNER_SNAPSHOT");
 assert(mishare_ssr_stop_blocked==blocked && "EXPECTED_SSR_RETENTION");
 if(blocked)assert(!ssr_parent_closes && !ssr_tail && "EXPECTED_SSR_RETENTION");
 else if(!missing && !epping)assert(ssr_parent_closes==((kind==9)?0:1) && ssr_tail==1 && "EXPECTED_POWER_COMPLETION");
 if(kind==1)assert(ssr_asserts==1); /* preserve ordinary vendor error behavior */
 if(kind==12)assert(ssr_ipa_forces==1 && ssr_scheduler_resumes==1 && ssr_capture_resumes==1 && !ssr_power_vdev_refs && !h->is_scheduler_suspended && !h->is_wiphy_suspended && !h->hdd_wlan_suspended);
 if(owned && !missing && !epping)assert(reset_holds==1 && reset_puts==1 && !reset_refs[0]);
 if(blocked){int calls=ssr_post_calls,masks=ssr_masks,stops=ssr_isr_stops;__hdd_soc_recovery_shutdown();assert(ssr_post_calls==calls && ssr_masks==masks && ssr_isr_stops==stops && "EXPECTED_NO_STOP_REPLAY");}
 if(mishare_module_stop.phase!=MISHARE_SSR_STOP_EMPTY) {
  int calls=ssr_post_calls;assert(ssr_stop_section(h,false,false)==-EBUSY && ssr_post_calls==calls && "EXPECTED_MODULE_NO_REPLAY");
 }
 memset(reset_slots,0,sizeof(reset_slots));idle_trace[0]=0;
 int blocked_errno=(kind==4 || kind==5 || kind==13)?-ENOENT:kind==6?-EOPNOTSUPP:-EBUSY;
 int result=hdd_soc_recovery_reinit(h->parent_dev,NULL,NULL,SSR_IPCI);
 assert(result==(blocked?blocked_errno:ssr_inner_result) && ssr_inner_reinits==(blocked?0:1) && "EXPECTED_NO_PRIVATE_REINIT");
 assert(ssr_start_calls==1 && ssr_start_status==(blocked?blocked_errno:0) && "EXPECTED_SSR_FAILURE_NOTIFICATION");
 assert(parent_owned==blocked && !rtnl_owned && "EXPECTED_PRIVATE_TRANSITION_RETAINED");parent_owned=true;rtnl_owned=true;
 if(active) {
  batch_rc=0;trace[0]=0;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));pins_empty();
  assert(mishare_ssr_stop_blocked && "EXPECTED_SSR_RETENTION");
  rtnl_owned=false;idle_trace[0]=0;assert(hdd_soc_recovery_reinit(h->parent_dev,NULL,NULL,SSR_IPCI)==blocked_errno && !ssr_inner_reinits && "EXPECTED_NO_PRIVATE_REINIT");parent_owned=true;rtnl_owned=true;
 }
 assert(!active && !registered);pins_empty();runtime_ssr=false;batch_rc=0;mishare_ssr_stop_blocked=false;
}
static void ssr_prepare_cases(struct hdd_context *h,struct wireless_dev *wdev)
{
 struct mishare_wonder_host *owner=NULL,*retained;
 assert(mishare_wonder_host_ssr_prepare_locked(NULL)==-EINVAL);
 struct hdd_context bad=*h;bad.parent_dev=NULL;assert(mishare_wonder_host_ssr_prepare_locked(&bad)==-EINVAL);
 bad=*h;bad.psoc=NULL;assert(mishare_wonder_host_ssr_prepare_locked(&bad)==-EINVAL);
 assert(!mishare_wonder_host_ssr_prepare_locked(h) && "EXPECTED_SSR_PREPARE_EMPTY");
 int attempts=rtnl_attempts,batches=batch_calls;
 runtime_ssr=true;runtime_registry_psoc=h->psoc;
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-EBUSY && rtnl_attempts==attempts && batch_calls==batches && "EXPECTED_SSR_PREPARE_OWNER");runtime_registry_psoc=NULL;runtime_ssr=false;
 reset(0);assert(!mishare_wonder_host_create_locked(h,mac,&owner));active->dev->ieee80211_ptr=wdev;assert(!mishare_wonder_host_vdev_create_locked(owner));retained=owner;
 runtime_ssr=true;assert(mishare_wonder_host_ssr_prepare_locked(h)==-EBUSY && owner==retained && !owner->session.closing && rtnl_attempts==attempts && "EXPECTED_SSR_PREPARE_OWNER");runtime_ssr=false;
 assert(!handoff_from_temporary(&owner));
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-ESHUTDOWN && "EXPECTED_SSR_PREPARE_RECOVERY");runtime_ssr=true;
 struct hdd_context foreign=*h;assert(mishare_wonder_host_ssr_prepare_locked(&foreign)==-EUCLEAN && rtnl_attempts==attempts);
 struct wlan_objmgr_psoc *psoc=h->psoc,other={0};h->psoc=&other;
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-EUCLEAN && rtnl_attempts==attempts);h->psoc=psoc;
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-EAGAIN && rtnl_owned && batch_calls==batches && "EXPECTED_SSR_PREPARE_LOCK");
 rtnl_owned=false;rtnl_contended=true;
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-EAGAIN && !rtnl_owned && batch_calls==batches && "EXPECTED_SSR_PREPARE_LOCK");rtnl_contended=false;
 struct mishare_runtime_owner *token=retained->runtime;
 for(int i=0;i<3;i++) {
  batch_rc=i==0?-EINPROGRESS:i==1?-ESHUTDOWN:-EUCLEAN;trace[0]=0;
  assert(mishare_wonder_host_ssr_prepare_locked(h)==batch_rc && "EXPECTED_SSR_PREPARE_RESULT");
  assert(!rtnl_owned && "EXPECTED_SSR_PREPARE_UNLOCK");
  assert(retained->runtime==token && retained->idle_owned && active && registered);pins_live();
 }
 batch_rc=0;batch_extra=true;
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-EBUSY && "EXPECTED_SSR_PREPARE_RESULT");assert(!rtnl_owned && "EXPECTED_SSR_PREPARE_UNLOCK");batch_extra=false;
 struct osif_vdev_sync *original=registered,foreign_sync={0};registered=&foreign_sync;trace[0]=0;
 assert(mishare_wonder_host_ssr_prepare_locked(h)==-EIO && "EXPECTED_SSR_PREPARE_RESULT");
 assert(!rtnl_owned && !retained->runtime && retained->idle_owned && active && registered==&foreign_sync);pins_live();registered=original;
 trace[0]=0;assert(!mishare_wonder_host_ssr_prepare_locked(h));assert(!rtnl_owned && !active && !registered);pins_empty();
 attempts=rtnl_attempts;assert(!mishare_wonder_host_ssr_prepare_locked(h) && rtnl_attempts==attempts && "EXPECTED_SSR_PREPARE_EMPTY");runtime_ssr=false;rtnl_owned=true;
}

static void ssr_journal_cases(struct hdd_context *h,struct wireless_dev *wdev)
{
 struct mishare_ssr_stop_checkpoint empty={0};bool tracked=true;
 assert(mishare_ssr_stop_begin_locked(NULL,h,&tracked)==-EINVAL);
 assert(mishare_ssr_stop_begin_locked(&empty,h,NULL)==-EINVAL);
 assert(mishare_ssr_stop_begin_locked(&empty,NULL,&tracked)==-EINVAL && !tracked);
 runtime_ssr=false;assert(!mishare_ssr_stop_begin_locked(&empty,h,&tracked) && !tracked);
 runtime_ssr=true;assert(!mishare_ssr_stop_begin_locked(&empty,h,&tracked) && !tracked);
 assert(mishare_ssr_stop_finish_locked(&empty,h,-EIO,false,false)==-EIO);
 assert(mishare_ssr_stop_step_locked(&empty,h,MISHARE_SSR_STOP_PARENTS,-EAGAIN,false)==-EAGAIN);
 runtime_ssr=false;
 for(int kind=0;kind<8;kind++) {
  struct mishare_ssr_stop_checkpoint c={0};struct mishare_wonder_host *owner=NULL;
  struct wlan_objmgr_pdev *pdev=h->pdev,replacement={0};struct device *dev=h->parent_dev,other_dev={0};
  struct wlan_objmgr_psoc *psoc=h->psoc,other_psoc={0};
  reset(0);assert(!mishare_wonder_host_create_locked(h,mac,&owner));active->dev->ieee80211_ptr=wdev;
  assert(!mishare_wonder_host_vdev_create_locked(owner));assert(!handoff_from_temporary(&owner));
  runtime_ssr=true;batch_rc=0;tracked=false;
  assert(!mishare_ssr_stop_begin_locked(&c,h,&tracked) && tracked && c.phase==MISHARE_SSR_STOP_PREFIX && "EXPECTED_JOURNAL_ARM");
  bool again=true;assert(mishare_ssr_stop_begin_locked(&c,h,&again)==-EBUSY && !again && "EXPECTED_JOURNAL_REPLAY");
  struct hdd_context foreign=*h;assert(mishare_ssr_stop_begin_locked(&c,&foreign,&again)==-EUCLEAN && "EXPECTED_JOURNAL_IDENTITY");
  h->parent_dev=&other_dev;assert(mishare_ssr_stop_begin_locked(&c,h,&again)==-EUCLEAN && "EXPECTED_JOURNAL_IDENTITY");h->parent_dev=dev;
  h->psoc=&other_psoc;assert(mishare_ssr_stop_begin_locked(&c,h,&again)==-EUCLEAN && "EXPECTED_JOURNAL_IDENTITY");h->psoc=psoc;
  h->pdev=&replacement;assert(mishare_ssr_stop_begin_locked(&c,h,&again)==-EUCLEAN && "EXPECTED_JOURNAL_IDENTITY");h->pdev=pdev;
  if(kind==0)assert(mishare_ssr_stop_finish_locked(&c,h,-EINPROGRESS,false,tracked)==-EINPROGRESS);
  else if(kind==3)assert(mishare_ssr_stop_finish_locked(&c,h,0,true,tracked)==-EIO && "EXPECTED_JOURNAL_ACK");
  else if(kind==4)assert(mishare_ssr_stop_step_locked(&c,h,MISHARE_SSR_STOP_PARENTS,0,tracked)==-EPROTO && "EXPECTED_JOURNAL_ORDER");
  else {
   assert(!mishare_ssr_stop_step_locked(&c,h,MISHARE_SSR_STOP_POST_DISABLED,0,tracked));
   if(kind==1)assert(mishare_ssr_stop_finish_locked(&c,h,-EAGAIN,false,tracked)==-EAGAIN);
   else {
    assert(!mishare_ssr_stop_step_locked(&c,h,MISHARE_SSR_STOP_PARENTS,0,tracked));
    if(kind==2){assert(mishare_ssr_stop_step_locked(&c,h,MISHARE_SSR_STOP_PARENTS,-EIO,tracked)==-EIO);assert(!mishare_ssr_stop_step_locked(&c,h,MISHARE_SSR_STOP_PARENTS,0,tracked));assert(mishare_ssr_stop_finish_locked(&c,h,0,true,tracked)==-EIO && "EXPECTED_JOURNAL_FIRST_ERROR");}
    if(kind==5)assert(mishare_ssr_stop_finish_locked(&c,h,0,false,tracked)==-EIO && "EXPECTED_JOURNAL_ACK");
    if(kind==7){h->pdev=&replacement;assert(mishare_ssr_stop_finish_locked(&c,h,0,true,tracked)==-EUCLEAN && "EXPECTED_JOURNAL_IDENTITY");h->pdev=pdev;}
   }
  }
  trace[0]=0;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));pins_empty();
  if(kind==6){h->pdev=NULL;assert(!mishare_ssr_stop_finish_locked(&c,h,0,true,tracked) && c.phase==MISHARE_SSR_STOP_EMPTY && !c.hdd && !c.psoc && !c.pdev && !c.parent_dev && "EXPECTED_JOURNAL_COMPLETE");h->pdev=pdev;}
  else {
   assert(c.phase!=MISHARE_SSR_STOP_EMPTY && "EXPECTED_JOURNAL_RETENTION");
   assert(mishare_ssr_stop_resume_locked(&c,h,&again)==-EBUSY && "EXPECTED_SSR_RESUME_HARD_FAILURE");
   assert(mishare_ssr_stop_begin_locked(&c,h,&again)==-EBUSY && "EXPECTED_JOURNAL_REPLAY");
   runtime_ssr=false;assert(mishare_ssr_stop_begin_locked(&c,h,&again)==-EBUSY && "EXPECTED_JOURNAL_REPLAY");
  }
  runtime_ssr=false;
 }
}

static void ssr_stop_cases(struct hdd_context *h,struct wireless_dev *wdev) {for(int kind=0;kind<15;kind++)ssr_stop_case(h,wdev,kind);}

static void ssr_resume_cases(struct hdd_context *h,struct wireless_dev *wdev)
{
 struct mishare_ssr_stop_checkpoint empty={0};bool tracked=true;
 assert(mishare_ssr_stop_resume_locked(NULL,h,&tracked)==-EINVAL);
 assert(mishare_ssr_stop_resume_locked(&empty,h,NULL)==-EINVAL);
 assert(mishare_ssr_stop_resume_locked(&empty,NULL,&tracked)==-EINVAL && !tracked);
 assert(mishare_ssr_stop_resume_locked(&empty,h,&tracked)==-ENOENT && !tracked);
 for(int kind=0;kind<17;kind++) {
  struct mishare_wonder_host *owner=NULL;struct device *dev=h->parent_dev,other_dev={0};
  struct wlan_objmgr_psoc *psoc=h->psoc,other_psoc={0};struct wlan_objmgr_pdev *pdev=h->pdev,other_pdev={0};
  reset(0);ssr_ctx=h;mishare_module_stop=(struct mishare_ssr_stop_checkpoint){0};mishare_ssr_stop_blocked=false;
  ssr_hif_missing=ssr_soc_present=ssr_epping=ssr_ipa=ssr_capture=ssr_monitor_present=ssr_vdev_present=ssr_unloading=ssr_lookup_missing=ssr_resume_tail_expected=false;ssr_transition_dev=NULL;ssr_smmu_completions=0;
  ssr_stop_force=ssr_after_retire_force=ssr_module_prefixes=ssr_post_calls=ssr_parent_closes=ssr_tail=0;
  ssr_masks=ssr_isr_stops=ssr_cleanup_calls=ssr_inner_reinits=ssr_start_calls=ssr_resume_calls=0;
  ssr_post_status=QDF_STATUS_SUCCESS;ssr_qualification_ready=true;ssr_qualified_wait=-EINPROGRESS;
  h->driver_status=17;h->is_scheduler_suspended=h->is_wiphy_suspended=h->hdd_wlan_suspended=false;
  assert(!mishare_wonder_host_create_locked(h,mac,&owner));active->dev->ieee80211_ptr=wdev;
  assert(!mishare_wonder_host_vdev_create_locked(owner));assert(!handoff_from_temporary(&owner));
  memset(reset_slots,0,sizeof(reset_slots));memset(reset_refs,0,sizeof(reset_refs));reset_holds=reset_puts=0;reset_slots[0]=active;
  runtime_ssr=true;rtnl_owned=false;rtnl_contended=kind==1;is_recovery_cleanup_done=0;trace[0]=0;
  __hdd_soc_recovery_shutdown();rtnl_contended=false;
  assert(mishare_module_stop.phase==MISHARE_SSR_STOP_POST_DISABLED && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_WAIT_PAUSE");
  assert(mishare_ssr_stop_blocked && active && !ssr_tail && !ssr_parent_closes && ssr_module_prefixes==1 && ssr_post_calls==1);
  assert(reset_holds==1 && reset_puts==1 && !reset_refs[0]);memset(reset_slots,0,sizeof(reset_slots));
  batch_rc=0;int result=0;struct osif_vdev_sync *sync=registered,foreign_sync={0};
  if(kind==2 || kind==3) {
   batch_rc=-EINPROGRESS;rtnl_contended=kind==3;
   result=hdd_mishare_resume_stop_modules(h);rtnl_contended=false;
   assert(result==(kind==3?-EAGAIN:-EINPROGRESS) && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_WAIT_PAUSE");batch_rc=0;
  }
  if(kind==4){struct hdd_context other=*h;assert(hdd_mishare_resume_stop_modules(&other)==-EUCLEAN && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_RESUME_IDENTITY");}
  if(kind==5){h->parent_dev=&other_dev;assert(hdd_mishare_resume_stop_modules(h)==-EUCLEAN && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_RESUME_IDENTITY");h->parent_dev=dev;}
  if(kind==6){h->psoc=&other_psoc;assert(hdd_mishare_resume_stop_modules(h)==-EUCLEAN && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_RESUME_IDENTITY");h->psoc=psoc;}
  if(kind==7){h->pdev=&other_pdev;assert(hdd_mishare_resume_stop_modules(h)==-EUCLEAN && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_RESUME_IDENTITY");h->pdev=pdev;}
  if(kind==8){h->driver_status++;assert(hdd_mishare_resume_stop_modules(h)==-EUCLEAN && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_RESUME_STATUS");h->driver_status--;}
  if(kind==9){runtime_ssr=false;assert(hdd_mishare_resume_stop_modules(h)==-ESHUTDOWN && mishare_module_stop.paused && !mishare_module_stop.first_error && "EXPECTED_SSR_RESUME_RECOVERY");runtime_ssr=true;}
  if(kind==10){ssr_epping=true;assert(hdd_mishare_resume_stop_modules(h)==-EOPNOTSUPP && "EXPECTED_SSR_RESUME_MODE");ssr_epping=false;}
  if(kind==11)assert(ssr_stop_section(h,true,true)==-EOPNOTSUPP && "EXPECTED_SSR_RESUME_MODE");
  if(kind==12)batch_rc=-EUCLEAN;
  if(kind==13)registered=&foreign_sync;
  if(kind==14){bool claimed=false;assert(!mishare_ssr_stop_resume_locked(&mishare_module_stop,h,&claimed) && claimed);assert(hdd_mishare_resume_stop_modules(h)==-EBUSY && "EXPECTED_SSR_RESUME_CLAIM");assert(mishare_ssr_stop_finish_locked(&mishare_module_stop,h,-EIO,false,claimed)==-EIO);}
  if(kind==15)ssr_after_retire_force=-EIO;
  if(kind==16){rtnl_owned=true;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));rtnl_owned=false;}
  if(kind!=14)result=hdd_mishare_resume_stop_modules(h);
  if(kind<12 || kind==16) {
   assert(!result && !active && !registered && mishare_module_stop.phase==MISHARE_SSR_STOP_EMPTY && "EXPECTED_SSR_RESUME_COMPLETE");
   assert(ssr_parent_closes==1 && hdd_mishare_resume_stop_modules(h)==-ENOENT && "EXPECTED_SSR_RESUME_ONCE");
  } else {
   if(kind!=14)assert(result==(kind==12?-EUCLEAN:-EIO));
   assert(mishare_module_stop.phase!=MISHARE_SSR_STOP_EMPTY && mishare_module_stop.first_error && !mishare_module_stop.paused);
   assert(hdd_mishare_resume_stop_modules(h)==-EBUSY && "EXPECTED_SSR_RESUME_HARD_FAILURE");
  }
  assert(ssr_module_prefixes==1 && ssr_post_calls==1 && "EXPECTED_SSR_RESUME_NO_PREFIX");
  assert(mishare_ssr_stop_blocked && !ssr_tail && "EXPECTED_SSR_MODULE_ONLY_ACK");
  assert(reset_holds==1 && reset_puts==1 && "EXPECTED_SSR_RESUME_NO_PREFIX");
  registered=sync; /* restore a deliberately mismatched sync, if still live */
  if(!active)registered=NULL;
  batch_rc=0;rtnl_owned=true;if(active)assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));pins_empty();
  runtime_ssr=false;mishare_module_stop=(struct mishare_ssr_stop_checkpoint){0};mishare_ssr_stop_blocked=false;
 }
}

static void ssr_upper_cases(struct hdd_context *h,struct wireless_dev *wdev)
{
 assert(hdd_mishare_resume_shutdown(NULL)==-EINVAL);
 for(int kind=0;kind<16;kind++) {
  struct mishare_wonder_host *owner=NULL;struct device foreign_dev={0};struct wlan_objmgr_pdev foreign_pdev={0},*pdev=h->pdev;
  struct osif_vdev_sync *sync,*foreign_sync=NULL,foreign_sync_value={0};foreign_sync=&foreign_sync_value;
  reset(0);ssr_ctx=h;mishare_module_stop=(struct mishare_ssr_stop_checkpoint){0};mishare_ssr_stop_blocked=false;
  ssr_hif_missing=ssr_soc_present=ssr_epping=ssr_ipa=ssr_capture=ssr_monitor_present=ssr_vdev_present=ssr_unloading=ssr_lookup_missing=ssr_resume_tail_expected=false;
  ssr_transition_dev=NULL;ssr_smmu_completions=ssr_stop_force=ssr_after_retire_force=ssr_module_prefixes=ssr_post_calls=ssr_parent_closes=ssr_tail=0;
  ssr_masks=ssr_isr_stops=ssr_cleanup_calls=ssr_inner_reinits=ssr_start_calls=ssr_resume_calls=0;
  ssr_inner_result=kind==12?-EIO:0;ssr_start_status=12345;is_recovery_cleanup_done=0;
  ssr_post_status=QDF_STATUS_SUCCESS;ssr_qualification_ready=true;ssr_qualified_wait=-EINPROGRESS;
  h->driver_status=17;h->is_scheduler_suspended=h->is_wiphy_suspended=h->hdd_wlan_suspended=false;
  assert(!mishare_wonder_host_create_locked(h,mac,&owner));active->dev->ieee80211_ptr=wdev;
  assert(!mishare_wonder_host_vdev_create_locked(owner));assert(!handoff_from_temporary(&owner));
  memset(reset_slots,0,sizeof(reset_slots));memset(reset_refs,0,sizeof(reset_refs));reset_holds=reset_puts=0;reset_slots[0]=active;
  runtime_ssr=true;rtnl_owned=false;trace[0]=0;__hdd_soc_recovery_shutdown();sync=registered;
  assert(mishare_module_stop.paused && mishare_ssr_stop_blocked && parent_owned);
  assert(ssr_module_prefixes==1 && ssr_post_calls==1 && !ssr_tail && !ssr_inner_reinits);
  memset(reset_slots,0,sizeof(reset_slots));ssr_resume_tail_expected=true;batch_rc=0;
  int expected=0;bool terminal=kind>=3 && kind<=6;
  if(kind==1 || kind==2) {
   batch_rc=-EINPROGRESS;rtnl_contended=kind==2;idle_trace[0]=0;
   int result=hdd_soc_recovery_reinit(h->parent_dev,NULL,NULL,SSR_IPCI);rtnl_contended=false;
   assert(result==(kind==2?-EAGAIN:-EINPROGRESS) && mishare_ssr_stop_blocked && mishare_module_stop.paused && parent_owned && !ssr_tail && !ssr_inner_reinits && "EXPECTED_UPPER_WAIT_RETAINED");batch_rc=0;
  }
  if(kind==3){batch_rc=-EUCLEAN;expected=-EUCLEAN;}
  if(kind==4){registered=foreign_sync;expected=-EIO;}
  if(kind==5){ssr_after_retire_force=-EIO;expected=-EIO;}
  if(kind==6){assert(!hdd_mishare_resume_stop_modules(h));expected=-ENOENT;}
  if(kind==7){ssr_lookup_missing=true;expected=-ENODEV;}
  if(kind==8){ssr_transition_dev=&foreign_dev;expected=-EUCLEAN;}
  if(kind==9){h->pdev=&foreign_pdev;expected=-EUCLEAN;}
  if(kind==10){runtime_ssr=false;expected=-ESHUTDOWN;}
  if(kind==11){ssr_epping=true;expected=-EOPNOTSUPP;}
  if(kind==12)expected=-EIO;
  if(kind==13) {
   int calls=ssr_resume_calls;ssr_unloading=true;
   assert(!hdd_soc_recovery_reinit(h->parent_dev,NULL,NULL,SSR_IPCI) && parent_owned && mishare_ssr_stop_blocked && !ssr_tail && ssr_resume_calls==calls && "EXPECTED_UPPER_UNLOAD_RETAINED");ssr_unloading=false;
  }
  if(kind==14){rtnl_owned=true;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));rtnl_owned=false;}
  if(kind==15)assert(hdd_mishare_resume_shutdown(NULL)==-EINVAL && mishare_module_stop.paused && "EXPECTED_UPPER_NULL_RETAINED");
  idle_trace[0]=0;int result=hdd_soc_recovery_reinit(ssr_transition_dev?ssr_transition_dev:h->parent_dev,NULL,NULL,SSR_IPCI);
  assert(result==expected && "EXPECTED_UPPER_RESULT");
  if(kind==6)assert(result==-ENOENT && "EXPECTED_UPPER_EMPTY_REFUSAL");
  if(expected && kind!=12) {
   assert(mishare_ssr_stop_blocked && parent_owned && !ssr_tail && !ssr_smmu_completions && !ssr_inner_reinits && "EXPECTED_UPPER_REFUSAL_RETAINED");
   assert(ssr_start_status==expected && "EXPECTED_UPPER_FAILURE_NOTIFY");
   if(terminal) {
    registered=active?sync:NULL;batch_rc=0;rtnl_owned=true;if(active)assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));rtnl_owned=false;
    int retry=hdd_soc_recovery_reinit(h->parent_dev,NULL,NULL,SSR_IPCI);
    assert(retry==(kind==6?-ENOENT:-EBUSY) && parent_owned && mishare_ssr_stop_blocked && !ssr_tail && !ssr_inner_reinits && "EXPECTED_UPPER_EMPTY_REFUSAL");
   } else {
    ssr_lookup_missing=ssr_epping=false;ssr_transition_dev=NULL;h->pdev=pdev;runtime_ssr=true;
    assert(!hdd_soc_recovery_reinit(h->parent_dev,NULL,NULL,SSR_IPCI));
   }
  }
  if(!terminal) {
   assert(!mishare_ssr_stop_blocked && !parent_owned && !active && !registered && ssr_parent_closes==1 && ssr_tail==1 && ssr_smmu_completions==1 && ssr_inner_reinits==1 && "EXPECTED_UPPER_COMPLETE");
   assert(ssr_start_status==(kind==12?-EIO:0) && "EXPECTED_UPPER_FAILURE_NOTIFY");
  }
  assert(ssr_module_prefixes==1 && ssr_post_calls==1 && reset_holds==1 && reset_puts==1 && ssr_masks==1 && ssr_isr_stops==1 && "EXPECTED_UPPER_NO_PREFIX_REPLAY");
  assert(!rtnl_owned);parent_owned=true;rtnl_owned=true;ssr_resume_tail_expected=false;
  h->pdev=pdev;registered=active?sync:NULL;batch_rc=0;if(active)assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));pins_empty();
  runtime_ssr=false;mishare_module_stop=(struct mishare_ssr_stop_checkpoint){0};mishare_ssr_stop_blocked=false;
 }
}
'''

HARNESS = r'''
static struct hdd_adapter *__hdd_open_adapter(struct hdd_context *h,uint8_t session_type,const char *name,tSirMacAddr address,unsigned char assign,bool locked,struct hdd_adapter_create_param *params,bool mishare_host_only)
{
 GUARD
 assert(h && session_type==17 && !strcmp(name,"misharewt%d") && assign==0 && locked && params->num_sessions==1);
 assert(!active && !memcmp(address,mac,6));event('H');
 if(failure==3)return NULL;
 active=calloc(1,sizeof(*active));active->dev=calloc(1,sizeof(*active->dev));active->deflink=calloc(1,sizeof(*active->deflink));active->device_mode=session_type;memcpy(active->mac_addr.bytes,address,6);
 return active;
}
static struct hdd_adapter *factory_rollback(struct hdd_context *hdd_ctx,struct hdd_adapter *adapter,bool mishare_host_only,bool rtnl_held)
{
 ROLLBACK
 abort();
}
static int handoff_from_temporary(struct mishare_wonder_host **owner)
{
 struct mishare_wonder_host *temporary=*owner;*owner=NULL;
 int ret=mishare_wonder_host_handoff_idle_locked(&temporary);
 if(ret)*owner=temporary;
 else assert(!temporary && "EXPECTED_IDLE_HANDOFF");
 return ret;
}
static void reject_replaced_parent(struct hdd_context *h,struct mishare_wonder_host **owner)
{
 struct device *dev=h->parent_dev;struct wlan_objmgr_psoc *psoc=h->psoc;struct wlan_objmgr_pdev *pdev=h->pdev;
 struct device foreign_dev={0};struct wlan_objmgr_psoc foreign_psoc={0};struct wlan_objmgr_pdev foreign_pdev={0};
 for(int identity=0;identity<3;identity++) {
  h->parent_dev=identity==0?&foreign_dev:dev;h->psoc=identity==1?&foreign_psoc:psoc;h->pdev=identity==2?&foreign_pdev:pdev;
  struct mishare_runtime_owner *token=(*owner)->runtime;bool closing=(*owner)->session.closing;int prior_closed=closed,prior_batches=batch_calls;
  trace[0]=0;identity_refusal_expected=true;
  assert(mishare_wonder_host_vdev_create_locked(*owner)==-EUCLEAN && "EXPECTED_PARENT_IDENTITY");
  assert(mishare_wonder_host_vdev_destroy_locked(*owner)==-EUCLEAN && "EXPECTED_PARENT_IDENTITY");
  assert(mishare_wonder_host_session_step_locked(*owner,5240,1,2)==-EUCLEAN && "EXPECTED_PARENT_IDENTITY");
  assert(mishare_wonder_host_destroy_locked(owner)==-EUCLEAN && "EXPECTED_PARENT_IDENTITY");
  assert(mishare_wonder_host_reclaim_ssr_locked(owner)==-EUCLEAN && "EXPECTED_PARENT_IDENTITY");
  assert(mishare_wonder_host_handoff_idle_locked(owner)==-EUCLEAN && "EXPECTED_PARENT_IDENTITY");
  assert(*owner && (*owner)->runtime==token && (*owner)->session.closing==closing && closed==prior_closed && batch_calls==prior_batches && active && registered);
  identity_refusal_expected=false;assert(!strcmp(trace,"PPPPPP"));pins_live();
 }
 h->parent_dev=dev;h->psoc=psoc;h->pdev=pdev;trace[0]=0;
}
static void reclaim_handoff_ssr_cases(struct hdd_context *h,struct wireless_dev *wdev)
{
 struct mishare_wonder_host *owner=NULL,*retained;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(NULL)==-EINVAL);
 struct hdd_context invalid=*h;invalid.parent_dev=NULL;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(&invalid)==-EINVAL);
 invalid=*h;invalid.psoc=NULL;assert(mishare_wonder_host_reclaim_handoff_ssr_locked(&invalid)==-EINVAL);
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-ESHUTDOWN && "EXPECTED_HANDOFF_SSR_ADMISSION");
 runtime_ssr=true;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));
 runtime_registry_psoc=h->psoc;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EBUSY && "EXPECTED_HANDOFF_SSR_COVERAGE");runtime_registry_psoc=NULL;runtime_ssr=false;
 reset(0);assert(!mishare_wonder_host_create_locked(h,mac,&owner));active->dev->ieee80211_ptr=wdev;
 assert(!mishare_wonder_host_vdev_create_locked(owner));retained=owner;
 int before_batches=batch_calls,before_close=closed;
 runtime_ssr=true;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EBUSY && owner==retained && !owner->session.closing && batch_calls==before_batches && "EXPECTED_HANDOFF_SSR_PREFLIGHT");
 runtime_ssr=false;assert(!handoff_from_temporary(&owner));assert(!owner && retained->idle_owned);
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-ESHUTDOWN && batch_calls==before_batches && "EXPECTED_HANDOFF_SSR_ADMISSION");runtime_ssr=true;
 struct hdd_context foreign=*h;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(&foreign)==-EUCLEAN && batch_calls==before_batches && "EXPECTED_HANDOFF_SSR_PREFLIGHT");
 struct device *dev=h->parent_dev;struct wlan_objmgr_psoc *psoc=h->psoc;struct wlan_objmgr_pdev *pdev=h->pdev;
 struct device other_dev={0};struct wlan_objmgr_psoc other_psoc={0};struct wlan_objmgr_pdev other_pdev={.psoc=psoc};
 for(int field=0;field<3;field++) {
  h->parent_dev=field==0?&other_dev:dev;h->psoc=field==1?&other_psoc:psoc;h->pdev=field==2?&other_pdev:pdev;
  assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EUCLEAN && batch_calls==before_batches && closed==before_close && "EXPECTED_HANDOFF_SSR_PREFLIGHT");pins_live();
 }
 h->parent_dev=dev;h->psoc=psoc;h->pdev=pdev;
 active->dev->running=true;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EBUSY && batch_calls==before_batches && "EXPECTED_HANDOFF_SSR_POLL");active->dev->running=false;
 struct mishare_runtime_owner *token=retained->runtime;
 batch_extra=true;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EBUSY && retained->runtime==token && retained->idle_owned && "EXPECTED_HANDOFF_SSR_POLL");batch_extra=false;
 for(int error=0;error<3;error++) {
  batch_rc=error==0?-ESHUTDOWN:error==1?-EUCLEAN:-EINPROGRESS;
  for(int poll=0;poll<3;poll++) {
   trace[0]=0;assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==batch_rc && "EXPECTED_HANDOFF_SSR_POLL");
   assert(retained->runtime==token && retained->idle_owned && active && registered && closed==before_close);pins_live();
  }
 }
 batch_rc=0;struct osif_vdev_sync *original=registered,foreign_sync={0};registered=&foreign_sync;trace[0]=0;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EIO && "EXPECTED_HANDOFF_SSR_POLL");
 assert(!retained->runtime && retained->idle_owned && active && registered==&foreign_sync && closed==before_close);pins_live();registered=original;
 trace[0]=0;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));
 assert(!active && !registered && !mishare_wonder_host_psoc_busy(psoc) && closed==before_close+1);pins_empty();
 assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));runtime_ssr=false;
 /* A handed-off host with no runtime still cannot hide another runtime. */
 reset(0);assert(!mishare_wonder_host_create_locked(h,mac,&owner));retained=owner;
 assert(!handoff_from_temporary(&owner));runtime_ssr=true;runtime_registry_psoc=psoc;before_close=closed;
 assert(mishare_wonder_host_reclaim_handoff_ssr_locked(h)==-EBUSY && "EXPECTED_HANDOFF_SSR_COVERAGE");
 assert(retained->idle_owned && active && registered && closed==before_close);pins_live();runtime_registry_psoc=NULL;
 trace[0]=0;assert(!mishare_wonder_host_reclaim_handoff_ssr_locked(h));pins_empty();runtime_ssr=false;
}
int main(void)
{
 struct device dev={0};struct wlan_objmgr_psoc psoc={0},other_psoc={0};struct wlan_objmgr_pdev pdev={.psoc=&psoc};struct wireless_dev wdev={0};struct hdd_context h={.parent_dev=&dev,.psoc=&psoc,.pdev=&pdev};struct mishare_wonder_host *owner=NULL;expected_psoc=&psoc;
 assert(!mishare_wonder_host_psoc_busy(NULL) && !mishare_wonder_host_psoc_busy(&psoc));
 idle_check(&h,0,"CBSWIMTE");
 idle_stop_result=-EIO;idle_check(&h,-EIO,"CBSWIMTE");idle_stop_result=0;
 idle_open=true;idle_check(&h,-EAGAIN,"CBSWITE");idle_open=false;
 idle_trans_failure=true;idle_check(&h,-EAGAIN,"CBSE");idle_trans_failure=false;
 assert(mishare_wonder_host_stop_ready_locked(NULL)==-EINVAL);
 struct hdd_context invalid_h=h;invalid_h.psoc=NULL;assert(mishare_wonder_host_stop_ready_locked(&invalid_h)==-EINVAL);invalid_h=h;invalid_h.parent_dev=NULL;assert(mishare_wonder_host_stop_ready_locked(&invalid_h)==-EINVAL);
 runtime_registry_psoc=&psoc;assert(mishare_wonder_host_stop_ready_locked(&h)==-EBUSY && "EXPECTED_RUNTIME_STOP_GUARD");assert(__hdd_driver_mode_change(&h,MODE_REQUESTED)==-EBUSY && "EXPECTED_MODE_REQUEST_ADMISSION");assert(!__hdd_driver_mode_change(&h,MODE_CURRENT));idle_check(&h,-EAGAIN,"CBSWTE");
 mode_context=&h;is_mode_change_psoc_idle_shutdown=true;idle_trace[0]=0;
 assert(__hdd_mode_change_psoc_idle_shutdown(&h)==-EBUSY && is_mode_change_psoc_idle_shutdown && !idle_trace[0]);
 assert(hdd_mode_change_psoc_idle_shutdown(&dev)==-EBUSY && !idle_trace[0]);
 runtime_registry_psoc=&other_psoc;assert(!mishare_wonder_host_stop_ready_locked(&h));assert(__hdd_driver_mode_change(&h,MODE_REQUESTED)==104);runtime_registry_psoc=NULL;
 idle_stop_result=-EIO;assert(__hdd_mode_change_psoc_idle_shutdown(&h)==-EIO && !is_mode_change_psoc_idle_shutdown && mode_ftm);idle_trace[0]=0;assert(hdd_mode_change_psoc_idle_shutdown(&dev)==-EIO && mode_ftm && !strcmp(idle_trace,"M"));idle_stop_result=0;
 mode_context=NULL;assert(hdd_mode_change_psoc_idle_shutdown(&dev)==-EINVAL);mode_context=&h;

 assert(mishare_wonder_host_create_locked(&h,mac,NULL)==-EINVAL);
 u8 invalid[6]={1,2,3,4,5,6};assert(mishare_wonder_host_create_locked(&h,invalid,&owner)==-EINVAL);
 assert(mishare_wonder_host_destroy_locked(NULL)==-EINVAL);
 assert(mishare_wonder_host_destroy_locked(&owner)==0);
 reset(1);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENOMEM && !owner);assert(!strcmp(trace,"PVLA"));
 reset(2);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENOMEM && !owner);assert(!strcmp(trace,"PVLAGQBSbqgF"));
 reset(3);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENODEV && !owner);assert(!strcmp(trace,"PVLAGQBSHDbqgF"));
 reset(4);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENODEV && !owner);assert(!strcmp(trace,"PV"));
 reset(5);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-EBUSY && !owner);assert(!strcmp(trace,"PVL"));
 reset(6);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENODEV && !owner);assert(!strcmp(trace,"PVLAGF"));
 reset(7);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ESHUTDOWN && !owner);assert(!strcmp(trace,"PVLAGQgF"));
 reset(8);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ESHUTDOWN && !owner);assert(!strcmp(trace,"PVLAGQBqgF"));
 reset(9);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-EUCLEAN && !owner && "EXPECTED_PARENT_RELATION");assert(!strcmp(trace,"PVLAGQBbqgF"));
 reset(0);struct hdd_context no_pdev=h;no_pdev.pdev=NULL;assert(mishare_wonder_host_create_locked(&no_pdev,mac,&owner)==-EINVAL && !trace[0]);
 assert(!mishare_wonder_host_psoc_busy(&psoc));idle_check(&h,0,"CBSWIMTE");
 reset(0);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==0 && owner && active && registered);assert(!strcmp(trace,"PVLAGQBSHR"));
 pins_live();reject_replaced_parent(&h,&owner);
 assert(mishare_wonder_host_psoc_busy(&psoc) && !mishare_wonder_host_psoc_busy(&other_psoc));
 assert(mishare_wonder_host_stop_ready_locked(&h)==-EBUSY && "EXPECTED_HOST_STOP_GUARD");assert(__hdd_driver_mode_change(&h,MODE_REQUESTED)==-EBUSY && "EXPECTED_MODE_REQUEST_ADMISSION");
 idle_trace[0]=0;is_mode_change_psoc_idle_shutdown=true;assert(__hdd_mode_change_psoc_idle_shutdown(&h)==-EBUSY && is_mode_change_psoc_idle_shutdown && !idle_trace[0]);assert(hdd_mode_change_psoc_idle_shutdown(&dev)==-EBUSY && !idle_trace[0]);
 idle_check(&h,-EAGAIN,"CBSWTE");
 struct hdd_context foreign_hdd=h;foreign_hdd.psoc=&other_psoc;idle_check(&foreign_hdd,0,"CBSWIMTE");
 trace[0]=0;assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-EBUSY && trace[0]==0);
 active->dev->running=true;assert(mishare_wonder_host_destroy_locked(&owner)==-EBUSY && owner && registered);active->dev->running=false;
 active->event_flags=1UL<<DEVICE_IFACE_OPENED;assert(mishare_wonder_host_destroy_locked(&owner)==-EBUSY && owner && registered);active->event_flags=0;
 active->deflink->link_flags[0]=1UL<<SME_SESSION_OPENED;assert(mishare_wonder_host_destroy_locked(&owner)==-EBUSY && owner && registered);active->deflink->link_flags[0]=0;
 struct osif_vdev_sync *original=registered, foreign={0};registered=&foreign;
 assert(mishare_wonder_host_destroy_locked(&owner)==-EIO && owner && active && registered==&foreign);idle_check(&h,-EAGAIN,"CBSWTE");registered=original;
 assert(mishare_wonder_host_vdev_create_locked(owner)==-ESHUTDOWN);
 assert(mishare_wonder_host_session_step_locked(owner,5240,1,2)==-ESHUTDOWN);
 assert(mishare_wonder_host_destroy_locked(&owner)==0 && !owner && !active && !registered);
 reset(0);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==0);
 active->dev->ieee80211_ptr=&wdev;
 assert(!mishare_wonder_host_vdev_create_locked(owner));
 assert(mishare_wonder_host_vdev_create_locked(owner)==-EBUSY);
 runtime_busy=1;
 assert(mishare_wonder_host_destroy_locked(&owner)==-EINPROGRESS && owner && active && registered);idle_check(&h,-EAGAIN,"CBSWTE");
 assert(mishare_wonder_host_vdev_destroy_locked(owner)==-EINPROGRESS);
 runtime_busy=0;
 assert(mishare_wonder_host_vdev_destroy_locked(owner)==0);
 assert(mishare_wonder_host_session_step_locked(owner,5240,1,2)==-ESHUTDOWN);
 assert(mishare_wonder_host_vdev_create_locked(owner)==-ESHUTDOWN);
 trace[0]=0;assert(mishare_wonder_host_destroy_locked(&owner)==0 && !owner && !active && !registered);assert(!strcmp(trace,"PUWCDbqgF"));
 assert(mishare_wonder_host_destroy_locked(&owner)==0 && runtime_closed==1);
 assert(!mishare_wonder_host_psoc_busy(&psoc));idle_check(&h,0,"CBSWIMTE");
 /* Explicit SSR retirement retains host/idle guard through every batch wait. */
 assert(mishare_wonder_host_reclaim_ssr_locked(NULL)==-EINVAL);
 assert(!mishare_wonder_host_reclaim_ssr_locked(&owner));
 reset(0);assert(!mishare_wonder_host_create_locked(&h,mac,&owner));active->dev->ieee80211_ptr=&wdev;
 assert(!mishare_wonder_host_vdev_create_locked(owner));
 reject_replaced_parent(&h,&owner);
 struct mishare_runtime_owner *token=owner->runtime;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-ESHUTDOWN && owner->runtime==token && !batch_calls && !owner->session.closing);
 runtime_ssr=true;h.psoc=&other_psoc;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EUCLEAN && owner->runtime==token && !batch_calls);h.psoc=&psoc;
 active->dev->running=true;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EBUSY && !batch_calls && owner->runtime==token);active->dev->running=false;
 active->event_flags=1UL<<DEVICE_IFACE_OPENED;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EBUSY && !batch_calls);active->event_flags=0;
 active->deflink->link_flags[0]=1UL<<SME_SESSION_OPENED;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EBUSY && !batch_calls);active->deflink->link_flags[0]=0;
 batch_extra=true;assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EBUSY && owner->runtime==token && owner->session.closing);
 idle_check(&h,-EAGAIN,"CBSWTE");batch_extra=false;batch_rc=-EINPROGRESS;
 for(int poll=0;poll<3;poll++) {
  assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EINPROGRESS && owner->runtime==token && active && registered);
  idle_check(&h,-EAGAIN,"CBSWTE");
 }
 /* Prepared/UP/invalid metadata rejection cannot fall through to close. */
 pid_t child=fork();assert(child>=0);
 if(!child) {
  int prior_closed=closed;batch_rc=-EUCLEAN;
  assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EUCLEAN && owner->runtime==token && closed==prior_closed && active && registered);
  assert(mishare_wonder_host_destroy_locked(&owner)==-EUCLEAN && owner->runtime==token);
  idle_check(&h,-EAGAIN,"CBSWTE");_Exit(0);
 }
 int child_status;assert(waitpid(child,&child_status,0)==child && WIFEXITED(child_status) && !WEXITSTATUS(child_status));
 batch_rc=0;original=registered;registered=&foreign;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EIO && owner && !owner->runtime && active && registered==&foreign);
 idle_check(&h,-EAGAIN,"CBSWTE");registered=original;
 assert(!mishare_wonder_host_reclaim_ssr_locked(&owner) && !owner && !active && !registered && runtime_closed==2);
 assert(!mishare_wonder_host_psoc_busy(&psoc));
 /* Even a host without its own runtime checks complete registry coverage. */
 runtime_ssr=false;reset(0);assert(!mishare_wonder_host_create_locked(&h,mac,&owner));runtime_ssr=true;batch_extra=true;
 assert(mishare_wonder_host_reclaim_ssr_locked(&owner)==-EBUSY && owner && !owner->runtime && active && registered);
 idle_check(&h,-EAGAIN,"CBSWTE");batch_extra=false;
 assert(!mishare_wonder_host_reclaim_ssr_locked(&owner) && !owner && !active && !registered);runtime_ssr=false;
 idle_check(&h,0,"CBSWIMTE");
 /* Explicit transfer lets ordinary native idle retire only its own sessions. */
 assert(mishare_wonder_host_handoff_idle_locked(NULL)==-EINVAL);
 assert(!mishare_wonder_host_handoff_idle_locked(&owner));
 reset(0);assert(!mishare_wonder_host_create_locked(&h,mac,&owner));
 struct mishare_wonder_host *retained=owner;
 runtime_ssr=true;assert(mishare_wonder_host_handoff_idle_locked(&owner)==-ESHUTDOWN && owner==retained && !owner->session.closing);runtime_ssr=false;
 failure=4;assert(mishare_wonder_host_handoff_idle_locked(&owner)==-ENODEV && owner==retained && !owner->idle_owned);failure=0;
 active->dev->running=true;assert(mishare_wonder_host_handoff_idle_locked(&owner)==-EBUSY && owner==retained);active->dev->running=false;
 active->event_flags=1UL<<DEVICE_IFACE_OPENED;assert(mishare_wonder_host_handoff_idle_locked(&owner)==-EBUSY && owner==retained);active->event_flags=0;
 active->deflink->link_flags[0]=1UL<<SME_SESSION_OPENED;assert(mishare_wonder_host_handoff_idle_locked(&owner)==-EBUSY && owner==retained);active->deflink->link_flags[0]=0;
 int attempts=rtnl_attempts,prior_closed=closed;
 idle_check(&h,-EAGAIN,"CBSWTE");assert(owner==retained && !owner->session.closing && closed==prior_closed && rtnl_attempts==attempts);
 assert(!handoff_from_temporary(&owner));
 assert(!owner && retained->idle_owned && retained->session.closing && active && registered && "EXPECTED_IDLE_HANDOFF");pins_live();
 /* A stale duplicate cannot transfer the already-transferred owner again. */
 struct mishare_wonder_host *alias=retained;
 assert(mishare_wonder_host_handoff_idle_locked(&alias)==-EBUSY && alias==retained);alias=NULL;
 struct hdd_context same_psoc_other_hdd=h;attempts=rtnl_attempts;
 idle_check(&same_psoc_other_hdd,-EAGAIN,"CBSWTE");assert(rtnl_attempts==attempts && "EXPECTED_IDLE_PREFLIGHT");
 struct device *saved_dev=h.parent_dev;h.parent_dev=NULL;
 assert(mishare_wonder_host_idle_prepare_locked(&h)==-EINVAL);h.parent_dev=saved_dev;
 h.psoc=&other_psoc;idle_check(&h,-EAGAIN,"CBSWTE");
 assert(mishare_wonder_host_stop_ready_locked(&h)==-EUCLEAN && "EXPECTED_STALE_PARENT_ADMISSION");
 assert(__hdd_driver_mode_change(&h,MODE_REQUESTED)==-EUCLEAN && "EXPECTED_STALE_PARENT_ADMISSION");
 assert(__hdd_mode_change_psoc_idle_shutdown(&h)==-EUCLEAN && "EXPECTED_STALE_PARENT_ADMISSION");
 mode_context=&h;assert(hdd_mode_change_psoc_idle_shutdown(h.parent_dev)==-EUCLEAN && "EXPECTED_STALE_PARENT_ADMISSION");h.psoc=&psoc;
 assert(rtnl_attempts==attempts && "EXPECTED_IDLE_PREFLIGHT");
 struct device another_dev={0};struct wlan_objmgr_pdev another_pdev={.psoc=&psoc};
 h.parent_dev=&another_dev;idle_check(&h,-EAGAIN,"CBSWTE");h.parent_dev=saved_dev;
 assert(rtnl_attempts==attempts && "EXPECTED_IDLE_PREFLIGHT");
 h.pdev=&another_pdev;idle_check(&h,-EAGAIN,"CBSWTE");h.pdev=&pdev;
 assert(rtnl_attempts==attempts && "EXPECTED_IDLE_PREFLIGHT");
 runtime_ssr=true;idle_check(&h,-EAGAIN,"CBSWTE");runtime_ssr=false;
 assert(rtnl_attempts==attempts && closed==prior_closed);
 rtnl_contended=true;idle_check(&h,-EAGAIN,"CBSWTE");rtnl_contended=false;
 assert(active && registered && closed==prior_closed && retained->idle_owned);pins_live();
 idle_retirement_expected=true;
 idle_open=true;idle_check(&h,-EAGAIN,"CBSWITE");idle_open=false;assert(!active && !registered && closed==prior_closed+1 && !mishare_wonder_host_psoc_busy(&psoc));pins_empty();
 idle_retirement_expected=false;
 /* Pending runtime and a later sync failure retain coordinator ownership. */
 reset(0);assert(!mishare_wonder_host_create_locked(&h,mac,&owner));active->dev->ieee80211_ptr=&wdev;
 assert(!mishare_wonder_host_vdev_create_locked(owner));retained=owner;
 assert(!mishare_wonder_host_handoff_idle_locked(&owner) && !owner && retained->idle_owned && retained->session.closing && "EXPECTED_IDLE_HANDOFF");
 idle_retirement_expected=true;runtime_busy=1;prior_closed=closed;
 for(int poll=0;poll<3;poll++) {trace[0]=0;idle_check(&h,-EAGAIN,"CBSWTE");assert(active && registered && closed==prior_closed && retained->runtime && retained->idle_owned);pins_live();}
 runtime_busy=0;original=registered;registered=&foreign;trace[0]=0;
 idle_check(&h,-EAGAIN,"CBSWTE");assert(active && registered==&foreign && !retained->runtime && retained->idle_owned && closed==prior_closed);pins_live();registered=original;
 /* Host close alone must not grant module stop while another runtime exists. */
 runtime_registry_psoc=&psoc;trace[0]=0;idle_check(&h,-EAGAIN,"CBSWTE");
 assert(!active && !registered && !mishare_wonder_host_psoc_busy(&psoc));pins_empty();
 runtime_registry_psoc=NULL;idle_retirement_expected=false;idle_check(&h,0,"CBSWIMTE");
 /* Quarantine cannot be converted to successful idle cleanup. */
 reset(0);assert(!mishare_wonder_host_create_locked(&h,mac,&owner));active->dev->ieee80211_ptr=&wdev;
 assert(!mishare_wonder_host_vdev_create_locked(owner));retained=owner;
 assert(!mishare_wonder_host_handoff_idle_locked(&owner));
 pid_t quarantine=fork();assert(quarantine>=0);
 if(!quarantine) {runtime_error=-EUCLEAN;idle_retirement_expected=true;idle_check(&h,-EAGAIN,"CBSWTE");assert(active && registered && retained->runtime && retained->idle_owned);pins_live();_Exit(0);}
 assert(waitpid(quarantine,&child_status,0)==quarantine && WIFEXITED(child_status) && !WEXITSTATUS(child_status));
 idle_retirement_expected=true;trace[0]=0;idle_stop_result=-EIO;idle_check(&h,-EIO,"CBSWIMTE");idle_stop_result=0;idle_retirement_expected=false;pins_empty();
 reclaim_handoff_ssr_cases(&h,&wdev);
 reset_owned_cases(&h,&wdev);
 ssr_prepare_cases(&h,&wdev);
 ssr_journal_cases(&h,&wdev);
 ssr_stop_cases(&h,&wdev);
 ssr_resume_cases(&h,&wdev);
 ssr_upper_cases(&h,&wdev);
 /* The ordinary production wrapper must reject PASSTHRU, factory-only override. */
 struct hdd_adapter_create_param params={.num_sessions=1};
 assert(hdd_open_adapter(&h,17,"misharewt%d",(u8*)mac,0,true,&params)==NULL && !active);
 assert(hdd_mishare_host_only_open(NULL)==-EOPNOTSUPP);
 expected_psoc=NULL;reset(0);struct hdd_adapter *a=hdd_mishare_host_adapter_open(&h,(u8*)mac);assert(a && active);
 trace[0]=0;assert(factory_rollback(&h,a,true,true)==NULL && !active);assert(!strcmp(trace,"CX") && dp_destroyed==1);
 pins_empty();assert(!dev.refs && !psoc.refs && !pdev.refs);
 puts("MISHARE_HOST_LIFETIME_FIXTURE_PASS_ONLY");return 0;
}
'''


def extract(text, pattern):
    match = re.search(pattern, text, re.S | re.M)
    if not match:
        raise ValueError('Changed production source: ' + pattern)
    return match[0]


def run(wlan, output):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Native compilation runs only on Actions')
    main = (wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_main.c').read_text()
    guard = extract(main, r'if \(session_type == QDF_PASSTHRU_MODE && !mishare_host_only\) \{.*?\n\t\}')
    rollback = extract(main, r'if \(mishare_host_only && adapter\) \{.*?\n\t\}')
    wrappers = '\n'.join(extract(main, pattern) for pattern in [
        r'^struct hdd_adapter \*hdd_open_adapter\([^;{]+?\)\s*\{.*?^\}',
        r'^struct hdd_adapter \*hdd_mishare_host_adapter_open\([^;{]+?\)\s*\{.*?^\}',
        r'^static int hdd_mishare_host_only_open\([^;{]+?\)\s*\{.*?^\}',
    ])
    # Function bodies contain semicolons; match through column-zero closing braces.
    idle = extract(main, r'^static int __hdd_psoc_idle_shutdown\([^;{]+?\)\s*\{.*?^\}')
    if hashlib.sha256(remove_idle_additions(idle).encode()).hexdigest() != '0d61f49fb96d09d35afb587284e02951aaeb996620ae669cfbacb756f63c6b54':
        raise ValueError('Unbounded native idle shutdown delta')
    assert idle.index('osif_psoc_sync_wait_for_ops(') < idle.index('mishare_wonder_host_idle_prepare_locked(') < idle.index('hdd_wlan_stop_modules(') < idle.index('osif_psoc_sync_trans_stop(')
    mode = '\n'.join(extract(main, r'^static int\s+'+name+r'\([^;{]+?\)\s*\{.*?^\}') for name in ['__hdd_mode_change_psoc_idle_shutdown','hdd_mode_change_psoc_idle_shutdown'])
    request_body=extract(main,r'^static int __hdd_driver_mode_change\([^;{]+?\)\s*\{.*?^\}')
    request_prefix=request_body[:request_body.index('\thdd_psoc_idle_timer_stop(hdd_ctx);')]
    assert request_prefix.count('mishare_wonder_host_stop_ready_locked(hdd_ctx)')==1
    request_model='#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wunused-variable"\n'+request_prefix+'\treturn 104; /* reached first adapter/timer side-effect boundary */\n}\n#pragma GCC diagnostic pop\n'
    mode += '\n'+request_model
    mode = '#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored \"-Wunused-parameter\"\n'+mode+'\n#pragma GCC diagnostic pop\n'
    reset_native = extract(main, r'^QDF_STATUS hdd_reset_all_adapters\([^;{]+?\)\s*\{.*?^\}')
    original_main = subprocess.check_output(['git','-C',str(wlan),'show','HEAD:qcacld-3.0/core/hdd/src/wlan_hdd_main.c'],text=True)
    reset_original = extract(original_main, r'^QDF_STATUS hdd_reset_all_adapters\([^;{]+?\)\s*\{.*?^\}')
    assert remove_parent_additions(reset_native) == reset_original, 'Unbounded native adapter reset delta'
    assert reset_native.index('mishare_wonder_host_adapter_owned(') < reset_native.index('hdd_adapter_for_each_active_link_info(')
    power_path='qcacld-3.0/core/hdd/src/wlan_hdd_power.c'
    ops_path='qcacld-3.0/core/hdd/src/wlan_hdd_driver_ops.c'
    qdf_path='qca-wifi-host-cmn/qdf/linux/src/qdf_status.c'
    power=(wlan/power_path).read_text();ops=(wlan/ops_path).read_text()
    sync_path='qcacld-3.0/os_if/sync/src/osif_psoc_sync.c'
    sync_source=(wlan/sync_path).read_text()
    assert sync_source==subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+sync_path],text=True)
    sync_resume=extract(sync_source,r'^int osif_psoc_sync_trans_resume\([^;{]+?\)\s*\{.*?^\}')
    sync_assert=extract(sync_source,r'^static QDF_STATUS __assert_trans_cb\([^;{]+?\)\s*\{.*?^\}')
    assert '__assert_trans_cb' in sync_resume and 'dsc_psoc_assert_trans_protected(dsc_psoc)' in sync_assert
    assert 'trans_start' not in sync_resume  # Resume asserts an already-held transition.
    power_completion=extract(power,r'/\* MISHARE_SSR_STOP_BEGIN:power_complete_helpers \*/\n.*?/\* MISHARE_SSR_STOP_END:power_complete_helpers \*/')
    power_native=extract(power,r'^QDF_STATUS hdd_wlan_shutdown\(void\)\s*\{.*?^\}')
    soc_native=extract(ops,r'^static void __hdd_soc_recovery_shutdown\(void\)\s*\{.*?^\}')
    reinit_native=extract(ops,r'^static int hdd_soc_recovery_reinit\([^;{]+?\)\s*\{.*?^\}')
    for path, fn in [(power_path,power_native),(ops_path,soc_native),(ops_path,reinit_native)]:
        pristine=subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+path],text=True)
        assert remove_ssr_stop_additions(fn) in pristine, 'Unbounded native SSR function delta'
    post_begin=main.index('\t\tqdf_status = cds_post_disable();',main.index('static int hdd_mishare_stop_modules('))
    post_end=main.index('\t\thdd_unregister_notifiers(hdd_ctx);',post_begin)
    post_native=main[post_begin:post_end]
    def journal_tag(tag):
        return extract(main, r'/\* MISHARE_SSR_STOP_BEGIN:journal_'+tag+r' \*/\n.*?/\* MISHARE_SSR_STOP_END:journal_'+tag+r' \*/')
    module_state=journal_tag('state');module_begin=journal_tag('begin');module_finish=journal_tag('finish')
    module_resume=extract(main,r'^int hdd_mishare_resume_stop_modules\([^;{]+?\)\s*\{.*?^\}')
    module_function=extract(main,r'^static int hdd_mishare_stop_modules\([^;{]+?\)\s*\{.*?^\}')
    assert module_function.index('mishare_ssr_stop_begin_locked(') < module_function.index('cds_set_driver_state_module_stop(true)') < module_function.index('cds_post_disable(')
    assert module_function.index('MISHARE_SSR_STOP_POST_DISABLED') < module_function.index('mishare_wonder_host_ssr_prepare_locked(') < module_function.index('MISHARE_SSR_STOP_PARENTS') < module_function.index('hdd_unregister_notifiers(')
    assert module_function.index('journal_dp_error') < module_function.index('ret = hdd_objmgr_release_and_destroy_pdev(') < module_function.index('journal_pdev_error') < module_function.index('qdf_status = cds_close(')
    state_native=extract(ops,r'/\* MISHARE_SSR_STOP_BEGIN:ops_state \*/\n.*?/\* MISHARE_SSR_STOP_END:ops_state \*/')
    qdf_enum=extract((wlan/'qca-wifi-host-cmn/qdf/inc/qdf_status.h').read_text(),r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;')
    qdf_from_os=extract((wlan/qdf_path).read_text(),r'^QDF_STATUS qdf_status_from_os_return\([^;{]+?\)\s*\{.*?^\}')
    assert qdf_from_os in subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+qdf_path],text=True)
    ssr_models=SSR_STOP_MODELS
    for tag, body in [('NATIVE_QDF_FROM_OS',qdf_from_os),('NATIVE_SSR_STATE',state_native),('NATIVE_MODULE_STATE',module_state),('NATIVE_MODULE_BEGIN',module_begin),('NATIVE_MODULE_FINISH',module_finish),('NATIVE_MODULE_RESUME',module_resume),('NATIVE_POST_DISABLE',post_native),('NATIVE_POWER_COMPLETION',power_completion),('NATIVE_POWER_SHUTDOWN',power_native),('NATIVE_SOC_SHUTDOWN',soc_native),('NATIVE_SOC_REINIT',reinit_native)]:
        ssr_models=ssr_models.replace(tag,body)
    code = wrappers + '\n#include "wlan_hdd_mishare_host.c"\n' + IDLE_MODELS.replace('NATIVE_IDLE',idle+'\n'+mode) + RESET_MODELS.replace('NATIVE_QDF_STATUS',qdf_enum).replace('NATIVE_RESET',reset_native) + ssr_models + HARNESS.replace('\n GUARD\n','\n '+guard+'\n').replace('\n ROLLBACK\n','\n '+rollback+'\n')
    production = ROOT/'kernel/popsicle-hdd'
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in production.glob('*') if p.is_file()}
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp)
        (d/'fixture.h').write_text(COMMON)
        for name in ['linux/device.h','wlan_objmgr_psoc_obj.h','wlan_objmgr_pdev_obj.h','linux/types.h','linux/etherdevice.h','linux/rtnetlink.h','linux/slab.h','linux/spinlock.h','cds_api.h','wlan_hdd_main.h','osif_psoc_sync.h','osif_vdev_sync.h']:
            p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* declarations supplied by fixture.h */\n')
        source=d/'test.c';source.write_text(code)
        exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread',
                        '-include',str(d/'fixture.h'),'-I'+str(d),'-I'+str(production),str(source),'-o',str(exe)]
        subprocess.run(command,check=True)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        stdout=subprocess.check_output([exe],text=True,env=env,timeout=10)
        # Mutation controls must reach behavior assertions, not fail compilation.
        host_source=(production/'wlan_hdd_mishare_host.c').read_text()
        stop_helper=extract(host_source, r'^int mishare_wonder_host_stop_ready_locked\([^;{]+?\)\s*\{.*?^\}')
        for needle,marker in [('mishare_runtime_psoc_busy(hdd->psoc)','EXPECTED_RUNTIME_STOP_GUARD'),('mishare_wonder_host_psoc_busy(hdd->psoc)','EXPECTED_HOST_STOP_GUARD')]:
            assert stop_helper.count(needle)==1
            (d/'wlan_hdd_mishare_host.c').write_text(host_source.replace(stop_helper,stop_helper.replace(needle,'false'),1))
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1000:])
        identity = extract(host_source, r'^static int mishare_host_parent_identity\([^;{]+?\)\s*\{.*?^\}')
        unpin = extract(host_source, r'^static void mishare_host_unpin_parents\([^;{]+?\)\s*\{.*?^\}')
        parent_controls = []
        for field in ['parent_dev', 'psoc', 'pdev']:
            needle = f'host->hdd->{field} != host->{field}'
            assert identity.count(needle) == 1
            parent_controls.append((host_source.replace(identity, identity.replace(needle, 'false'), 1), 'EXPECTED_PARENT_IDENTITY'))
        for statement, marker in [
            ('wlan_objmgr_pdev_release_ref(host->pdev, WLAN_HDD_ID_OBJ_MGR);', 'EXPECTED_PARENT_RELEASE_ORDER'),
            ('wlan_objmgr_psoc_release_ref(host->psoc, WLAN_HDD_ID_OBJ_MGR);', 'EXPECTED_PARENT_RELEASE_ORDER'),
            ('put_device(host->parent_dev);', 'EXPECTED_PARENT_UNPIN'),
        ]:
            assert unpin.count(statement) == 1
            parent_controls.append((host_source.replace(unpin, unpin.replace(statement, '/* omitted by mutation */'), 1), marker))
        relation = 'wlan_pdev_get_psoc(hdd->pdev) != hdd->psoc'
        assert host_source.count(relation) == 1
        # Keep evaluating the boundary so controls cannot pass by making a stub unused.
        parent_controls.append((host_source.replace(relation, '('+relation+') && false', 1), 'EXPECTED_PARENT_RELATION'))
        for mutation, marker in parent_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(mutation)
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])
        handoff = extract(host_source, r'^int mishare_wonder_host_handoff_idle_locked\([^;{]+?\)\s*\{.*?^\}')
        prepare = extract(host_source, r'^int mishare_wonder_host_idle_prepare_locked\([^;{]+?\)\s*\{.*?^\}')
        candidate = extract(host_source, r'^static int mishare_host_idle_candidate\([^;{]+?\)\s*\{.*?^\}')
        idle_controls = []
        def mutate_body(body, needle, replacement, marker):
            assert body.count(needle) == 1, needle
            idle_controls.append((host_source.replace(body, body.replace(needle, replacement, 1), 1), marker))
        for needle in ['host->idle_owned = true;', 'host->session.closing = true;', '*owner = NULL;']:
            mutate_body(handoff, needle, '/* omitted by mutation */', 'EXPECTED_IDLE_HANDOFF')
        for needle, marker in [
            ('!host->idle_owned', 'EXPECTED_IDLE_OWNERSHIP'),
            ('host->hdd != hdd', 'EXPECTED_IDLE_OWNERSHIP'),
            ('host->parent_dev != hdd->parent_dev', 'EXPECTED_IDLE_PREFLIGHT'),
            ('host->pdev != hdd->pdev', 'EXPECTED_IDLE_PREFLIGHT'),
            ('host->psoc != hdd->psoc', 'EXPECTED_IDLE_RESULT'),
        ]:
            mutate_body(candidate, needle, '(false && ('+needle+'))', marker)
        mutate_body(prepare, 'return -EAGAIN;', 'return 0;', 'EXPECTED_STOP_ADMISSION')
        mutate_body(prepare, 'if (ret)\n            break;', 'if (ret) { rtnl_unlock(); return 0; }', 'EXPECTED_STOP_ADMISSION')
        mutate_body(prepare, '    rtnl_unlock();', '    if (ret) rtnl_unlock();', 'EXPECTED_IDLE_UNLOCK')
        final = '    return mishare_wonder_host_stop_ready_locked(hdd);'
        index = prepare.rindex(final)
        changed = prepare[:index] + prepare[index:].replace(final, '    return 0;', 1)
        idle_controls.append((host_source.replace(prepare, changed, 1), 'EXPECTED_STOP_ADMISSION'))
        assert len(idle_controls) == 12
        for mutation, marker in idle_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(mutation)
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])
        ssr = extract(host_source, r'^int mishare_wonder_host_reclaim_handoff_ssr_locked\([^;{]+?\)\s*\{.*?^\}')
        ssr_controls = []
        def ssr_mutate(body, needle, replacement, marker):
            assert body.count(needle) == 1, needle
            ssr_controls.append((host_source.replace(body, body.replace(needle, replacement, 1), 1), marker))
        ssr_mutate(candidate, 'host->hdd == hdd && hdd->psoc != host->psoc',
                   'false && host->hdd == hdd && hdd->psoc != host->psoc', 'EXPECTED_HANDOFF_SSR_ADMISSION')
        ssr_mutate(ssr, '!cds_is_driver_recovering()', 'false && !cds_is_driver_recovering()', 'EXPECTED_HANDOFF_SSR_ADMISSION')
        ssr_mutate(ssr, 'mishare_wonder_host_reclaim_ssr_locked(&host)',
                   'mishare_wonder_host_destroy_locked(&host)', 'EXPECTED_HANDOFF_SSR_POLL')
        ssr_mutate(ssr, '        if (ret)\n            return ret;\n        ret = mishare_host_idle_candidate',
                   '        if (ret)\n            return 0;\n        ret = mishare_host_idle_candidate', 'EXPECTED_HANDOFF_SSR_POLL')
        ssr_mutate(ssr, '    ret = mishare_host_idle_candidate(hdd, &host);\n    if (ret)\n        return ret;',
                   '    ret = mishare_host_idle_candidate(hdd, &host);\n    if (ret && ret != -EBUSY)\n        return ret;', 'EXPECTED_HANDOFF_SSR_PREFLIGHT')
        ssr_mutate(stop_helper, 'mishare_host_hdd_mismatch(hdd)', 'mishare_host_hdd_mismatch(hdd) && false', 'EXPECTED_STALE_PARENT_ADMISSION')
        assert len(ssr_controls) == 6
        for mutation, marker in ssr_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(mutation)
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])
        (d/'wlan_hdd_mishare_host.c').unlink()
        bodies=[idle,request_prefix]+[extract(main,r'^static int\s+'+name+r'\([^;{]+?\)\s*\{.*?^\}') for name in ['__hdd_mode_change_psoc_idle_shutdown','hdd_mode_change_psoc_idle_shutdown']]
        for body in bodies:
            needle='mishare_wonder_host_idle_prepare_locked(hdd_ctx)' if body==idle else 'mishare_wonder_host_stop_ready_locked(hdd_ctx)';assert body.count(needle)==1 and code.count(body)==1
            source.write_text(code.replace(body,body.replace(needle,'0'),1));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            marker='EXPECTED_MODE_REQUEST_ADMISSION' if body==request_prefix else 'EXPECTED_STOP_ADMISSION'
            assert bad.returncode==-6 and marker in bad.stderr,(bad.returncode,bad.stderr[-1000:])

        # A snapshot-only gate would keep handed-off owners permanently busy.
        needle = 'mishare_wonder_host_idle_prepare_locked(hdd_ctx)'
        assert idle.count(needle) == 1
        source.write_text(code.replace(idle, idle.replace(needle, 'mishare_wonder_host_stop_ready_locked(hdd_ctx)', 1), 1))
        subprocess.run(command, check=True)
        bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
        assert bad.returncode == -6 and 'EXPECTED_IDLE_RESULT' in bad.stderr, (bad.returncode, bad.stderr[-1000:])

        # New reset controls must fail behavior/ownership assertions after compiling.
        source.write_text(code)
        query = extract(host_source, r'^bool mishare_wonder_host_adapter_owned\([^;{]+?\)\s*\{.*?^\}')
        query_controls = [
            (query.replace('if (!adapter)', 'if (false && !adapter)', 1), 'EXPECTED_NULL_ADAPTER_QUERY'),
            (query.replace('host->adapter == adapter', 'false && host->adapter == adapter', 1), 'EXPECTED_ADAPTER_OWNER_QUERY'),
        ]
        for changed, marker in query_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(host_source.replace(query, changed, 1))
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])
        (d/'wlan_hdd_mishare_host.c').unlink()
        needle = 'mishare_wonder_host_adapter_owned(adapter)'
        assert reset_native.count(needle) == 1
        put = 'hdd_adapter_dev_put_debug(adapter,\n\t\t\t\t\t\t  NET_DEV_HOLD_RESET_ALL_ADAPTERS);'
        assert reset_native.count(put) == 1
        reset_controls = [
            (reset_native.replace(needle, 'false && '+needle, 1), 'EXPECTED_PRIVATE_RESET_SKIP'),
            (reset_native.replace(put, '/* omitted iterator put */', 1), 'EXPECTED_RESET_ITERATOR_BALANCE'),
            (reset_native.replace(needle, '(adapter->device_mode == QDF_PASSTHRU_MODE || '+needle+')', 1), 'EXPECTED_UNOWNED_RESET'),
        ]
        for changed, marker in reset_controls:
            source.write_text(code.replace(reset_native, changed, 1))
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])

        # Native stop/power/shutdown/reinit controls use fresh base code each time.
        ssr_chain_controls = []
        def chain_mutate(body, needle, replacement, marker):
            assert body.count(needle) == 1, needle
            ssr_chain_controls.append((code.replace(body, body.replace(needle, replacement, 1), 1), marker))
        chain_mutate(post_native, 'is_recovery_stop &&\n\t\t\t    mishare_wonder_host_stop_ready_locked(hdd_ctx)',
                     'is_recovery_stop && false &&\n\t\t\t    mishare_wonder_host_stop_ready_locked(hdd_ctx)', 'EXPECTED_POST_DISABLE_ERROR')
        chain_mutate(post_native, 'int stop_ret = mishare_wonder_host_ssr_prepare_locked(hdd_ctx);',
                     'int stop_ret = 0 * mishare_wonder_host_ssr_prepare_locked(hdd_ctx);', 'EXPECTED_PARENT_BOUNDARY')
        chain_mutate(power_native, 'if (stop_ret && private_stop)', 'if (stop_ret && private_stop && false)', 'EXPECTED_SSR_RETENTION')
        chain_mutate(soc_native, 'mishare_ssr_stop_blocked = true;', 'mishare_ssr_stop_blocked = false;', 'EXPECTED_SSR_RETENTION')
        chain_mutate(soc_native, 'if (mishare_ssr_stop_blocked)\n\t\treturn;',
                     'if (false && mishare_ssr_stop_blocked)\n\t\treturn;', 'EXPECTED_NO_STOP_REPLAY')
        chain_mutate(reinit_native, 'if (!errno)\n\t\terrno = __hdd_soc_recovery_reinit', 'if (true)\n\t\terrno = __hdd_soc_recovery_reinit', 'EXPECTED_NO_PRIVATE_REINIT')
        chain_mutate(reinit_native, 'hdd_start_complete(mishare_private_resume ? errno : 0);',
                     'hdd_start_complete(0 * (mishare_private_resume ? errno : 0));', 'EXPECTED_SSR_FAILURE_NOTIFICATION')
        chain_mutate(power_native, 'if (stop_ret && private_stop)',
                     'if (stop_ret && private_stop && mishare_wonder_host_stop_ready_locked(hdd_ctx))', 'EXPECTED_OWNER_SNAPSHOT')
        assert len(ssr_chain_controls) == 8
        for changed_code, marker in ssr_chain_controls:
            source.write_text(changed_code)
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])

        source.write_text(code)
        prepare_ssr = extract(host_source, r'^int mishare_wonder_host_ssr_prepare_locked\([^;{]+?\)\s*\{.*?^\}')
        prepare_controls = []
        def prepare_mutate(needle, replacement, marker):
            assert prepare_ssr.count(needle) == 1, needle
            prepare_controls.append((host_source.replace(prepare_ssr, prepare_ssr.replace(needle, replacement, 1), 1), marker))
        prepare_mutate('return -EAGAIN;', 'return 0;', 'EXPECTED_SSR_PREPARE_LOCK')
        prepare_mutate('    rtnl_unlock();', '    if (!ret) rtnl_unlock();', 'EXPECTED_SSR_PREPARE_UNLOCK')
        prepare_mutate('    rtnl_unlock();\n    /*', '    rtnl_unlock();\n    if (ret) return 0;\n    /*', 'EXPECTED_SSR_PREPARE_RESULT')
        prepare_mutate('mishare_wonder_host_reclaim_handoff_ssr_locked(hdd)', 'mishare_wonder_host_destroy_locked(&host)', 'EXPECTED_SSR_PREPARE_RESULT')
        prepare_mutate('    if (ret != -EBUSY)\n        return ret;', '    if (ret != -EBUSY)\n        return ret;\n    if (ret == -EBUSY) return 0;', 'EXPECTED_SSR_PREPARE_OWNER')
        prepare_mutate('!cds_is_driver_recovering()', 'false && !cds_is_driver_recovering()', 'EXPECTED_SSR_PREPARE_RECOVERY')
        assert len(prepare_controls) == 6
        for changed, marker in prepare_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(changed)
            subprocess.run(command, check=True)
            bad = subprocess.run([exe], capture_output=True, text=True, env=env, timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr, (marker, bad.returncode, bad.stderr[-1000:])
        (d/'wlan_hdd_mishare_host.c').unlink()
        needle='mishare_wonder_host_ssr_prepare_locked(hdd_ctx)'
        assert post_native.count(needle)==1
        source.write_text(code.replace(post_native,post_native.replace(needle,'mishare_wonder_host_stop_ready_locked(hdd_ctx)',1),1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
        assert bad.returncode == -6 and 'EXPECTED_NATIVE_SSR_RETIRE' in bad.stderr,(bad.returncode,bad.stderr[-1000:])

        journal_controls=[]
        def journal_mutate(needle, replacement, marker):
            assert host_source.count(needle)==1, needle
            journal_controls.append((host_source.replace(needle,replacement,1),marker))
        journal_mutate('c->phase = MISHARE_SSR_STOP_PREFIX;', 'c->phase = MISHARE_SSR_STOP_EMPTY;', 'EXPECTED_JOURNAL_ARM')
        journal_mutate('mishare_ssr_checkpoint_matches(c, hdd, false) ? -EBUSY : -EUCLEAN',
                       'mishare_ssr_checkpoint_matches(c, hdd, false) ? 0 : -EUCLEAN', 'EXPECTED_JOURNAL_REPLAY')
        journal_mutate('c->psoc == hdd->psoc &&', '(true || c->psoc == hdd->psoc) &&', 'EXPECTED_JOURNAL_IDENTITY')
        journal_mutate('phase == MISHARE_SSR_STOP_POST_DISABLED) ||',
                       '(phase == MISHARE_SSR_STOP_POST_DISABLED || phase == MISHARE_SSR_STOP_PARENTS)) ||', 'EXPECTED_JOURNAL_ORDER')
        journal_mutate('if (!ret && (c->phase != MISHARE_SSR_STOP_PARENTS || !modules_closed))',
                       'if (false && !ret && (c->phase != MISHARE_SSR_STOP_PARENTS || !modules_closed))', 'EXPECTED_JOURNAL_ACK')
        journal_mutate('ret = c->first_error;', 'ret = result;', 'EXPECTED_JOURNAL_FIRST_ERROR')
        journal_mutate('if (c->phase != MISHARE_SSR_STOP_EMPTY) {\n        ret = mishare_ssr_checkpoint_matches',
                       'if (cds_is_driver_recovering() && c->phase != MISHARE_SSR_STOP_EMPTY) {\n        ret = mishare_ssr_checkpoint_matches', 'EXPECTED_JOURNAL_REPLAY')
        assert len(journal_controls)==7
        source.write_text(code)
        for changed,marker in journal_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(changed)
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1000:])
        (d/'wlan_hdd_mishare_host.c').unlink()
        needle='mishare_gate = mishare_ssr_stop_begin_locked('
        assert module_begin.count(needle)==1
        source.write_text(code.replace(module_begin,module_begin.replace(needle,'mishare_gate = 0 * mishare_ssr_stop_begin_locked(',1),1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
        assert bad.returncode == -6 and 'EXPECTED_MODULE_NO_REPLAY' in bad.stderr,(bad.returncode,bad.stderr[-1000:])

        pause_body=extract(host_source,r'^int mishare_ssr_stop_pause_locked\([^;{]+?\)\s*\{.*?^\}')
        resume_body=extract(host_source,r'^int mishare_ssr_stop_resume_locked\([^;{]+?\)\s*\{.*?^\}')
        resume_host_controls=[]
        def resume_mutate(body,needle,replacement,marker):
            assert body.count(needle)==1,needle
            resume_host_controls.append((host_source.replace(body,body.replace(needle,replacement,1),1),marker))
        resume_mutate(pause_body,'if ((result == -EINPROGRESS || result == -EAGAIN) &&',
                      'if (false && (result == -EINPROGRESS || result == -EAGAIN) &&','EXPECTED_SSR_WAIT_PAUSE')
        resume_mutate(pause_body,'c->paused = true;', 'c->paused = true; c->first_error = result;', 'EXPECTED_SSR_WAIT_PAUSE')
        resume_mutate(resume_body,'else if (!cds_is_driver_recovering())',
                      'else if (false && !cds_is_driver_recovering())','EXPECTED_SSR_RESUME_RECOVERY')
        resume_mutate(resume_body,'if (!mishare_ssr_checkpoint_matches(c, hdd, false) ||\n        c->driver_status != hdd->driver_status)',
                      'if (false && (!mishare_ssr_checkpoint_matches(c, hdd, false) ||\n        c->driver_status != hdd->driver_status))','EXPECTED_SSR_RESUME_IDENTITY')
        resume_mutate(resume_body,'c->driver_status != hdd->driver_status',
                      '(false && c->driver_status != hdd->driver_status)','EXPECTED_SSR_RESUME_STATUS')
        resume_mutate(resume_body,'else if (c->phase != MISHARE_SSR_STOP_POST_DISABLED ||\n             c->first_error || !c->paused)',
                      'else if (false && (c->phase != MISHARE_SSR_STOP_POST_DISABLED ||\n             c->first_error || !c->paused))','EXPECTED_SSR_RESUME_HARD_FAILURE')
        assert len(resume_host_controls)==6
        source.write_text(code)
        for changed,marker in resume_host_controls:
            (d/'wlan_hdd_mishare_host.c').write_text(changed)
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1000:])
        (d/'wlan_hdd_mishare_host.c').unlink()
        native_resume_controls=[]
        def native_resume_mutate(body,needle,replacement,marker):
            assert body.count(needle)==1,needle
            native_resume_controls.append((code.replace(body,body.replace(needle,replacement,1),1),marker))
        native_resume_mutate(module_begin,'if (ftm_mode || hdd_get_conparam() != QDF_GLOBAL_MISSION_MODE)',
                             'if (false && (ftm_mode || hdd_get_conparam() != QDF_GLOBAL_MISSION_MODE))','EXPECTED_SSR_RESUME_MODE')
        native_resume_mutate(module_begin,'goto mishare_post_disable_resume;',
                             'if (false) goto mishare_post_disable_resume;','EXPECTED_SSR_RESUME_COMPLETE')
        native_resume_mutate(module_resume,'hdd_mishare_stop_modules(hdd_ctx, false, true)',
                             'hdd_mishare_stop_modules(hdd_ctx, false, false)','EXPECTED_SSR_RESUME_COMPLETE')
        native_resume_mutate(post_native,'int stop_ret = mishare_wonder_host_ssr_prepare_locked(hdd_ctx);',
                             'int stop_ret = mishare_resume ? 0 : mishare_wonder_host_ssr_prepare_locked(hdd_ctx);','EXPECTED_PARENT_BOUNDARY')
        assert len(native_resume_controls)==4
        for changed,marker in native_resume_controls:
            source.write_text(changed)
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1000:])

        power_resume=extract(power_completion,r'^int hdd_mishare_resume_shutdown\([^;{]+?\)\s*\{.*?^\}')
        upper_controls=[]
        def upper_mutate(body,needle,replacement,marker):
            assert body.count(needle)==1,needle
            upper_controls.append((code.replace(body,body.replace(needle,replacement,1),1),marker))
        upper_mutate(power_resume,'if (ret)\n\t\treturn ret;',
                     'if (false && ret)\n\t\treturn ret;','EXPECTED_POWER_ACK_ORDER')
        upper_mutate(power_resume,'\thdd_mishare_shutdown_complete(hdd_ctx);',
                     '\t/* omitted power completion */','EXPECTED_UPPER_ACK_REQUIRED')
        upper_mutate(reinit_native,'if (!errno)\n\t\t\tmishare_ssr_stop_blocked = false;',
                     'if (true)\n\t\t\tmishare_ssr_stop_blocked = false;','EXPECTED_PRIVATE_TRANSITION_RETAINED')
        upper_mutate(reinit_native,'if (!mishare_ssr_stop_blocked)\n\t\tosif_psoc_sync_trans_stop(psoc_sync);',
                     'if (true)\n\t\tosif_psoc_sync_trans_stop(psoc_sync);','EXPECTED_PRIVATE_TRANSITION_RETAINED')
        upper_mutate(reinit_native,'else if (hdd_ctx->parent_dev != dev)',
                     'else if (false && hdd_ctx->parent_dev != dev)','EXPECTED_CALLBACK_DEVICE')
        upper_mutate(power_resume,'\tret = hdd_mishare_resume_stop_modules(hdd_ctx);',
                     '\thdd_mishare_shutdown_complete(hdd_ctx);\n\tret = hdd_mishare_resume_stop_modules(hdd_ctx);','EXPECTED_POWER_ACK_ORDER')
        upper_mutate(reinit_native,'hdd_start_complete(mishare_private_resume ? errno : 0);',
                     'hdd_start_complete(mishare_ssr_stop_blocked ? errno : 0);','EXPECTED_UPPER_FAILURE_NOTIFY')
        upper_mutate(power_resume,'if (ret)\n\t\treturn ret;',
                     'if (ret && ret != -ENOENT)\n\t\treturn ret;','EXPECTED_NO_PRIVATE_REINIT')
        upper_mutate(reinit_native,'errno = hdd_mishare_resume_shutdown(hdd_ctx);',
                     'errno = __hdd_soc_recovery_reinit(dev, bdev, bid, bus_type);','EXPECTED_NO_PRIVATE_REINIT')
        upper_mutate(power_resume,'\thdd_mishare_shutdown_complete(hdd_ctx);',
                     '\thdd_mishare_shutdown_complete(hdd_ctx);\n\thdd_mishare_shutdown_complete(hdd_ctx);','EXPECTED_UPPER_ACK_REQUIRED')
        assert len(upper_controls)==10
        for changed,marker in upper_controls:
            source.write_text(changed)
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode == -6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1000:])

    report={'status':'MISHARE_HOST_LIFETIME_FIXTURE_PASS_ONLY','negative_stop_controls_rejected':6,'negative_parent_controls_rejected':7,'negative_idle_controls_rejected':13,'negative_handoff_ssr_controls_rejected':6,'negative_reset_controls_rejected':5,'negative_ssr_stop_controls_rejected':8,'negative_ssr_prepare_controls_rejected':7,'ssr_prepare_contract_cases':18,'ssr_journal_scenarios':8,'ssr_resume_scenarios':17,'ssr_upper_scenarios':16,'native_sync_resume_sha256':hashlib.sha256(sync_resume.encode()).hexdigest(),'native_sync_source_sha256':hashlib.sha256(sync_source.encode()).hexdigest(),'negative_ssr_upper_controls_rejected':10,'negative_ssr_resume_controls_rejected':10,'negative_ssr_journal_controls_rejected':8,'native_module_begin_sha256':hashlib.sha256(module_begin.encode()).hexdigest(),'native_module_finish_sha256':hashlib.sha256(module_finish.encode()).hexdigest(),'native_module_resume_sha256':hashlib.sha256(module_resume.encode()).hexdigest(),'ssr_stop_contract_cases':15,'native_reset_contract_cases':62,'parent_identity_rejections':36,'production_sha256':hashes,'fixture_sha256':hashlib.sha256((COMMON+code).encode()).hexdigest(),
            'production_ssr_prepare_sha256':hashlib.sha256(prepare_ssr.encode()).hexdigest(),'native_idle_sha256':hashlib.sha256(idle.encode()).hexdigest(),'native_reset_sha256':hashlib.sha256(reset_native.encode()).hexdigest(),'native_reset_original_sha256':hashlib.sha256(reset_original.encode()).hexdigest(),'native_ssr_source_sha256':{name:hashlib.sha256((wlan/name).read_bytes()).hexdigest() for name in ['qcacld-3.0/core/hdd/src/wlan_hdd_main.c',power_path,ops_path,qdf_path]},'native_ssr_function_sha256':{name:hashlib.sha256(body.encode()).hexdigest() for name,body in [('hdd_wlan_shutdown',power_native),('__hdd_soc_recovery_shutdown',soc_native),('hdd_soc_recovery_reinit',reinit_native),('qdf_status_from_os_return',qdf_from_os),('post_disable_section',post_native),('power_completion_helpers',power_completion)]},
            'native_mode_stop_sha256':hashlib.sha256(mode.encode()).hexdigest(),'native_mode_request_prefix_sha256':hashlib.sha256(request_prefix.encode()).hexdigest(),'checks':['actual native post-disable calls production SSR preparation and qualified host reclamation; failed CDS disable never admits cleanup', 'SSR prepare uses RTNL trylock, preserves empty/standalone/caller-owned/foreign-parent admission and exact recovery qualification, and unlocks on every pending/error/success result', 'asynchronous runtime token, quarantine policy and sync-close failure retain registry authority for later qualified polling', 'native SSR post-disable prefix refuses retained owners before modeled parent close and preserves CDS failure instead of entering its assert/teardown continuation', 'complete native power shutdown and SoC shutdown/reinit functions propagate private stop errors, retain failure across owner retirement, reject duplicate stop and block reinit with failure notification', 'native QDF errno-to-status converter executes unchanged; production post-disable qualified retirement success permits normal completion under modeled qualification, but metadata retirement plus pending parent stop still blocks', 'no-private-owner recovery, legacy status handling, HIF-missing and EPPING behavior preserved; suspended/IPA/capture power branches execute with modeled primitives', 'native hdd_reset_all_adapters skips exact registered private adapters before any link reset and balances current/next iterator references', 'caller-owned, runtime-attached, pending ordinary drain and handed-off pending SSR hosts retain ownership through native reset; modeled quarantine child also skips reset', 'empty registry and mixed STA/P2P/SAP/unowned PAS preserve native queue/WMM/scan/stop and VDEV reference boundaries; owned pointer at first/middle/last position', 'NULL lookup during pre-adapter construction is false; publication and global ownership lookup use the same registry lock', 'same HDD with a replaced PSOC blocks both native idle and handed-off SSR polling; foreign HDD/PSOC pairs remain excluded', 'qualified explicit handed-off SSR entry rejects caller-owned hosts, wrong parents, missing recovery, omitted runtime coverage and policy errors without losing registry ownership', 'SSR poll preserves runtime token across repeated waits and quarantine, retains host/pins after runtime retirement if sync close fails, and later completes without stale caller slots', 'empty host registry and runtime-free host cannot hide a standalone runtime; modeled allocated runtime token count balances', 'explicit handoff closes admission, transfers sole ownership and clears a temporary caller slot without retaining its address', 'native ordinary idle retires handed-off DOWN hosts only; caller-owned, foreign-HDD, changed device/PDEV and recovering sessions cannot be adopted', 'RTNL trylock contention defers without cleanup; pending runtime drain, quarantine and sync mismatch retain registry ownership and pins', 'post-drain standalone runtime guard and original open-interface/native-stop error behavior retained; RTNL released on every attempted cleanup', 'device/PSOC/PDEV pins acquired before host registration; device, PSOC and PDEV refusal and wrong PDEV parent fully roll back', 'pins remain through runtime waits, policy rejection, sync mismatch, adapter close and sync destruction; release in reverse order exactly once', 'all six host operations reject each changed HDD parent identity before mutation, both without and with a runtime token', 'idle, mode request and both mode-change stop entries reject runtime-only and host-only ownership before native module stop; rejected inner mode retains flag; empty registries preserve native errors','SSR host bridge rejects missing recovery state, changed psoc and running/open/session adapters before handoff', 'runtime token restored on incomplete coverage, asynchronous wait and policy rejection', 'host and idle inhibition retained after runtime retirement if sync close fails', 'runtime-free host still requires exact-psoc registry emptiness', 'complete native idle shutdown defers tracked DOWN host before module stop', 'host tracked before sync/adapter allocation and retained through adapter/sync close', 'failed create rolls back idle inhibition', 'pending runtime drain and sync mismatch retain idle inhibition', 'foreign psoc and no owner preserve native idle stop result', 'failed psoc transition and open-interface paths preserve native flow', 'invalid input','owner allocation failure','sync allocation failure','adapter creation failure','context rejection','existing adapter rejection','duplicate owner rejection','running/open/session rejection retaining owner','sync registry mismatch retaining owner','unregister/drain/close/destroy ordering','repeat destroy','ordinary wrapper rejection','ndo_open rejection','factory registered-netdev failure rollback'],
            'sanitizers':['address','undefined','leak detection'],'limitations':'Complete native power shutdown/internal SoC shutdown/reinit and a bounded post-disable section execute against modeled CDS/parent-stop/probe/IRQ primitives. The native post-disable call now invokes production host preparation and qualified reclamation. SSR qualification results and later parent/probe operations remain models; no fake CDS callback performs retirement. Only explicit POST_DISABLED transient waits have a native module-suffix resume API; the native reinit callback performs one qualified module poll and the shared power tail before clearing the upper gate; pending/hard failures retain the transition; no independent worker/timer is installed; hard failures have no reset API; this is failure admission/propagation, not a complete recovery coordinator. Physical remove/close is unchanged. Complete native adapter-reset function executes with modeled held-safe iterator, one active link per adapter, queue/scan/WMM/TWT/TDLS/stop primitives and VDEV references. No real SSR timing, kernel iterator concurrency, adapter-stop bodies or native parent teardown is certified by this reset fixture. Real helper C and extracted factory/rollback fragments with simulated HDD and synchronization. Complete native idle shutdown executes against modeled psoc synchronization, event and module-stop calls. SSR batch is a result/ownership model here; actual runtime batch, recovery policy and native callbacks are exercised by the separate existing runtime fixtures. The ordinary-idle coordinator executes production C against modeled runtime return values and synchronization; real native runtime destruction is covered separately, not end-to-end with this host here. This does not certify SSR/remove or prepared/UP recovery. Registry mutexes model spinlocks. Device and object-manager reference primitives are models; this validates host pin ownership and identity admission, not physical native parent deletion. Allocation pins do not preserve HDD, native components or firmware. Caller must retain and serialize complete parent lifetime across polls. The explicit handed-off SSR poll delegates qualification to the existing bridge and modeled batch here; actual batch policy/native cleanup have separate fixtures. Native SSR post-disable now reaches the qualified bridge; native reinit-triggered continuation is installed; independent retry scheduling and physical-remove coordination remain unconnected. This does not certify native kernel locking, teardown or radio validation.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(stdout,end='')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.wlan,args.output)
