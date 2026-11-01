#!/usr/bin/env python3
"""Actions-only ordinary post-DOWN PE/peer/VDEV cleanup composite; no SSR claim."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import mishare_native_wma_start_fixture as previous
from mishare_recovery_fixture import function

owner = previous.owner
engine = previous.engine
EARLY = r'''
static bool clean_active,clean_peer_unmapped,clean_peer_deleted,clean_peer_gone,clean_dp_deferred,clean_unmap_inline,clean_flush_cap;
static unsigned clean_modes,clean_fault,clean_peer_users,clean_peer_phase,clean_peer_flushes,clean_peer_sends,clean_peer_dp_deletes,clean_obj_deletes,clean_sm_destroys;
'''
PEER = r'''
static void clean_try_peer_gone(void) {
 if(clean_peer_gone || !clean_peer_unmapped || !clean_peer_deleted || clean_peer_users)return;
 assert(ctx_reset_peer_count==1);ctx_reset_peer_count--;clean_peer_gone=true;
}
static void clean_peer_unmap(void) {
 assert(clean_active && clean_peer_dp_deletes==1 && !clean_peer_unmapped);
 clean_peer_unmapped=true;clean_try_peer_gone();
 if(clean_dp_deferred && clean_peer_gone) {clean_dp_deferred=false;finish_dp();}
}
static void *clean_get_soc(int id) {assert(clean_active && id==QDF_MODULE_ID_SOC && timers_live && !wma_context.wmi_handle->wmi_stopinprogress);return wma_context.psoc;}
static struct wlan_objmgr_peer *clean_get_peer_mac(struct wlan_objmgr_psoc *p,u8 *mac,int ref) {assert(clean_active && p==wma_context.psoc && mac && ref==WLAN_LEGACY_WMA_ID && ctx_peer_present && !clean_peer_deleted);clean_peer_users++;return &ctx_peer;}
static struct wlan_objmgr_peer *clean_get_peer(struct wlan_objmgr_psoc *p,u8 id,u8 *mac,int ref) {assert(!id);return clean_get_peer_mac(p,mac,ref);}
static void clean_release_peer(struct wlan_objmgr_peer *p,int ref) {assert(p==&ctx_peer && ref==WLAN_LEGACY_WMA_ID && clean_peer_users);clean_peer_users--;clean_try_peer_gone();}
static void clean_table_remove(struct wlan_objmgr_peer *p,bool add,void *ctx) {assert(p==&ctx_peer && !add && !ctx && !clean_peer_phase && !pe_heap_live && !pe_pending.bodyptr);clean_peer_phase=1;}
static void clean_dp_teardown(void *soc,uint8_t id,uint8_t *mac) {assert(soc==wma_context.psoc && id==7 && mac && clean_peer_phase==1 && clean_peer_users==1);clean_peer_phase=2;}
static bool clean_service(struct wmi_unified *w,int cap) {assert(w==wma_context.wmi_handle);if(cap==wmi_service_peer_delete_no_peer_flush_tids_cmd)return clean_flush_cap;return wmi_service_enabled(w,cap);}
static QDF_STATUS clean_flush_send(void *w,uint8_t *mac,struct peer_flush_params *p) {assert(w==wma_context.wmi_handle && mac && p->vdev_id==7 && !(p->peer_tid_bitmap&(1u<<WMI_MGMT_TID)) && clean_peer_phase==2 && !clean_peer_flushes);clean_peer_flushes++;return QDF_STATUS_SUCCESS;}
static QDF_STATUS clean_peer_send(void *w,uint8_t *mac,struct peer_delete_cmd_params *p) {
 assert(w==wma_context.wmi_handle && mac && p->vdev_id==7 && !p->is_mlo_link_switch && clean_peer_phase==2 && !clean_peer_sends && ctx_pending && ctx_requests==1 && wma_context.wmi_cmd_rsp_wake_lock);
 clean_peer_sends++;ctx_delete_calls++;
 if(ctx_early_reply)ctx_fw_origin(ctx_pending);
 return ctx_send_error?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static void clean_dp_delete(void *soc,uint8_t id,uint8_t *mac,uint32_t bitmap) {
 assert(soc==wma_context.psoc && id==7 && mac && clean_peer_phase==2 && clean_peer_sends==1 && !clean_peer_dp_deletes && (bitmap==1 || bitmap==2));
 clean_peer_dp_deletes++;clean_peer_phase=3;if(clean_unmap_inline)clean_peer_unmap();
}
static void clean_key_release(struct wlan_objmgr_vdev *v,uint8_t *mac) {assert(v==ctx_peer.vdev && mac && v->mlme->ext_vdev_ptr && clean_peer_phase==3 && !clean_peer_users);clean_peer_phase=4;}
static QDF_STATUS clean_obj_delete(struct wlan_objmgr_peer *p) {assert(p==&ctx_peer && clean_peer_phase==4 && clean_peer_users==1 && !clean_peer_deleted && ctx_peer_present);clean_peer_phase=5;clean_peer_deleted=true;ctx_peer_present=false;clean_obj_deletes++;clean_try_peer_gone();return QDF_STATUS_SUCCESS;}
#pragma push_macro("QDF_BUG")
#undef QDF_BUG
#define QDF_BUG(x) assert(x)
#define cds_get_context clean_get_soc
#define wma_remove_peer clean_native_remove_peer
#define wma_remove_objmgr_peer clean_native_remove_objmgr_peer
#define wlan_objmgr_get_peer_by_mac clean_get_peer_mac
#define wlan_objmgr_get_peer clean_get_peer
#define wlan_objmgr_peer_release_ref clean_release_peer
#define wlan_objmgr_peer_obj_delete clean_obj_delete
#define wma_peer_tbl_trans_add_entry clean_table_remove
#define cdp_peer_teardown clean_dp_teardown
#define cdp_peer_delete clean_dp_delete
#define wmi_service_enabled clean_service
#define wmi_unified_peer_flush_tids_send clean_flush_send
#define wmi_unified_peer_delete_send clean_peer_send
#define wlan_release_peer_key_wakelock clean_key_release
NATIVE_PEER_FUNCTIONS
#undef wlan_release_peer_key_wakelock
#undef wmi_unified_peer_delete_send
#undef wmi_unified_peer_flush_tids_send
#undef wmi_service_enabled
#undef cdp_peer_delete
#undef cdp_peer_teardown
#undef wma_peer_tbl_trans_add_entry
#undef wlan_objmgr_peer_obj_delete
#undef wlan_objmgr_peer_release_ref
#undef wlan_objmgr_get_peer
#undef wlan_objmgr_get_peer_by_mac
#undef wma_remove_objmgr_peer
#undef wma_remove_peer
#undef cds_get_context
#pragma pop_macro("QDF_BUG")
'''

FINAL = r'''
static void clean_component_sm(struct wlan_objmgr_vdev *v) {
 if(!v->mlme->sm_hdl)return;
 assert(clean_active && clean_peer_gone && !dp_objects && !stats_live && !pending_dp_cb && "EXPECTED_DP_COMPLETION_BEFORE_SM_DELETE");
 assert(!v->refs && v->dead && !pe_heap_live && !ctx_peer_present && !ctx_requests && !ctx_locks && !timers_live && !wma_context.interfaces[7].vdev && !detach_calls && !final_free_calls);
 assert(mishare_runtime_owners && !mishare_runtime_owners->events && !mishare_runtime_owners->radio && !clean_sm_destroys);
 owner_destroy(v->mlme,v->mlme->sm_hdl);owner_expected=NULL;clean_sm_destroys++;
}
static void clean_blocked(struct mishare_runtime_owner *o) {
 assert(mishare_runtime_destroy(&o)==-EUCLEAN && o && !state(o).freed && !state(o).host_delete_accepted && !clean_sm_destroys && !detach_calls && !final_free_calls && engine_allocations==1);
}
static void clean_end(struct mishare_runtime_owner **o) {
 clean_active=true;ctx_early_reply=clean_modes&1;clean_unmap_inline=clean_modes&2;early_dp=clean_modes&4;clean_flush_cap=clean_modes&8;early_delete=clean_modes&16;
 assert(*o && !(*o)->radio && state(*o).radio.down_accepted && state(*o).radio.phase==MISHARE_RADIO_DOWN && ch_state==WLAN_VDEV_S_INIT && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt);
 assert(pe_pending.bodyptr && pe_heap_live && ctx_peer_present && objects_live && dp_objects && engine_allocations==1);
 if(clean_fault==1) {run_pe(true);clean_blocked(*o);assert(pe_heap_live && !clean_peer_sends && !wire_deletes && !dp_detaches);return;}
 run_pe(false);assert(!pe_heap_live && !pe_pending.bodyptr && pe_deletes==1 && state(*o).ndi.pe_delete_completed);
 if(clean_fault==2)ctx_send_error=true;
 int ret=mishare_runtime_destroy(o);
 if(clean_fault==2) {
  assert(ret==-EUCLEAN && clean_peer_sends==1 && ctx_pending);ctx_fw_origin(ctx_pending);clean_blocked(*o);
  assert(!wire_deletes && !dp_detaches && dp_objects && wma_context.interfaces[7].vdev && last_vdev->mlme->ext_vdev_ptr);return;
 }
 assert(ret==-EINPROGRESS && clean_peer_sends==1 && clean_peer_dp_deletes==1 && clean_obj_deletes==1 && clean_peer_phase==5 && !clean_peer_users && !ctx_peer_present && !wire_deletes && !dp_detaches);
 assert(clean_peer_flushes==(clean_flush_cap?0u:1u) && !reset_force_detaches && !reset_obj_deletes && !reset_wmi_calls);
 if(clean_fault==3) {assert(ctx_pending);ctx_timeout_origin(ctx_pending);clean_blocked(*o);assert(!wire_deletes && !dp_detaches);return;}
 if(!ctx_early_reply) {
  assert(ctx_pending && !state(*o).ndi.peer_delete_replied);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !wire_deletes && !dp_detaches && "EXPECTED_PEER_ACK_BEFORE_VDEV_DELETE");
  ctx_fw_origin(ctx_pending);
 }
 assert(state(*o).ndi.peer_delete_replied && !ctx_pending && !ctx_requests && !wma_context.wmi_cmd_rsp_wake_lock && ctx_dp_acks==1);
 if(clean_fault==4)delete_timeout=true;
 ret=mishare_runtime_destroy(o);
 if(clean_fault==4) {assert(ret==-EUCLEAN);clean_blocked(*o);assert(wire_deletes==1 && !dp_detaches);return;}
 assert(ret==-EINPROGRESS && wire_deletes==1 && !dp_detaches && !delete_calls);
 if(!early_delete) {
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !dp_detaches && !delete_calls);reply();
 }
 assert(state(*o).ndi.delete_replied && !timers_live && pm_releases==1);
 if(clean_fault==5)dp_detach_status=QDF_STATUS_E_FAILURE;
 ret=mishare_runtime_destroy(o);
 if(clean_fault==5) {assert(ret==-EUCLEAN);clean_blocked(*o);assert(dp_detaches==1 && dp_objects && stats_live && !pending_dp_cb);return;}
 assert(ret==-EINPROGRESS && dp_detaches==1 && !delete_calls && engine_allocations==1);
 if(!clean_peer_gone) {
  assert(clean_peer_deleted && !clean_peer_unmapped && ctx_reset_peer_count==1 && pending_dp_cb);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !delete_calls && engine_allocations==1 && "EXPECTED_DP_COMPLETION_BEFORE_SM_DELETE");
  clean_peer_unmap();
 }
 if(pending_dp_cb)finish_dp();
 assert(clean_peer_gone && !ctx_reset_peer_count && !dp_objects && !stats_live && !pending_dp_cb && state(*o).ndi.dp_freed && engine_allocations==1);
 struct wlan_objmgr_vdev *held=last_vdev;
 bool hold=clean_modes&8;
 if(hold)assert(wlan_objmgr_vdev_try_get_ref(held,WLAN_HDD_ID_OBJ_MGR)==QDF_STATUS_SUCCESS);
 if(clean_fault==6)delete_fail=true;
 ret=mishare_runtime_destroy(o);
 if(clean_fault==6) {assert(ret==-EUCLEAN);clean_blocked(*o);assert(!dp_objects && !ctx_locks && !wma_context.interfaces[7].vdev && !last_vdev->mlme->ext_vdev_ptr);return;}
 if(hold) {
  assert(ret==-EINPROGRESS && *o && state(*o).host_delete_accepted && state(*o).draining && !state(*o).freed && !clean_sm_destroys && !detach_calls && !final_free_calls && engine_allocations==1);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !clean_sm_destroys && engine_allocations==1);
  wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);assert(!mishare_runtime_destroy(o));
 } else assert(!ret);
 assert(!*o && !mishare_runtime_owners && !mishare_event_owners && !last_vdev && !objects_live && !allocations && !ctx_locks && !pe_request_allocs && !pe_heap_live && !dp_objects && !stats_live && !engine_allocations && !owner_dump_live && !owner_sm_live && !owner_mutex_live);
 assert(clean_sm_destroys==1 && detach_calls==2 && final_free_calls==1 && wire_deletes==1 && dp_detaches==1 && stats_resets==1 && !clean_dp_deferred);
 assert(!mishare_runtime_destroy(o) && clean_sm_destroys==1 && final_free_calls==1);
}
static void clean_extra_cases(void) {
 for(unsigned mode=0;mode<32;mode++) {pid_t child=fork();assert(child>=0);if(!child) {clean_modes=mode;engine_cycle(5240,false,0);_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
 for(unsigned fault=1;fault<=6;fault++) {pid_t child=fork();assert(child>=0);if(!child) {clean_fault=fault;engine_cycle(5240,false,0);_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
}
'''


def fixture(root):
    source, exits, stubbed = previous.fixture(root)
    source = owner.replace_once(source, 'static void finish_dp(void) {', EARLY + '\nstatic void finish_dp(void) {\n if(clean_active && !clean_peer_gone) {clean_dp_deferred=true;return;}')
    native = '\n'.join(function((root / previous.WMA).read_text(), name) for name in ['wma_remove_objmgr_peer', 'wma_remove_peer'])
    delete = function(source, 'mishare_ndi_self_peer_delete')
    block = PEER.replace('NATIVE_PEER_FUNCTIONS', native)
    replacement = block + '\n#define wma_remove_peer clean_native_remove_peer\n' + delete + '\n#undef wma_remove_peer\n'
    source = owner.replace_once(source, delete, replacement)
    source = owner.replace_once(source, 'static void simulated_component_destroy(struct wlan_objmgr_vdev *v) {', 'static void clean_component_sm(struct wlan_objmgr_vdev *);\nstatic void simulated_component_destroy(struct wlan_objmgr_vdev *v) {')
    source = owner.replace_once(source, 'if(v->mlme){free(v->mlme);', 'if(v->mlme){clean_component_sm(v);free(v->mlme);')
    # Definitions follow the owner helper and precede the lifecycle cycle.
    component = FINAL[:FINAL.index('static void clean_extra_cases')]
    source = owner.replace_once(source, 'static void engine_cycle(', component + '\nstatic void engine_cycle(')
    cycle = function(source, 'engine_cycle')
    tail = 'owner_destroy(last_vdev->mlme,s);last_vdev->mlme->sm_hdl=NULL;assert(!engine_allocations);'
    changed = owner.replace_once(cycle, tail, 'clean_end(&o);')
    source = owner.replace_once(source, cycle, changed)
    extra = FINAL[FINAL.index('static void clean_extra_cases'):]
    main = function(source, 'main')
    changed = owner.replace_once(main, 'post_extra_cases();', 'post_extra_cases();clean_extra_cases();')
    source = owner.replace_once(source, main, extra + '\n' + changed)
    return source, exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    previous.negative_controls(directory, c_file, command, env, source, root)
    executable = directory / 'engine'
    target = owner.replace_once(source, function(source, 'main'), 'int main(void) {engine_cycle(5240,false,0);_Exit(0);}')
    runtime = (engine.ROOT / 'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    override = directory / 'wlan_hdd_mishare_runtime.c'
    c_file.write_text(target)
    subprocess.run(command, check=True)
    subprocess.run([executable], check=True, timeout=45, env=env)
    controls = [
        ('if (ndi->peer_created && (!ndi->peer_delete_submitted ||\n                              !ndi->peer_delete_replied)) {', 'EXPECTED_PEER_ACK_BEFORE_VDEV_DELETE'),
        ('if (ndi->create.dp_attached && !ndi->dp_freed) {', 'EXPECTED_DP_COMPLETION_BEFORE_SM_DELETE'),
    ]
    try:
        for needle, marker in controls:
            override.write_text(owner.replace_once(runtime, needle, 'if (false) { /* negative: bypass ordinary completion gate */'))
            subprocess.run(command, check=True)
            bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
            assert bad.returncode == -6 and marker in bad.stderr
    finally:
        override.unlink(missing_ok=True)


def audit(root):
    report = engine.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    report['base_engine_status'] = report['status']
    report['status'] = 'MISHARE_NATIVE_ORDINARY_CLEANUP_FIXTURE_PASS_ONLY'
    report['native_peer_cleanup_function_sha256'] = {name: hashlib.sha256(function((root / previous.WMA).read_text(), name).encode()).hexdigest() for name in ['wma_remove_peer', 'wma_remove_objmgr_peer']}
    report['native_owned_peer_delete_sha256'] = hashlib.sha256(function((root / previous.WMA).read_text(), 'mishare_ndi_self_peer_delete').encode()).hexdigest()
    report['ordinary_peer_cleanup_alias'] = 'Native bodies compiled again under clean_native_* names with separate ordinary endpoint models; SSR/no-FW instance unchanged.'
    for name in ['missing_native_SM_free', 'hidden_native_allocation_failure', 'missing_PAS_START_binding', 'hidden_native_callback_error', 'missing_native_BSS_channel_copy', 'missing_native_PAS_DP_MAC_update', 'missing_peer_ACK_gate', 'missing_DP_completion_gate']:
        report['negative_control_' + name + '_rejected'] = True
    report['checks'] = [s.replace('unchanged native transition/deliver bridges and 0081 selected native handlers plus native exit functions', 'native transition/entry/event/exit bodies with the explicit 0085 WMA delivery probe') for s in report['checks']]
    report['checks'] += [
        '0085 full WMA/SM lifecycle continues through native PE destructor and ordinary native WMA peer remove and object-peer remove bodies',
        'normal peer DELETE transport and reply/timeout origins; no SSR force detach or no-FW peer deletion reused',
        '32 serialized callback/reference cases: inline/deferred peer ACK, peer unmap, DP VDEV callback, external final-free ref and VDEV DELETE ACK; both flush-service branches covered',
        'DP VDEV callback held by the platform model until peer unmap/logical deletion completes; controller waits through real production completion gates',
        'native SM destroy runs from a modeled component destructor at VDEV zero-ref, before native parent detach/storage free and runtime final notification',
        'six failure cases retain the unfinished remainder: PE flush, peer send error plus late ACK, peer timeout, VDEV timeout, DP detach rejection, host-delete rejection',
        'all previous nine negatives plus production peer-ACK and DP-completion gate removal are caught',
    ]
    report['limitations'] = (
        'Normal complete cleanup composite executes production owner, native PE destructor, ordinary native WMA peer remove/object-peer helper, DELETE/DP wrappers, native SM create/destroy and native VDEV storage free. '
        'Peer object references/logical delete/unmap, DP teardown/callback, WMI transport, component destructor caller, locks and physical parent lists remain platform models. '
        'The model deliberately gates DP VDEV final completion on peer unmap; no real DP/peer object-manager destructor graph or hardware completion ordering is certified. '
        'External VDEV refs are explicit test-held references; original pdev/psoc are retained by the harness, not an automatic native parent lease/coordinator. '
        'Inline/deferred cases are serialized model interleavings, not real QDF workers/concurrent teardown. Failure children preserve remaining resources until process exit. '
        '0085 WMA context/config/DP/policy models, delivery probe, two validation/down table probes and inactive legacy conditional branches retain their prior boundaries. '
        'No active START/UP SSR recovery, safe module unload, backend activation, phone/firmware/RF or AirDrop certification.'
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
