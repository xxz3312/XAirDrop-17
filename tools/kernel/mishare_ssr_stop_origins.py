"""Restore only bounded private SSR stop/error/reinit changes."""
import re
from mishare_live_origins import restore_live_additions

ORIGINALS = {'unregister_ipci_checked': '', 'remove_receipt_begin': '', 'remove_receipt_transition': '\tif (errno)\n\t\treturn;\n', 'remove_receipt_context': '\tif (!pld_context)\n\t\tgoto out;\n', 'remove_receipt_finish': '', 'unregister_ipci_stub': '', 'unregister_ipci_decl': '', 'unregister_common_checked': 'void pld_unregister_driver(void)\n{\n\tstruct pld_context *pld_context;\n\n\tpld_context = pld_get_global_context();\n\n\tif (!pld_context) {\n\t\tpr_err("global context is NULL\\n");\n\t\treturn;\n\t}\n\n\tif (!pld_context->ops) {\n\t\tpr_err("driver not registered\\n");\n\t\treturn;\n\t}\n\n\tpld_pcie_unregister_driver();\n\tpld_snoc_fw_sim_unregister_driver();\n\tpld_pcie_fw_sim_unregister_driver();\n\tpld_snoc_unregister_driver();\n\tpld_sdio_unregister_driver();\n\tpld_usb_unregister_driver();\n\tpld_ipci_unregister_driver();\n\n\tpld_context->pld_driver_state = 0;\n\n\tpld_context->ops = NULL;\n}\n', 'unregister_common_decl': '', 'unregister_hdd_checked': 'void wlan_hdd_unregister_driver(void)\n{\n\tpld_unregister_driver();\n}\n', 'unregister_hdd_decl': '', 'unload_checked_unregister': '\twlan_hdd_unregister_driver();\n','execution_idle_slots': '\t.idle_restart = pld_ipci_idle_restart_cb,\n\t.idle_shutdown = pld_ipci_idle_shutdown_cb,\n',
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

# Restore private registration/load additions before the original SSR tags.
REGISTRATION_ORIGINALS = {'reg_pcie_state': '', 'reg_pcie_register': 'int pld_pcie_register_driver(void)\n{\n#ifdef CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER\n\tint ret, cleanup;\n\n\tret = opairshare_wlan_execution_register_pcie_v3(&pld_pcie_execution);\n\tif (ret)\n\t\treturn ret;\n\tret = cnss_wlan_register_driver(&pld_pcie_ops);\n\tif (ret) {\n\t\tcleanup = opairshare_wlan_execution_unregister(THIS_MODULE);\n\t\tif (cleanup)\n\t\t\treturn cleanup;\n\t}\n\treturn ret;\n#else\n\treturn cnss_wlan_register_driver(&pld_pcie_ops);\n#endif\n}', 'reg_pcie_unregister': 'int pld_pcie_unregister_driver_checked(void)\n{\n\tint ret;\n\n\tret = opairshare_wlan_execution_unregister_begin(THIS_MODULE,\n\t\t\t\t\t\t      !module_is_live(THIS_MODULE));\n\tif (ret)\n\t\treturn ret;\n\t/* Strong checked CNSS2 import; never fall back after admission. */\n\tret = cnss_wlan_unregister_driver_checked_v1(&pld_pcie_ops,\n\t\t\t\t\t   opairshare_wlan_execution_remove_status);\n\treturn opairshare_wlan_execution_unregister_end(THIS_MODULE, ret);\n}', 'reg_pcie_decl': '', 'reg_common_decl': '', 'reg_common_helpers': '', 'reg_deinit_guard': '', 'reg_common_register': 'int pld_register_driver(struct pld_driver_ops *ops)\n{\n\tint ret = 0;\n\tstruct pld_context *pld_context;\n\n\tpld_context = pld_get_global_context();\n\n\tif (!pld_context) {\n\t\tpr_err("global context is NULL\\n");\n\t\tret = -ENODEV;\n\t\tgoto out;\n\t}\n\n\tif (pld_context->ops) {\n\t\tpr_err("driver already registered\\n");\n\t\tret = -EEXIST;\n\t\tgoto out;\n\t}\n\n\tif (!ops || !ops->probe || !ops->remove ||\n\t    !ops->suspend || !ops->resume) {\n\t\tpr_err("Required callback functions are missing\\n");\n\t\tret = -EINVAL;\n\t\tgoto out;\n\t}\n\n\tpld_context->ops = ops;\n\tpld_context->pld_driver_state = 0;\n\n\tret = pld_pcie_register_driver();\n\tif (ret) {\n\t\tpld_err_rl("Fail to register pcie driver\\n");\n\t\tgoto fail_pcie;\n\t}\n\tpld_context->pld_driver_state |= PLD_PCIE_REGISTERED;\n\n\tret = pld_snoc_register_driver();\n\tif (ret) {\n\t\tpld_err_rl("Fail to register snoc driver\\n");\n\t\tgoto fail_snoc;\n\t}\n\tpld_context->pld_driver_state |= PLD_SNOC_REGISTERED;\n\n\tret = pld_sdio_register_driver();\n\tif (ret) {\n\t\tpr_err("Fail to register sdio driver\\n");\n\t\tgoto fail_sdio;\n\t}\n\tpld_context->pld_driver_state |= PLD_SDIO_REGISTERED;\n\n\tret = pld_snoc_fw_sim_register_driver();\n\tif (ret) {\n\t\tpr_err("Fail to register snoc fw sim driver\\n");\n\t\tgoto fail_snoc_fw_sim;\n\t}\n\tpld_context->pld_driver_state |= PLD_SNOC_FW_SIM_REGISTERED;\n\n\tret = pld_pcie_fw_sim_register_driver();\n\tif (ret) {\n\t\tpr_err("Fail to register pcie fw sim driver\\n");\n\t\tgoto fail_pcie_fw_sim;\n\t}\n\tpld_context->pld_driver_state |= PLD_PCIE_FW_SIM_REGISTERED;\n\n\tret = pld_usb_register_driver();\n\tif (ret) {\n\t\tpr_err("Fail to register usb driver\\n");\n\t\tgoto fail_usb;\n\t}\n\tpld_context->pld_driver_state |= PLD_USB_REGISTERED;\n\n\tret = pld_ipci_register_driver();\n\tif (ret) {\n\t\tpld_err_rl("Fail to register ipci driver\\n");\n\t\tgoto fail_ipci;\n\t}\n\tpld_context->pld_driver_state |= PLD_IPCI_REGISTERED;\n\n\treturn ret;\n\nfail_ipci:\n\tpld_usb_unregister_driver();\nfail_usb:\n\tpld_pcie_fw_sim_unregister_driver();\nfail_pcie_fw_sim:\n\tpld_snoc_fw_sim_unregister_driver();\nfail_snoc_fw_sim:\n\tpld_sdio_unregister_driver();\nfail_sdio:\n\tpld_snoc_unregister_driver();\nfail_snoc:\n\tpld_pcie_unregister_driver();\nfail_pcie:\n\tpld_context->pld_driver_state = 0;\n\tpld_context->ops = NULL;\nout:\n\treturn ret;\n}', 'reg_hdd_state': '', 'reg_hdd_retry': '', 'reg_hdd_load_entry': '', 'reg_hdd_load_unregister': '\n\twlan_hdd_unregister_driver();', 'reg_hdd_load_fail': '', 'reg_hdd_mode': '', 'reg_hdd_unload': '', 'reg_hdd_module_init': 'static int hdd_module_init(void)\n{\n\tif (hdd_driver_load())\n\t\treturn -EINVAL;\n\n\treturn 0;\n}'}

def remove_ssr_stop_additions(text):
    text = restore_live_additions(text)
    text = text.replace('hdd_driver_unload_internal(bool *private_refused, int *private_result)',
                        'hdd_driver_unload_internal(bool *private_refused)')
    text = text.replace('hdd_driver_unload_internal(&private_refused, NULL);',
                        'hdd_driver_unload_internal(&private_refused);')
    text = text.replace('hdd_driver_unload_internal(NULL, NULL);',
                        'hdd_driver_unload_internal(NULL);')
    for tag in ['initial', 'transition', 'late_transition', 'admission',
                'unregister', 'success', 'entry', 'assert', 'late_assert']:
        pattern = (r'\n/\* MISHARE_SSR_STOP_BEGIN:result_' + tag +
                   r' \*/\n.*?/\* MISHARE_SSR_STOP_END:result_' + tag + r' \*/\n')
        text, count = re.subn(pattern, ('\t\tQDF_BUG(QDF_IS_STATUS_SUCCESS(status));' if tag in ['assert', 'late_assert'] else ''), text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate private unload-result insertion: ' + tag)
    for tag, original in REGISTRATION_ORIGINALS.items():
        pattern = (r'\n/\* MISHARE_SSR_STOP_BEGIN:' + tag +
                   r' \*/\n.*?/\* MISHARE_SSR_STOP_END:' + tag + r' \*/\n')
        text, count = re.subn(pattern, lambda m: original, text, flags=re.S)
        if count > 1:
            raise ValueError('Duplicate private registration insertion: ' + tag)
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
