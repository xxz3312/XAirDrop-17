#!/usr/bin/env python3
"""Execute production provider, core binding, HDD metadata and master callbacks."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import wonder_managed_fixture as lifecycle

ROOT = Path(__file__).resolve().parents[2]
COMMON = lifecycle.COMMON + r'''
#include <stdlib.h>
#define DEFINE_MUTEX(n) struct mutex n={0}
#define WARN_ON(x) (x)
#define __init
#define __exit
#define EXPORT_SYMBOL(x)
#define module_init(x)
#define module_exit(x)
#define module_param(a,b,c)
#define MODULE_PARM_DESC(a,b)
#define MODULE_LICENSE(x)
#define MODULE_DESCRIPTION(x)
#define hdd_err(...) wonder_error(__VA_ARGS__)
#define pr_info(...) wonder_info(__VA_ARGS__)
#define dev_info(d,...) do {(void)(d);wonder_info(__VA_ARGS__);}while(0)
#define dev_err(d,...) dev_info(d,__VA_ARGS__)
#define PLATFORM_DEVID_NONE (-1)
#define unlikely(x) (x)
#define WONDER_PROVIDER_DEV_NAME "qcom,cnss-vendor-wlan-wonder"
struct device { void *drvdata;const char *name; };
struct platform_device { struct device dev; };
struct hdd_context { int identity; };
struct component_ops {
 int (*bind)(struct device *,struct device *,void *);
 void (*unbind)(struct device *,struct device *,void *);
};
static int component_error, master_bound, component_live, component_adds, component_dels;
static int symbol_available=1, lookup_missing;
static struct module provider_module;
static struct device master_dev={.name="wonder"};
static void *dev_get_drvdata(struct device *d) {return d->drvdata;}
static const char *dev_name(struct device *d) {return d->name;}
static struct platform_device *platform_device_alloc(const char *name,int id)
{(void)id;struct platform_device *p=calloc(1,sizeof(*p));assert(p);p->dev.name=name;return p;}
static int platform_device_add(struct platform_device *p) {assert(p);return 0;}
static void platform_device_put(struct platform_device *p) {free(p);}
static void platform_device_unregister(struct platform_device *p) {free(p);}
static void platform_set_drvdata(struct platform_device *p,void *v) {p->dev.drvdata=v;}
static void *platform_get_drvdata(struct platform_device *p) {return p->dev.drvdata;}
static void put_device(struct device *d) {(void)d;}
static int component_add(struct device *,const struct component_ops *);
static void component_del(struct device *,const struct component_ops *);
static int component_bind_all(struct device *,void *);
static void component_unbind_all(struct device *,void *);
void *__symbol_get(const char *);
void __symbol_put(const char *);
'''
HARNESS = r'''
#include "provider/provider.c"
#undef THIS_MODULE
#define THIS_MODULE (&backend_module)
#include "hdd/wlan_hdd_mishare_backend.c"
#undef THIS_MODULE
#define THIS_MODULE (&self_module)
#include "wonder/wondertap.c"
#include "wonder/wondertap_provider_binding.c"
bool wonder_external_monitor;
struct wonder_data { struct wondertap_data wondertap_data;void *hw; };
static struct wonder_data instance,*g_wonder;
static int ssr_exits,feature_exits,hw_frees;
static void wonder_ssr_exit(struct wonder_data *w) {assert(w==&instance);ssr_exits++;}
static void wonder_features_exit(struct wonder_data *w) {assert(w==&instance);feature_exits++;}
static void ieee80211_free_hw(void *hw) {assert(hw==instance.hw);hw_frees++;}
static struct platform_device *wonder_find_provider_by_name(const char *name)
{assert(!strcmp(name,WONDER_PROVIDER_DEV_NAME));return lookup_missing?NULL:provider;}
static struct platform_device *of_find_device_by_node(void *node)
{assert(node);return provider;}
static bool wonder_ver_can_support(enum wondertap_ver slave,enum wondertap_ver master)
{return slave>=0 && slave<WONDER_VERSION_MAX && master==WONDER_VERSION_1_5_1;}
MASTER_BIND
MASTER_UNBIND
MAC_EXIT

static int component_bind_all(struct device *dev,void *data)
{return provider_ops.bind(&provider->dev,dev,data);}
static void component_unbind_all(struct device *dev,void *data)
{provider_ops.unbind(&provider->dev,dev,data);}
static int component_add(struct device *dev,const struct component_ops *ops)
{
 assert(dev==&provider->dev && ops==&provider_ops && !component_live);
 component_adds++;
 if(component_error)return component_error;
 int ret=wonder_master_bind(&master_dev);
 if(!ret){master_bound=1;component_live=1;}
 return ret;
}
static void component_del(struct device *dev,const struct component_ops *ops)
{
 assert(dev==&provider->dev && ops==&provider_ops && component_live);
 component_dels++;
 if(master_bound){wonder_master_unbind(&master_dev);master_bound=0;}
 component_live=0;
}
void *__symbol_get(const char *name)
{assert(!strcmp(name,MANAGED_CONTROL_SYMBOL));if(!symbol_available)return NULL;provider_module.refs++;return (void *)opairshare_wonder_managed_control;}
void __symbol_put(const char *name)
{assert(!strcmp(name,MANAGED_CONTROL_SYMBOL) && provider_module.refs>0);provider_module.refs--;}
static void prepare(void)
{
 assert(!provider_module.refs && !backend_module.refs && !self_module.refs);
 memset(&instance,0,sizeof(instance));g_wonder=&instance;instance.hw=&instance;
 struct wondertap_data *w=&instance.wondertap_data;wondertap_prep(w);
 w->ver=WONDER_VERSION_1_5_1;
 w->cache_flags=WONDERTAP_CACHE_FREQ_SET|WONDERTAP_CACHE_TX_RATE_SET|
                WONDERTAP_CACHE_BSSID_SET|WONDERTAP_CACHE_COUNTRY_CODE_SET;
 w->cached_freq.freq=5240;w->cached_tx_rate.nss=1;memcpy(w->cached_country_code,"CN",3);
 master_dev.drvdata=w;ssr_exits=feature_exits=hw_frees=0;
}
static int token, start_calls, stop_calls, poll_calls, stop_pending;
static int fake_start(void **h,const struct wondertap_init_params *p)
{assert(!*h && p->channel.freq==5240);*h=&token;start_calls++;return -EINPROGRESS;}
static int fake_poll(void *h) {assert(h==&token);poll_calls++;return 0;}
static int fake_stop(void **h)
{assert(*h==&token);stop_calls++;if(stop_pending)return -EINPROGRESS;*h=NULL;return 0;}
static const struct wondertap_ops fake_ops={.init=fake_start};
static const struct wondertap_priv fake_priv={.ver=WONDER_VERSION_1_4_1,.wonder_ops=&fake_ops};
static const struct wondertap_managed_ops fake_managed={.ops=&fake_ops,.owner=&backend_module,.poll_start=fake_poll,.retire=fake_stop};

int main(void)
{
 struct hdd_context h={1},wrong={2};struct wondertap_init_params params={0};
 const struct wondertap_managed_ops *out=NULL;struct wondertap_data *w=&instance.wondertap_data;
 assert(provider_init()==0);prepare();
 assert(mishare_wonder_backend_register(&h)==0 && !active_priv && !component_adds);
 mishare_wonder_attach=true;
 component_error=-ENOMEM;
 assert(mishare_wonder_backend_register(&h)==-ENOMEM && !active_priv && !active_managed && !mishare_backend_owner);
 component_error=0;lookup_missing=1;
 assert(mishare_wonder_backend_register(&h)==-ENODEV && !active_priv && !w->managed_bound);
 lookup_missing=0;
 backend_module.deny=true;
 assert(mishare_wonder_backend_register(&h)!=0 && !active_priv && !provider_module.refs);
 backend_module.deny=false;
 assert(mishare_wonder_backend_register(&h)==0 && w->managed_bound && !w->managed_quiescing);
 assert(claim_cookie==w && claim_quiesce && provider_module.refs==1 && backend_module.refs==1);
 assert(w->managed.ops==&mishare_backend_ops && w->managed.owner==&backend_module);
 assert(wondertap_init(w,&params)==-EOPNOTSUPP && !w->vendor_handle && !self_module.refs);
 assert(mishare_wonder_backend_register(&h)==0);
 assert(mishare_wonder_backend_register(&wrong)==-EBUSY);
 assert(mishare_wonder_backend_unregister(&wrong)==0 && active_priv);
 assert(opairshare_wonder_managed_control(WONDERTAP_PROVIDER_RELEASE,active_priv,&wrong,NULL,NULL)==-ENOENT);
 assert(mishare_wonder_backend_unregister(&h)==0 && !active_priv && !active_managed && !claim_cookie);
 assert(!w->managed_bound && !w->managed_provider_control && !provider_module.refs && !backend_module.refs);
 assert(wondertap_init(w,&params)==-ESHUTDOWN); /* No reopen between preflight and component detach. */
 /* Rebinding opens only after the new claim has been accepted. */
 assert(mishare_wonder_backend_register(&h)==0 && !w->managed_quiescing);
 assert(mishare_wonder_backend_unregister(&h)==0);
 /* Legacy descriptor uses the unchanged registration API and no module pin. */
 prepare();assert(opairshare_set_wonder_priv_data(&mishare_backend_priv)==0);
 assert(!w->managed_bound && !w->managed_quiescing && !provider_module.refs);
 assert(opairshare_set_wonder_priv_data(NULL)==0);
 /* Busy fake radio owns the same real transport/core, never a firmware fake. */
 prepare();assert(opairshare_set_wonder_managed_priv_data(&fake_priv,&fake_managed)==0);
 assert(wondertap_init(w,&params)==-EINPROGRESS && start_calls==1 && self_module.refs==1);
 assert(wondertap_init(w,&params)==0 && poll_calls==1);
 int dels=component_dels;
 assert(opairshare_set_wonder_priv_data(NULL)==-EBUSY && component_dels==dels && component_live);
 assert(active_priv==&fake_priv && claim_cookie==w && provider_closing);
 assert(wondertap_init(w,&params)==-ESHUTDOWN && start_calls==1);
 assert(opairshare_wonder_managed_control(WONDERTAP_PROVIDER_QUERY,&fake_priv,NULL,NULL,&out)==-ESHUTDOWN);
 assert(opairshare_wonder_managed_control(WONDERTAP_PROVIDER_CLAIM,&fake_priv,&wrong,wondertap_provider_quiesce,NULL)==-ESHUTDOWN);
 assert(opairshare_set_wonder_managed_priv_data(&fake_priv,&fake_managed)==-ESHUTDOWN);
 wonder_mac80211_exit();assert(g_wonder==&instance && !hw_frees && !ssr_exits);
 stop_pending=1;assert(wondertap_retire(w)==-EINPROGRESS && stop_calls==1);
 assert(opairshare_set_wonder_priv_data(NULL)==-EBUSY && component_dels==dels);
 stop_pending=0;assert(wondertap_retire(w)==0 && !self_module.refs);
 assert(opairshare_set_wonder_priv_data(NULL)==0 && component_dels==dels+1 && !claim_cookie);
 assert(!provider_module.refs && !backend_module.refs);
 wonder_mac80211_exit();assert(!g_wonder && ssr_exits==1 && feature_exits==1 && hw_frees==1);
 /* Old providers without the private symbol remain usable. */
 prepare();symbol_available=0;
 assert(opairshare_set_wonder_priv_data(&mishare_backend_priv)==0 && !w->managed_bound);
 assert(opairshare_set_wonder_priv_data(NULL)==0);symbol_available=1;
 provider_exit();assert(!provider);
 puts("WONDER_PROVIDER_BINDING_FIXTURE_PASS_ONLY");return 0;
}
'''

def extract(source, name, prefix):
    match = re.search(r'^'+prefix+r' '+name+r'\([^;]+?\)\s*\{.*?^\}', source, re.S | re.M)
    if not match:
        raise ValueError('Changed production function: '+name)
    return match[0]

def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Native compilation runs on Actions')
    main_source = (ROOT/'kernel/wonder/main.c').read_text()
    fragments = {
        'MASTER_BIND': extract(main_source, 'wonder_master_bind', 'static int'),
        'MASTER_UNBIND': extract(main_source, 'wonder_master_unbind', 'static void'),
        'MAC_EXIT': extract((ROOT/'kernel/wonder/mac80211.c').read_text(), 'wonder_mac80211_exit', 'void'),
    }
    harness = HARNESS
    for key, value in fragments.items():
        harness = harness.replace(key, value)
    names = ['kernel/provider/provider.c', 'kernel/provider/wondertap.h',
             'kernel/wonder/wondertap.c', 'kernel/wonder/wondertap_internal.h',
             'kernel/wonder/wondertap_managed.h', 'kernel/wonder/wondertap_provider_binding.c',
             'kernel/wonder/include/wonder/wondertap.h',
             'kernel/popsicle-hdd/wlan_hdd_mishare_backend.c',
             'kernel/popsicle-hdd/wlan_hdd_mishare_backend.h']
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name in names:
            destination = d/name.removeprefix('kernel/').replace('popsicle-hdd/', 'hdd/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, destination)
        shutil.copyfile(ROOT/'kernel/provider/wondertap.h', d/'hdd/wlan_hdd_mishare_wonder_api.h')
        shutil.copyfile(ROOT/'kernel/wonder/wondertap_managed.h', d/'hdd/wlan_hdd_mishare_managed.h')
        for name in ['linux/export.h', 'linux/module.h', 'linux/mutex.h', 'linux/string.h',
                     'linux/etherdevice.h', 'linux/delay.h', 'linux/ieee80211.h',
                     'linux/if_ether.h', 'linux/component.h', 'linux/platform_device.h',
                     'wonder/wonder_log.h', 'hdd/wlan_hdd_main.h', 'hdd/wlan_hdd_trace.h']:
            p = d/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('/* fixture declarations */\n')
        (d/'fixture.h').write_text(COMMON)
        (d/'test.c').write_text(harness)
        exe = d/'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-include', str(d/'fixture.h'),
                        '-I'+str(d), '-I'+str(d/'hdd'), str(d/'test.c'), '-o', str(exe)], check=True)
        subprocess.run([exe], check=True, timeout=10,
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                                UBSAN_OPTIONS='halt_on_error=1'))
    output = ROOT/'.popsicle-ci/artifacts/reports/wonder-provider-fixture.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        'status': 'WONDER_PROVIDER_BINDING_FIXTURE_PASS_ONLY',
        'production_sha256': {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names},
        'production_fragment_sha256': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in fragments.items()},
        'limitations': 'Production provider/core/HDD metadata and extracted master/free callbacks with modeled modules, mutexes, platform/component services and version acceptance. Not native races, teardown leases, firmware or RF proof.'
    }, indent=2)+'\n')

if __name__ == '__main__':
    main()
