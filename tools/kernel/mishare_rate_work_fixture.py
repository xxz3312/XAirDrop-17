#!/usr/bin/env python3
"""Production rate work ownership with modeled scheduler/runtime/ref APIs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HARNESS=r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int QDF_STATUS;
#define ETH_ALEN 6
#define BIT(n) (1U<<(n))
#define GFP_KERNEL 0
#define QDF_STATUS_SUCCESS 0
#define QDF_STATUS_E_INVAL 9
#define QDF_IS_STATUS_ERROR(x) ((x)!=0)
#define QDF_MODULE_ID_HDD 1
#define QDF_MODULE_ID_PE 2
#define QDF_MODULE_ID_TARGET_IF 3
#define WLAN_LEGACY_MAC_ID 4
#include "wlan_hdd_mishare_rate.h"
struct wlan_objmgr_vdev {int refs;};
struct scheduler_msg {void *bodyptr;QDF_STATUS (*callback)(struct scheduler_msg *),(*flush_callback)(struct scheduler_msg *);};
static struct scheduler_msg queued;
static struct wlan_objmgr_vdev v={1};
static int owner,allocs,pending,users,execs,done_calls,last_result,exec_error;
static bool fail_alloc,fail_ref,fail_get,fail_post,fenced,inline_finish;
static struct mishare_rate_submission observed;
static void *kzalloc(size_t n,int flags){assert(flags==0);if(fail_alloc)return NULL;allocs++;return calloc(1,n);}
static void kfree(void *p){assert(p && allocs==1);allocs--;free(p);}
static int qdf_status_to_os_return(int s){return s?-EIO:0;}
static int wlan_objmgr_vdev_try_get_ref(struct wlan_objmgr_vdev *x,int id){assert(x==&v && id==4 && x->refs==1);if(fail_ref)return 1;x->refs++;return 0;}
static void wlan_objmgr_vdev_release_ref(struct wlan_objmgr_vdev *x,int id){assert(x==&v && id==4 && x->refs==2 && !pending && !users && "EXPECTED_RATE_WORK_REF");x->refs--;}
static int mishare_runtime_work_get(struct wlan_objmgr_vdev *x,void *o){assert(x==&v && o==&owner && v.refs==2 && !pending);if(fail_get)return -ESHUTDOWN;pending++;return 0;}
static int mishare_runtime_work_enter(struct wlan_objmgr_vdev *x,void *o){assert(x==&v && o==&owner && pending==1 && !users && "EXPECTED_RATE_WORK_ENTER");if(fenced)return -ESHUTDOWN;users++;return 0;}
static void mishare_runtime_work_exit(struct wlan_objmgr_vdev *x,void *o){assert(x==&v && o==&owner && pending==1 && users==1 && "EXPECTED_RATE_WORK_EXIT");users--;}
static void mishare_runtime_work_put(struct wlan_objmgr_vdev *x,void *o){assert(x==&v && o==&owner && v.refs==2 && pending==1 && !users && "EXPECTED_RATE_WORK_PUT");pending--;}
int mishare_rate_submit_mc(struct wlan_objmgr_vdev *x,const struct wondertap_fixed_tx_rate_params *p,struct mishare_rate_submission *r){
 assert(x==&v && v.refs==2 && pending==1 && users==1 && "EXPECTED_RATE_WORK_EXECUTE");
 assert(p->nss==1 && p->mcs==7 && p->preamble==WONDERTAP_RATE_PREAMBLE_HT && !p->reserved[0] && "EXPECTED_RATE_WORK_SNAPSHOT");
 execs++;r->attempted=true;r->attempted_mask=exec_error?1:7;r->submitted_mask=exec_error?0:7;r->first_error=exec_error;r->complete=!exec_error;return exec_error;
}
static int scheduler_post_message(int a,int b,int c,struct scheduler_msg *m){
 assert(a==1 && b==2 && c==3 && v.refs==2 && pending==1 && m->bodyptr && m->callback && m->flush_callback && "EXPECTED_RATE_WORK_PUBLICATION");
 if(fail_post)return 1;
 queued=*m;
 if(inline_finish)assert(!queued.callback(&queued));
 return 0;
}
#include "wlan_hdd_mishare_rate_work.c"
static void completed(void *o,const struct mishare_rate_submission *r,int result){
 assert(o==&owner && v.refs==2 && pending==1 && !users && !allocs && !queued.bodyptr && "EXPECTED_RATE_WORK_COMPLETION");
 done_calls++;observed=*r;last_result=result;
}
static void reset(void){
 assert(v.refs==1 && !pending && !users && !allocs && "EXPECTED_RATE_WORK_BALANCE");
 queued=(struct scheduler_msg){0};observed=(struct mishare_rate_submission){0};execs=done_calls=0;exec_error=last_result=0;
 fail_alloc=fail_ref=fail_get=fail_post=fenced=inline_finish=false;
}
int main(void){
 struct wondertap_fixed_tx_rate_params p={.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7};
 assert(mishare_rate_post(NULL,&owner,&p,completed)==-EINVAL);
 assert(mishare_rate_post(&v,NULL,&p,completed)==-EINVAL);
 assert(mishare_rate_post(&v,&owner,NULL,completed)==-EINVAL);
 assert(mishare_rate_post(&v,&owner,&p,NULL)==-EINVAL);
 p.nss=0;assert(mishare_rate_post(&v,&owner,&p,completed)==-EINVAL);p.nss=1;
 for(int fault=0;fault<4;fault++){
  reset();fail_alloc=fault==0;fail_ref=fault==1;fail_get=fault==2;fail_post=fault==3;
  int expected=fault==0?-ENOMEM:fault==1?-ENODEV:fault==2?-ESHUTDOWN:-EIO;
  assert(mishare_rate_post(&v,&owner,&p,completed)==expected && !queued.bodyptr && !done_calls && !execs && "EXPECTED_RATE_WORK_REFUSAL");
  assert(v.refs==1 && !pending && !users && !allocs && "EXPECTED_RATE_WORK_BALANCE");
 }
 for(int mode=0;mode<6;mode++){
  reset();inline_finish=mode==4;exec_error=mode==3?-ENOSPC:0;
  memset(p.reserved,255,sizeof(p.reserved));
  assert(!mishare_rate_post(&v,&owner,&p,completed));
  if(mode!=4){
   assert(v.refs==2 && pending==1 && !users && allocs==1 && !done_calls && !execs && "EXPECTED_RATE_WORK_RETAINED");
   if(mode==2)fenced=true;
   if(mode==5){p.nss=0;p.mcs=99;}
   assert(!(mode==1?queued.flush_callback(&queued):queued.callback(&queued)));
   p.nss=1;p.mcs=7;
  }
  int expected=mode==1?-ECANCELED:mode==2?-ESHUTDOWN:mode==3?-ENOSPC:0;
  assert(done_calls==1 && last_result==expected && execs==((mode==1 || mode==2)?0:1) && "EXPECTED_RATE_WORK_RESULT");
  assert(observed.attempted==!!execs && observed.complete==(!expected) && "EXPECTED_RATE_WORK_RESULT");
  assert(v.refs==1 && !pending && !users && !allocs && "EXPECTED_RATE_WORK_BALANCE");
  assert(queued.flush_callback(&queued)==QDF_STATUS_E_INVAL && done_calls==1 && "EXPECTED_RATE_WORK_ONCE");
 }
 reset();puts("MISHARE_RATE_WORK_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    src=ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_rate_work.c';original=src.read_text()
    headers={'wlan_hdd_mishare_rate.h':ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_rate.h','wlan_hdd_mishare_wonder_api.h':ROOT/'kernel/provider/wondertap.h'}
    mutations=[
        ('complete(owner, &receipt, ret);','mishare_runtime_work_put(vdev, owner); complete(owner, &receipt, ret);'),
        ('complete(owner, &receipt, ret);','wlan_objmgr_vdev_release_ref(vdev, WLAN_LEGACY_MAC_ID); complete(owner, &receipt, ret);'),
        ('ret = flushed ? -ECANCELED :','ret = (false && flushed) ? -ECANCELED :'),
        ('if (!ret) {','if (true) {'),
        ('msg.flush_callback = mishare_rate_flush;','msg.flush_callback = false ? mishare_rate_flush : NULL;'),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['linux/slab.h','qdf_status.h','scheduler_api.h','wlan_objmgr_vdev_obj.h','wlan_hdd_mishare_ndi.h','linux/if_ether.h']:(d/name).write_text('/* modeled in harness */\n')
        (d/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        for name,path in headers.items():(d/name).write_bytes(path.read_bytes())
        body=d/src.name;body.write_text(original);source=d/'test.c';source.write_text(HARNESS);exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks='+('1' if os.environ.get('GITHUB_ACTIONS')=='true' else '0')+':abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(command,check=True);result=subprocess.check_output([exe],text=True,env=env,timeout=10).strip()
        for needle,replacement in mutations:
            assert original.count(needle)==1,needle
            body.write_text(original.replace(needle,replacement));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode==-6 and 'EXPECTED_RATE_WORK_' in bad.stderr,(needle,bad.returncode,bad.stderr[-1600:])
    out=ROOT/'.popsicle-ci/artifacts/reports/mishare-rate-work-fixture.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':result,'mutation_controls':len(mutations),'production_sha256':hashlib.sha256(original.encode()).hexdigest(),'limitations':'Production MC wrapper with modeled scheduler/ref/runtime accounting and executor; separate rate fixture executes actual rate encoder submission and native WMA helper. No complete runtime/native shutdown integration, parent lifetime, firmware ACK, RF or Apple certification.'},indent=2)+'\n');print(result)


if __name__=='__main__':main()
