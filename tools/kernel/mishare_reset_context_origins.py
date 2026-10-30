"""Remove only the bounded pre-PE context reset helper for older source audits."""
import re


def remove_reset_context_additions(text):
    pattern = (r'\n/\* MISHARE_RESET_CONTEXT_BEGIN:(?:release|timer|dp) \*/\n.*?'
               r'/\* MISHARE_RESET_CONTEXT_END:(?:release|timer|dp) \*/\n')
    text, count = re.subn(pattern, '', text, flags=re.S)
    if count > 3 or 'MISHARE_RESET_CONTEXT_' in text:
        raise ValueError('Unknown or duplicate reset context helper')
    return text
