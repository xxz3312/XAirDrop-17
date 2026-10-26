#!/usr/bin/env python3
"""Actions-only production command/registry/transaction C with native-send stubs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_events_fixture import COMMON, ROOT
from popsicle_backend_audit import PIN
QDF='qca-wifi-host-cmn/qdf/inc/qdf_status.h'
QDF_C='qca-wifi-host-cmn/qdf/linux/src/qdf_status.c'
TRANSPORT=r'''
#define WLAN_VDEV_MLME_TYPE_PASSTHRU 9
struct vdev_mlme_obj {
 struct wlan_objmgr_vdev *vdev;
 struct { struct { u8 type,subtype; } generic; } mgmt;
};
static struct vdev_mlme_obj *wlan_vdev_mlme_get_cmpt_obj(struct wlan_objmgr_vdev *v) {
 assert(v->refs>0);return v->mlme;
}
static QDF_STATUS send_status;
static int callback_mode,start_calls,stop_calls;
static QDF_STATUS native_send(struct vdev_mlme_obj *m,enum mishare_txn_command command) {
 assert(!lock_depth && m && m->vdev->refs>0);
 assert(wlan_vdev_mlme_get_cmpt_obj(m->vdev)==m);
 if(command==MISHARE_TXN_START)start_calls++;else stop_calls++;
 struct wlan_objmgr_vdev *v=m->vdev;
 if(callback_mode==1)assert(!mishare_events_notify(v->psoc,v->id,command,MISHARE_EVENT_FIRMWARE,true));
 if(callback_mode==2)assert(mishare_events_notify(v->psoc,v->id,command,MISHARE_EVENT_FIRMWARE,false)==-EREMOTEIO);
 if(callback_mode==3)assert(mishare_events_notify(v->psoc,v->id,command,MISHARE_EVENT_TIMEOUT,false)==-ETIMEDOUT);
 if(callback_mode==4)assert(mishare_events_notify(v->psoc,v->id+1,command,MISHARE_EVENT_FIRMWARE,true)==-ENOENT);
 return send_status;
}
static QDF_STATUS vdev_mgr_start_send(struct vdev_mlme_obj *m,bool restart) {
 assert(!restart);return native_send(m,MISHARE_TXN_START);
}
static QDF_STATUS vdev_mgr_stop_send(struct vdev_mlme_obj *m) {
 return native_send(m,MISHARE_TXN_STOP);
}
#include "wlan_hdd_mishare_commands.c"
'''
HARNESS=r'''
struct context { struct wlan_objmgr_vdev v; struct vdev_mlme_obj m;struct mishare_event_owner *owner; };
static struct wlan_objmgr_psoc psoc={1};
static void setup(struct context *c,u8 id) {
 *c=(struct context){0};c->v.psoc=&psoc;c->v.id=id;c->v.mode=17;c->v.mlme=&c->m;
 c->m.vdev=&c->v;c->m.mgmt.generic.type=9;
 assert(!mishare_events_bind(&c->v,&c->owner));
 send_status=QDF_STATUS_SUCCESS;callback_mode=0;start_calls=stop_calls=0;
}
static struct mishare_vdev_txn snapshot(struct context *c) {
 struct mishare_vdev_txn s;assert(!mishare_events_snapshot(c->owner,&s));return s;
}
static void finish(struct context *c) {
 mishare_events_unbind(&c->owner);assert(!c->owner && !c->v.refs);
}
int main(void) {
 struct context a,b;u64 ticket=123,other=123;
 assert(mishare_command_submit_start(NULL,NULL,&ticket)==-EINVAL && !ticket);
 assert(mishare_command_submit_start(NULL,NULL,NULL)==-EINVAL);
 assert(mishare_command_submit_stop(NULL,NULL,&ticket)==-EINVAL && !ticket);
 setup(&a,20);setup(&b,21);
 assert(mishare_events_begin_vdev(NULL,&a.v,MISHARE_TXN_START,&ticket)==-EINVAL && !ticket);
 assert(mishare_events_begin_vdev(a.owner,NULL,MISHARE_TXN_START,&ticket)==-EINVAL && !ticket);
 assert(mishare_events_begin_vdev(a.owner,&a.v,MISHARE_TXN_START,NULL)==-EINVAL);
 assert(mishare_command_submit_start(a.owner,NULL,&ticket)==-EINVAL && !ticket);
 struct vdev_mlme_obj empty={0};
 assert(mishare_command_submit_start(a.owner,&empty,&ticket)==-EINVAL && !ticket);
 assert(mishare_command_submit_start(a.owner,&b.m,&ticket)==-EXDEV && !ticket);
 assert(snapshot(&a).state==MISHARE_TXN_COLD && snapshot(&b).state==MISHARE_TXN_COLD);
 a.m.mgmt.generic.type=2;
 assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==-EOPNOTSUPP && !ticket);
 a.m.mgmt.generic.type=9;a.m.mgmt.generic.subtype=1;
 assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==-EOPNOTSUPP && !ticket);
 a.m.mgmt.generic.subtype=0;a.v.mode=0;
 assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==-EOPNOTSUPP && !ticket);
 a.v.mode=17;a.v.mlme=NULL;
 assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==-EINVAL && !ticket);
 a.v.mlme=&a.m;struct vdev_mlme_obj foreign=a.m;
 assert(mishare_command_submit_start(a.owner,&foreign,&ticket)==-EINVAL && !ticket);
 assert(!start_calls && !stop_calls && !snapshot(&a).serial);
 assert(mishare_command_submit_stop(a.owner,&a.m,&ticket)==-EALREADY && !ticket);
 assert(!mishare_command_submit_start(a.owner,&a.m,&ticket) && ticket);
 assert(start_calls==1 && !stop_calls);
 assert(snapshot(&a).state==MISHARE_TXN_COLD && snapshot(&a).submitted && !snapshot(&a).replied);
 assert(mishare_command_submit_start(a.owner,&a.m,&other)==-EBUSY && !other && start_calls==1);
 assert(!mishare_events_notify(&psoc,20,MISHARE_TXN_START,MISHARE_EVENT_FIRMWARE,true));
 assert(snapshot(&a).state==MISHARE_TXN_STARTED);
 assert(!mishare_command_submit_stop(a.owner,&a.m,&other) && other>ticket && stop_calls==1);
 assert(snapshot(&a).state==MISHARE_TXN_STARTED && snapshot(&a).pending==MISHARE_TXN_STOP);
 assert(!mishare_events_notify(&psoc,20,MISHARE_TXN_STOP,MISHARE_EVENT_FIRMWARE,true));
 assert(snapshot(&a).state==MISHARE_TXN_STOPPED);
 assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==-ESHUTDOWN && !ticket && start_calls==1);
 finish(&a);finish(&b);
 /* Native sends can synchronously deliver an origin notification before return. */
 setup(&a,22);callback_mode=1;
 assert(!mishare_command_submit_start(a.owner,&a.m,&ticket));
 assert(snapshot(&a).state==MISHARE_TXN_STARTED && start_calls==1);
 assert(!mishare_command_submit_stop(a.owner,&a.m,&ticket));
 assert(snapshot(&a).state==MISHARE_TXN_STOPPED && stop_calls==1);finish(&a);
 for(int mode=2;mode<=3;mode++) {
  setup(&a,23+mode);callback_mode=mode;
  assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==-EUCLEAN && ticket);
  assert(snapshot(&a).state==MISHARE_TXN_QUARANTINED && allocations==1 && a.v.refs==1);
  assert(mishare_command_submit_start(a.owner,&a.m,&other)==-EUCLEAN && !other && start_calls==1);
  finish(&a);
 }
 /* Every generic native error is UNKNOWN, even an INVAL or timeout status. */
 QDF_STATUS errors[]={QDF_STATUS_E_IO,QDF_STATUS_E_INVAL,QDF_STATUS_E_TIMEOUT,QDF_STATUS_E_PENDING};
 for(unsigned int i=0;i<sizeof(errors)/sizeof(errors[0]);i++) {
  for(int early=0;early<2;early++) {
   setup(&a,30+i*2+early);send_status=errors[i];callback_mode=early;
   assert(mishare_command_submit_start(a.owner,&a.m,&ticket)==qdf_status_to_os_return(errors[i]) && ticket);
   assert(snapshot(&a).state==MISHARE_TXN_QUARANTINED && allocations==1 && a.v.refs==1 && start_calls==1);
   finish(&a);
  }
 }
 /* An unrelated vdev notification cannot satisfy this command. */
 setup(&a,40);callback_mode=4;
 assert(!mishare_command_submit_start(a.owner,&a.m,&ticket));
 assert(snapshot(&a).pending==MISHARE_TXN_START && !snapshot(&a).replied);finish(&a);
 /* STOP send failure also preserves ownership and quarantines. */
 setup(&a,41);callback_mode=1;
 assert(!mishare_command_submit_start(a.owner,&a.m,&ticket));
 callback_mode=0;send_status=QDF_STATUS_E_IO;
 assert(mishare_command_submit_stop(a.owner,&a.m,&ticket)==-EIO && ticket && stop_calls==1);
 assert(snapshot(&a).state==MISHARE_TXN_QUARANTINED && allocations==1 && a.v.refs==1);finish(&a);
 assert(!allocations && !mishare_event_owners);
 puts("MISHARE_COMMAND_SUBMIT_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    status=re.search(r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;',(root/QDF).read_text(),re.S)[0]
    mapping=re.search(r'#else\n(int qdf_status_to_os_return\(QDF_STATUS status\)\n\{.*?^\})',(root/QDF_C).read_text(),re.S|re.M)[1]
    common=COMMON.replace('int mode,refs,dead;','int mode,refs,dead; struct vdev_mlme_obj *mlme;').replace(', legacy_calls','')
    return status+'\n'+common+'\n'+mapping+'\n'+TRANSPORT+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected source commit')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;\ntypedef uint64_t u64;\n')
        for n in ['linux/bug.h','linux/slab.h','linux/spinlock.h','wlan_objmgr_vdev_obj.h','qdf_status.h','wlan_vdev_mlme.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* fixture declarations */\n')
        (d/'test.c').write_text(source);exe=d/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'test.c'),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if output.strip()!='MISHARE_COMMAND_SUBMIT_FIXTURE_PASS_ONLY':raise ValueError('Unexpected output')
    names=['wlan_hdd_mishare_commands.c','wlan_hdd_mishare_commands.h','wlan_hdd_mishare_events.c','wlan_hdd_mishare_events.h','wlan_hdd_mishare_txn.c','wlan_hdd_mishare_txn.h']
    return {'status':'MISHARE_COMMAND_SUBMIT_FIXTURE_PASS_ONLY','source_commit':PIN,
            'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},
            'qdf_status_mapping_sha256':hashlib.sha256((root/QDF_C).read_bytes()).hexdigest(),
            'checks':['null and unpublished/foreign MLME rejection','mode/type/subtype preflight','exact bound vdev check','no send on preflight/state rejection','queued submission remains pending','one native call per accepted transaction','START never uses RESTART','early success/failure/timeout without registry lock','unrelated vdev exclusion','generic native errors quarantine','native error mapping retained','no free/ref release on submission failure','STOP submission and terminal reuse rejection'],
            'limitations':'Production command/registry/transaction C with native vdev-manager sends, component lookup and object manager mocked. Not actual native parameter packing, channel/concurrency/DFS setup, WMI transmission, dedicated MLME ops, teardown or radio certification. No runtime command caller yet.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
