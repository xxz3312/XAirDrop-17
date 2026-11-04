"""Restore only bounded private SSR stop/error/reinit changes."""
import re

ORIGINALS = {'post_error': '',
 'post_ready': '',
 'power_include': '',
 'ops_state': '',
 'power_stop': '\thdd_wlan_stop_modules(hdd_ctx, false);\n',
 'shutdown_local': '',
 'shutdown_begin': '',
 'shutdown_call': '\t\thdd_wlan_shutdown();\n',
 'reinit_call': '\terrno = __hdd_soc_recovery_reinit(dev, bdev, bid, bus_type);\n',
 'reinit_complete': '\thdd_start_complete(0);\n'}

def remove_ssr_stop_additions(text):
    for tag, original in ORIGINALS.items():
        pattern = (r'\n/\* MISHARE_SSR_STOP_BEGIN:' + tag +
                   r' \*/\n.*?/\* MISHARE_SSR_STOP_END:' + tag + r' \*/\n')
        text, count = re.subn(pattern, lambda m: original, text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate private SSR stop insertion: ' + tag)
    if 'MISHARE_SSR_STOP_' in text:
        raise ValueError('Unknown private SSR stop insertion')
    return text
