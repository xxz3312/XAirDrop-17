"""Remove only bounded parent-teardown window closure additions."""
import re

TAGS = ('cds_dp_close', 'hdd_pdev_close', 'dispatcher_include',
        'dispatcher_pdev_close')


def remove_parent_additions(text):
    from mishare_idle_origins import remove_idle_additions
    text = remove_idle_additions(text)
    for tag in TAGS:
        pattern = (r'\n/\* MISHARE_PARENT_BEGIN:' + tag +
                   r' \*/\n.*?/\* MISHARE_PARENT_END:' + tag + r' \*/\n')
        text, count = re.subn(pattern, '', text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate parent-teardown insertion: ' + tag)
    if 'MISHARE_PARENT_' in text:
        raise ValueError('Unknown parent-teardown insertion')
    return text
