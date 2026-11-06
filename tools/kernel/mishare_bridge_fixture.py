#!/usr/bin/env python3
"""Production bridge controller; native host/lifetime/completions are models."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'kernel/popsicle-hdd/wlan_hdd_mishare_bridge.h'
DECL = r'''
#include <stdbool.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define ETH_ALEN 6
struct hdd_context { int id; };
struct mishare_wonder_host { int id; };
int mishare_wonder_host_create_locked(struct hdd_context *, const u8 *, struct mishare_wonder_host **);
int mishare_wonder_host_vdev_create_locked(struct mishare_wonder_host *);
int mishare_wonder_host_session_step_locked(struct mishare_wonder_host *, u32, u8, u8);
int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **);
static bool is_valid_ether_addr(const u8 *m)
{ return !(m[0]&1) && (m[0]|m[1]|m[2]|m[3]|m[4]|m[5]); }
'''
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "wlan_hdd_mishare_bridge.h"
static struct hdd_context parent, wrong;
static struct mishare_wonder_host host;
static const u8 mac[6]={2,1,2,3,4,5};
static unsigned creates, attaches, steps, destroys;
static int create_ret, attach_ret, step_ret, destroy_ret, destroy_bad;
static bool missing_host, retained_create, parent_lease;
int mishare_wonder_host_create_locked(struct hdd_context *h,const u8 *m,struct mishare_wonder_host **o)
{ assert(parent_lease && h==&parent && !memcmp(m,mac,6) && !*o);creates++;
  if(!missing_host && (!create_ret || retained_create))
    *o=&host;
  return create_ret; }
int mishare_wonder_host_vdev_create_locked(struct mishare_wonder_host *o)
{ assert(parent_lease && o==&host);attaches++;return attach_ret; }
int mishare_wonder_host_session_step_locked(struct mishare_wonder_host *o,u32 f,u8 a,u8 b)
{ assert(parent_lease && o==&host && f==5240 && a==1 && b==2);steps++;return step_ret; }
int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **o)
{ assert(parent_lease && *o==&host);destroys++;
  if((!destroy_ret && destroy_bad!=1) || destroy_bad==2)
    *o=NULL;
  return destroy_ret; }
static int step(struct mishare_bridge *b)
{ return mishare_bridge_step_locked(b,&parent,mac,5240,1,2); }
static int retire(struct mishare_bridge *b)
{ return mishare_bridge_retire_locked(b,&parent); }
static void reset(struct mishare_bridge *b)
{ memset(b,0,sizeof(*b));creates=attaches=steps=destroys=0;
  create_ret=attach_ret=destroy_ret=destroy_bad=0;step_ret=-EINPROGRESS;
  missing_host=retained_create=false;parent_lease=true; }
int main(void)
{
 struct mishare_bridge b;
 u8 changed[6]={2,1,2,3,4,6}, bad[6]={0};
 reset(&b);
 assert(mishare_bridge_step_locked(NULL,&parent,mac,5240,1,2)==-EINVAL);
 assert(mishare_bridge_step_locked(&b,&parent,bad,5240,1,2)==-EINVAL);
 assert(mishare_bridge_step_locked(&b,&parent,mac,0,1,2)==-EINVAL);
 assert(mishare_bridge_step_locked(&b,&parent,mac,5240,0,2)==-EINVAL);
 assert(mishare_bridge_step_locked(&b,&parent,mac,5240,1,3)==-EINVAL);
 assert(!creates && !b.attempted);
 assert(step(&b)==-EINPROGRESS && creates==1 && !attaches && !steps);
 assert(mishare_bridge_step_locked(&b,&wrong,mac,5240,1,2)==-EBUSY);
 assert(mishare_bridge_step_locked(&b,&parent,changed,5240,1,2)==-EBUSY);
 assert(mishare_bridge_step_locked(&b,&parent,mac,5745,1,2)==-EBUSY);
 assert(mishare_bridge_step_locked(&b,&parent,mac,5240,2,2)==-EBUSY);
 assert(mishare_bridge_retire_locked(&b,&wrong)==-EBUSY && !b.closing);
 assert(step(&b)==-EINPROGRESS && attaches==1 && !steps);
 for(unsigned i=0;i<5;i++)assert(step(&b)==-EINPROGRESS);
 assert(creates==1 && attaches==1 && steps==5);
 step_ret=0;assert(step(&b)==0); /* Radio only; no Wonder-ready publication. */
 destroy_ret=-EINPROGRESS;
 for(unsigned i=0;i<3;i++)assert(retire(&b)==-EINPROGRESS && b.host==&host && !b.retired);
 unsigned before=steps;assert(step(&b)==-ESHUTDOWN && steps==before);
 destroy_ret=-EBUSY;assert(retire(&b)==-EBUSY && b.host==&host);
 destroy_ret=0;assert(retire(&b)==0 && !b.host && b.retired);
 before=destroys;assert(retire(&b)==0 && destroys==before && step(&b)==-ESHUTDOWN);
 /* Failures at each stage are sticky; retirement still owns the host. */
 for(unsigned stage=0;stage<3;stage++) {
  reset(&b);
  if(stage==0)create_ret=-ENOMEM;
  if(stage==1)attach_ret=-EUCLEAN;
  if(stage==2)step_ret=-ESHUTDOWN;
  for(unsigned i=0;i<stage;i++)assert(step(&b)==-EINPROGRESS);
  int expected=stage==0?-ENOMEM:stage==1?-EUCLEAN:-ESHUTDOWN;
  assert(step(&b)==expected);
  before=creates+attaches+steps;
  assert(step(&b)==expected && creates+attaches+steps==before);
  assert(retire(&b)==0 && !b.host && destroys==(stage?1u:0u));
 }
 reset(&b);create_ret=-EUCLEAN;retained_create=true;
 assert(step(&b)==-EUCLEAN && b.host==&host);
 assert(retire(&b)==0 && destroys==1);
 reset(&b);missing_host=true;assert(step(&b)==-EUCLEAN && creates==1);
 assert(step(&b)==-EUCLEAN && creates==1 && retire(&b)==0);
 for(int kind=1;kind<=2;kind++) {
  reset(&b);assert(step(&b)==-EINPROGRESS);destroy_bad=kind;
  destroy_ret=kind==2?-EINPROGRESS:0;
  assert(retire(&b)==-EUCLEAN && !b.retired);
  before=destroys;assert(retire(&b)==-EUCLEAN && destroys==before);
 }
 reset(&b);b.host=&host;assert(step(&b)==-EUCLEAN && !creates);
 assert(retire(&b)==-EUCLEAN && !destroys && b.host==&host);
 reset(&b);assert(retire(&b)==0 && !destroys && step(&b)==-ESHUTDOWN);
 puts("MISHARE_BRIDGE_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Native compilation runs on Actions')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'linux').mkdir()
        (root/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        (root/'linux/string.h').write_text('#include <string.h>\n')
        (root/'linux/etherdevice.h').write_text('/* declarations in host model */\n')
        (root/'wlan_hdd_mishare_host.h').write_text(DECL)
        (root/HEADER.name).write_bytes(HEADER.read_bytes())
        source = root/'test.c'
        source.write_text(HARNESS)
        exe = root/'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-I'+str(root), str(source),
                        '-o', str(exe)], check=True)
        result = subprocess.check_output([exe], text=True, timeout=10,
            env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                     UBSAN_OPTIONS='halt_on_error=1'))
    report = ROOT/'.popsicle-ci/artifacts/reports/mishare-bridge-fixture.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        'status': result.strip(), 'header_sha256': hashlib.sha256(HEADER.read_bytes()).hexdigest(),
        'limitations': 'Production bridge controller only. Host allocation, RTNL/PSOC serialization, parent lease and native completions are models. No automatic caller/lease, Wonder parameter mapping, RX/TX, firmware, phone or Apple interoperability proof.'
    }, indent=2)+'\n')
    print(result.strip())


if __name__ == '__main__':
    main()
