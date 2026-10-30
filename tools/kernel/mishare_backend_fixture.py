#!/usr/bin/env python3
"""Actions-only test of real typed backend registration with a reentrant provider."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
COMMON=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define ETH_ALEN 6
#define BIT(n) (1U<<(n))
#define DEFINE_MUTEX(name) int name
#define module_param(a,b,c)
#define MODULE_PARM_DESC(a,b)
#define WARN_ON(x) (x)
#define hdd_err(...) ((void)0)
static void mutex_lock(int *p) { assert(!*p);*p=1; }
static void mutex_unlock(int *p) { assert(*p);*p=0; }
struct hdd_context { int identity; };
struct module { int dummy; };
static struct module backend_module;
#define THIS_MODULE (&backend_module)
'''
HARNESS=r'''
static const struct wondertap_priv *bound;
static int provider_error,registrations,removals,queries;
int opairshare_set_wonder_managed_priv_data(const void *p,const struct wondertap_managed_ops *managed)
{
 assert(mishare_backend_lock==1);
 if(provider_error)return provider_error;
 const struct wondertap_priv *priv=p;
 if(priv) {
  assert(managed && managed->ops==priv->wonder_ops && managed->owner==THIS_MODULE);
  assert(managed->poll_start(NULL)==-EINVAL);
  void *none=NULL;assert(managed->retire(&none)==0 && !none);
  assert(!bound && priv->ver==WONDER_VERSION_1_4_1);bound=priv;registrations++;
 } else { assert(bound);removals++; }
 /* Component bind/unbind can synchronously invoke callbacks under owner lock. */
 struct wondertap_capability caps;memset(&caps,0xa5,sizeof(caps));
 assert(bound->wonder_ops->get_capabilities(NULL,&caps)==0 && !caps.version && !caps.raw_bits);queries++;
 struct wondertap_init_params params={0};void *handle=(void*)1;
 assert(bound->wonder_ops->init(&handle,&params)==-EOPNOTSUPP && !handle);
 if(!priv)bound=NULL;
 return 0;
}
int main(void)
{
 struct hdd_context a={1},b={2};
 assert(!mishare_wonder_attach);
 assert(mishare_wonder_backend_register(&a)==0 && !bound && !mishare_backend_owner);
 assert(mishare_wonder_backend_register(NULL)==-EINVAL);
 mishare_wonder_backend_unregister(NULL);mishare_wonder_backend_unregister(&a);
 mishare_wonder_attach=true;provider_error=-EBUSY;
 assert(mishare_wonder_backend_register(&a)==-EBUSY && !bound && !mishare_backend_owner);
 provider_error=0;
 assert(mishare_wonder_backend_register(&a)==0 && bound && mishare_backend_owner==&a);
 assert(mishare_wonder_backend_register(&a)==0 && registrations==1);
 assert(mishare_wonder_backend_register(&b)==-EBUSY && mishare_backend_owner==&a);
 mishare_wonder_backend_unregister(&b);assert(bound && removals==0);
 const struct wondertap_ops *ops=bound->wonder_ops;void *h=(void*)1;
 assert(ops->init(NULL,NULL)==-EINVAL);
 assert(ops->init(&h,NULL)==-EINVAL && !h);
 assert(ops->get_capabilities(NULL,NULL)==-EINVAL);
 assert(ops->set_freq(NULL,NULL)==-EOPNOTSUPP);
 assert(ops->set_filter(NULL,WONDERTAP_FILTER_TYPE_FRAME,NULL)==-EOPNOTSUPP);
 assert(ops->set_fixed_tx_rate(NULL,NULL)==-EOPNOTSUPP);
 assert(ops->set_tx_rate_mask(NULL,NULL)==-EOPNOTSUPP);
 ops->deinit(NULL,NULL);
 provider_error=-EBUSY;
 assert(mishare_wonder_backend_unregister(&a)==-EBUSY && bound && mishare_backend_owner==&a);
 assert(mishare_wonder_backend_register(&a)==-ESHUTDOWN);
 provider_error=0;
 mishare_wonder_backend_unregister(&a);assert(!bound && !mishare_backend_owner && removals==1);
 mishare_wonder_backend_unregister(&a);assert(removals==1);
 assert(mishare_wonder_backend_register(&b)==0 && mishare_backend_owner==&b);
 mishare_wonder_backend_unregister(&b);assert(!bound && registrations==2 && removals==2 && queries==4);
 puts("MISHARE_BACKEND_TABLE_FIXTURE_PASS_ONLY");return 0;
}
'''


def run(output):
    if os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('Native compilation runs only on Actions')
    production=ROOT/'kernel/popsicle-hdd'
    api=ROOT/'kernel/provider/wondertap.h'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'fixture.h').write_text(COMMON)
        for name in ['linux/module.h','linux/mutex.h','linux/string.h','linux/if_ether.h','wlan_hdd_main.h','wlan_hdd_trace.h']:
            p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* fixture declarations */\n')
        (d/'wlan_hdd_mishare_wonder_api.h').write_bytes(api.read_bytes())
        (d/'wlan_hdd_mishare_managed.h').write_bytes((ROOT/'kernel/wonder/wondertap_managed.h').read_bytes())
        code='#include "wlan_hdd_mishare_backend.c"\n'+HARNESS
        (d/'test.c').write_text(code)
        exe=d/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                        '-include',str(d/'fixture.h'),'-I'+str(d),'-I'+str(production),str(d/'test.c'),'-o',str(exe)],check=True)
        stdout=subprocess.check_output([exe],text=True,timeout=10,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))
    inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [production/'wlan_hdd_mishare_backend.c',production/'wlan_hdd_mishare_backend.h',api,ROOT/'kernel/wonder/wondertap_managed.h']}
    report={'status':'MISHARE_BACKEND_TABLE_FIXTURE_PASS_ONLY','production_sha256':inputs,
            'fixture_sha256':hashlib.sha256((COMMON+code).encode()).hexdigest(),
            'checks':['default-disabled','registration failure rollback','duplicate registration','conflicting HDD owner','wrong-owner detach','synchronous capability/init queries during bind/unbind without recursive lock','init never publishes a handle','zero capabilities','all radio methods unsupported','repeat detach','re-registration'],
            'sanitizers':['address','undefined','leak detection'],'limitations':'Production typed table and owner state with simulated provider/mutex, not actual kernel component binding or radio.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(stdout,end='')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output)
