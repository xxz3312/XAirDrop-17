"""Remove only bounded live-controller wrappers for independent core fixtures.

The old fixtures execute the unchanged native cores. The live-controller
fixture separately executes these wrappers and the actual external provider.
No compiler or runtime guard is bypassed by this read-only source assembly.
"""
import re

def restore_live_additions(text):
    for name in ['state','hdd_wlan_soft_driver_load','hdd_wlan_soft_driver_unload',
                 'mode_wrapper','load_wrapper','void_gate','controller','arm']:
        pattern=r'\n/\* MISHARE_SSR_STOP_BEGIN:live_'+name+r' \*/\n.*?/\* MISHARE_SSR_STOP_END:live_'+name+r' \*/\n'
        text,count=re.subn(pattern,'',text,flags=re.S)
        if count>1:raise ValueError('Duplicate live controller insertion: '+name)
    text=text.replace('static int hdd_driver_load_internal(void)','int hdd_driver_load(void)')
    text=text.replace('con_mode_handler_internal(', 'con_mode_handler(')
    text=text.replace('static int hdd_mishare_driver_unload_checked_internal(void)',
                      'int hdd_mishare_driver_unload_checked(void)')
    return text
