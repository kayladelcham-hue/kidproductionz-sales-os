"""Pure, evidence-based channel recommendations; no network capabilities."""
import re
from urllib.parse import urlsplit
from normalize import phone, url, phrase
from crm_normalize import unprotect

ROUTES = ('CALL_FIRST','EMAIL_FIRST','DM_FIRST','RESEARCH')

def routing(row, cfg):
    raw = {k:unprotect(str(row.get(k,'') or '')).strip() for k in ('phone','email','social','website')}
    clean = {'phone':phone(raw['phone']), 'website':url(raw['website']), 'email':'', 'social':''}
    if re.fullmatch(r"[^\s@;,]+@[^\s@;,]+\.[A-Za-z]{2,}",raw['email']): clean['email']=raw['email']
    social=url(raw['social'])
    if social:
        parsed=urlsplit(social)
        host=(parsed.hostname or '').removeprefix('www.')
        if host in cfg['social_domains'] and parsed.path.strip('/') and parsed.path.strip('/') not in ('share','login','explore'):
            clean['social']=social
    category=row.get('normalized_category') or row.get('category','')
    flags=str(row.get('flags',''))
    identity=all(str(row.get(k,'')).strip() for k in ('name','city','state'))
    ambiguous=any(raw[k] and not clean[k] for k in ('phone','email','social'))
    conflict=any(t in flags for t in cfg['conflict_terms']) or bool(row.get('duplicate_of'))
    weak_phone=any(t in flags for t in cfg['phone_weak_terms'])
    if not identity or conflict or ambiguous:
        return 'RESEARCH','Identity/contact evidence missing, conflicting, or ambiguous; verify before outreach.',clean
    professional=any(phrase(category,t) for t in cfg['professional_terms'])
    social_first=any(phrase(category,t) for t in cfg['social_first_terms'])
    if social_first and clean['social']:
        return 'DM_FIRST','Individual/social-first category and usable social profile favor a DM; social activity is unknown.',clean
    if professional and clean['email']:
        return 'EMAIL_FIRST','Professional/B2B category and usable business email favor email.',clean
    if clean['phone'] and not weak_phone:
        return 'CALL_FIRST','Qualified business with clear identity and usable phone; verify business hours before calling.',clean
    if clean['email']:
        return 'EMAIL_FIRST','Usable email is the strongest available direct channel.',clean
    if clean['social']:
        return 'DM_FIRST','Usable social profile is the strongest available channel; verify the profile belongs to the business.',clean
    return 'RESEARCH','No sufficiently reliable direct channel; website/booking links require human research.',clean
