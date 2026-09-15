"""Exact public business email links only; never generate addresses."""
import re
from urllib.parse import unquote

def emails(links):
    result=set()
    for link in links:
        if link.lower().startswith('mailto:'):
            value=unquote(link[7:].split('?')[0]).strip()
            if re.fullmatch(r'[^\s@;,]+@[^\s@;,]+\.[A-Za-z]{2,}',value):result.add(value)
    return sorted(result)

def email_type(value):
    local=value.split('@')[0].lower()
    return 'BOOKING' if local in ('booking','appointments','bookings') else 'SUPPORT' if local in ('support','help') else 'GENERAL' if local in ('hello','info','contact','office') else 'OTHER'
