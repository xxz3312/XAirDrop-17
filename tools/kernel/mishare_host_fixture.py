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
struct hdd_context { struct device *parent_dev; struct wlan_objmgr_psoc *psoc; struct wlan_objmgr_pdev *pdev; };
bool mishare_wonder_host_psoc_busy(struct wlan_objmgr_psoc *psoc);
struct hdd_adapter { struct net_device *dev; struct link_info *deflink; unsigned long event_flags; int device_mode; struct qdf_mac_addr mac_addr; };
struct hdd_adapter_create_param { int num_sessions; };
struct osif_vdev_sync { int id; };
static bool rtnl_owned=true, parent_owned=true, identity_refusal_expected;
static bool rtnl_contended, native_idle_active, idle_retirement_expected;
static int rtnl_attempts;
static struct wlan_objmgr_psoc *expected_psoc;
static int failure, validations, closed, dp_destroyed;
static int device_pins, psoc_pins, pdev_pins;
#define WLAN_HDD_ID_OBJ_MGR 9
#define QDF_STATUS_SUCCESS 0
static void pins_live(void) { assert(device_pins==1 && psoc_pins==1 && pdev_pins==1 && "EXPECTED_PARENT_PINS"); }
static void pins_empty(void) { assert(!device_pins && !psoc_pins && !pdev_pins && "EXPECTED_PARENT_UNPIN"); }
static char trace[256];
static struct hdd_adapter *active;
static struct osif_vdev_sync *registered;
static const u8 mac[6]={2,3,4,5,6,7};
static void event(char c) { size_t n=strlen(trace);assert(n+1<sizeof(trace));trace[n]=c;trace[n+1]=0; }
static void reset(int fail) { pins_empty();assert(!active && !registered);assert(!expected_psoc || !mishare_wonder_host_psoc_busy(expected_psoc));failure=fail;trace[0]=0; }
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
static int osif_vdev_sync_create(struct device *d,struct osif_vdev_sync **s) { assert(d && parent_owned && mishare_wonder_host_psoc_busy(expected_psoc));pins_live();event('S');if(failure==2)return -ENOMEM;*s=calloc(1,sizeof(**s));return 0; }
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
 pins_live();assert(psoc==expected_psoc && parent_owned && rtnl_owned && runtime_ssr);
 assert(count<=1 && (count ? items && items[0].owner : !items));batch_calls++;
 if(batch_extra)return -EBUSY;
 if(batch_rc) {if(count)items[0].result=batch_rc;return batch_rc;}
 if(count) {free(items[0].owner);items[0].owner=NULL;items[0].result=0;runtime_closed++;}
 return 0;
}
int mishare_runtime_create(struct wlan_objmgr_pdev *pdev,const u8 *address,void *osif,struct wireless_dev *wdev,struct mishare_runtime_owner **owner) { pins_live();assert(pdev && pdev->refs==1 && address && osif && wdev);if(*owner)return -EBUSY;*owner=calloc(1,sizeof(**owner));return 0; }
int mishare_runtime_destroy(struct mishare_runtime_owner **owner) { idle_cleanup_boundary();pins_live();if(!*owner)return 0;if(runtime_ssr)return -EUCLEAN;if(runtime_error)return runtime_error;if(runtime_busy)return -EINPROGRESS;free(*owner);*owner=NULL;runtime_closed++;return 0; }
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
    code = wrappers + '\n#include "wlan_hdd_mishare_host.c"\n' + IDLE_MODELS.replace('NATIVE_IDLE',idle+'\n'+mode) + HARNESS.replace('\n GUARD\n','\n '+guard+'\n').replace('\n ROLLBACK\n','\n '+rollback+'\n')
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

    report={'status':'MISHARE_HOST_LIFETIME_FIXTURE_PASS_ONLY','negative_stop_controls_rejected':6,'negative_parent_controls_rejected':7,'negative_idle_controls_rejected':13,'parent_identity_rejections':36,'production_sha256':hashes,'fixture_sha256':hashlib.sha256((COMMON+code).encode()).hexdigest(),
            'native_idle_sha256':hashlib.sha256(idle.encode()).hexdigest(),
            'native_mode_stop_sha256':hashlib.sha256(mode.encode()).hexdigest(),'native_mode_request_prefix_sha256':hashlib.sha256(request_prefix.encode()).hexdigest(),'checks':['explicit handoff closes admission, transfers sole ownership and clears a temporary caller slot without retaining its address', 'native ordinary idle retires handed-off DOWN hosts only; caller-owned, foreign-HDD, changed device/PDEV and recovering sessions cannot be adopted', 'RTNL trylock contention defers without cleanup; pending runtime drain, quarantine and sync mismatch retain registry ownership and pins', 'post-drain standalone runtime guard and original open-interface/native-stop error behavior retained; RTNL released on every attempted cleanup', 'device/PSOC/PDEV pins acquired before host registration; device, PSOC and PDEV refusal and wrong PDEV parent fully roll back', 'pins remain through runtime waits, policy rejection, sync mismatch, adapter close and sync destruction; release in reverse order exactly once', 'all six host operations reject each changed HDD parent identity before mutation, both without and with a runtime token', 'idle, mode request and both mode-change stop entries reject runtime-only and host-only ownership before native module stop; rejected inner mode retains flag; empty registries preserve native errors','SSR host bridge rejects missing recovery state, changed psoc and running/open/session adapters before handoff', 'runtime token restored on incomplete coverage, asynchronous wait and policy rejection', 'host and idle inhibition retained after runtime retirement if sync close fails', 'runtime-free host still requires exact-psoc registry emptiness', 'complete native idle shutdown defers tracked DOWN host before module stop', 'host tracked before sync/adapter allocation and retained through adapter/sync close', 'failed create rolls back idle inhibition', 'pending runtime drain and sync mismatch retain idle inhibition', 'foreign psoc and no owner preserve native idle stop result', 'failed psoc transition and open-interface paths preserve native flow', 'invalid input','owner allocation failure','sync allocation failure','adapter creation failure','context rejection','existing adapter rejection','duplicate owner rejection','running/open/session rejection retaining owner','sync registry mismatch retaining owner','unregister/drain/close/destroy ordering','repeat destroy','ordinary wrapper rejection','ndo_open rejection','factory registered-netdev failure rollback'],
            'sanitizers':['address','undefined','leak detection'],'limitations':'Real helper C and extracted factory/rollback fragments with simulated HDD and synchronization. Complete native idle shutdown executes against modeled psoc synchronization, event and module-stop calls. SSR batch is a result/ownership model here; actual runtime batch, recovery policy and native callbacks are exercised by the separate existing runtime fixtures. The ordinary-idle coordinator executes production C against modeled runtime return values and synchronization; real native runtime destruction is covered separately, not end-to-end with this host here. This does not certify SSR/remove or prepared/UP recovery. Registry mutexes model spinlocks. Device and object-manager reference primitives are models; this validates host pin ownership and identity admission, not physical native parent deletion. Allocation pins do not preserve HDD, native components or firmware. Caller must retain and serialize complete parent lifetime across polls. This is not an SSR/remove coordinator, native kernel locking, teardown or radio validation.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(stdout,end='')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.wlan,args.output)
