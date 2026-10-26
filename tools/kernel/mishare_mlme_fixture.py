#!/usr/bin/env python3
"""Actions-only execution of actual MLME create code with resource/WMI stubs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from passthru_mode_fixture import QDF, MLME, enum, function
from popsicle_backend_audit import PIN


def fixture(root):
    read = lambda name: (root / name).read_text()
    status = re.search(r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;', read('qca-wifi-host-cmn/qdf/inc/qdf_status.h'), re.S)[0]
    macros = '\n'.join(line for line in read('qca-wifi-host-cmn/umac/mlme/include/wlan_vdev_mlme.h').splitlines()
                       if re.match(r'#define WLAN_VDEV_MLME_(TYPE|SUBTYPE)_\w+\s+0x[0-9a-fA-F]+$', line))
    macros += '\n' + re.search(r'^#define WMI_HOST_VDEV_TYPE_MONITOR\s+0x[0-9a-fA-F]+$', read('qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h'), re.M)[0]
    source = '#include <assert.h>\n#include <stdint.h>\n#include <stdlib.h>\n#include <string.h>\n'
    source += enum(read(QDF), 'QDF_OPMODE') + '\n' + status + '\n' + macros
    source += r'''
#define QDF_IS_STATUS_ERROR(s) ((s) != QDF_STATUS_SUCCESS)
#define mlme_err(...) ((void)0)
#define mlme_legacy_debug(...) ((void)0)
struct wlan_objmgr_vdev { enum QDF_OPMODE mode; struct { uint8_t vdev_id; } vdev_objmgr; };
struct mlme_legacy_priv {
 struct { void *fils_con_info; } connect_info;
 int wait_key_timer, bss_color_change_wakelock, bss_color_change_runtime_lock;
 int disconnect_runtime_lock, set_key_wakelock_counter;
 int peer_set_key_wakelock, peer_set_key_rt_wakelock;
};
struct vdev_mlme_obj {
 struct wlan_objmgr_vdev *vdev;
 struct mlme_legacy_priv *ext_vdev_ptr;
 struct { struct { uint8_t type, subtype; } generic; } mgmt;
 struct { struct { uint8_t nss_2g, nss_5g; } generic; } proto;
};
static int alloc_fail, send_fail, allocations, initializations, sends, destroys;
static enum QDF_OPMODE wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { return v->mode; }
static uint8_t wlan_vdev_get_id(struct wlan_objmgr_vdev *v) { return v->vdev_objmgr.vdev_id; }
static void *qdf_mem_common_alloc(size_t n) { allocations++; return alloc_fail ? NULL : calloc(1,n); }
static void mlme_init_rate_config(struct vdev_mlme_obj *m) { assert(m->ext_vdev_ptr); initializations++; }
static void mlme_init_connect_chan_info_config(struct vdev_mlme_obj *m) { assert(m->ext_vdev_ptr); initializations++; }
static void mlme_cm_alloc_roam_stats_info(struct vdev_mlme_obj *m) { assert(m->ext_vdev_ptr); initializations++; }
static void mlme_init_wait_for_key_timer(struct wlan_objmgr_vdev *v, int *p) { assert(v); *p=1; initializations++; }
static void qdf_wake_lock_create(int *p, const char *name) { assert(name && !*p); *p=1; initializations++; }
static void qdf_runtime_lock_init(int *p) { assert(!*p); *p=1; initializations++; }
static void qdf_atomic_init(int *p) { *p=0; initializations++; }
static void sme_get_vdev_type_nss(enum QDF_OPMODE mode, uint8_t *a, uint8_t *b) { (void)mode; *a=1; *b=2; initializations++; }
static void check_initialized(struct vdev_mlme_obj *m) {
 struct mlme_legacy_priv *p=m->ext_vdev_ptr;
 assert(p && p->wait_key_timer && p->bss_color_change_wakelock);
 assert(p->bss_color_change_runtime_lock && p->disconnect_runtime_lock);
 assert(p->peer_set_key_wakelock && p->peer_set_key_rt_wakelock);
}
static QDF_STATUS vdev_mgr_create_send(struct vdev_mlme_obj *m) {
 check_initialized(m); assert(m->vdev->mode != QDF_PASSTHRU_MODE);
 assert(m->mgmt.generic.type != 9); sends++;
 return send_fail ? QDF_STATUS_E_FAILURE : QDF_STATUS_SUCCESS;
}
/* Destruction is mocked: this fixture certifies create's call order only. */
static QDF_STATUS vdevmgr_mlme_ext_hdl_destroy(struct vdev_mlme_obj *m) {
 check_initialized(m); destroys++; free(m->ext_vdev_ptr); m->ext_vdev_ptr=NULL;
 return QDF_STATUS_SUCCESS;
}
'''
    source += '\n' + function(read(MLME), 'mlme_get_vdev_types')
    source += '\n' + function(read(MLME), 'vdevmgr_mlme_ext_hdl_create')
    source += r'''
static void reset(void) { alloc_fail=send_fail=allocations=initializations=sends=destroys=0; }
int main(void) {
 struct wlan_objmgr_vdev v={.mode=QDF_PASSTHRU_MODE};
 struct vdev_mlme_obj m={.vdev=&v};
 reset();
 assert(vdevmgr_mlme_ext_hdl_create(NULL)==QDF_STATUS_E_INVAL);
 m.vdev=NULL;
 assert(vdevmgr_mlme_ext_hdl_create(&m)==QDF_STATUS_E_INVAL);
 assert(!allocations && !initializations && !sends && !destroys);
 m.vdev=&v;
 for(int fail=0;fail<2;fail++) {
  reset(); alloc_fail=fail;
  m.mgmt.generic.type=0xa5; m.mgmt.generic.subtype=0xa5;
  uint8_t type=0, subtype=0xa5;
  assert(mlme_get_vdev_types(QDF_PASSTHRU_MODE,&type,&subtype)==QDF_STATUS_SUCCESS);
  assert(type==9 && subtype==0);
  assert(vdevmgr_mlme_ext_hdl_create(&m)==QDF_STATUS_E_NOSUPPORT);
  assert(!m.ext_vdev_ptr && m.mgmt.generic.type==0xa5 && m.mgmt.generic.subtype==0xa5);
  assert(!allocations && !initializations && !sends && !destroys);
 }
 for(int mode=-1;mode<=18;mode++) {
  if(mode==QDF_PASSTHRU_MODE) continue;
  v.mode=mode;
  uint8_t type=0,subtype=0;
  QDF_STATUS expected=mlme_get_vdev_types(mode,&type,&subtype);
  for(int failure=0;failure<3;failure++) {
   reset(); alloc_fail=failure==1; send_fail=failure==2;
   m.mgmt.generic.type=0xa5; m.mgmt.generic.subtype=0xa5;
   QDF_STATUS result=vdevmgr_mlme_ext_hdl_create(&m);
   if(expected!=QDF_STATUS_SUCCESS) {
    assert(result==expected && !allocations && !initializations && !sends && !destroys);
    assert(m.mgmt.generic.type==0xa5 && m.mgmt.generic.subtype==0xa5);
   } else if(alloc_fail) {
    assert(result==QDF_STATUS_E_NOMEM && allocations==1 && !initializations && !sends && !destroys);
   } else {
    assert(allocations==1 && initializations==11 && sends==1);
    assert(m.mgmt.generic.type==type && m.mgmt.generic.subtype==subtype);
    if(send_fail) assert(result==QDF_STATUS_E_FAILURE && destroys==1 && !m.ext_vdev_ptr);
    else { assert(result==QDF_STATUS_SUCCESS && !destroys); vdevmgr_mlme_ext_hdl_destroy(&m); }
   }
   assert(!m.ext_vdev_ptr);
  }
 }
 return 0;
}
'''
    # Logging is compiled out by the fixture; keep the actual accessor checked.
    source = source.replace('#define mlme_err(...) ((void)0)', '#define mlme_err(...) ((void)wlan_vdev_get_id)')
    return source


def audit(root):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    head = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if head != PIN:
        raise ValueError('Unexpected source commit')
    source = fixture(root)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'mlme.c'; path.write_text(source); exe=Path(tmp)/'mlme'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined',str(path),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True,timeout=10,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    return {'status':'MISHARE_MLME_PREFLIGHT_FIXTURE_PASS_ONLY','source_commit':head,
            'fixture_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'mlme_source_sha256':hashlib.sha256((root/MLME).read_bytes()).hexdigest(),
            'host_translation':{'qdf_mode':17,'type':9,'subtype':0},
            'passthru_create':'E_NOSUPPORT_BEFORE_ALLOCATION_OR_COMMAND',
            'limitations':'Actual production create/type conversion with mocked resource and WMI boundaries. No firmware acceptance, real cleanup, event, concurrency or radio certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wlan',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); result=audit(args.wlan)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n'); print(result['status'])
