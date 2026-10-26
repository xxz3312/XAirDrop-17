#!/usr/bin/env python3
"""Actions-only differential execution of real mode functions, before/after patch.

Stubs supply object access and log plumbing only. No kernel/device execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from popsicle_backend_audit import code_only, PIN

QDF = 'qca-wifi-host-cmn/qdf/inc/qdf_types.h'
DP = 'qca-wifi-host-cmn/dp/inc/cdp_txrx_cmn_struct.h'
TYPES = 'qca-wifi-host-cmn/qdf/src/qdf_types.c'
UTIL = 'qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/src/wlan_vdev_mgr_utils_api.c'
MLME = 'qcacld-3.0/components/mlme/core/src/wlan_mlme_vdev_mgr_interface.c'


def enum(text, name):
    return re.search(r'enum\s+' + name + r'\s*\{[^}]+\};', text, re.S)[0]


def function(text, name):
    # These fixed upstream functions use a column-zero closing brace.
    match = re.search(r'(?:static )?(?:const char \*|enum wlan_op_mode|QDF_STATUS|bool)\s*\n?\s*' + name + r'\([^;{]+?\)\s*\{.*?^\}', text, re.S | re.M)
    if not match:
        raise ValueError('Cannot extract upstream function: ' + name)
    return match[0]


def fixture(read, legacy_qdf, legacy_dp):
    status = re.search(r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;', read('qca-wifi-host-cmn/qdf/inc/qdf_status.h'), re.S)[0]
    macros = '\n'.join(line for line in read('qca-wifi-host-cmn/umac/mlme/include/wlan_vdev_mlme.h').splitlines()
                       if re.match(r'#define WLAN_VDEV_MLME_(TYPE|SUBTYPE)_\w+\s+0x[0-9a-fA-F]+$', line))
    macros += '\n' + re.search(r'^#define WMI_HOST_VDEV_TYPE_MONITOR\s+0x[0-9a-fA-F]+$', read('qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h'), re.M)[0]
    code = '#include <stdio.h>\n#include <stdint.h>\n#include <stdbool.h>\n#include <assert.h>\n'
    code += enum(read(QDF), 'QDF_OPMODE') + '\n' + enum(read(DP), 'wlan_op_mode') + '\n' + status + '\n' + macros
    code += '''
#define mlme_err(...) ((void)0)
struct wlan_objmgr_vdev { struct { enum QDF_OPMODE vdev_opmode; } vdev_mlme; };
struct vdev_mlme_ops { int identity; };
static struct vdev_mlme_ops sta_mlme_ops={1}, ap_mlme_ops={2}, mon_mlme_ops={3};
struct vdev_mlme_obj { struct wlan_objmgr_vdev *vdev; struct vdev_mlme_ops *ops; };
static enum QDF_OPMODE wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { return v->vdev_mlme.vdev_opmode; }
'''
    for path, name in [(TYPES, 'qdf_opmode_str'), (UTIL, 'wlan_util_vdev_get_cdp_txrx_opmode'),
                       (MLME, 'mlme_is_vdev_in_beaconning_mode'), (MLME, 'mlme_register_vdev_mgr_ops'), (MLME, 'mlme_get_vdev_types')]:
        code += '\n' + function(read(path), name) + '\n'
    code += '\nint main(void) {\n'
    for i, name in enumerate(legacy_qdf):
        code += f'assert({name} == {i});\n'
    for i, name in enumerate(legacy_dp):
        code += f'assert({name} == {i});\n'
    code += '''
 for (int i=0;i<17;i++) {
  struct wlan_objmgr_vdev v={.vdev_mlme={.vdev_opmode=i}};
  struct vdev_mlme_obj m={.vdev=&v,.ops=NULL};
  uint8_t type=0xa5, sub=0xa5;
  int status=mlme_get_vdev_types(i,&type,&sub), reg=mlme_register_vdev_mgr_ops(&m);
  printf("%d|%s|%d|%d|%u|%u|%d|%d\\n",i,qdf_opmode_str(i),wlan_util_vdev_get_cdp_txrx_opmode(&v),status,type,sub,reg,m.ops?m.ops->identity:0);
 }
#ifdef NEW_TREE
 assert(QDF_PASSTHRU_MODE==17 && QDF_MAX_NO_OF_MODE==18 && wlan_op_mode_passthru==7);
 struct wlan_objmgr_vdev v={.vdev_mlme={.vdev_opmode=QDF_PASSTHRU_MODE}};
 struct vdev_mlme_obj m={.vdev=&v,.ops=&sta_mlme_ops};
 uint8_t type=0xa5, sub=0xa5;
 assert(wlan_util_vdev_get_cdp_txrx_opmode(&v)==wlan_op_mode_passthru);
 assert(mlme_register_vdev_mgr_ops(&m)==QDF_STATUS_E_NOSUPPORT && m.ops==NULL);
 assert(mlme_get_vdev_types(QDF_PASSTHRU_MODE,&type,&sub)==QDF_STATUS_E_NOSUPPORT && type==0 && sub==0);
#else
 assert(QDF_MAX_NO_OF_MODE==17);
#endif
 return 0;
}
'''
    return code


def audit(root):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('Unexpected source commit')
    def before(path):
        return subprocess.check_output(['git', '-C', str(root), 'show', 'HEAD:' + path], text=True)
    def after(path):
        return (root / path).read_text()
    qdf = re.findall(r'\bQDF_\w+(?=\s*,)', code_only(enum(before(QDF), 'QDF_OPMODE')))
    dp = re.findall(r'\bwlan_op_mode_\w+(?=\s*,)', code_only(enum(before(DP), 'wlan_op_mode')))
    if len(qdf) != 17 or len(dp) != 7:
        raise ValueError('Legacy enum inventory changed')
    results, inputs = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        for label, read in [('before', before), ('after', after)]:
            source = fixture(read, qdf, dp)
            path = Path(tmp) / (label + '.c')
            path.write_text(source)
            exe = Path(tmp) / label
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror'] + (['-DNEW_TREE=1'] if label=='after' else []) + [str(path), '-o', str(exe)], check=True)
            results[label] = subprocess.check_output([exe], text=True, timeout=5)
            inputs[label] = hashlib.sha256(source.encode()).hexdigest()
    if results['before'] != results['after']:
        raise ValueError('Existing mode behavior changed')
    return {'status':'HOST_MODE_FIXTURE_PASS_ONLY','source_commit':head,'legacy_qdf_modes':17,'legacy_dp_modes':7,
            'legacy_results':results['after'].splitlines(),'fixture_source_sha256':inputs,
            'passthru_qdf_mode':17,'passthru_dp_mode':7,'mlme_registration':'E_NOSUPPORT','firmware_type_conversion':'E_NOSUPPORT_ZERO_OUTPUTS',
            'limitations':'Real C functions with object/log stubs. Not kernel concurrency, policy arrays, layout, firmware or radio certification.'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.wlan)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])
