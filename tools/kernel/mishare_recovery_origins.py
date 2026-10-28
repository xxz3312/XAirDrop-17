"""Exact removal of bounded early-NDI recovery additions for older audits."""
import json
import re
ORIGINALS = json.loads(r'''{
  "cds_helper": "",
  "cds_window": "",
  "cds_close": "",
  "timer": "",
  "dp_cookie": "",
  "dp_detach": ""
}''')
def remove_recovery_additions(text):
    for tag, original in ORIGINALS.items():
        p = r'\n/\* MISHARE_RECOVERY_BEGIN:' + tag + r' \*/\n.*?/\* MISHARE_RECOVERY_END:' + tag + r' \*/\n'
        text, count = re.subn(p, lambda m: original, text, flags=re.S)
        if count > 1:raise ValueError('Duplicate recovery insertion: '+tag)
    if 'MISHARE_RECOVERY_' in text:raise ValueError('Unknown recovery insertion')
    return text
