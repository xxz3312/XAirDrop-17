#!/usr/bin/env python3
"""Actions-only execution and bounded event-sequence exploration of production C."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
static unsigned long explored;
static int same(const struct mishare_vdev_txn *a, const struct mishare_vdev_txn *b) {
 return a->state==b->state && a->pending==b->pending && a->serial==b->serial &&
        a->vdev_id==b->vdev_id && a->submitted==b->submitted && a->replied==b->replied;
}
static void invariant(const struct mishare_vdev_txn *t) {
 assert(t->state>=MISHARE_TXN_COLD && t->state<=MISHARE_TXN_QUARANTINED);
 assert(t->pending>=MISHARE_TXN_NONE && t->pending<=MISHARE_TXN_STOP);
 if(t->state==MISHARE_TXN_QUARANTINED || t->state==MISHARE_TXN_STOPPED) assert(t->pending==MISHARE_TXN_NONE);
 if(t->pending==MISHARE_TXN_START) assert(t->state==MISHARE_TXN_COLD);
 if(t->pending==MISHARE_TXN_STOP) assert(t->state==MISHARE_TXN_STARTED);
 assert(t->vdev_id==7);
}
static void walk(struct mishare_vdev_txn before, int depth) {
 if(!depth) return;
 for(int event=0;event<16;event++) {
  struct mishare_vdev_txn t=before; u64 ticket=123; int ret;
  switch(event) {
   case 0:ret=mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&ticket);break;
   case 1:ret=mishare_vdev_txn_begin(&t,MISHARE_TXN_STOP,&ticket);break;
   case 2:ret=mishare_vdev_txn_submitted(&t,t.serial,MISHARE_TXN_ACCEPTED);break;
   case 3:ret=mishare_vdev_txn_submitted(&t,t.serial,MISHARE_TXN_NOT_SENT);break;
   case 4:ret=mishare_vdev_txn_submitted(&t,t.serial,MISHARE_TXN_UNKNOWN);break;
   case 5:ret=mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true);break;
   case 6:ret=mishare_vdev_txn_response(&t,7,MISHARE_TXN_STOP,true);break;
   case 7:ret=mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,false);break;
   case 8:ret=mishare_vdev_txn_response(&t,7,MISHARE_TXN_STOP,false);break;
   case 9:ret=mishare_vdev_txn_timeout(&t,t.serial);break;
   case 10:ret=mishare_vdev_txn_timeout(&t,t.serial?t.serial-1:0);break;
   case 11:ret=mishare_vdev_txn_response(&t,8,MISHARE_TXN_START,true);break;
   case 12:ret=mishare_vdev_txn_submitted(&t,t.serial,99);break;
   case 13:ret=mishare_vdev_txn_begin(&t,MISHARE_TXN_NONE,&ticket);break;
   case 14:ret=mishare_vdev_txn_response(&t,7,MISHARE_TXN_NONE,true);break;
   default:ret=mishare_vdev_txn_submitted(&t,t.serial?t.serial-1:0,MISHARE_TXN_ACCEPTED);break;
  }
  explored++; invariant(&t); assert(t.serial>=before.serial);
  if(event==0 || event==1 || event==13) {
   if(ret) assert(ticket==0); else assert(ticket==t.serial && ticket!=0);
  }
  if(before.state==MISHARE_TXN_QUARANTINED) assert(same(&t,&before));
  if(ret && ret!=-EIO && ret!=-EPROTO && ret!=-EREMOTEIO && ret!=-ETIMEDOUT && ret!=-EOVERFLOW)
   assert(same(&t,&before));
  if(t.state==MISHARE_TXN_STARTED && before.state!=MISHARE_TXN_STARTED)
   assert(t.submitted && t.replied && before.pending==MISHARE_TXN_START);
  if(t.state==MISHARE_TXN_STOPPED && before.state!=MISHARE_TXN_STOPPED)
   assert(t.submitted && t.replied && before.pending==MISHARE_TXN_STOP);
  walk(t,depth-1);
 }
}
int main(void) {
 struct mishare_vdev_txn t; u64 start,stop,again,invalid;
 assert(mishare_vdev_txn_begin(NULL,MISHARE_TXN_START,&invalid)==-EINVAL && invalid==0);
 assert(mishare_vdev_txn_begin(NULL,MISHARE_TXN_START,NULL)==-EINVAL);
 assert(mishare_vdev_txn_submitted(NULL,1,MISHARE_TXN_ACCEPTED)==-EINVAL);
 assert(mishare_vdev_txn_response(NULL,7,MISHARE_TXN_START,true)==-EINVAL);
 assert(mishare_vdev_txn_timeout(NULL,1)==-EINVAL);
 mishare_vdev_txn_init(&t,7);
 assert(mishare_vdev_txn_begin(&t,MISHARE_TXN_STOP,&invalid)==-EALREADY);
 assert(!mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&start));
 assert(mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&invalid)==-EBUSY && !invalid);
 assert(!mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true));
 assert(t.state==MISHARE_TXN_COLD && !t.submitted && t.replied);
 assert(mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true)==-EALREADY);
 assert(!mishare_vdev_txn_submitted(&t,start,MISHARE_TXN_ACCEPTED));
 assert(t.state==MISHARE_TXN_STARTED);
 assert(mishare_vdev_txn_timeout(&t,start)==-EALREADY);
 assert(!mishare_vdev_txn_begin(&t,MISHARE_TXN_STOP,&stop));
 assert(mishare_vdev_txn_timeout(&t,start)==-ESTALE);
 assert(mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true)==-ENOENT);
 assert(!mishare_vdev_txn_submitted(&t,stop,MISHARE_TXN_ACCEPTED));
 assert(t.state==MISHARE_TXN_STARTED && t.pending==MISHARE_TXN_STOP);
 assert(!mishare_vdev_txn_response(&t,7,MISHARE_TXN_STOP,true));
 assert(t.state==MISHARE_TXN_STOPPED);
 assert(mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&invalid)==-ESHUTDOWN);
 assert(mishare_vdev_txn_response(&t,7,MISHARE_TXN_STOP,true)==-EALREADY);
 /* Proven not-sent permits retry, but old local tickets cannot touch it. */
 mishare_vdev_txn_init(&t,7);
 assert(!mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&start));
 assert(!mishare_vdev_txn_submitted(&t,start,MISHARE_TXN_NOT_SENT));
 assert(!mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&again) && again>start);
 assert(mishare_vdev_txn_submitted(&t,start,MISHARE_TXN_ACCEPTED)==-ESTALE);
 assert(!mishare_vdev_txn_submitted(&t,again,MISHARE_TXN_ACCEPTED));
 assert(mishare_vdev_txn_timeout(&t,again)==-ETIMEDOUT);
 assert(mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true)==-EUCLEAN);
 assert(mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&invalid)==-EUCLEAN);
 /* Early response contradicting not-sent, uncertain send, negative reply. */
 for(int mode=0;mode<3;mode++) {
  mishare_vdev_txn_init(&t,7);
  assert(!mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&start));
  if(mode==0) {
   assert(!mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true));
   assert(mishare_vdev_txn_submitted(&t,start,MISHARE_TXN_NOT_SENT)==-EPROTO);
  } else if(mode==1) assert(mishare_vdev_txn_submitted(&t,start,MISHARE_TXN_UNKNOWN)==-EIO);
  else assert(mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,false)==-EREMOTEIO);
  assert(t.state==MISHARE_TXN_QUARANTINED);
 }
 mishare_vdev_txn_init(&t,7);
 assert(!mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&start));
 assert(!mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,true));
 assert(mishare_vdev_txn_response(&t,7,MISHARE_TXN_START,false)==-EPROTO);
 assert(t.state==MISHARE_TXN_QUARANTINED);
 mishare_vdev_txn_init(&t,7); t.serial=~(u64)0;
 assert(mishare_vdev_txn_begin(&t,MISHARE_TXN_START,&invalid)==-EOVERFLOW && !invalid);
 assert(t.state==MISHARE_TXN_QUARANTINED);
 /* Fresh standalone test instances only; never used as production recovery. */
 mishare_vdev_txn_init(&t,7); walk(t,5);
 assert(explored==1118480UL);
 printf("explored=%lu\n",explored);
 return 0;
}
'''


def fixture():
    return '#include "wlan_hdd_mishare_txn.c"\n' + HARNESS


def audit():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp); (path/'linux').mkdir()
        (path/'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;\ntypedef uint64_t u64;\n')
        (path/'fixture.c').write_text(fixture()); exe=path/'fixture'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-I',str(path),'-I',str(production),str(path/'fixture.c'),'-o',str(exe)],check=True)
        output=subprocess.check_output([str(exe)],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if output.strip()!='explored=1118480':
            raise ValueError('Unexpected event exploration count')
    return {'status':'MISHARE_TXN_EVENT_FIXTURE_PASS_ONLY','explored_event_edges':1118480,'max_sequence_length':5,
            'production_sha256':{name:hashlib.sha256((production/name).read_bytes()).hexdigest() for name in ['wlan_hdd_mishare_txn.c','wlan_hdd_mishare_txn.h']},
            'fixture_sha256':hashlib.sha256(fixture().encode()).hexdigest(),
            'checks':['early response','submission is not completion','wrong response kind and vdev','duplicate completion','definitely not sent retry','stale local ticket','timeout quarantine','uncertain send quarantine','negative response quarantine','contradictory not-sent quarantine','conflicting early response quarantine','terminal stop blocks same-command reuse','serial overflow'],
            'limitations':'Serialized pure production transaction accounting, not real MLME callbacks, firmware, timers, event draining, object cleanup, synchronization or AirDrop. Local tickets are not firmware response cookies.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=audit();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
