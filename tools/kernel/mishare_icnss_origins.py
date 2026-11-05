"""Restore bounded optional ICNSS unregister extension to pinned source."""
import re

ORIGINALS = {'handler': 'static int icnss_driver_event_unregister_driver(struct icnss_priv '
            '*priv,\n'
            '\t\t\t\t\t\t\t void *data)\n'
            '{\n'
            '\tif (!test_bit(ICNSS_DRIVER_PROBED, &priv->state)) {\n'
            '\t\tpriv->ops = NULL;\n'
            '\t\tgoto out;\n'
            '\t}\n'
            '\n'
            '\tset_bit(ICNSS_DRIVER_UNLOADING, &priv->state);\n'
            '\n'
            '\ticnss_block_shutdown(true);\n'
            '\n'
            '\tif (priv->ops)\n'
            '\t\tpriv->ops->remove(&priv->pdev->dev);\n'
            '\n'
            '\ticnss_block_shutdown(false);\n'
            '\n'
            '\tclear_bit(ICNSS_DRIVER_UNLOADING, &priv->state);\n'
            '\tclear_bit(ICNSS_DRIVER_PROBED, &priv->state);\n'
            '\n'
            '\tpriv->ops = NULL;\n'
            '\n'
            '\ticnss_hw_power_off(priv);\n'
            '\n'
            'out:\n'
            '\treturn 0;\n'
            '}\n',
 'checked_entry': '',
 'failure_bit': '',
 'checked_decl': ''}

def restore(text):
    for tag, original in ORIGINALS.items():
        pattern = r"\n/\* MISHARE_ICNSS_BEGIN:"+tag+r" \*/\n.*?/\* MISHARE_ICNSS_END:"+tag+r" \*/\n"
        text, count = re.subn(pattern, lambda m: original, text, flags=re.S)
        if count > 1: raise ValueError("Duplicate ICNSS tag: "+tag)
    if "MISHARE_ICNSS_" in text: raise ValueError("Unknown ICNSS origin tag")
    return text
