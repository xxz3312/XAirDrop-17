#!/usr/bin/env python3
"""Actions-only native VDEV destroy dispatcher and MLME component destructor."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import mishare_native_cleanup_fixture as previous
from mishare_recovery_fixture import function

owner = previous.owner
engine = previous.engine
OBJECT = 'qca-wifi-host-cmn/umac/cmn_services/obj_mgr/src/wlan_objmgr_vdev_obj.c'
MLME = 'qca-wifi-host-cmn/umac/mlme/mlme_objmgr/dispatcher/src/wlan_vdev_mlme_main.c'
COMMON = 'qca-wifi-host-cmn/umac/cmn_services/inc/wlan_cmn.h'
STATE = 'qca-wifi-host-cmn/umac/cmn_services/obj_mgr/inc/wlan_objmgr_cmn.h'
NAMES = ['wlan_objmgr_vdev_object_status', 'wlan_objmgr_vdev_component_obj_detach', 'wlan_objmgr_vdev_obj_destroy']

SUPPORT = r'''
#define QDF_STATUS_COMP_ASYNC 101
#define QDF_STATUS_MAXCOMP_FAIL 102
#define WLAN_VDEV_OP 2
#define WLAN_MD_OBJMGR_VDEV 201
#define WLAN_MD_OBJMGR_VDEV_MLME 202
static void obj_log(const char *fmt,...) {(void)fmt;}
#define obj_mgr_debug obj_log
#define obj_mgr_alert obj_log
#define mlme_err(...) ((void)0)
typedef QDF_STATUS (*wlan_objmgr_vdev_destroy_handler)(struct wlan_objmgr_vdev *,void *);
static struct {wlan_objmgr_vdev_destroy_handler vdev_destroy_handler[WLAN_UMAC_MAX_COMPONENTS];void *vdev_destroy_handler_arg[WLAN_UMAC_MAX_COMPONENTS];} obj_handlers,*g_umac_glb_obj=&obj_handlers;
static unsigned obj_mode,obj_prefix,obj_phase,obj_bug_count,obj_dispatch_calls,obj_free_attempts;
static void *obj_async_context;
static int obj_bad_pointer;
static QDF_STATUS obj_dispatch_result;
static QDF_STATUS wlan_objmgr_vdev_component_obj_detach(struct wlan_objmgr_vdev *,enum wlan_umac_comp_id,void *);
static void obj_bug(int condition) {assert(!condition && (obj_mode==2 || obj_mode==4));obj_bug_count++;}
static void wlan_objmgr_notify_destroy(struct wlan_objmgr_vdev *v,unsigned kind) {
 assert(v==last_vdev && kind==WLAN_VDEV_OP && clean_active && !v->refs && v->dead && !v->vdev_lock && !pending_dp_cb && clean_peer_gone && !obj_prefix && "EXPECTED_DP_COMPLETION_BEFORE_SM_DELETE");
 obj_prefix=1;
}
static QDF_STATUS wlan_objmgr_vdev_mlo_dev_ctxt_detach(struct wlan_objmgr_vdev *v) {assert(v==last_vdev && obj_prefix==2 && !obj_phase);obj_prefix=3;return obj_mode==3?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;}
static void obj_minidump_remove(void *p,size_t n,struct wlan_objmgr_psoc *parent,unsigned kind,const char *name) {
 assert(parent==&psoc);
 if(kind==WLAN_MD_OBJMGR_VDEV) {assert(p==last_vdev && n==sizeof(*last_vdev) && !strcmp(name,"wlan_objmgr_vdev") && obj_prefix==1);obj_prefix=2;return;}
 assert(kind==WLAN_MD_OBJMGR_VDEV_MLME && p==last_vdev->mlme && n==sizeof(struct vdev_mlme_obj) && !strcmp(name,"vdev_mlme") && obj_phase==7);obj_phase=8;
}
static void obj_timer_free(int *timer) {assert(last_vdev && timer==&last_vdev->mlme->ml_reconfig_timer && *timer==1 && obj_phase==2 && "EXPECTED_NATIVE_REVERSE_COMPONENT_ORDER");*timer=0;obj_phase=3;}
static void wlan_cm_deinit(struct vdev_mlme_obj *m) {assert(m==last_vdev->mlme && obj_phase==3);obj_phase=4;}
static QDF_STATUS obj_sm_destroy(struct vdev_mlme_obj *m) {assert(m==last_vdev->mlme && obj_phase==4);clean_component_sm(m->vdev);obj_phase=5;return QDF_STATUS_SUCCESS;}
static QDF_STATUS mlme_vdev_ops_ext_hdl_destroy(struct vdev_mlme_obj *m) {assert(m==last_vdev->mlme && !m->ext_vdev_ptr && !engine_allocations && obj_phase==5 && "EXPECTED_NATIVE_MLME_SM_DESTROY");obj_phase=6;return QDF_STATUS_SUCCESS;}
static QDF_STATUS obj_mlme_detach(struct wlan_objmgr_vdev *v,enum wlan_umac_comp_id id,void *p) {
 assert(v==last_vdev && id==WLAN_UMAC_COMP_MLME && p==v->mlme && obj_phase==6);
 if(obj_mode==5)v->vdev_comp_priv_obj[id]=&obj_bad_pointer;
 QDF_STATUS ret=wlan_objmgr_vdev_component_obj_detach(v,id,p);assert(ret==(obj_mode==5?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS));obj_phase=7;return ret;
}
static void obj_mlme_free(void *p) {assert(p==last_vdev->mlme && obj_phase==8);free(p);last_vdev->mlme=NULL;obj_phase=9;}
static QDF_STATUS obj_storage_free(struct wlan_objmgr_vdev *v) {
 obj_free_attempts++;
 assert(!obj_async_context && "EXPECTED_NATIVE_COMPONENT_WAIT");
 if(obj_mode!=5)for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)assert(!v->vdev_comp_priv_obj[i] && v->obj_status[i]!=QDF_STATUS_E_FAILURE && "EXPECTED_NATIVE_COMPONENT_SUCCESS");
 assert(obj_phase==9 && !v->mlme && clean_sm_destroys==1);
 return wlan_objmgr_vdev_obj_free(v);
}
#pragma push_macro("QDF_BUG")
#undef QDF_BUG
#define QDF_BUG(x) obj_bug(x)
#define WLAN_OBJMGR_BUG(x) obj_bug(x)
#define wlan_minidump_remove obj_minidump_remove
#define wlan_objmgr_vdev_obj_free obj_storage_free
NATIVE_OBJECT_FUNCTIONS
#undef wlan_objmgr_vdev_obj_free
#undef wlan_minidump_remove
#undef WLAN_OBJMGR_BUG
#pragma pop_macro("QDF_BUG")
#define qdf_timer_free obj_timer_free
#define mlme_vdev_sm_destroy obj_sm_destroy
#define wlan_objmgr_vdev_component_obj_detach obj_mlme_detach
#define wlan_minidump_remove obj_minidump_remove
#define qdf_mem_free obj_mlme_free
NATIVE_MLME_DESTRUCTOR
#undef qdf_mem_free
#undef wlan_minidump_remove
#undef wlan_objmgr_vdev_component_obj_detach
#undef mlme_vdev_sm_destroy
#undef qdf_timer_free
static QDF_STATUS obj_high_handler(struct wlan_objmgr_vdev *v,void *arg) {
 unsigned id=WLAN_UMAC_COMP_ID_MAX-1;assert(arg==&obj_handlers && v==last_vdev && obj_prefix==3 && !obj_phase && "EXPECTED_NATIVE_REVERSE_COMPONENT_ORDER");obj_phase=1;
 if(obj_mode==2)return QDF_STATUS_E_FAILURE;
 void *p=v->vdev_comp_priv_obj[id];assert(p);
 if(obj_mode==1 || obj_mode==6) {obj_async_context=p;v->vdev_comp_priv_obj[id]=NULL;return QDF_STATUS_COMP_ASYNC;}
 assert(wlan_objmgr_vdev_component_obj_detach(v,id,p)==QDF_STATUS_SUCCESS);free(p);return QDF_STATUS_SUCCESS;
}
static QDF_STATUS obj_middle_handler(struct wlan_objmgr_vdev *v,void *arg) {
 assert(v==last_vdev && arg==&obj_handlers && obj_phase==1 && "EXPECTED_NATIVE_REVERSE_COMPONENT_ORDER");obj_phase=2;
 void *p=v->vdev_comp_priv_obj[WLAN_UMAC_COMP_SCAN];assert(p);assert(wlan_objmgr_vdev_component_obj_detach(v,WLAN_UMAC_COMP_SCAN,p)==QDF_STATUS_SUCCESS);free(p);return QDF_STATUS_SUCCESS;
}
static void obj_dispatch(struct wlan_objmgr_vdev *v) {
 assert(clean_active && v==last_vdev && v->mlme && v->mlme->sm_hdl && !v->refs && v->dead && !obj_dispatch_calls);obj_dispatch_calls++;
 memset(&obj_handlers,0,sizeof(obj_handlers));
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++) {assert(i==0 || !v->vdev_comp_priv_obj[i]);v->obj_status[i]=QDF_STATUS_COMP_DISABLED;}
 v->obj_status[WLAN_UMAC_COMP_MLME]=QDF_STATUS_SUCCESS;v->mlme->ml_reconfig_timer=1;
 obj_handlers.vdev_destroy_handler[WLAN_UMAC_COMP_MLME]=mlme_vdev_obj_destroy_handler;
 unsigned ids[]={WLAN_UMAC_COMP_SCAN,WLAN_UMAC_COMP_ID_MAX-1};
 for(unsigned i=0;i<2;i++) {unsigned id=ids[i];v->vdev_comp_priv_obj[id]=malloc(1);assert(v->vdev_comp_priv_obj[id]);v->obj_status[id]=QDF_STATUS_SUCCESS;obj_handlers.vdev_destroy_handler_arg[id]=&obj_handlers;}
 obj_handlers.vdev_destroy_handler[WLAN_UMAC_COMP_SCAN]=obj_middle_handler;
 obj_handlers.vdev_destroy_handler[WLAN_UMAC_COMP_ID_MAX-1]=obj_high_handler;
 if(obj_mode==4)v->obj_state=WLAN_OBJ_STATE_CREATED;
 obj_dispatch_result=wlan_objmgr_vdev_obj_destroy(v);
}
static bool obj_finish(struct mishare_runtime_owner **o,int ret,struct wlan_objmgr_vdev *held,bool hold) {
 if(hold) {
  assert(ret==-EINPROGRESS && *o && !obj_dispatch_calls && engine_allocations==1);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !obj_dispatch_calls && "EXPECTED_NATIVE_LAST_REFERENCE");
  wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);ret=mishare_runtime_destroy(o);
 }
 if(!obj_mode) {assert(!ret && !*o && obj_dispatch_result==QDF_STATUS_SUCCESS && obj_phase==9 && obj_free_attempts==1 && !obj_bug_count);return true;}
 assert(*o && state(*o).host_delete_accepted && !state(*o).freed && !detach_calls && !final_free_calls && objects_live==1 && !last_vdev->refs && last_vdev->dead && obj_dispatch_calls==1);
 if(obj_mode==1 || obj_mode==6) {
  assert(ret==-EINPROGRESS && obj_dispatch_result==QDF_STATUS_COMP_ASYNC && last_vdev->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED && obj_async_context && obj_phase==9 && !engine_allocations && !obj_free_attempts && !obj_bug_count);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !obj_free_attempts && obj_dispatch_calls==1);
  unsigned id=WLAN_UMAC_COMP_ID_MAX-1;
  if(obj_mode==6) {assert(wlan_objmgr_vdev_component_obj_detach(last_vdev,id,&obj_bad_pointer)==QDF_STATUS_E_FAILURE);assert(last_vdev->obj_status[id]==QDF_STATUS_E_FAILURE && last_vdev->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED && obj_async_context && !obj_free_attempts);assert(mishare_runtime_destroy(o)==-EINPROGRESS);return false;}
  struct wlan_objmgr_vdev *v=last_vdev;void *p=obj_async_context;obj_async_context=NULL;free(p);
  assert(wlan_objmgr_vdev_component_obj_detach(v,id,NULL)==QDF_STATUS_SUCCESS);
  assert(!mishare_runtime_destroy(o) && !*o && !objects_live && !engine_allocations && obj_free_attempts==1 && obj_phase==9);return true;
 }
 if(obj_mode==2)assert(ret==-EINPROGRESS && obj_dispatch_result==QDF_STATUS_E_FAILURE && obj_bug_count==1 && obj_phase==9 && !engine_allocations && !obj_free_attempts && last_vdev->vdev_comp_priv_obj[WLAN_UMAC_COMP_ID_MAX-1]);
 if(obj_mode==3)assert(ret==-EINPROGRESS && obj_dispatch_result==QDF_STATUS_E_FAILURE && !obj_bug_count && obj_prefix==3 && !obj_phase && engine_allocations==1 && !obj_free_attempts);
 if(obj_mode==4)assert(ret==-EINPROGRESS && obj_dispatch_result==QDF_STATUS_E_FAILURE && obj_bug_count==1 && obj_prefix==1 && !obj_phase && engine_allocations==1 && !obj_free_attempts);
 if(obj_mode==5)assert(ret==-EUCLEAN && obj_dispatch_result==QDF_STATUS_E_BUSY && !obj_bug_count && obj_phase==9 && !engine_allocations && obj_free_attempts==1 && state(*o).blocked && last_vdev->vdev_comp_priv_obj[0]==&obj_bad_pointer);
 assert(mishare_runtime_destroy(o)==ret && !detach_calls && !final_free_calls && obj_dispatch_calls==1);return false;
}
'''

EXTRA = r'''
static void obj_contract(void) {
 struct wlan_objmgr_vdev v={0};struct wlan_objmgr_pdev p={0};struct vdev_mlme_obj m={0};v.pdev=&p;
 assert(mlme_vdev_obj_destroy_handler(NULL,NULL)==QDF_STATUS_E_FAILURE);
 assert(mlme_vdev_obj_destroy_handler(&v,NULL)==QDF_STATUS_SUCCESS);
 v.mlme=&m;assert(mlme_vdev_obj_destroy_handler(&v,NULL)==QDF_STATUS_SUCCESS);v.mlme=NULL;
 assert(wlan_objmgr_vdev_obj_destroy(NULL)==QDF_STATUS_E_FAILURE && wlan_objmgr_vdev_obj_destroy(&v)==QDF_STATUS_E_FAILURE);
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)v.obj_status[i]=QDF_STATUS_COMP_DISABLED;
 assert(wlan_objmgr_vdev_object_status(&v)==QDF_STATUS_SUCCESS);
 v.obj_status[0]=QDF_STATUS_COMP_ASYNC;assert(wlan_objmgr_vdev_object_status(&v)==QDF_STATUS_COMP_ASYNC);
 v.vdev_comp_priv_obj[0]=&m;assert(wlan_objmgr_vdev_object_status(&v)==QDF_STATUS_SUCCESS);
 v.obj_status[0]=QDF_STATUS_E_NOMEM;assert(wlan_objmgr_vdev_object_status(&v)==QDF_STATUS_E_FAILURE);
 v.obj_status[0]=QDF_STATUS_E_FAILURE;assert(wlan_objmgr_vdev_object_status(&v)==QDF_STATUS_E_FAILURE);
 v.obj_status[0]=QDF_STATUS_E_INVAL;assert(wlan_objmgr_vdev_object_status(&v)==QDF_STATUS_SUCCESS);
 assert(wlan_objmgr_vdev_component_obj_detach(&v,WLAN_UMAC_COMP_ID_MAX,NULL)==QDF_STATUS_MAXCOMP_FAIL);
 assert(wlan_objmgr_vdev_component_obj_detach(&v,WLAN_UMAC_COMP_MLME,NULL)==QDF_STATUS_E_FAILURE && v.vdev_comp_priv_obj[0]==&m);
 v.obj_state=WLAN_OBJ_STATE_LOGICALLY_DELETED;
 assert(wlan_objmgr_vdev_component_obj_detach(&v,WLAN_UMAC_COMP_MLME,&m)==QDF_STATUS_SUCCESS && !v.vdev_comp_priv_obj[0] && v.obj_status[0]==QDF_STATUS_SUCCESS);
}
static void obj_extra_cases(void) {
 for(unsigned mode=1;mode<=6;mode++)for(unsigned hold=0;hold<2;hold++) {pid_t c=fork();assert(c>=0);if(!c) {obj_mode=mode;clean_modes=hold?8:0;engine_cycle(5240,false,0);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));}
}
'''


def fixture(root):
    source, exits, stubbed = previous.fixture(root)
    common = (root / COMMON).read_text()
    ids = re.search(r'^enum wlan_umac_comp_id \{.*?^\};', common, re.M | re.S)[0]
    states = re.search(r'^typedef enum \{\n\s*WLAN_OBJ_STATE_ALLOCATED.*?^\} WLAN_OBJ_STATE;', (root / STATE).read_text(), re.M | re.S)[0]
    source = owner.replace_once(source, '#define WLAN_UMAC_MAX_COMPONENTS 4', ids + '\n' + states + '\n#define WLAN_UMAC_MAX_COMPONENTS WLAN_UMAC_COMP_ID_MAX')
    source = owner.replace_once(source, 'struct vdev_mlme_obj { struct wlan_sm *sm_hdl;', 'struct vdev_mlme_obj { int ml_reconfig_timer;struct wlan_sm *sm_hdl;')
    source = owner.replace_once(source, 'int mode,refs,dead,vdev_lock;', 'int mode,refs,dead,vdev_lock;WLAN_OBJ_STATE obj_state;')
    source = owner.replace_once(source, 'void *vdev_comp_priv_obj[4];QDF_STATUS obj_status[4];', 'void *vdev_comp_priv_obj[WLAN_UMAC_MAX_COMPONENTS];QDF_STATUS obj_status[WLAN_UMAC_MAX_COMPONENTS];')
    source = owner.replace_once(source, 'v->dead=1;assert(v->refs>0);', 'v->dead=1;v->obj_state=WLAN_OBJ_STATE_LOGICALLY_DELETED;assert(v->refs>0);')
    body = function(source, 'simulated_component_destroy')
    source = owner.replace_once(source, body, 'static void obj_dispatch(struct wlan_objmgr_vdev *);\nstatic void simulated_component_destroy(struct wlan_objmgr_vdev *v) {obj_dispatch(v);}')
    native = '\n'.join(function((root / OBJECT).read_text(), n) for n in NAMES)
    # component detach is public in the native source; keep its declaration public.
    block = SUPPORT.replace('static QDF_STATUS wlan_objmgr_vdev_component_obj_detach(', 'QDF_STATUS wlan_objmgr_vdev_component_obj_detach(')
    block = block.replace('NATIVE_OBJECT_FUNCTIONS', native).replace('NATIVE_MLME_DESTRUCTOR', function((root / MLME).read_text(), 'mlme_vdev_obj_destroy_handler'))
    source = owner.replace_once(source, 'static void clean_end(', block + '\nstatic void clean_end(')
    start = source.index(' if(hold) {\n  assert(ret==-EINPROGRESS && *o && state(*o).host_delete_accepted', source.index('static void clean_end('))
    end = source.index(' assert(!*o && !mishare_runtime_owners', start)
    source = source[:start] + ' if(!obj_finish(o,ret,held,hold))return;\n' + source[end:]
    main = function(source, 'main')
    changed = owner.replace_once(main, 'callback_contract();', 'obj_contract();callback_contract();')
    changed = owner.replace_once(changed, 'clean_extra_cases();', 'clean_extra_cases();obj_extra_cases();')
    return owner.replace_once(source, main, EXTRA + '\n' + changed), exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    previous.negative_controls(directory, c_file, command, env, source, root)
    exe = directory / 'engine'
    controls = [
        (0, 'wlan_objmgr_vdev_obj_destroy', 'for (id = WLAN_UMAC_COMP_ID_MAX - 1; id >= 0; id--)', 'for (id = 0; id < WLAN_UMAC_COMP_ID_MAX; id++)', 'EXPECTED_NATIVE_REVERSE_COMPONENT_ORDER'),
        (1, 'wlan_objmgr_vdev_obj_destroy', 'if (obj_status == QDF_STATUS_COMP_ASYNC) {', 'if (false) {', 'EXPECTED_NATIVE_COMPONENT_WAIT'),
        (2, 'wlan_objmgr_vdev_obj_destroy', 'if (obj_status == QDF_STATUS_E_FAILURE) {', 'if (false) {', 'EXPECTED_NATIVE_COMPONENT_SUCCESS'),
        (0, 'mlme_vdev_obj_destroy_handler', 'mlme_vdev_sm_destroy(vdev_mlme);', '/* negative: omit native SM destructor caller */', 'EXPECTED_NATIVE_MLME_SM_DESTROY'),
    ]
    for mode, name, needle, mutation, marker in controls:
        target = owner.replace_once(source, function(source, 'main'), f'int main(void) {{obj_mode={mode};engine_cycle(5240,false,0);_Exit(0);}}')
        c_file.write_text(target)
        subprocess.run(command, check=True)
        subprocess.run([exe], check=True, timeout=45, env=env)
        body = function(target, name)
        c_file.write_text(owner.replace_once(target, body, owner.replace_once(body, needle, mutation)))
        subprocess.run(command, check=True)
        bad = subprocess.run([exe], capture_output=True, text=True, timeout=45, env=env)
        assert bad.returncode == -6 and marker in bad.stderr, (name, marker, bad.returncode, bad.stderr[-300:])


def audit(root):
    report = engine.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    report['base_engine_status'] = report['status']
    report['status'] = 'MISHARE_NATIVE_OBJECT_DESTRUCTOR_FIXTURE_PASS_ONLY'
    report['native_object_function_sha256'] = {name: hashlib.sha256(function((root / OBJECT).read_text(), name).encode()).hexdigest() for name in NAMES}
    report['native_component_enum_sha256'] = hashlib.sha256(re.search(r'^enum wlan_umac_comp_id \{.*?^\};', (root / COMMON).read_text(), re.M | re.S)[0].encode()).hexdigest()
    report['native_object_state_enum_sha256'] = hashlib.sha256(re.search(r'^typedef enum \{\n\s*WLAN_OBJ_STATE_ALLOCATED.*?^\} WLAN_OBJ_STATE;', (root / STATE).read_text(), re.M | re.S)[0].encode()).hexdigest()
    report['native_MLME_destructor_sha256'] = hashlib.sha256(function((root / MLME).read_text(), 'mlme_vdev_obj_destroy_handler').encode()).hexdigest()
    for name in ['missing_native_SM_free', 'hidden_native_allocation_failure', 'missing_PAS_START_binding', 'hidden_native_callback_error', 'missing_native_BSS_channel_copy', 'missing_native_PAS_DP_MAC_update', 'missing_peer_ACK_gate', 'missing_DP_completion_gate', 'forward_component_order', 'missing_component_ASYNC_gate', 'missing_component_failure_gate', 'missing_MLME_SM_destroy_caller']:
        report['negative_control_' + name + '_rejected'] = True
    report['checks'] = [
        '0086 ordinary WMA/PE/peer/DP cleanup feeds native VDEV destroy dispatcher, native component status aggregation/detach and full native MLME destroy handler',
        'complete original component ID and object-state enums; 54 native component slots with MLME plus two instrumented sentinel handlers, other handlers disabled',
        'native reverse dispatch, timer/CM/SM/ext/detach/minidump/free ordering and final native VDEV storage free; reference-release primitives and registration remain modeled',
        'previous 16 lifecycle and 3 ratemask cycles plus 32 serialized cleanup combinations, previous 6 cleanup failures and 8 WMA failures retained',
        '12 additional held/unheld cases: asynchronous component success, component failure, MLO detach rejection, wrong logical state, MLME detach mismatch, wrong asynchronous completion token',
        'native status contracts preserve ASYNC plus present pointer treated as success and unlisted status ignored; no invented aggregation semantics',
        'native MLME handler ignores detach failure; production final-free attached-pointer veto retains object and parents after SM/MLME are already freed',
        'all previous eleven negatives plus reverse dispatch, asynchronous completion gate, failed-component gate and MLME SM-destroy caller omissions rejected',
    ]
    report['limitations'] = (
        'Native VDEV destroy/status/component-detach and MLME destroy handler execute unchanged body text in the ordinary composite. '
        'VDEV logical delete, acquisition/release/reference counters, creation and handler registration remain platform models; the real release_ref/debug variants and registration init are not compiled here. '
        'Only MLME is a native registered-handler body; two other component handlers are instrumented sentinels. CM deinit, reconfiguration timer, ext-destroy endpoint, minidump, MLO detach, component objects, locks, parent lists and DP/peer graph remain models. '
        'SM caller uses an observation adapter that executes the real native wrapper through the existing owner helper and clears the parent handle only as test bookkeeping. '
        'Async sentinel saves its modeled context outside the VDEV and clears the published slot before returning COMP_ASYNC, matching the original status aggregator; completion uses native detach with a NULL published token. '
        'Controlled QDF_BUG branches count a modeled trap and return for inspection; real firmware/kernel BUG policy is not certified. Failure cases retain remaining resources until child process exit; earlier SM/component frees are not rolled back. '
        '0086 serialized DP-peer completion and 0085 WMA probe/configuration limitations remain. No physical peer destruction graph, automatic parent shutdown coordinator, active START/UP SSR recovery, backend activation, phone/firmware/RF or AirDrop certification.'
    )
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.wlan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
