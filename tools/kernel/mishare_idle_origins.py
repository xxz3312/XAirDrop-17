"""Remove the single bounded idle guard for previous native-source audits."""
import re


def remove_idle_additions(text):
    pattern = (r'\n/\* MISHARE_IDLE_BEGIN:host_guard \*/\n.*?'
               r'/\* MISHARE_IDLE_END:host_guard \*/\n\n')
    text, count = re.subn(pattern, '', text, flags=re.S)
    if count > 1:
        raise ValueError('Duplicate idle host guard')
    for name in ['mode_inner', 'mode_change', 'mode_request']:
        mode = r'/\* MISHARE_IDLE_BEGIN:' + name + r' \*/\n.*?/\* MISHARE_IDLE_END:' + name + r' \*/\n'
        text, count = re.subn(mode, '', text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate mode stop guard')
    if 'MISHARE_IDLE_' in text:

        raise ValueError('Unknown or duplicate idle lifetime guard')
    return text
