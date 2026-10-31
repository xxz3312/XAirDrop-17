"""Restore earlier native baselines by removing only the bounded PE reset helper."""
import re


def remove_pe_reset_additions(text):
    text, count = re.subn(r'\n/\* MISHARE_PE_RESET_BEGIN:helpers \*/\n.*?'
                         r'/\* MISHARE_PE_RESET_END:helpers \*/\n', '', text, flags=re.S)
    if count > 1 or 'MISHARE_PE_RESET_' in text:
        raise ValueError('Unknown or duplicate PE reset helper')
    return text
