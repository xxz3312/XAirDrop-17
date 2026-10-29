#!/usr/bin/env python3
"""Run the production mgmt RX owner helper with modeled SME/HDD, only in CI."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
ENV=r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define EBUSY 16
#define ESHUTDOWN 108
#define PAGE_SIZE 4096
#define scnprintf snprintf
#define DEFINE_MUTEX(x) int x
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
#define smp_load_acquire(x) (*(x))
#define smp_store_release(x,v) (*(x)=(v))
#define module_param(a,b,c)
#define MODULE_PARM_DESC(a,b)
#define module_param_cb(a,b,c,d)
#define hdd_info(...) ((void)0)
#define hdd_err(...) ((void)0)
#define QDF_STA_MODE 0
#define WLAN_UMAC_VDEV_ID_MAX 255
#define QDF_IS_STATUS_ERROR(s) ((s)!=0)
typedef int QDF_STATUS;
typedef struct {long long n;} atomic64_t;
#define ATOMIC64_INIT(x) {x}
static long long atomic64_read(atomic64_t *x){return x->n;}
static long long atomic64_inc_return(atomic64_t *x){return ++x->n;}
struct kernel_param {};
struct kernel_param_ops {int (*get)(char *,const struct kernel_param *);};
struct net_device {unsigned char dev_addr[6];};
struct hdd_adapter;
struct wlan_hdd_link_info {struct hdd_adapter *adapter;unsigned char vdev_id;};
struct hdd_adapter {struct wlan_hdd_link_info *deflink;struct net_device *dev;int device_mode;bool ml,link;};
#define hdd_adapter_is_ml_adapter(a) ((a)->ml)
#define hdd_adapter_is_link_adapter(a) ((a)->link)
static bool is_multicast_ether_addr(const unsigned char *a){return a[0]&1;}
static bool ether_addr_equal(const unsigned char *a,const unsigned char *b){return !memcmp(a,b,6);}
static bool mac_alive=true;
static void *hdd_adapter_get_mac_handle(struct hdd_adapter *a){(void)a;return mac_alive?(void *)1:NULL;}
static int qdf_status_to_os_return(int n){return n?-5:0;}
static int reg_calls,unreg_calls,reg_fail,unreg_fail;
static int sme_register_mgmt_frame(void *m,unsigned char id,unsigned short type,unsigned char *p,unsigned short len){
 assert(m && id<255 && type==0xd0 && len==5 && !memcmp(p,"\x7f\x00\x17\xf2\x08",5));reg_calls++;return reg_fail;
}
static int sme_deregister_mgmt_frame(void *m,unsigned char id,unsigned short type,unsigned char *p,unsigned short len){
 assert(m && id<255 && type==0xd0 && len==5 && !memcmp(p,"\x7f\x00\x17\xf2\x08",5));unreg_calls++;return unreg_fail;
}
'''
TEST=r'''
int main(void){
 struct net_device dev={{2,1,2,3,4,5}},dev2={{2,2,3,4,5,6}};
 struct hdd_adapter a={.dev=&dev},b={.dev=&dev2};
 struct wlan_hdd_link_info la={.adapter=&a,.vdev_id=1},lb={.adapter=&b,.vdev_id=2};
 a.deflink=&la;b.deflink=&lb;
 unsigned char frame[400]={0xd0};frame[4]=0xff;memcpy(frame+24,"\x7f\x00\x17\xf2\x08",5);
 assert(!mishare_mgmt_rx_register(&a) && !reg_calls);
 assert(!mishare_mgmt_rx_route(&la,frame,277));
 mishare_mgmt_rx=true;a.device_mode=1;assert(!mishare_mgmt_rx_register(&a) && !reg_calls);a.device_mode=0;
 a.ml=true;assert(!mishare_mgmt_rx_register(&a) && !reg_calls);a.ml=false;
 reg_fail=1;assert(mishare_mgmt_rx_register(&a)<0 && !mishare_mgmt_owner && !mishare_mgmt_reserved);reg_fail=0;
 assert(!mishare_mgmt_rx_register(&a) && mishare_mgmt_owner==&a);
 assert(mishare_mgmt_rx_route(&la,frame,277));
 assert(!mishare_mgmt_rx_route(&la,frame,2305));assert(!mishare_mgmt_rx_route(&la,frame,39));
 frame[1]=0x40;assert(!mishare_mgmt_rx_route(&la,frame,277));frame[1]=0;
 frame[22]=1;assert(!mishare_mgmt_rx_route(&la,frame,277));frame[22]=0;
 frame[28]=9;assert(!mishare_mgmt_rx_route(&la,frame,277));frame[28]=8;
 memset(frame+4,2,6);assert(!mishare_mgmt_rx_route(&la,frame,277));memcpy(frame+4,dev.dev_addr,6);
 assert(mishare_mgmt_rx_route(&la,frame,277));
 assert(!mishare_mgmt_rx_route(&lb,frame,277));
 assert(mishare_mgmt_rx_register(&b)==-EBUSY);mishare_mgmt_rx_unregister(&b);assert(!unreg_calls);
 int n=reg_calls;assert(!mishare_mgmt_rx_register(&a) && reg_calls==n+1); /* SSR replay re-posts. */
 reg_fail=1;assert(mishare_mgmt_rx_register(&a)<0 && !mishare_mgmt_owner && mishare_mgmt_reserved==&a);reg_fail=0;
 assert(!mishare_mgmt_rx_route(&la,frame,277));
 mishare_mgmt_rx_unregister(&a);assert(unreg_calls==1 && !mishare_mgmt_reserved);
 assert(!mishare_mgmt_rx_register(&b));unreg_fail=1;mishare_mgmt_rx_unregister(&b);
 assert(mishare_mgmt_fault && !mishare_mgmt_owner && !mishare_mgmt_reserved);
 assert(mishare_mgmt_rx_register(&a)==-ESHUTDOWN);
 /* Separate modeled reload: a vanished MAC must never reach SME deregister. */
 mishare_mgmt_fault=false;unreg_fail=0;assert(!mishare_mgmt_rx_register(&a));
 int before=unreg_calls;mac_alive=false;mishare_mgmt_rx_unregister(&a);
 assert(unreg_calls==before && mishare_mgmt_fault && !mishare_mgmt_owner && !mishare_mgmt_reserved);
 puts("MISHARE_MGMT_RX_OWNER_MODEL_PASS_ONLY");return 0;
}
'''

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':
        raise RuntimeError('C fixture compilation is CI-only')
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)
        for name in ['linux/errno.h','linux/module.h','linux/mutex.h','linux/etherdevice.h','wlan_hdd_main.h','sme_api.h']:
            f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('')
        source=p/'test.c'
        source.write_text(ENV+'\n#include "'+str(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_mgmt_rx.c')+'"\n'+TEST)
        exe=p/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-g','-fsanitize=address,undefined','-I'+str(p),str(source),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})

if __name__=='__main__':main()
