#!/usr/bin/env python3
"""Actions-only production bridge/scope execution with modeled native guards."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT/'kernel/popsicle-hdd'
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <linux/errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define ETH_ALEN 6
#define QDF_MODULE_ID_HDD 11
struct device { int refs; };
struct osif_psoc_sync { int unused; };
struct hdd_context { struct device *parent_dev; void *psoc, *pdev; };
struct mishare_wonder_host { int unused; };
static struct device device, foreign;
static struct hdd_context hdd={&device,&device,&device}, replacement;
static struct hdd_context *lookup;
static struct osif_psoc_sync sync;
static struct mishare_wonder_host host;
static bool transition, rtnl, pin_fail, rtnl_busy;
static int trans_error, health_error, destroy_result, creates, attaches, steps, destroys;
static char events[100];
static unsigned event_count;
static void event(char c) { assert(event_count<sizeof(events)-1);events[event_count++]=c;events[event_count]=0; }
static struct device *get_device(struct device *d)
{ assert(d==&device && !transition && !rtnl);event('G');if(pin_fail)return NULL;d->refs++;return d; }
static void put_device(struct device *d)
{ assert(d==&device && !transition && !rtnl && d->refs==1);event('P');d->refs--; }
static int osif_psoc_sync_trans_start(struct device *d,struct osif_psoc_sync **s)
{ assert(d==&device && d->refs==1 && !transition && !rtnl);event('S');*s=NULL;
  if(trans_error)return trans_error;
  transition=true;*s=&sync;return 0; }
static void osif_psoc_sync_wait_for_ops(struct osif_psoc_sync *s)
{ assert(s==&sync && transition && !rtnl);event('W'); }
static bool rtnl_trylock(void)
{ assert(transition && !rtnl);event('L');if(rtnl_busy)return false;rtnl=true;return true; }
static void rtnl_unlock(void) { assert(transition && rtnl);event('U');rtnl=false; }
static void osif_psoc_sync_trans_stop(struct osif_psoc_sync *s)
{ assert(s==&sync && transition && !rtnl);event('T');transition=false; }
static void *cds_get_context(int id)
{ assert(id==QDF_MODULE_ID_HDD && transition && rtnl);event('H');return lookup; }
static int wlan_hdd_validate_context(struct hdd_context *h)
{ assert(h==lookup && transition && rtnl);event('V');return health_error; }
static bool is_valid_ether_addr(const u8 *m)
{ return !(m[0]&1) && (m[0]|m[1]|m[2]|m[3]|m[4]|m[5]); }
static int mishare_wonder_host_create_locked(struct hdd_context *h,const u8 *mac,struct mishare_wonder_host **o)
{ assert(h==&hdd && transition && rtnl && mac[0]==2 && !*o);event('C');creates++;*o=&host;return 0; }
static int mishare_wonder_host_vdev_create_locked(struct mishare_wonder_host *o)
{ assert(o==&host && transition && rtnl);event('A');attaches++;return 0; }
static int mishare_wonder_host_session_step_locked(struct mishare_wonder_host *o,u32 f,u8 a,u8 b)
{ assert(o==&host && transition && rtnl && f==5240 && a==1 && b==2);event('R');steps++;return -EINPROGRESS; }
static int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **o)
{ assert(*o==&host && transition && rtnl);event('D');destroys++;
  if(!destroy_result)*o=NULL;
  return destroy_result; }
#include "wlan_hdd_mishare_bridge_scope.h"
static const u8 mac[6]={2,1,2,3,4,5};
static int step(struct mishare_bridge *b)
{ return mishare_bridge_step(b,&device,mac,5240,1,2); }
static void reset_events(void)
{ assert(!transition && !rtnl && !device.refs);event_count=0;events[0]=0; }
static void reset(struct mishare_bridge *b)
{ reset_events();memset(b,0,sizeof(*b));pin_fail=rtnl_busy=false;
  trans_error=health_error=destroy_result=creates=attaches=steps=destroys=0;
  hdd.parent_dev=&device;hdd.psoc=hdd.pdev=&device;lookup=&hdd; }
int main(void)
{
 struct mishare_bridge b, saved;
 struct mishare_bridge_scope scope={0};
 reset(&b);pin_fail=true;assert(step(&b)==-ENODEV && !strcmp(events,"G") && !b.attempted);
 reset(&b);trans_error=-EBUSY;assert(step(&b)==-EBUSY && !strcmp(events,"GSP") && !b.attempted);
 reset(&b);rtnl_busy=true;assert(step(&b)==-EAGAIN && !strcmp(events,"GSWLTP") && !b.attempted);
 for(int kind=0;kind<4;kind++) {
  reset(&b);
  if(kind==0)lookup=NULL;
  if(kind==1)hdd.parent_dev=&foreign;
  if(kind==2)hdd.psoc=NULL;
  if(kind==3)hdd.pdev=NULL;
  assert(step(&b)==-ENODEV && !strcmp(events,"GSWLHUTP") && !b.attempted);
 }
 reset(&b);health_error=-ESHUTDOWN;
 assert(step(&b)==-ESHUTDOWN && !strcmp(events,"GSWLHVUTP") && !b.attempted);
 reset(&b);assert(step(&b)==-EINPROGRESS && !strcmp(events,"GSWLHVCUTP"));
 saved=b;reset_events();trans_error=-EAGAIN;
 assert(step(&b)==-EAGAIN && !memcmp(&b,&saved,sizeof(b)));
 trans_error=0;rtnl_busy=true;reset_events();
 assert(mishare_bridge_retire(&b,&device)==-EAGAIN && !memcmp(&b,&saved,sizeof(b)));
 rtnl_busy=false;reset_events();replacement=hdd;lookup=&replacement;
 assert(step(&b)==-EBUSY && !strcmp(events,"GSWLHVUTP") && !memcmp(&b,&saved,sizeof(b)));
 reset_events();assert(mishare_bridge_retire(&b,&device)==-EBUSY && !b.closing && !destroys);
 lookup=&hdd;reset_events();assert(step(&b)==-EINPROGRESS && !strcmp(events,"GSWLHVAUTP"));
 reset_events();assert(step(&b)==-EINPROGRESS && !strcmp(events,"GSWLHVRUTP"));
 reset_events();health_error=-EIO;destroy_result=-EINPROGRESS;
 assert(mishare_bridge_retire(&b,&device)==-EINPROGRESS && b.host==&host && b.closing);
 assert(!strcmp(events,"GSWLHDUTP")); /* Cleanup is not gated by health. */
 reset_events();destroy_result=-EBUSY;
 assert(mishare_bridge_retire(&b,&device)==-EBUSY && b.host==&host);
 reset_events();destroy_result=0;
 assert(mishare_bridge_retire(&b,&device)==0 && b.retired && !b.host);
 reset_events();assert(mishare_bridge_retire(&b,&device)==0 && !strcmp(events,"GSWLHUTP"));
 assert(creates==1 && attaches==1 && steps==1 && destroys==3);
 reset_events();assert(mishare_bridge_step(NULL,&device,mac,5240,1,2)==-EINVAL && !event_count);
 assert(mishare_bridge_retire(NULL,&device)==-EINVAL && !event_count);
 assert(mishare_bridge_scope_begin(NULL,&device)==-EINVAL && !event_count);
 scope.dev=&device;assert(mishare_bridge_scope_begin(&scope,&device)==-EBUSY && !event_count);
 scope.dev=NULL;lookup=&hdd;assert(mishare_bridge_scope_begin(&scope,&device)==0);
 assert(scope.hdd==&hdd && scope.sync==&sync && transition && rtnl);
 mishare_bridge_scope_end(&scope);assert(!scope.dev && !scope.sync && !scope.hdd);
 reset_events();puts("MISHARE_BRIDGE_SCOPE_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Native compilation runs on Actions')
    names = ['wlan_hdd_mishare_bridge_scope.h', 'wlan_hdd_mishare_bridge.h']
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ['linux/device.h', 'linux/rtnetlink.h', 'linux/etherdevice.h',
                     'cds_api.h', 'wlan_hdd_main.h', 'osif_psoc_sync.h',
                     'wlan_hdd_mishare_host.h']:
            p = root/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('/* declarations supplied by native model */\n')
        (root/'linux/string.h').write_text('#include <string.h>\n')
        (root/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        for name in names:
            (root/name).write_bytes((PRODUCTION/name).read_bytes())
        source = root/'test.c'
        source.write_text(HARNESS)
        exe = root/'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I'+str(root), str(source), '-o', str(exe)], check=True)
        result = subprocess.check_output([exe], text=True, timeout=10,
            env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                     UBSAN_OPTIONS='halt_on_error=1'))
    report = ROOT/'.popsicle-ci/artifacts/reports/mishare-bridge-scope-fixture.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        'status': result.strip(),
        'production_sha256': {n: hashlib.sha256((PRODUCTION/n).read_bytes()).hexdigest() for n in names},
        'limitations': 'Production scope and bridge controllers only. Native sync, RTNL, context lookup, allocation and host completions are models. No between-call parent lease, installed callback, native concurrency, SSR recovery, firmware or Apple validation.'
    }, indent=2)+'\n')
    print(result.strip())


if __name__ == '__main__':
    main()
