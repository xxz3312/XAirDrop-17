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
struct device { int dummy; };
struct wireless_dev { int dummy; };
struct net_device { bool running; struct wireless_dev *ieee80211_ptr; };
struct link_info { unsigned long link_flags[1]; };
struct qdf_mac_addr { u8 bytes[6]; };
struct wlan_objmgr_pdev { int dummy; };
struct hdd_context { struct device *parent_dev; void *psoc; struct wlan_objmgr_pdev *pdev; };
struct hdd_adapter { struct net_device *dev; struct link_info *deflink; unsigned long event_flags; int device_mode; struct qdf_mac_addr mac_addr; };
struct hdd_adapter_create_param { int num_sessions; };
struct osif_vdev_sync { int id; };
static bool rtnl_owned=true, parent_owned=true;
static int failure, validations, closed, dp_destroyed;
static char trace[256];
static struct hdd_adapter *active;
static struct osif_vdev_sync *registered;
static const u8 mac[6]={2,3,4,5,6,7};
static void event(char c) { size_t n=strlen(trace);assert(n+1<sizeof(trace));trace[n]=c;trace[n+1]=0; }
static void reset(int fail) { assert(!active && !registered);failure=fail;trace[0]=0; }
static bool is_valid_ether_addr(const u8 *a) { u8 v=0;for(int i=0;i<6;i++)v|=a[i];return v && !(a[0]&1); }
static void ether_addr_copy(u8 *d,const u8 *s) { memcpy(d,s,6); }
static void *kzalloc(size_t n,int flags) { (void)flags;event('A');return failure==1?NULL:calloc(1,n); }
static void kfree(void *p) { event('F');free(p); }
static bool test_bit(unsigned n,const unsigned long *p) { return !!(*p & (1UL<<n)); }
static bool netif_running(struct net_device *d) { return d->running; }
static void osif_psoc_sync_assert_trans_protected(struct device *d) { assert(d && rtnl_owned && parent_owned);event('P'); }
static int wlan_hdd_validate_context(struct hdd_context *h) { assert(h);validations++;event('V');return failure==4?-ENODEV:0; }
static struct hdd_adapter *hdd_get_adapter(struct hdd_context *h,int mode) { assert(h && mode==17);event('L');return failure==5?(struct hdd_adapter*)1:active; }
static int osif_vdev_sync_create(struct device *d,struct osif_vdev_sync **s) { assert(d && parent_owned);event('S');if(failure==2)return -ENOMEM;*s=calloc(1,sizeof(**s));return 0; }
static void osif_vdev_sync_destroy(struct osif_vdev_sync *s) { assert(s && s!=registered);event('D');free(s); }
static void osif_vdev_sync_register(struct net_device *d,struct osif_vdev_sync *s) { assert(d && s && !registered);registered=s;event('R'); }
static struct osif_vdev_sync *osif_vdev_sync_unregister(struct net_device *d) { assert(d);struct osif_vdev_sync *s=registered;registered=NULL;event('U');return s; }
static void osif_vdev_sync_wait_for_ops(struct osif_vdev_sync *s) { assert(s && !registered);event('W'); }
static void hdd_close_adapter(struct hdd_context *h,struct hdd_adapter *a,bool locked) { assert(h && a==active && locked && rtnl_owned);event('C');free(a->dev);free(a->deflink);free(a);active=NULL;closed++; }
static void hdd_cleanup_adapter(struct hdd_context *h,struct hdd_adapter *a,bool locked) { hdd_close_adapter(h,a,locked); }
static void qdf_copy_macaddr(struct qdf_mac_addr *d,const struct qdf_mac_addr *s) { memcpy(d,s,sizeof(*d)); }
static void ucfg_dp_destroy_intf(void *p,struct qdf_mac_addr *a) { assert(p && !memcmp(a->bytes,mac,6));event('X');dp_destroyed++; }
#include "wlan_hdd_mishare_runtime.h"
struct mishare_runtime_owner { int dummy; };
static int runtime_busy,runtime_closed;
int mishare_runtime_create(struct wlan_objmgr_pdev *pdev,const u8 *address,void *osif,struct wireless_dev *wdev,struct mishare_runtime_owner **owner) { assert(pdev && address && osif && wdev);if(*owner)return -EBUSY;*owner=calloc(1,sizeof(**owner));return 0; }
int mishare_runtime_destroy(struct mishare_runtime_owner **owner) { if(!*owner)return 0;if(runtime_busy)return -EINPROGRESS;free(*owner);*owner=NULL;runtime_closed++;return 0; }
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
int main(void)
{
 struct device dev={0};struct wlan_objmgr_pdev pdev={0};struct wireless_dev wdev={0};struct hdd_context h={.parent_dev=&dev,.psoc=&dev,.pdev=&pdev};struct mishare_wonder_host *owner=NULL;
 assert(mishare_wonder_host_create_locked(&h,mac,NULL)==-EINVAL);
 u8 invalid[6]={1,2,3,4,5,6};assert(mishare_wonder_host_create_locked(&h,invalid,&owner)==-EINVAL);
 assert(mishare_wonder_host_destroy_locked(NULL)==-EINVAL);
 assert(mishare_wonder_host_destroy_locked(&owner)==0);
 reset(1);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENOMEM && !owner);assert(!strcmp(trace,"PVLA"));
 reset(2);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENOMEM && !owner);assert(!strcmp(trace,"PVLASF"));
 reset(3);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENODEV && !owner);assert(!strcmp(trace,"PVLASHDF"));
 reset(4);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-ENODEV && !owner);assert(!strcmp(trace,"PV"));
 reset(5);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-EBUSY && !owner);assert(!strcmp(trace,"PVL"));
 reset(0);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==0 && owner && active && registered);assert(!strcmp(trace,"PVLASHR"));
 trace[0]=0;assert(mishare_wonder_host_create_locked(&h,mac,&owner)==-EBUSY && trace[0]==0);
 active->dev->running=true;assert(mishare_wonder_host_destroy_locked(&owner)==-EBUSY && owner && registered);active->dev->running=false;
 active->event_flags=1UL<<DEVICE_IFACE_OPENED;assert(mishare_wonder_host_destroy_locked(&owner)==-EBUSY && owner && registered);active->event_flags=0;
 active->deflink->link_flags[0]=1UL<<SME_SESSION_OPENED;assert(mishare_wonder_host_destroy_locked(&owner)==-EBUSY && owner && registered);active->deflink->link_flags[0]=0;
 struct osif_vdev_sync *original=registered, foreign={0};registered=&foreign;
 assert(mishare_wonder_host_destroy_locked(&owner)==-EIO && owner && active && registered==&foreign);registered=original;
 assert(mishare_wonder_host_vdev_create_locked(owner)==-ESHUTDOWN);
 assert(mishare_wonder_host_session_step_locked(owner,5240,1,2)==-ESHUTDOWN);
 assert(mishare_wonder_host_destroy_locked(&owner)==0 && !owner && !active && !registered);
 reset(0);assert(mishare_wonder_host_create_locked(&h,mac,&owner)==0);
 active->dev->ieee80211_ptr=&wdev;
 assert(!mishare_wonder_host_vdev_create_locked(owner));
 assert(mishare_wonder_host_vdev_create_locked(owner)==-EBUSY);
 runtime_busy=1;
 assert(mishare_wonder_host_destroy_locked(&owner)==-EINPROGRESS && owner && active && registered);
 assert(mishare_wonder_host_vdev_destroy_locked(owner)==-EINPROGRESS);
 runtime_busy=0;
 assert(mishare_wonder_host_vdev_destroy_locked(owner)==0);
 assert(mishare_wonder_host_session_step_locked(owner,5240,1,2)==-ESHUTDOWN);
 assert(mishare_wonder_host_vdev_create_locked(owner)==-ESHUTDOWN);
 trace[0]=0;assert(mishare_wonder_host_destroy_locked(&owner)==0 && !owner && !active && !registered);assert(!strcmp(trace,"PUWCDF"));
 assert(mishare_wonder_host_destroy_locked(&owner)==0 && runtime_closed==1);
 /* The ordinary production wrapper must reject PASSTHRU, factory-only override. */
 struct hdd_adapter_create_param params={.num_sessions=1};
 assert(hdd_open_adapter(&h,17,"misharewt%d",(u8*)mac,0,true,&params)==NULL && !active);
 assert(hdd_mishare_host_only_open(NULL)==-EOPNOTSUPP);
 reset(0);struct hdd_adapter *a=hdd_mishare_host_adapter_open(&h,(u8*)mac);assert(a && active);
 trace[0]=0;assert(factory_rollback(&h,a,true,true)==NULL && !active);assert(!strcmp(trace,"CX") && dp_destroyed==1);
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
    code = wrappers + '\n#include "wlan_hdd_mishare_host.c"\n' + HARNESS.replace('GUARD',guard).replace('ROLLBACK',rollback)
    production = ROOT/'kernel/popsicle-hdd'
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in production.glob('*') if p.is_file()}
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp)
        (d/'fixture.h').write_text(COMMON)
        for name in ['linux/types.h','linux/etherdevice.h','linux/rtnetlink.h','linux/slab.h','wlan_hdd_main.h','osif_psoc_sync.h','osif_vdev_sync.h']:
            p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* declarations supplied by fixture.h */\n')
        source=d/'test.c';source.write_text(code)
        exe=d/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                        '-include',str(d/'fixture.h'),'-I'+str(d),'-I'+str(production),str(source),'-o',str(exe)],check=True)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        stdout=subprocess.check_output([exe],text=True,env=env,timeout=10)
    report={'status':'MISHARE_HOST_LIFETIME_FIXTURE_PASS_ONLY','production_sha256':hashes,'fixture_sha256':hashlib.sha256((COMMON+code).encode()).hexdigest(),
            'checks':['invalid input','owner allocation failure','sync allocation failure','adapter creation failure','context rejection','existing adapter rejection','duplicate owner rejection','running/open/session rejection retaining owner','sync registry mismatch retaining owner','unregister/drain/close/destroy ordering','repeat destroy','ordinary wrapper rejection','ndo_open rejection','factory registered-netdev failure rollback'],
            'sanitizers':['address','undefined','leak detection'],'limitations':'Real helper C and extracted factory/rollback fragments with simulated HDD and synchronization. Not native kernel locking, netdev registration, teardown or radio validation.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(stdout,end='')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.wlan,args.output)
