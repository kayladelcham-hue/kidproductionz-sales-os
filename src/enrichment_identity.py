"""Conservative first-party identity corroboration."""
from normalize import key,phone
from urllib.parse import urlsplit
import re

def identity(row,url,text,cfg):
    host=(urlsplit(url).hostname or '').removeprefix('www.')
    if any(host==d or host.endswith('.'+d) for d in cfg['shared_domains']):return False,'Shared platform requires manual business-specific verification'
    name=key(row.get('name') or row.get('company_name',''))
    city=key(row.get('city',''))
    textkey=key(text)
    phones={phone(v) for v in re.findall(r'\+?\d[\d () .-]{8,}\d',text)}
    exact_phone=bool(phone(row.get('phone',''))) and phone(row.get('phone','')) in phones
    if not name or name not in textkey:return False,'Business name not corroborated on source'
    if not city or city not in textkey:return False,'City not corroborated; possible different location'
    if not exact_phone:return False,'Phone not corroborated; shared/location identity uncertain'
    return True,'Source website plus business name, city and exact phone corroborated'
