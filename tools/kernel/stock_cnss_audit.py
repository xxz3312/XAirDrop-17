#!/usr/bin/env python3
"""Read-only legacy CNSS2 import gate, not a runtime/teardown certificate."""
import argparse
import json
from pathlib import Path

from module_abi import inspect

LEGACY = {'cnss_wlan_register_driver', 'cnss_wlan_unregister_driver'}
CHECKED = {'cnss_wlan_register_driver_checked_v1',
           'cnss_wlan_unregister_driver_checked_v1'}
LIVE = {'opairshare_wlan_live_unload_arm_v1'}


def audit(module, stock):
    providers = [m for m in stock['modules'] if m['name'] == 'cnss2']
    if len(providers) != 1 or not LEGACY <= providers[0]['exports'].keys():
        raise ValueError('Expected one captured CNSS2 with both legacy exports')
    exports = providers[0]['exports']
    # cnss_utils_* belongs to a separate captured module, not CNSS2.
    captured_names = {name for provider in stock['modules']
                      for name in provider['exports']}
    undefined = set(module['undefined'])
    versions = module['versions']
    references = undefined | versions.keys()
    forbidden = sorted(references & (CHECKED | LIVE))
    unknown = sorted(n for n in references if n.startswith('cnss_') and n not in captured_names)
    missing = sorted(LEGACY - undefined)
    imports = sorted(undefined & exports.keys())
    crc_errors = {n: {'actual': versions.get(n), 'stock': exports[n]['crc']}
                  for n in imports if versions.get(n) != exports[n]['crc']}
    dependencies = {name for value in module['modinfo'].get('depends', [])
                    for name in value.split(',') if name}
    missing_dependencies = sorted({'cnss2', 'opairshare_wonder_provider'} - dependencies)
    passed = not (forbidden or unknown or missing or crc_errors or missing_dependencies)
    return {
        'status': 'STOCK_CNSS2_IMPORTS_MATCH_ONLY' if passed else 'STOCK_CNSS2_IMPORTS_REJECTED',
        'module_sha256': module.get('sha256'),
        'firmware': stock['firmware'],
        'cnss2_imports': imports,
        'forbidden_checked_or_live_imports': forbidden,
        'unknown_cnss_imports': unknown,
        'missing_legacy_imports': missing,
        'crc_errors': crc_errors,
        'missing_dependencies': missing_dependencies,
        'runtime_certified': False,
        'limitations': 'CNSS2 import names/CRCs and dependency records only. Does not certify '
                       'private structure layout, callback KCFI, firmware, native unload, '
                       'provider lifetime, RF or Apple interoperability. No deployment bundle.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module', type=Path)
    parser.add_argument('--stock', type=Path, default=Path(__file__).resolve().parents[2] /
                        'kernel/abi/popsicle-stock-exports.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit(inspect(args.module), json.loads(args.stock.read_text()))
    content = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(content)
    print(content, end='')
    return 0 if report['status'] == 'STOCK_CNSS2_IMPORTS_MATCH_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
