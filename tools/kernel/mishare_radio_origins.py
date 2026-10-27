"""Bounded owned radio additions; ordinary native paths must remain unchanged."""
import re
TABLE_CALLBACKS = {
 'mlme_vdev_validate_basic_params': ('mishare_radio_validate', 'passthru_mlme_reject_0'),
 'mlme_vdev_start_send': ('mishare_radio_start_send', 'passthru_mlme_reject_0'),
 'mlme_vdev_start_continue': ('mishare_radio_start_continue', 'passthru_mlme_reject_0'),
 'mlme_vdev_up_send': ('mishare_radio_up_send', 'passthru_mlme_reject_0'),
 'mlme_vdev_notify_up_complete': ('mishare_radio_up_complete', 'passthru_mlme_reject_0'),
 'mlme_vdev_update_beacon': ('passthru_radio_beacon', 'passthru_mlme_reject_2'),
 'mlme_vdev_disconnect_peers': ('passthru_radio_disconnect', 'passthru_mlme_reject_3'),
 'mlme_vdev_stop_send': ('mishare_radio_stop_send', 'passthru_mlme_reject_0'),
 'mlme_vdev_stop_continue': ('mishare_radio_stop_continue', 'passthru_mlme_reject_0'),
 'mlme_vdev_down_send': ('mishare_radio_down_send', 'passthru_mlme_reject_0'),
 'mlme_vdev_notify_down_complete': ('mishare_radio_down_complete', 'passthru_mlme_reject_0'),
 'mlme_vdev_ext_start_rsp': ('passthru_radio_start_rsp', 'passthru_mlme_reject_5'),
 'mlme_vdev_ext_stop_rsp': ('passthru_radio_stop_rsp', 'passthru_mlme_reject_4'),
}

def remove_radio_additions(text):
    begin='/* MISHARE_BEGIN:radio_table */\n'
    end='\n/* MISHARE_END:radio_table */'
    if begin in text:
        if text.count(begin)!=1 or text.count(end)!=1:
            raise ValueError('Unexpected radio table marker count')
        start=text.index(begin);finish=text.index(end,start)+len(end)
        table=text[start+len(begin):finish-len(end)]
        for field,(after,before) in TABLE_CALLBACKS.items():
            needle='.'+field+' = '+after+','
            if table.count(needle)!=1:
                raise ValueError('Unexpected radio callback: '+field)
            table=table.replace(needle,'.'+field+' = '+before+',')
        text=text[:start]+table+text[finish:]
        text=text.replace('#include "wlan_hdd_mishare_radio_mlme.h"\n','')
    text=re.sub(r'\n/\* MISHARE_BEGIN:radio_\w+ \*/\n.*?/\* MISHARE_END:radio_\w+ \*/\n','',text,flags=re.S)
    # Wrapper insertion replaced the original table, whose preceding newline
    # is kept by the removal expression above.
    return text
