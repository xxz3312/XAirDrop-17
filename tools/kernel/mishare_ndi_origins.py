"""Bounded native owned DELETE insertions; shared by source and C fixtures."""
DELETE_TIMEOUT_HOOK = '\t\t/* An owned CREATE has no ordinary SME/WMA delete references. */\n\t\tif (mishare_runtime_ndi_delete_owned(psoc, vdev_id)) {\n\t\t\tmishare_runtime_ndi_delete_event(psoc, vdev_id, false);\n\t\t\ttarget_if_vdev_mgr_handle_recovery(psoc, vdev_id,\n\t\t\t\t\t\t   recovery_reason, rsp_pos);\n\t\t\treturn;\n\t\t}\n'
DELETE_FW_HOOK = '\t/* Timer/RT cleanup succeeded above; publish only a real extracted reply.\n\t * Release PM state before allowing the owner to reclaim its parent.\n\t */\n\tif (mishare_runtime_ndi_delete_owned(psoc, vdev_del_resp.vdev_id)) {\n\t\ttarget_if_wake_lock_timeout_release(psoc, DELETE_WAKELOCK);\n\t\tmishare_runtime_ndi_delete_event(psoc, vdev_del_resp.vdev_id, true);\n\t\treturn 0;\n\t}\n'

def remove_owned_delete_hooks(text):
    header='#include "wlan_hdd_mishare_ndi.h"\n'
    if text.count(header)!=1:raise ValueError('Missing owned DELETE header')
    for name,block in [('timeout',DELETE_TIMEOUT_HOOK),('firmware',DELETE_FW_HOOK)]:
        if text.count(block)!=1:raise ValueError('Unexpected owned DELETE hook: '+name)
        text=text.replace(block,'')
    return text.replace(header,'')
