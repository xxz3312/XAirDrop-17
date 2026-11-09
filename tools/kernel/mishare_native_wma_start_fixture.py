#!/usr/bin/env python3
"""Actions-only complete native WMA START-response body in the PAS composite."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import mishare_native_callbacks_fixture as callbacks
from mishare_recovery_fixture import function

owner = callbacks.owner
engine = callbacks.engine
WMA = 'qcacld-3.0/core/wma/src/wma_dev_if.c'
PUBLIC = 'qcacld-3.0/components/mlme/dispatcher/inc/wlan_mlme_public_struct.h'
POLICY = 'qcacld-3.0/components/cmn_services/policy_mgr/inc/wlan_policy_mgr_public_struct.h'
PARAM = 'qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h'
WMH = 'qcacld-3.0/core/wma/inc/wma.h'
NAMES = ['wma_get_ratemask_type', 'wma_set_and_update_mac_id',
         'wma_handle_channel_switch_resp', 'wma_vdev_start_resp_handler']

SUPPORT = r'''
NATIVE_CONFIG_TYPES
NATIVE_MAC_DEFINES
#define OL_TXRX_PDEV_ID 0
#define WMI_VDEV_RESTART_RESP_EVENT WMI_HOST_VDEV_RESTART_RESP_EVENT
#define WMI_VDEV_TYPE_AP WLAN_VDEV_MLME_TYPE_AP
#define WMI_VDEV_TYPE_STA WLAN_VDEV_MLME_TYPE_STA
#define WMI_VDEV_TYPE_MONITOR WLAN_VDEV_MLME_TYPE_MONITOR
#define WMI_VDEV_TYPE_OCB WLAN_VDEV_MLME_TYPE_OCB
#ifndef wma_debug
#define wma_debug(...) ((void)0)
#endif
#ifndef FL
#define FL(s) s
#endif
typedef struct {bool use_pdev_id;} target_resource_config;
enum vdev_assoc_type {VDEV_ASSOC,VDEV_REASSOC};
struct qdf_mac_addr {uint8_t bytes[6];};
struct config_ratemask_params {uint8_t vdev_id,type;uint32_t lower32,higher32,lower32_2,higher32_2;};
struct wlan_mlme_psoc_ext_obj {struct {struct wlan_mlme_ratemask ratemask_cfg;} cfg;};
static struct wlan_mlme_psoc_ext_obj post_mlme={.cfg={.ratemask_cfg={.type=WLAN_MLME_RATEMASK_TYPE_NO_MASK,.lower32=0x11,.higher32=0x22,.lower32_2=0x33,.higher32_2=0x44}}};
static target_resource_config post_resource;
static bool post_no_wma,post_no_mac,post_no_cfg,post_no_resource,post_no_mlme,post_invalid_wmi,post_mask_send_fail,post_drop_event;
static unsigned post_mac_writes,post_dp_updates,post_start_events,post_mask_commands,post_last_mac;
static int post_dp;
static bool wlan_vdev_mlme_is_mlo_ap(struct wlan_objmgr_vdev *);
static void *post_context(int id) {
 if(id==QDF_MODULE_ID_WMA)return post_no_wma?NULL:&wma_context;
 if(id==QDF_MODULE_ID_PE)return post_no_mac?NULL:&pe_mac;
 assert(id==QDF_MODULE_ID_SOC);return &post_dp;
}
static struct wlan_mlme_psoc_ext_obj *mlme_get_psoc_ext_obj(struct wlan_objmgr_psoc *p) {assert(p==&psoc);return post_no_cfg?NULL:&post_mlme;}
static target_resource_config *lmac_get_tgt_res_cfg(struct wlan_objmgr_psoc *p) {assert(p==&psoc);post_resource.use_pdev_id=post_use_pdev;return post_no_resource||radio_apply_fail?NULL:&post_resource;}
static struct vdev_mlme_obj *post_get_mlme(struct wlan_objmgr_vdev *v) {assert(v==last_vdev);return post_no_mlme?NULL:wlan_vdev_mlme_get_cmpt_obj(v);}
static void wlan_mlme_set_vdev_mac_id(struct wlan_objmgr_pdev *p,unsigned id,unsigned mac) {
 assert(p==&pdev && id==7 && mac==1 && !post_mac_writes && !sm_depth);
 assert(!memcmp(last_vdev->vdev_mlme.bss_chan,last_vdev->vdev_mlme.des_chan,sizeof(struct wlan_channel)) && "EXPECTED_NATIVE_WMA_CHANNEL_COPY");
 post_mac_writes++;post_last_mac=mac;
}
static void cdp_update_mac_id(void *soc,unsigned id,unsigned mac) {assert(soc==&post_dp && id==7 && mac==1 && post_mac_writes==1 && !post_dp_updates && !sm_depth);post_dp_updates++;}
static bool wma_is_vdev_in_ap_mode(tp_wma_handle w,unsigned id) {assert(w==&wma_context && id==7);return false;}
static bool wma_get_hidden_ssid_restart_in_progress(struct wma_txrx_node *n) {assert(n==&wma_context.interfaces[7]);return false;}
static bool mlme_is_chan_switch_in_progress(struct wlan_objmgr_vdev *v) {assert(v==last_vdev);return false;}
static void mlme_set_chan_switch_in_progress(struct wlan_objmgr_vdev *v,bool flag) {(void)v;(void)flag;assert(!"UNSUPPORTED_WMA_RESTART");}
static void lim_process_switch_channel_rsp(struct mac_context *m,struct vdev_start_response *r) {(void)m;(void)r;assert(!"UNSUPPORTED_WMA_RESTART");}
static void wma_peer_send_phymode(void) {assert(!"UNSUPPORTED_WMA_RESTART");}
static void wlan_objmgr_iterate_peerobj_list(struct wlan_objmgr_vdev *v,void (*fn)(void),void *arg,unsigned id) {(void)v;(void)fn;(void)arg;(void)id;assert(!"UNSUPPORTED_WMA_RESTART");}
static void wma_update_rate_flags_after_vdev_restart(tp_wma_handle w,struct wma_txrx_node *n) {(void)w;(void)n;assert(!"UNSUPPORTED_WMA_RESTART");}
static void wma_dcs_clear_vdev_starting(struct mac_context *m,unsigned id) {(void)m;(void)id;assert(!"UNSUPPORTED_WMA_AP");}
static void wma_dcs_wlan_interference_mitigation_enable(struct mac_context *m,unsigned id,struct vdev_start_response *r) {(void)m;(void)id;(void)r;assert(!"UNSUPPORTED_WMA_AP");}
static void wma_handle_hidden_ssid_restart(tp_wma_handle w,struct wma_txrx_node *n) {(void)w;(void)n;assert(!"UNSUPPORTED_WMA_AP");}
static enum vdev_assoc_type mlme_get_assoc_type(struct wlan_objmgr_vdev *v) {(void)v;assert(!"UNSUPPORTED_WMA_STA");return VDEV_ASSOC;}
static void ucfg_ocb_config_channel(struct wlan_objmgr_pdev *p) {(void)p;assert(!"UNSUPPORTED_WMA_OCB");}
static QDF_STATUS wlan_vdev_get_bss_peer_mac(struct wlan_objmgr_vdev *v,struct qdf_mac_addr *m) {(void)v;(void)m;assert(!"UNSUPPORTED_WMA_LEGACY_BSS");return QDF_STATUS_E_FAILURE;}
static void wma_vdev_start_rsp(tp_wma_handle w,struct wlan_objmgr_vdev *v,struct vdev_start_response *r) {(void)w;(void)v;(void)r;assert(!"UNSUPPORTED_WMA_LEGACY_BSS");}
static bool wma_is_vdev_up(unsigned id) {(void)id;assert(!"UNSUPPORTED_WMA_AP");return false;}
static void wma_set_sap_keepalive(tp_wma_handle w,unsigned id) {(void)w;(void)id;assert(!"UNSUPPORTED_WMA_AP");}
static int post_validate_wmi(struct wmi_unified *w) {assert(w==&wmi);return post_invalid_wmi?1:0;}
static QDF_STATUS wmi_unified_vdev_config_ratemask_cmd_send(struct wmi_unified *w,struct config_ratemask_params *r) {
 assert(w==&wmi && r->vdev_id==7 && r->type==WMI_RATEMASK_TYPE_HT && ch_state==WLAN_VDEV_S_UP && post_start_events==1 && !radio_start_pm && !radio_rt);
 assert(r->lower32==0x11 && r->higher32==0x22 && r->lower32_2==0x33 && r->higher32_2==0x44);
 post_mask_commands++;return post_mask_send_fail?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
}
static void post_observe_event(struct vdev_mlme_obj *m,uint16_t n,void *p) {
 struct vdev_start_response *r=p;
 assert(m==last_vdev->mlme && sm_depth==1 && !lock_depth && n==sizeof(r) && r && r->vdev_id==7 && !r->status && !post_start_events);
 assert(m->mgmt.generic.tx_pwrlimit==17 && m->mgmt.generic.minpower==3 && post_mac_writes==1 && post_dp_updates==1 && "EXPECTED_NATIVE_WMA_EFFECTS");
 post_start_events++;
}
#pragma push_macro("FEATURE_AP_MCC_CH_AVOIDANCE")
#undef FEATURE_AP_MCC_CH_AVOIDANCE
#define cds_get_context post_context
#define wlan_vdev_mlme_get_cmpt_obj post_get_mlme
#define wmi_validate_handle post_validate_wmi
NATIVE_WMA_FUNCTIONS
#undef wmi_validate_handle
#undef wlan_vdev_mlme_get_cmpt_obj
#undef cds_get_context
#pragma pop_macro("FEATURE_AP_MCC_CH_AVOIDANCE")
'''

CHECKS = r'''
static void post_assert_up(void) {
 assert(post_mac_writes==1 && post_dp_updates==1 && post_start_events==1 && post_last_mac==1 && "EXPECTED_NATIVE_WMA_EFFECTS");
 assert(wma_context.interfaces[7].tx_streams==2 && last_vdev->mlme->mgmt.generic.tx_pwrlimit==17 && last_vdev->mlme->mgmt.generic.minpower==3);
 assert(!memcmp(last_vdev->vdev_mlme.bss_chan,last_vdev->vdev_mlme.des_chan,sizeof(struct wlan_channel)));
 assert(post_mask_commands==(post_mlme.cfg.ratemask_cfg.type==WLAN_MLME_RATEMASK_TYPE_HT?1u:0u));
}
static void post_mapping_contract(void) {
 for(unsigned type=WLAN_MLME_RATEMASK_TYPE_CCK;type<=WLAN_MLME_RATEMASK_TYPE_HE;type++) {uint8_t fw=99;assert(wma_get_ratemask_type(type,&fw)==QDF_STATUS_SUCCESS && fw==type-1);}
 uint8_t fw=99;assert(wma_get_ratemask_type(WLAN_MLME_RATEMASK_TYPE_NO_MASK,&fw)==QDF_STATUS_E_INVAL && fw==99);
 assert(wma_get_ratemask_type(WLAN_MLME_RATEMASK_TYPE_MAX,&fw)==QDF_STATUS_E_INVAL && fw==99);
}
'''

FAULTS = r'''
static void post_fault(unsigned fault) {
 reset_pe_test();struct mishare_runtime_owner *o=queued_start_owner(5240);attach_engine(o);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && radio_starts==1);
 if(fault==0)post_no_wma=true;
 if(fault==1)post_no_mac=true;
 if(fault==2)post_no_cfg=true;
 if(fault==3)post_no_resource=true;
 if(fault==4)post_use_pdev=post_zero_pdev=true;
 if(fault==5)post_no_mlme=true;
 if(fault==6) {post_mlme.cfg.ratemask_cfg.type=WLAN_MLME_RATEMASK_TYPE_HT;post_invalid_wmi=true;}
 if(fault==7)post_drop_event=true;
 assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && o->radio && !state(o).radio.down_accepted && !radio_downs && !radio_stops && !radio_timer && !sm_depth);
 assert(post_mac_writes==(fault>=5?1u:0u) && post_dp_updates==(fault>=5?1u:0u));
 assert(post_start_events==(fault>=6?1u:0u));
 assert(state(o).radio.host_up==(fault==6));
 if(fault==6)assert(ch_state==WLAN_VDEV_S_UP && !radio_start_pm && !radio_rt && !post_mask_commands);
 else assert(ch_state==WLAN_VDEV_S_START && radio_start_pm && radio_rt);
 assert(mishare_runtime_destroy(&o)==-EUCLEAN && o->radio && pe_heap_live && ctx_peer_present && objects_live && dp_objects && !pe_deletes && !dp_detaches);
 /* Deliberately retained resources: child process scope ends without claiming
  * native recovery, physical teardown or an owner/parent destruction order. */
}
static void post_extra_cases(void) {
 for(unsigned fault=0;fault<8;fault++) {pid_t child=fork();assert(child>=0);if(!child) {post_fault(fault);_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
 for(unsigned mask=0;mask<3;mask++) {pid_t child=fork();assert(child>=0);if(!child) {
  post_mlme.cfg.ratemask_cfg.type=mask==2?WLAN_MLME_RATEMASK_TYPE_MAX:WLAN_MLME_RATEMASK_TYPE_HT;post_mask_send_fail=mask==1;
  engine_cycle(5240,false,0);_Exit(0);
 }int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
}
'''


def declared(text, tag):
    return re.search(r'(?:enum|struct) ' + tag + r'\s*\{.*?^\};', text, re.S | re.M)[0]


def native_defines(root):
    policy = (root / POLICY).read_text()
    wmh = (root / WMH).read_text()
    ops = (root / callbacks.OPS_HEADER).read_text()
    result = [re.search(r'^#define MAX_MAC \d+$', policy, re.M)[0],
              re.search(r'^#define WMA_PDEV_TO_MAC_MAP\(x\).+$', wmh, re.M)[0]]
    for name in ['AP', 'STA', 'MONITOR', 'OCB']:
        # AP is already supplied by the 0081 preparation model, at value 1.
        if name != 'AP':
            result.append(re.search(r'^#define WLAN_VDEV_MLME_TYPE_' + name + r'\s+0x\w+$', ops, re.M)[0])
    return '\n'.join(result)


def fixture(root):
    source, exits, stubbed = callbacks.fixture(root)
    wma = (root / WMA).read_text()
    config = (root / PUBLIC).read_text()
    types = '\n'.join([declared(config, 'wlan_mlme_ratemask_type'),
                       declared(config, 'wlan_mlme_ratemask'),
                       declared((root / PARAM).read_text(), 'wmi_ratemask_type')])
    native = '\n'.join(function(wma, name) for name in NAMES)
    source = owner.replace_once(source, 'reg_class_id; } generic;', 'reg_class_id,tx_pwrlimit; } generic;')
    source = owner.replace_once(source, 'void *del_staself_req;unsigned peer_count;};', 'void *del_staself_req;unsigned peer_count,tx_streams,aid;};')
    source = owner.replace_once(source, 'struct wma {struct wlan_objmgr_psoc *psoc;', 'struct wma {struct wlan_objmgr_psoc *psoc;struct wlan_objmgr_pdev *pdev;struct mac_context *mac_context;')
    source = owner.replace_once(source, 'wma_context.psoc=&psoc;', 'wma_context.psoc=&psoc;wma_context.pdev=&pdev;wma_context.mac_context=&pe_mac;')
    source = owner.replace_once(source, 'v->vdev_mlme.bss_chan=malloc(1);', 'v->vdev_mlme.bss_chan=calloc(1,sizeof(struct wlan_channel));')
    source = owner.replace_once(source, 'static unsigned radio_q_len;', 'static bool post_use_pdev,post_zero_pdev;\nstatic unsigned radio_q_len;')
    reply = function(source, 'radio_reply_start')
    changed = owner.replace_once(reply, '.status=status}', '.status=status,.mac_id=post_zero_pdev?0:(post_use_pdev?2:1),.cfgd_tx_streams=2,.cfgd_rx_streams=1,.max_allowed_tx_power=17,.min_allowed_tx_power=3}')
    source = owner.replace_once(source, reply, changed)
    old = function(source, 'wma_vdev_start_resp_handler')
    replacement = SUPPORT.replace('NATIVE_CONFIG_TYPES', types).replace('NATIVE_MAC_DEFINES', native_defines(root)).replace('NATIVE_WMA_FUNCTIONS', native)
    source = owner.replace_once(source, old, replacement)
    bridge = function(source, 'mlme_vdev_sm_deliver_event')
    changed = owner.replace_once(bridge, 'return wlan_sm_dispatch(', 'if (event == WLAN_VDEV_SM_EV_START_RESP) {post_observe_event(vdev_mlme,event_data_len,event_data);if(post_drop_event)return QDF_STATUS_E_FAILURE;}\n\treturn wlan_sm_dispatch(')
    source = owner.replace_once(source, bridge, changed)
    source = owner.replace_once(source, 'static void engine_cycle(', CHECKS + '\nstatic void engine_cycle(')
    cycle = function(source, 'engine_cycle')
    changed = owner.replace_once(cycle, 'assert(mishare_runtime_destroy(&o)==-EINPROGRESS);', 'post_assert_up();assert(mishare_runtime_destroy(&o)==-EINPROGRESS);')
    source = owner.replace_once(source, cycle, changed)
    main = function(source, 'main')
    changed = owner.replace_once(main, 'engine_contract();', 'post_mapping_contract();engine_contract();')
    changed = owner.replace_once(changed, 'for(unsigned initial=0;', 'for(unsigned mac_mode=0;mac_mode<2;mac_mode++)for(unsigned initial=0;')
    changed = owner.replace_once(changed, '{engine_cycle(', '{post_use_pdev=mac_mode;engine_cycle(')
    changed = owner.replace_once(changed, 'puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");', 'post_extra_cases();puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");')
    source = owner.replace_once(source, main, FAULTS + '\n' + changed)
    return source, exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    callbacks.negative_controls(directory, c_file, command, env, source, root)
    executable = directory / 'engine'
    target = owner.replace_once(source, function(source, 'main'), 'int main(void) {engine_cycle(5240,false,0);_Exit(0);}')
    c_file.write_text(target)
    subprocess.run(command, check=True)
    subprocess.run([executable], check=True, timeout=45, env=env)
    handler = function(target, 'wma_vdev_start_resp_handler')
    changed, count = re.subn(r'qdf_mem_copy\(iface->vdev->vdev_mlme.bss_chan,\s*iface->vdev->vdev_mlme.des_chan,\s*sizeof\(struct wlan_channel\)\);', '(void)iface; /* negative: omit BSS channel copy */', handler)
    assert count == 1
    c_file.write_text(owner.replace_once(target, handler, changed))
    subprocess.run(command, check=True)
    bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
    assert bad.returncode == -6 and 'EXPECTED_NATIVE_WMA_CHANNEL_COPY' in bad.stderr
    update = function(target, 'wma_set_and_update_mac_id')
    changed = owner.replace_once(update, 'cdp_update_mac_id(dp_soc, rsp->vdev_id, mac_id);', '(void)dp_soc; /* negative: omit PAS/NDI DP update */')
    c_file.write_text(owner.replace_once(target, update, changed))
    subprocess.run(command, check=True)
    bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
    assert bad.returncode == -6 and 'EXPECTED_NATIVE_WMA_EFFECTS' in bad.stderr


def audit(root):
    report = engine.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    report['base_engine_status'] = report['status']
    report['status'] = 'MISHARE_NATIVE_WMA_START_FIXTURE_PASS_ONLY'
    report['native_WMA_function_sha256'] = {name: hashlib.sha256(function((root / WMA).read_text(), name).encode()).hexdigest() for name in NAMES}
    report['native_config_type_sha256'] = {name: hashlib.sha256(declared((root / PUBLIC).read_text(), name).encode()).hexdigest() for name in ['wlan_mlme_ratemask_type', 'wlan_mlme_ratemask']}
    report['native_callback_sha256'] = {name: hashlib.sha256(callbacks.inline_function((root / engine.SMHEADER).read_text(), name).encode()).hexdigest() for name in callbacks.ADAPTERS}
    report['native_PAS_table_sha256'] = hashlib.sha256(callbacks.ops_table((root / engine.MLME).read_text()).encode()).hexdigest()
    report['instrumented_table_targets'] = dict(callbacks.PROBES.values())
    report['instrumented_native_bridge'] = 'mlme_vdev_sm_deliver_event: START_RESP argument/effect observation and one deliberate dispatch failure'
    report['native_START_RESP_length_expression'] = 'sizeof(rsp), the original pointer size, not sizeof(*rsp)'
    report['legacy_AP_MCC_conditional_enabled'] = False
    for name in ['missing_native_SM_free', 'hidden_native_allocation_failure', 'missing_PAS_START_binding', 'hidden_native_callback_error', 'missing_native_BSS_channel_copy', 'missing_native_PAS_DP_MAC_update']:
        report['negative_control_' + name + '_rejected'] = True
    report['checks'] = [s.replace('unchanged native transition/deliver bridges and 0081 selected native handlers plus native exit functions', 'native transition and selected entry/event/exit bodies; delivery bridge has an explicit WMA observation/failure probe') for s in report['checks']]
    report['checks'] += [
        'complete patched native WMA START-response body, native MAC/DP update, channel-switch response and ratemask mapping functions',
        '16 main combinations: INIT/0 or IDLE, 2437/5240 MHz, ordinary/early response, direct MAC or pdev-to-MAC mapping',
        'BSS channel copy, TX streams, native host/DP MAC id, power fields and original pointer-sized START_RESP arguments observed before native UP',
        'eight failures: missing WMA/MAC/config/resource, invalid pdev id, missing MLME object, invalid WMI after UP, rejected SM event; controllers/parents retained',
        'ratemask mapping contract and three extra full cycles: valid send, logged send failure accepted by native body, out-of-range config skipped',
        'seven previous negative controls and missing channel-copy/DP-update negative controls rejected',
    ]
    report['limitations'] = (
        'Four unchanged patched native WMA function bodies execute for qualified PAS/NDI successful START responses; native callbacks, owner and engine composite retained. '
        'Context/configuration objects, legacy/WMA fields, locks/minidump and allocator are platform models. DP MAC update and policy/ratemask transport endpoints are instrumented models, not actual DP/firmware operations. '
        'Inactive AP/STA/OCB/restart paths abort in stubs; FEATURE_AP_MCC_CH_AVOIDANCE is disabled around the extracted bodies. Full function text is not full configuration/callee coverage. '
        'Validation/down table probes and a START_RESP observation/failure probe in the native delivery bridge are explicit. WMA ignores the delivery return; production phase checks still quarantine a rejected event. '
        'Native WMA may fail after channel/MAC mutations or after UP; no rollback/recovery is claimed. Child fault cases retain all resources until process scope ends. '
        'No physical PE/peer teardown, automatic parent/shutdown coordination, active START/UP SSR recovery, backend activation, phone/firmware/RF or AirDrop proof.'
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
