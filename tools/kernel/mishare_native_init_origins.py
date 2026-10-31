"""Restore only bounded native INIT rejection provenance insertions."""
import re

def remove_native_init_additions(text):
    for tag in ('include','notify'):
        pattern=r'\n\n/\* MISHARE_INIT_REJECT_BEGIN:'+tag+r' \*/\n.*?/\* MISHARE_INIT_REJECT_END:'+tag+r' \*/'
        text,count=re.subn(pattern,'',text,flags=re.S)
        if count>1:raise ValueError('Duplicate native INIT origin: '+tag)
    if 'MISHARE_INIT_REJECT_' in text:raise ValueError('Unknown native INIT origin')
    return text
