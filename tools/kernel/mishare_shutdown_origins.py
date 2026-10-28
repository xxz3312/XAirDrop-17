"""Remove explicitly bounded shutdown insertions for earlier source audits."""
import re

TAGS = ('platform', 'ssr', 'remove', 'module_stop', 'main_include',
        'pe', 'channel', 'start_plan')

def remove_shutdown_additions(text):
    for tag in TAGS:
        pattern = (r'\n/\* MISHARE_SHUTDOWN_BEGIN:' + tag +
                   r' \*/\n.*?/\* MISHARE_SHUTDOWN_END:' + tag + r' \*/\n')
        text, count = re.subn(pattern, '', text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate shutdown insertion: ' + tag)
    if 'MISHARE_SHUTDOWN_' in text:
        raise ValueError('Unrecognized shutdown insertion')
    return text
