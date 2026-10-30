#!/usr/bin/env python3
"""Run the complete production WonderTap C entry points with native mocks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
COMMON = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define ETH_ALEN 6
#define BIT(n) (1U<<(n))
#define WRITE_ONCE(p,v) ((p)=(v))
#define IEEE80211_FTYPE_MGMT 0
#define IEEE80211_FTYPE_CTL 4
#define IEEE80211_FTYPE_DATA 8
#define IEEE80211_FCTL_STYPE 0xf0
struct mutex { int held; };
static void mutex_init(struct mutex *m) { m->held=0; }
static void mutex_lock(struct mutex *m) { assert(!m->held);m->held=1; }
static void mutex_unlock(struct mutex *m) { assert(m->held);m->held=0; }
struct module { int refs; bool deny; };
static struct module self_module, backend_module;
#define THIS_MODULE (&self_module)
static bool try_module_get(struct module *m) { if(m->deny)return false;m->refs++;return true; }
static void module_put(struct module *m) { assert(m->refs>0);m->refs--; }
static int mac_generation;
static void eth_random_addr(u8 *m) { memset(m,0,6);m[0]=2;m[5]=(u8)++mac_generation; }
#define wonder_info(...) do { if(0)printf(__VA_ARGS__); } while(0)
#define wonder_warn(...) wonder_info(__VA_ARGS__)
#define wonder_error(...) wonder_info(__VA_ARGS__)
'''
HARNESS = r'''
#include "wondertap.c"
bool wonder_external_monitor;
static int token, replacement;
static int init_result, poll_result, retire_mode, init_calls, poll_calls, retire_calls;
static int legacy_stops, config_calls, caps_calls;
static bool publish_handle=true;
static int cb_init(void **h,const struct wondertap_init_params *p)
{ assert(p && !*h);init_calls++;if(publish_handle)*h=&token;return init_result; }
static int cb_poll(void *h) { assert(h==&token);poll_calls++;return poll_result; }
static int cb_retire(void **h)
{ assert(*h==&token);retire_calls++;
 switch(retire_mode) {
 case 0:*h=NULL;return 0;
 case 1:return -EINPROGRESS;
 case 2:return -EIO;
 case 3:return 0;
 case 4:*h=&replacement;return -EINPROGRESS;
 case 6:*h=&replacement;return 0;
 default:*h=NULL;return -EIO;
 } }
static void cb_legacy_stop(void *h,const struct wondertap_deinit_params *p)
{ assert(h==&token && p);legacy_stops++; }
static int cb_freq(void *h,const struct wondertap_set_freq_params *p)
{ assert(h==&token && p);config_calls++;return 0; }
static int cb_caps(void *h,struct wondertap_capability *p)
{ assert((!h || h==&token) && p);caps_calls++;memset(p,0,sizeof(*p));p->bits.frame_type_filter=1;return 0; }
static const struct wondertap_ops ops={.init=cb_init,.deinit=cb_legacy_stop,.set_freq=cb_freq,.get_capabilities=cb_caps};
static const struct wondertap_ops foreign_ops={0};
static const struct wondertap_managed_ops managed={.ops=&ops,.owner=&backend_module,.poll_start=cb_poll,.retire=cb_retire};
static struct wondertap_init_params params;
static void prepare(struct wondertap_data *w,bool bind)
{
 memset(w,0,sizeof(*w));wondertap_prep(w);
 w->cache_flags=WONDERTAP_CACHE_FREQ_SET|WONDERTAP_CACHE_TX_RATE_SET|
                WONDERTAP_CACHE_BSSID_SET|WONDERTAP_CACHE_COUNTRY_CODE_SET;
 w->cached_freq.freq=5240;w->cached_tx_rate.nss=1;
 memcpy(w->cached_country_code,"CN",3);
 init_result=-EINPROGRESS;poll_result=-EINPROGRESS;retire_mode=1;publish_handle=true;
 init_calls=poll_calls=retire_calls=legacy_stops=config_calls=caps_calls=0;
 wondertap_register_ops(&ops);
 if(bind)assert(wondertap_bind_managed(w,&managed)==0);
}
static void finish(struct wondertap_data *w)
{
 retire_mode=0;assert(wondertap_retire(w)==0);
 assert(w->state==WONDERTAP_STATE_DOWN && !w->vendor_handle && !w->managed_instance_pin);
 assert(wondertap_unbind_managed(w)==0);
 assert(wondertap_unbind_managed(w)==0);
}
int main(void)
{
 struct wondertap_data w, quarantined[7];struct wondertap_capability caps;
 struct wondertap_set_freq_params freq={.freq=5180};
 struct wondertap_fixed_tx_rate_params rate={0};struct wondertap_tx_rate_mask_params mask={0};
 u8 bssid[6]={2,0,0,0,0,1};
 assert(wondertap_bind_managed(NULL,&managed)==-EINVAL);
 assert(wondertap_unbind_managed(NULL)==-EINVAL && wondertap_retire(NULL)==-EINVAL);
 prepare(&w,false);
 assert(wondertap_bind_managed(&w,NULL)==-EINVAL);
 wonder_external_monitor=true;assert(wondertap_bind_managed(&w,&managed)==-EOPNOTSUPP);wonder_external_monitor=false;
 backend_module.deny=true;assert(wondertap_bind_managed(&w,&managed)==-ENODEV);backend_module.deny=false;
 wondertap_register_ops(&foreign_ops);assert(wondertap_bind_managed(&w,&managed)==-ENODEV);
 wondertap_register_ops(&ops);assert(wondertap_bind_managed(&w,&managed)==0 && backend_module.refs==1);
 assert(wondertap_bind_managed(&w,&managed)==-EBUSY);
 assert(wondertap_get_capabilities(&w,&caps)==0 && caps_calls==1);
 assert(wondertap_init(NULL,&params)==-EINVAL && wondertap_init(&w,NULL)==-EINVAL);
 self_module.deny=true;assert(wondertap_init(&w,&params)==-ENODEV && !init_calls);self_module.deny=false;
 assert(wondertap_init(&w,&params)==-EINPROGRESS && init_calls==1 && self_module.refs==1);
 int mac_before=mac_generation;
 for(int i=0;i<4;i++)assert(wondertap_init(&w,&params)==-EINPROGRESS);
 assert(init_calls==1 && poll_calls==4 && mac_generation==mac_before);
 assert(wondertap_set_freq(&w,&freq)==-EBUSY && w.cached_freq.freq==5240);
 assert(wondertap_set_fixed_tx_rate(&w,&rate)==-EBUSY && w.cached_tx_rate.nss==1);
 assert(wondertap_set_tx_rate_mask(&w,&mask)==-EBUSY && w.cached_tx_rate.nss==1);
 assert(wondertap_set_reg(&w,"US")==-EBUSY && !memcmp(w.cached_country_code,"CN",3));
 assert(wondertap_set_bssid_filter(&w,bssid)==-EBUSY);
 assert(wondertap_get_capabilities(&w,&caps)==0 && caps.bits.frame_type_filter && caps_calls==1);
 assert(wondertap_unbind_managed(&w)==-EBUSY && backend_module.refs==1);
 poll_result=0;assert(wondertap_init(&w,&params)==0 && w.state==WONDERTAP_STATE_UP);
 assert(wondertap_init(&w,&params)==-EBUSY);
 /* Active instance uses its pinned callbacks after global replacement/detach. */
 wondertap_register_ops(&foreign_ops);
 assert(wondertap_set_freq(&w,&freq)==0 && config_calls==1);
 assert(wondertap_get_capabilities(&w,&caps)==0 && caps_calls==2);
 wondertap_unregister_ops(&foreign_ops);
 wondertap_deinit(&w);
 assert(w.state==WONDERTAP_STATE_DRAINING && w.vendor_handle==&token && retire_calls==1 && !legacy_stops);
 assert(wondertap_unbind_managed(&w)==-EBUSY && self_module.refs==1);
 assert(wondertap_retire(&w)==-EINPROGRESS && retire_calls==2);
 finish(&w);assert(!backend_module.refs && !self_module.refs);
 prepare(&w,true);init_result=-EIO;
 assert(wondertap_init(&w,&params)==-EIO && w.state==WONDERTAP_STATE_DRAINING);
 assert(wondertap_init(&w,&params)==-EBUSY && init_calls==1);finish(&w);
 prepare(&w,true);publish_handle=false;init_result=-ENOMEM;
 assert(wondertap_init(&w,&params)==-ENOMEM && w.state==WONDERTAP_STATE_DOWN && !self_module.refs);
 assert(wondertap_unbind_managed(&w)==0);
 prepare(&w,true);assert(wondertap_init(&w,&params)==-EINPROGRESS);poll_result=-EIO;
 assert(wondertap_init(&w,&params)==-EIO && w.state==WONDERTAP_STATE_DRAINING);finish(&w);
 /* A native reset of the visible state cannot authorize overwriting ownership. */
 prepare(&w,true);assert(wondertap_init(&w,&params)==-EINPROGRESS);
 w.state=WONDERTAP_STATE_DOWN;
 assert(wondertap_init(&w,&params)==-EBUSY && init_calls==1);
 assert(wondertap_set_freq(&w,&freq)==-EBUSY);
 assert(wondertap_get_capabilities(&w,&caps)==-EBUSY);finish(&w);
 /* Protocol failures retain tokens/pins; production never retries their stop. */
 for(int i=0;i<7;i++) {
  struct wondertap_data *q=&quarantined[i];prepare(q,true);
  if(i<2) {publish_handle=false;init_result=i?0:-EINPROGRESS;
   assert(wondertap_init(q,&params)==-EUCLEAN);
  } else {init_result=0;assert(wondertap_init(q,&params)==0);retire_mode=i;
   assert(wondertap_retire(q)!=0);
  }
  assert(q->state==WONDERTAP_STATE_BLOCKED && q->managed_instance_pin);
  int before=retire_calls;assert(wondertap_retire(q)!=0 && retire_calls==before);
  assert(wondertap_unbind_managed(q)==-EBUSY);
  assert(wondertap_get_capabilities(q,&caps)==-EBUSY);
 }
 assert(self_module.refs==7 && backend_module.refs==7);
 /* Legacy synchronous ops and external monitor keep their original contract. */
 prepare(&w,false);init_result=0;assert(wondertap_init(&w,&params)==0);
 wondertap_deinit(&w);assert(legacy_stops==1 && w.state==WONDERTAP_STATE_DOWN && !w.vendor_handle);
 wonder_external_monitor=true;assert(wondertap_set_freq(&w,&freq)==-EOPNOTSUPP);
 assert(wondertap_get_capabilities(&w,&caps)==0 && caps.bits.frame_type_filter);
 puts("WONDER_MANAGED_LIFECYCLE_FIXTURE_PASS_ONLY");return 0;
}
'''

def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Native compilation runs on Actions')
    production = ROOT/'kernel/wonder'
    names = ['wondertap.c', 'wondertap_internal.h', 'wondertap_managed.h',
             'include/wonder/wondertap.h']
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name in names:
            target = d/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(production/name, target)
        for name in ['linux/export.h', 'linux/module.h', 'linux/etherdevice.h',
                     'linux/delay.h', 'linux/ieee80211.h', 'linux/if_ether.h', 'wonder_log.h']:
            p = d/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('/* declarations supplied by fixture.h */\n')
        (d/'fixture.h').write_text(COMMON)
        (d/'test.c').write_text(HARNESS)
        exe = d/'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-include', str(d/'fixture.h'), '-I'+str(d), str(d/'test.c'),
                        '-o', str(exe)], check=True)
        subprocess.run([exe], check=True, timeout=10,
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                                UBSAN_OPTIONS='halt_on_error=1'))
    output = ROOT/'.popsicle-ci/artifacts/reports/wonder-managed-fixture.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        'status': 'WONDER_MANAGED_LIFECYCLE_FIXTURE_PASS_ONLY',
        'production_sha256': {n: hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},
        'limitations': 'Complete production WonderTap entry points with modeled modules, mutexes and vendor ops; not native locking, parent lifetime, firmware or RF proof.'
    }, indent=2)+'\n')

if __name__ == '__main__':
    main()
