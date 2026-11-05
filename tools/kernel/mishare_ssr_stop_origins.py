"""Restore only bounded private SSR stop/error/reinit changes."""
import re

ORIGINALS = {'execution_idle_slots': '\t.idle_restart = pld_ipci_idle_restart_cb,\n\t.idle_shutdown = pld_ipci_idle_shutdown_cb,\n',
 'execution_idle_guard': '\tif (pld_context->ops->shutdown)\n',
 'execution_include': '',
 'execution_descriptor': '',
 'execution_slots': '\t.shutdown   = pld_ipci_shutdown,\n\t.reinit     = pld_ipci_reinit,\n',
 'execution_register': '\treturn icnss_register_driver(&pld_ipci_ops);\n',
 'execution_unregister': '\ticnss_unregister_driver(&pld_ipci_ops);\n',
 'unload_helper': '',
 'unload_upper': '',
 'unload_forward': '',
 'unload_soft_local': '',
 'unload_soft_call': '\thdd_driver_unload();\n',
 'unload_wrapper': '',
 'unload_local': '',
 'unload_admission': '',
 'post_error': '',
 'post_ready': '',
 'power_include': '',
 'ops_state': '',
 'resume_label': '',
 'resume_wrappers': '',
 'power_complete_helpers': '',
 'remove_module': '',
 'remove_prepare': '',
 'remove_include': '',
 'remove_admission': '',
 'power_complete': '\thdd_lpass_notify_stop(hdd_ctx);\n\n\tqdf_set_smmu_fault_state(false);\n\thdd_info("WLAN driver shutdown complete");\n',
 'reinit_local': '',
 'reinit_transition': '\tosif_psoc_sync_trans_stop(psoc_sync);\n',
 'power_stop': '\thdd_wlan_stop_modules(hdd_ctx, false);\n',
 'shutdown_local': '',
 'shutdown_begin': '',
 'shutdown_call': '\t\thdd_wlan_shutdown();\n',
 'reinit_call': '\terrno = __hdd_soc_recovery_reinit(dev, bdev, bid, bus_type);\n',
 'reinit_complete': '\thdd_start_complete(0);\n'}

def remove_ssr_stop_additions(text):
    text = text.replace('static void hdd_driver_unload_internal(bool *private_refused)\n{',
                        'void hdd_driver_unload(void)\n{')
    text = text.replace('static int hdd_mishare_stop_modules(struct hdd_context *hdd_ctx, bool ftm_mode,\n\t\t\t\t    bool mishare_resume)',
                        'int hdd_wlan_stop_modules(struct hdd_context *hdd_ctx, bool ftm_mode)')
    # Journal tags may precede a complete native function. Remove each exact
    # bounded insertion before restoring the inherited SSR stop tags.
    for tag in ['state', 'local', 'begin', 'post', 'parents', 'dp_error',
                'pdev_error', 'finish']:
        pattern = (r'\n/\* MISHARE_SSR_STOP_BEGIN:journal_' + tag +
                   r' \*/\n.*?/\* MISHARE_SSR_STOP_END:journal_' + tag + r' \*/\n')
        text, count = re.subn(pattern, '', text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate private SSR journal insertion: ' + tag)
    for tag, original in ORIGINALS.items():
        pattern = (r'\n/\* MISHARE_SSR_STOP_BEGIN:' + tag +
                   r' \*/\n.*?/\* MISHARE_SSR_STOP_END:' + tag + r' \*/\n')
        text, count = re.subn(pattern, lambda m: original, text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate private SSR stop insertion: ' + tag)
    if 'MISHARE_SSR_STOP_' in text:
        raise ValueError('Unknown private SSR stop insertion')
    return text
