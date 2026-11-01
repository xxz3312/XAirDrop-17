#!/usr/bin/env python3
"""Actions-only native MLME callback dispatch and complete PAS ops binding model."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import mishare_native_sm_owner_fixture as owner
from mishare_recovery_fixture import function

engine = owner.previous
OPS_HEADER = 'qca-wifi-host-cmn/umac/mlme/include/wlan_vdev_mlme.h'
ADAPTERS = [
    'mlme_vdev_validate_basic_params', 'mlme_vdev_start_send',
    'mlme_vdev_start_continue', 'mlme_vdev_update_beacon',
    'mlme_vdev_up_send', 'mlme_vdev_notify_up_complete',
    'mlme_vdev_disconnect_peers', 'mlme_vdev_stop_send',
    'mlme_vdev_stop_continue', 'mlme_vdev_down_send',
    'mlme_vdev_notify_down_complete', 'mlme_vdev_notify_start_state_exit',
]
PROBES = {
    'mlme_vdev_validate_basic_params': ('mishare_radio_validate', 'callback_probe_validate'),
    'mlme_vdev_notify_down_complete': ('mishare_radio_down_complete', 'callback_probe_down'),
}
SPY = r'''
static struct vdev_mlme_obj *callback_expected;
static unsigned callback_calls;
static QDF_STATUS callback_status;
static uint16_t callback_len;
static void *callback_data;
static QDF_STATUS callback_spy(struct vdev_mlme_obj *m,uint16_t n,void *p) {
 assert(m==callback_expected && n==callback_len && p==callback_data && "EXPECTED_NATIVE_CALLBACK_ARGUMENTS");
 callback_calls++;return callback_status;
}
static QDF_STATUS callback_beacon_spy(struct vdev_mlme_obj *m,enum beacon_update_op op,uint16_t n,void *p) {
 assert(op==BEACON_UPDATE && "EXPECTED_NATIVE_CALLBACK_ARGUMENTS");return callback_spy(m,n,p);
}
static QDF_STATUS callback_disconnect_spy(struct vdev_mlme_obj *m,uint16_t n,void *p,bool legacy) {
 assert(legacy && "EXPECTED_NATIVE_CALLBACK_ARGUMENTS");return callback_spy(m,n,p);
}
static QDF_STATUS callback_exit_spy(struct vdev_mlme_obj *m) {
 assert(m==callback_expected && "EXPECTED_NATIVE_CALLBACK_ARGUMENTS");callback_calls++;return callback_status;
}
'''


def inline_function(text, name):
    matches = re.findall(r'static\s+inline\s+QDF_STATUS\s+' + name + r'\([^;{]+\)\s*\{.*?^\}', text, re.S | re.M)
    if len(matches) != 1:
        raise ValueError('Expected one native callback adapter: ' + name)
    return matches[0]


def ops_table(text):
    matches = re.findall(r'static struct vdev_mlme_ops passthru_mlme_ops = \{.*?^\};', text, re.S | re.M)
    if len(matches) != 1:
        raise ValueError('Expected complete native PAS ops table')
    return matches[0]


def ops_type(text):
    return re.search(r'struct vdev_mlme_ops\s*\{.*?^\};', text, re.S | re.M)[0]


def model_adapter(text, name):
    # These adapter models are deliberately single-line definitions. The shared
    # native extractor expects a closing brace on its own line and would consume
    # following functions when used for this compact model representation.
    matches = re.findall(r'^static QDF_STATUS ' + name + r'\([^\n]*\) \{[^\n]*\}', text, re.M)
    if len(matches) != 1:
        raise ValueError('Expected one compact model adapter: ' + name)
    return matches[0]


def contract(table):
    bindings = re.findall(r'\.(\w+)\s*=\s*(\w+)', table)
    expected_probes = {original: probe for original, probe in PROBES.values()}
    out = [SPY, 'static void callback_bindings(void) {']
    out += [' assert(passthru_mlme_ops.' + field + '==' + expected_probes.get(target, target) + ' && "EXPECTED_PASSTHRU_CALLBACK_BINDINGS");' for field, target in bindings]
    out += ['}', 'static void callback_contract(void) {',
            ' struct vdev_mlme_obj m={0};struct vdev_mlme_ops ops={0};int payload=37;',
            ' callback_expected=&m;callback_len=19;callback_data=&payload;callback_calls=0;',
            ' QDF_STATUS statuses[]={QDF_STATUS_SUCCESS,QDF_STATUS_E_FAILURE,QDF_STATUS_E_NOSUPPORT};']
    for name in ADAPTERS:
        args = '&m,callback_len,callback_data'
        spy = 'callback_spy'
        if name == 'mlme_vdev_update_beacon':
            args = '&m,BEACON_UPDATE,callback_len,callback_data'
            spy = 'callback_beacon_spy'
        elif name == 'mlme_vdev_disconnect_peers':
            args += ',true'
            spy = 'callback_disconnect_spy'
        elif name == 'mlme_vdev_notify_start_state_exit':
            args = '&m'
            spy = 'callback_exit_spy'
        call = name + '(' + args + ')'
        out += [' {unsigned before=callback_calls;m.ops=NULL;',
                ' assert(' + call + '==QDF_STATUS_SUCCESS && callback_calls==before && "EXPECTED_NATIVE_NULL_OPS_DEFAULT");',
                ' m.ops=&ops;assert(' + call + '==QDF_STATUS_SUCCESS && callback_calls==before && "EXPECTED_NATIVE_NULL_SLOT_DEFAULT");',
                ' ops.' + name + '=' + spy + ';',
                ' for(unsigned i=0;i<sizeof(statuses)/sizeof(statuses[0]);i++) {callback_status=statuses[i];before=callback_calls;',
                ' assert(' + call + '==callback_status && callback_calls==before+1 && "EXPECTED_NATIVE_CALLBACK_RETURN");}',
                ' ops.' + name + '=NULL;}']
    out += [' callback_expected=NULL;callback_data=NULL;', '}']
    return '\n'.join(out)


def fixture(root):
    source, exits, stubbed = owner.fixture(root)
    header = (root / engine.SMHEADER).read_text()
    interface = (root / engine.MLME).read_text()
    types = (root / OPS_HEADER).read_text()
    table = ops_table(interface)
    source = owner.replace_once(source,
        'struct engine_exit_ops_type {QDF_STATUS (*mlme_vdev_notify_start_state_exit)(struct vdev_mlme_obj *);};',
        'struct vdev_mlme_ops;')
    source = owner.replace_once(source, 'const struct engine_exit_ops_type *ops;', 'const struct vdev_mlme_ops *ops;')
    # Full original ops declaration follows the model's existing response/beacon
    # types. It is source fidelity evidence, not private ABI/layout certification.
    enum = re.search(r'enum vdev_cmd_type\s*\{.*?^\};', types, re.S | re.M)[0]
    type_block = ('struct peer_delete_all_response;struct ml_rv_info;\n'
                  '#undef START_REQ\n#undef RESTART_REQ\n#undef STOP_REQ\n#undef DELETE_REQ\n' + enum + '\n' + ops_type(types) + '\n')
    anchor = 'static unsigned native_lifecycle_events,native_lifecycle_transitions;'
    source = owner.replace_once(source, anchor, type_block + anchor)
    for name in ADAPTERS:
        if name == 'mlme_vdev_notify_start_state_exit':
            # 0082 already inserted this unchanged native inline adapter.
            assert source.count(inline_function(header, name)) == 1
            continue
        old = model_adapter(source, name)
        replacement = inline_function(header, name)
        if name in PROBES:
            _, probe = PROBES[name]
            # Preserve original race/provenance instrumentation at the callback
            # entry, while the native inline body and original table text remain
            # unchanged. These two table targets are explicit test probes.
            replacement = owner.replace_once(old, name + '(', probe + '(') + '\n' + replacement
        source = owner.replace_once(source, old, replacement)
    source = owner.replace_once(source,
        'static const struct engine_exit_ops_type engine_exit_ops={passthru_mlme_reject_6};\n', '')
    source = owner.replace_once(source, 'm->ops=&engine_exit_ops;', 'm->ops=&passthru_mlme_ops;')
    extras = []
    for target in sorted(set(re.findall(r'=\s*(passthru_\w+)', table))):
        body = function(interface, target)
        try:
            existing = function(source, target)
        except ValueError:
            extras.append(body)
        else:
            assert existing == body, 'Unexpected PAS callback model: ' + target
    # Existing reject_6 and fallback wrappers precede this insertion point.
    defines = '\n'.join('#define ' + original + ' ' + probe for original, probe in PROBES.values())
    undefs = '\n'.join('#undef ' + original for original, _ in PROBES.values())
    block = '\n'.join(extras) + '\n' + defines + '\n' + table + '\n' + undefs + '\n' + contract(table) + '\n'
    anchor = 'static struct wlan_sm *attach_engine('
    source = owner.replace_once(source, anchor, block + anchor)
    main = function(source, 'main')
    changed = owner.replace_once(main, 'engine_contract();', 'callback_contract();callback_bindings();engine_contract();')
    source = owner.replace_once(source, main, changed)
    return source, exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    owner.negative_controls(directory, c_file, command, env, source, root)
    executable = directory / 'engine'
    target = owner.replace_once(source, function(source, 'main'), 'int main(void) {callback_contract();callback_bindings();_Exit(0);}')
    c_file.write_text(target)
    subprocess.run(command, check=True)
    subprocess.run([executable], check=True, timeout=45, env=env)
    table = ops_table(target)
    changed = owner.replace_once(table, '.mlme_vdev_start_send = mishare_radio_start_send,', '.mlme_vdev_start_send = NULL,')
    c_file.write_text(owner.replace_once(target, table, changed))
    subprocess.run(command, check=True)
    bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
    assert bad.returncode == -6 and 'EXPECTED_PASSTHRU_CALLBACK_BINDINGS' in bad.stderr
    adapter = inline_function(target, 'mlme_vdev_start_send')
    changed = owner.replace_once(adapter, 'return ret;', 'return QDF_STATUS_SUCCESS; /* negative: hide callback failure */')
    c_file.write_text(owner.replace_once(target, adapter, changed))
    subprocess.run(command, check=True)
    bad = subprocess.run([executable], capture_output=True, text=True, timeout=45, env=env)
    assert bad.returncode == -6 and 'EXPECTED_NATIVE_CALLBACK_RETURN' in bad.stderr


def audit(root):
    report = engine.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    report['base_engine_status'] = report['status']
    report['status'] = 'MISHARE_NATIVE_CALLBACKS_FIXTURE_PASS_ONLY'
    header = (root / engine.SMHEADER).read_text()
    interface = (root / engine.MLME).read_text()
    report['native_callback_sha256'] = {name: hashlib.sha256(inline_function(header, name).encode()).hexdigest() for name in ADAPTERS}
    report['native_ops_header_sha256'] = hashlib.sha256((root / OPS_HEADER).read_bytes()).hexdigest()
    report['native_ops_type_sha256'] = hashlib.sha256(ops_type((root / OPS_HEADER).read_text()).encode()).hexdigest()
    report['native_PAS_table_sha256'] = hashlib.sha256(ops_table(interface).encode()).hexdigest()
    report['native_owner_wrapper_sha256'] = {name: hashlib.sha256(function((root / engine.SM).read_text(), name).encode()).hexdigest() for name in ['mlme_vdev_sm_create', 'mlme_vdev_sm_destroy']}
    report['instrumented_table_targets'] = dict(PROBES.values())
    report['native_callback_adapter_count'] = len(ADAPTERS)
    report['native_PAS_table_binding_count'] = len(re.findall(r'\.(\w+)\s*=\s*(\w+)', ops_table(interface)))
    report['negative_control_missing_native_SM_free_rejected'] = True
    report['negative_control_hidden_native_allocation_failure_rejected'] = True
    report['negative_control_missing_PAS_START_binding_rejected'] = True
    report['negative_control_hidden_native_callback_error_rejected'] = True
    report['checks'] += [
        '12 unchanged native inline callback adapters with complete original ops declaration and full PAS table',
        'each adapter: NULL ops and NULL slot default success with no callback; complete argument forwarding and exact SUCCESS/FAILURE/NOSUPPORT propagation',
        'all PAS table targets checked, including explicit reject/noop slots; missing START binding and hidden error negative controls rejected',
        'all eight native lifecycle combinations and owner allocation/free controls retained; validation/down provenance probes explicitly recorded',
    ]
    report['limitations'] = (
        'Native inline callback bodies and full PAS table/type text execute in the 0083 owner/0082 engine composite. '
        'Two table targets use named validation/down test probes to preserve existing race/provenance injection; they then call the real controller functions. '
        'Other native PAS callbacks use original bindings; callback contract spies are separate from production lifecycle cases. '
        'Original missing-ops/slot default SUCCESS is verified as behavior, not accepted as proof of a completed radio operation. '
        'Ops object fields, locks/minidump, allocation and transport/WMA postprocessing remain modeled; full declaration is not private ABI/layout proof. '
        'Native object-manager create/destroy callers, physical DP/peer cleanup, parent coordinator and active START/UP SSR recovery remain outside scope. '
        'No backend activation, phone/firmware/RF or AirDrop certification.'
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
