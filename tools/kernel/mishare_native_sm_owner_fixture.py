#!/usr/bin/env python3
"""Execute pinned native MLME SM create/destroy around the 0082 engine model."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import mishare_native_engine_fixture as previous
from mishare_recovery_fixture import function

EARLY = r'''
static bool owner_fail_next,owner_sm_live,owner_mutex_live,owner_dump_live;
static unsigned owner_trace,owner_free_calls,owner_free_before;
static struct vdev_mlme_obj *owner_expected;
'''

PLATFORM = r'''
#ifndef QDF_ARRAY_SIZE
#define QDF_ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#endif
#define qdf_scnprintf(buf,n,...) snprintf((char *)(buf),n,__VA_ARGS__)
#ifndef mlme_err
#define mlme_err(...) engine_log(__VA_ARGS__)
#endif
#define WLAN_MD_OBJMGR_VDEV_SM 1
static void wlan_minidump_log(void *p,size_t n,struct wlan_objmgr_psoc *psoc,unsigned type,const char *name) {
 assert(owner_expected && p==owner_expected->sm_hdl && n==sizeof(struct wlan_sm));
 assert(psoc==wlan_vdev_get_psoc(owner_expected->vdev) && type==WLAN_MD_OBJMGR_VDEV_SM && !strcmp(name,"wlan_sm"));
 assert(!owner_trace && !owner_dump_live && !owner_sm_live && !owner_mutex_live && engine_allocations==1);
 owner_dump_live=true;owner_trace=1;
}
static void mlme_vdev_sm_spinlock_create(struct vdev_mlme_obj *m) {
 assert(m==owner_expected && owner_trace==1 && owner_dump_live && !owner_sm_live);
 owner_sm_live=true;owner_trace=12;
}
static void mlme_vdev_cmd_mutex_create(struct vdev_mlme_obj *m) {
 assert(m==owner_expected && owner_trace==12 && owner_sm_live && !owner_mutex_live);
 owner_mutex_live=true;owner_trace=123;
}
static void mlme_vdev_cmd_mutex_destroy(struct vdev_mlme_obj *m) {
 assert(m==owner_expected && owner_trace==123 && owner_mutex_live && owner_sm_live && !sm_depth);
 owner_mutex_live=false;owner_trace=1234;
}
static void mlme_vdev_sm_spinlock_destroy(struct vdev_mlme_obj *m) {
 assert(m==owner_expected && owner_trace==1234 && !owner_mutex_live && owner_sm_live && !sm_depth);
 owner_sm_live=false;owner_trace=12345;
}
static void wlan_minidump_remove(void *p,size_t n,struct wlan_objmgr_psoc *psoc,unsigned type,const char *name) {
 assert(owner_expected && p==owner_expected->sm_hdl && n==sizeof(struct wlan_sm));
 assert(psoc==wlan_vdev_get_psoc(owner_expected->vdev) && type==WLAN_MD_OBJMGR_VDEV_SM && !strcmp(name,"wlan_sm"));
 assert(owner_trace==12345 && owner_dump_live && !owner_sm_live && !owner_mutex_live && engine_allocations==1);
 owner_dump_live=false;owner_trace=123456;
}
NATIVE_WRAPPERS
static void owner_arm(struct vdev_mlme_obj *m) {
 assert(!engine_allocations && !owner_dump_live && !owner_sm_live && !owner_mutex_live && !m->sm_hdl);
 owner_expected=m;owner_trace=0;owner_free_before=owner_free_calls;
}
static void owner_created(struct vdev_mlme_obj *m,unsigned initial_substate) {
 char expected[WLAN_SM_ENGINE_MAX_NAME];snprintf(expected,sizeof(expected),"VM-%d",wlan_vdev_get_id(m->vdev));
 assert(owner_expected==m && owner_trace==123 && owner_dump_live && owner_sm_live && owner_mutex_live && engine_allocations==1);
 assert(m->sm_hdl && m->sm_hdl->ctx==m && !strcmp((char *)m->sm_hdl->name,expected));
 assert(m->sm_hdl->cur_state==WLAN_VDEV_S_INIT && ch_state==WLAN_VDEV_S_INIT && radio_native_substate==initial_substate && !sm_depth);
}
static void owner_destroy(struct vdev_mlme_obj *m,struct wlan_sm *s) {
 assert(m==owner_expected && m->sm_hdl==s && !sm_depth);
 assert(mlme_vdev_sm_destroy(m)==QDF_STATUS_SUCCESS);
 assert(!engine_allocations && owner_free_calls==owner_free_before+1 && "EXPECTED_NATIVE_SM_OWNER_FREE");
 assert(owner_trace==123456 && !owner_dump_live && !owner_sm_live && !owner_mutex_live);
 /* The native wrapper does not clear the parent field. Only fixture bookkeeping
  * clears it here, after checking the actual wrapper's free and ordering. */
 m->sm_hdl=NULL;
}
static void owner_contract(void) {
 reset_pe_test();radio_native_substate=0;
 struct mishare_runtime_owner *o=queued_start_owner(5240);assert(o);
 struct vdev_mlme_obj *m=last_vdev->mlme;
 owner_arm(m);owner_fail_next=true;
 assert(mlme_vdev_sm_create(m)==QDF_STATUS_E_FAILURE && "EXPECTED_NATIVE_CREATE_FAILURE");
 assert(!owner_fail_next && !m->sm_hdl && !engine_allocations && !owner_trace && !owner_sm_live && !owner_mutex_live && !owner_dump_live && owner_free_calls==owner_free_before);
 assert(ch_state==WLAN_VDEV_S_INIT && radio_native_substate==0 && !radio_starts && !radio_timer && !sm_depth);
 /* Real wrapper create/destroy can be repeated once the fixture-owned parent
  * field has been cleared; the native wrapper itself is not idempotent. */
 for(unsigned cycle=0;cycle<3;cycle++) {
  owner_arm(m);assert(mlme_vdev_sm_create(m)==QDF_STATUS_SUCCESS);owner_created(m,0);
  owner_destroy(m,m->sm_hdl);
 }
}
'''


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Unexpected native owner fixture anchor: ' + before[:90])
    return source.replace(before, after, 1)


def fixture(root):
    source, exits, stubbed = previous.fixture(root)
    sm = (root / previous.SM).read_text()
    wrappers = '\n'.join(function(sm, n) for n in ['mlme_vdev_sm_create', 'mlme_vdev_sm_destroy'])
    source = replace_once(source, 'static unsigned engine_allocations;', EARLY + '\nstatic unsigned engine_allocations;')
    source = replace_once(source, 'static void *engine_mem_malloc(size_t n) {void *p=calloc(1,n);', 'static void *engine_mem_malloc(size_t n) {if(owner_fail_next) {owner_fail_next=false;return NULL;}void *p=calloc(1,n);')
    source = replace_once(source, 'engine_allocations--;free(p);', 'engine_allocations--;owner_free_calls++;free(p);')
    # Insert after all original tables and native handlers, before the harness.
    marker = function(source, 'attach_engine')
    attach = r'''static struct wlan_sm *attach_engine(struct mishare_runtime_owner *o) {
 struct vdev_mlme_obj *m=last_vdev->mlme;assert(o && !m->sm_hdl && ch_state==WLAN_VDEV_S_INIT && (radio_native_substate==0 || radio_native_substate==WLAN_VDEV_SS_IDLE));
 owner_arm(m);assert(mlme_vdev_sm_create(m)==QDF_STATUS_SUCCESS);owner_created(m,radio_native_substate);
 m->ops=&engine_exit_ops;native_full=true;return m->sm_hdl;
}'''
    source = replace_once(source, marker, PLATFORM.replace('NATIVE_WRAPPERS', wrappers) + '\n' + attach)
    for name in ['engine_cycle', 'engine_init_rejection', 'engine_drift_rejected']:
        body = function(source, name)
        changed = replace_once(body, 'wlan_sm_delete(s);', 'owner_destroy(last_vdev->mlme,s);')
        source = replace_once(source, body, changed)
    main = function(source, 'main')
    changed = replace_once(main, 'engine_contract();', 'engine_contract();\n pid_t owner_child=fork();assert(owner_child>=0);if(!owner_child) {owner_contract();_Exit(0);}int owner_status;assert(waitpid(owner_child,&owner_status,0)==owner_child && WIFEXITED(owner_status) && !WEXITSTATUS(owner_status));')
    source = replace_once(source, main, changed)
    return source, exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    executable = directory / 'engine'
    target = replace_once(source, function(source, 'main'), 'int main(void) {owner_contract();_Exit(0);}')
    c_file.write_text(target)
    subprocess.run(command, check=True)
    subprocess.run([executable], check=True, timeout=45, env=env)
    destroy = function(target, 'mlme_vdev_sm_destroy')
    changed = replace_once(destroy, 'wlan_sm_delete(vdev_mlme->sm_hdl);', '/* negative: omit actual SM release */')
    c_file.write_text(replace_once(target, destroy, changed))
    subprocess.run(command, check=True)
    bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
    assert bad.returncode == -6 and 'EXPECTED_NATIVE_SM_OWNER_FREE' in bad.stderr
    create = function(target, 'mlme_vdev_sm_create')
    changed = replace_once(create, 'return QDF_STATUS_E_FAILURE;', 'return QDF_STATUS_SUCCESS; /* negative: hide allocation failure */')
    c_file.write_text(replace_once(target, create, changed))
    subprocess.run(command, check=True)
    bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
    assert bad.returncode == -6 and 'EXPECTED_NATIVE_CREATE_FAILURE' in bad.stderr


def audit(root):
    result = previous.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    result['base_engine_status'] = result['status']
    result['status'] = 'MISHARE_NATIVE_SM_OWNER_FIXTURE_PASS_ONLY'
    sm = (root / previous.SM).read_text()
    result['native_owner_wrapper_sha256'] = {
        name: hashlib.sha256(function(sm, name).encode()).hexdigest()
        for name in ['mlme_vdev_sm_create', 'mlme_vdev_sm_destroy']
    }
    result['negative_control_missing_native_SM_free_rejected'] = True
    result['negative_control_hidden_native_allocation_failure_rejected'] = True
    result['checks'] += [
        'unchanged native MLME SM create/destroy wrappers execute around all eight original lifecycle combinations and held-resource/drift cases',
        'failed engine allocation propagates failure without handle publication, minidump, lock setup, or native state entry',
        'native VM-id naming, engine context/state, minidump registration before lock setup and mutex/spinlock/minidump teardown before engine free',
        'three successive create/destroy pairs with exactly one engine free each; fixture explicitly clears parent handle after native destroy',
        'two owner negative controls plus the three original engine/substate negative controls are rejected',
    ]
    result['limitations'] = (
        'Executes unchanged pinned native MLME SM create/destroy wrapper bodies and the 0082 generic engine composite. '
        'Lock create/destroy, minidump registration/removal, allocator failure and object-parent bookkeeping remain instrumented platform models; '
        'no real QDF lock/minidump implementation or concurrent lock teardown is executed. The fixture, not the native destroy wrapper, clears the parent handle. '
        'Native object-manager create/destroy callers, callback adapters, full WMA postprocessing, physical DP/peer lifecycle and parent coordinator remain outside this composite. '
        'Unused native handlers still abort. Ordinary physical peer/PE cleanup after queued deletion remains outside this composite. '
        'No active START/UP SSR recovery, automatic shutdown, backend activation, phone/firmware/RF or AirDrop proof.'
    )
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.wlan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
