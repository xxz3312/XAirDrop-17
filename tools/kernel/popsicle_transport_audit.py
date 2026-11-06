#!/usr/bin/env python3
"""Match a pinned target profile to actual recorded stock platform imports."""
import hashlib
import json
from pathlib import Path


def audit(profile,record):
    raw=profile.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record['profile_sha256']:
        raise ValueError('Target profile changed; re-audit actual stock transport')
    config=dict(x.split('=',1) for x in raw.decode().splitlines() if x.startswith('CONFIG_') and '=' in x)
    pcie=config.get('CONFIG_PLD_PCIE_CNSS_FLAG')=='y'
    ipci=config.get('CONFIG_PLD_IPCI_ICNSS_FLAG')=='y'
    if pcie==ipci:raise ValueError('Target transport selection is missing or ambiguous')
    source='PCIE_CNSS' if pcie else 'IPCI_ICNSS'
    required={'PCIE_CNSS':{'cnss_wlan_register_driver','cnss_wlan_unregister_driver'},
              'IPCI_ICNSS':{'__icnss_register_driver','icnss_unregister_driver'}}
    imports=set(record['actual_stock_platform_imports'])
    if not required[source]<=imports:raise ValueError('Source target bus disagrees with actual stock ELF imports')
    foreign=required['IPCI_ICNSS' if pcie else 'PCIE_CNSS']
    if imports&foreign:raise ValueError('Stock ELF imports another transport; explicit mixed-bus audit required')
    if record['transport']!=source:raise ValueError('Recorded transport label disagrees with evidence')
    return {'status':'SOURCE_PROFILE_AND_RECORDED_STOCK_IMPORTS_AGREE_ONLY','transport':source,
            'platform_module':'cnss2' if pcie else 'icnss2',
            'profile_sha256':record['profile_sha256'],'stock_wlan_sha256':record['stock_wlan_sha256'],
            'stock_platform_imports':record['actual_stock_platform_imports'],
            'limitations':'Pinned source flag plus recorded original stock ELF imports/dependencies only; not a current phone inventory, active hardware session or radio validation.'}
