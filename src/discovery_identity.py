"""Only fetched visible page evidence can corroborate identity."""
import re
from normalize import key,phone
from enrichment_website import Page
from discovery_candidates import kind

def verify(row,url,page,crosslink=''):
    text=' '.join(Page(page.get('html','')).text);k=' '+key(text)+' '
    name=key(row.get('name') or row.get('company_name',''));city=key(row.get('city',''));state=key(row.get('state',''))
    found={phone(x) for x in re.findall(r'\+?\d[\d () .-]{8,}\d',text)}-{''}
    expected=phone(row.get('phone',''))
    mn=bool(name) and ' '+name+' ' in k;mc=bool(city) and ' '+city+' ' in k
    mp=bool(expected) and expected in found
    address=key(row.get('address',''));ma=bool(address) and ' '+address+' ' in k
    result=dict(matched_name=mn,matched_phone=mp,matched_address=ma,matched_city_state=mc and bool(state) and ' '+state+' ' in k,crosslink_evidence=crosslink)
    status='REVIEW';reason='Insufficient source-page identity evidence';score=20*mn+20*mc+40*mp+20*ma
    if expected and found and not mp:status='REJECTED';reason='Source phone conflicts with lead phone'
    elif mn and not mc:status='REVIEW';reason='City absent or conflicting; cannot verify location'
    elif any(s in str(row.get('flags','')) for s in ('SHARED_PHONE','UNCERTAIN_DUPLICATE','IDENTITY_CONFLICT')):reason='Shared/conflicting identity signals'
    elif kind(url) in ('BOOKING_PLATFORM','BUSINESS_DIRECTORY'):reason='Shared platform requires manual verification'
    elif mn and mc and mp:status='VERIFIED';reason='Fetched page corroborates exact business name, city and phone'
    elif mn and mc and ma:status='LIKELY';reason='Name/city/address corroborated; exact phone still required'
    if status=='VERIFIED' and kind(url) in ('INSTAGRAM','FACEBOOK','TIKTOK') and not crosslink:
        status='LIKELY';reason='Social identity corroborated but official-site crosslink is missing'
    return dict(**result,candidate_status=status,candidate_confidence='HIGH' if status=='VERIFIED' else 'MEDIUM' if status=='LIKELY' else 'LOW',identity_score=score,identity_reason=reason,conflict_flags=reason if status in ('REVIEW','REJECTED') else '')
