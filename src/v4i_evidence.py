"""Bounded observability only; no fetch or enrichment decisions."""
import hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin,urlunsplit,parse_qsl,urlencode
from v4g_redirects import registrable

MAX_OUTPUT=120000
SENSITIVE=re.compile(r'(token|secret|password|authorization|cookie|api.?key|session)',re.I)
def clean(text):
    text=re.sub(r'(?i)Bearer\s+[^\s<>]+','[REDACTED]',str(text))
    text=re.sub(r'(?i)(?:authorization|cookie|api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s<>]+','[REDACTED]',text)
    return text

def safe_url(value):
    p=urlsplit(value)
    if p.username or p.password:return '[REDACTED_URL]'
    return clean(urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if not SENSITIVE.search(k)]),'')))

def link_type(value):
    p=urlsplit(value);h=(p.hostname or '').removeprefix('www.')
    if p.scheme=='mailto':return 'mailto'
    if p.scheme=='tel':return 'other_contact'
    for site in ('instagram','facebook','tiktok','linkedin'):
        if h==site+'.com':return site
    if re.search(r'/(contact|contact-us)/?$',p.path):return 'contact_link'
    if re.search(r'/(about|about-us)/?$',p.path):return 'about_link'
    if any(x in h for x in ('booksy.','vagaro.','fresha.','styleseat.','salonlofts.')) or re.search(r'/(book|booking|schedule|appointments)',p.path):return 'booking_link'
    return ''
def channel_type(kind):
    return {'mailto':'EMAIL','instagram':'INSTAGRAM','facebook':'FACEBOOK','tiktok':'TIKTOK','linkedin':'LINKEDIN','contact_link':'CONTACT_PAGE','about_link':'ABOUT_PAGE','booking_link':'BOOKING','other_contact':'OTHER_PUBLIC_CONTACT'}.get(kind,'')

class Parser(HTMLParser):
    def __init__(self,base):super().__init__();self.base=base;self.stack=[];self.text=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);hidden=bool(self.stack and self.stack[-1][1]) or tag in ('script','style','template','noscript') or 'hidden' in a or a.get('aria-hidden')=='true' or any(x in a.get('style','').replace(' ','').lower() for x in ('display:none','visibility:hidden'))
        if tag not in ('br','img','meta','link','input','hr','area','base','embed','source','wbr'):self.stack.append((tag,hidden))
        if not hidden and tag=='a' and a.get('href'):
            raw=a['href'];normalized=safe_url(urljoin(self.base,raw));kind=link_type(normalized)
            if kind:self.links.append(dict(raw_representation=safe_url(raw),normalized_value=normalized,link_type=kind,source_url=safe_url(self.base),extracted=None,retained=None,promoted=None,reason='Decision not recorded'))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):
        if not(self.stack and self.stack[-1][1]):self.text.append(clean(data))

def path_for(folder,lead_id,url):
    lead=hashlib.sha256(str(lead_id).encode()).hexdigest()[:16]
    return Path(folder)/lead/(hashlib.sha256(url.encode()).hexdigest()+'.json')

def capture(folder,lead_id,original_url,final_url,raw,metadata,decisions=None):
    if len(raw)>500000:raise ValueError('Evidence input exceeds existing bound')
    parser=Parser(final_url);parser.feed(raw.decode('utf-8',errors='replace'))
    text=' '.join(' '.join(parser.text).split());links=parser.links
    emails=[dict(normalized_email=e,source_representation=e,representation='plain_text',extracted=None,retained=None,promoted=None,reason='Decision not recorded') for e in sorted(set(token.strip('(),;<>') for token in text.split() if '@' in token and re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',token.strip('(),;<>'))))]
    for link in links:
        link['channel_type']=channel_type(link.get('link_type','')); link['raw_representation']=link.get('raw_representation',''); link['normalized_representation']=link.get('normalized_value',''); link['source_url']=safe_url(final_url); link['extracted_by_current_logic']=link.get('extracted'); link['promoted']=link.get('promoted'); link['rejection_or_ambiguity_reason']=link.get('reason','')
        if link['link_type']=='mailto':emails.append(dict(normalized_email=urlsplit(link['normalized_value']).path,source_representation=link['raw_representation'],representation='mailto',extracted=None,retained=None,promoted=None,reason='Decision not recorded'))
    evidence=dict(lead_id=lead_id,original_requested_url=safe_url(original_url),final_resolved_url=safe_url(final_url),registrable_domain=registrable(urlsplit(final_url).hostname or ''),http_status=metadata.get('http_status'),redirect_chain=[{k:safe_url(str(v)) if 'url' in k else clean(v) for k,v in hop.items() if k in ('source_url','destination_url','http_status','classification','followed','blocking_reason')} for hop in metadata.get('redirect_chain',[])],source_verification_status=metadata.get('source_verification_status','UNKNOWN'),inspected_byte_count=len(raw),total_bytes_available=metadata.get('total_bytes_available'),truncation=metadata.get('truncation',True),content_type=metadata.get('content_type','text/html'),visible_text=text[:24000],evidence_text_truncated=len(text)>24000,links=links[:100],links_truncated=len(links)>100,emails=emails[:100],emails_truncated=len(emails)>100,structured_contact_evidence=links[:100]+emails[:100],evidence_budget_bytes=MAX_OUTPUT,structured_contact_bytes=0,contextual_contact_bytes=0,general_text_bytes=len(text.encode('utf-8')),run_id=metadata.get('run_id'),source_fetch_artifact=metadata.get('source_fetch_artifact'),generated_at=datetime.now(timezone.utc).isoformat(),sanitization=['scripts/styles/hidden content excluded','whitespace normalized','sensitive URL parameters and credential-like values redacted'],capture_version='V4I-1')
    # Record decision evidence without making a new promotion decision.
    for record in evidence['links']+evidence['emails']:
        value=record.get('normalized_email',record.get('normalized_value','')).rstrip('/').replace('www.','')
        if decisions:
            found=any(value.casefold()==e['value'].rstrip('/').casefold() for e in decisions.get('extracted',[]))
            promoted=value.casefold() in [v.rstrip('/').casefold() for v in decisions.get('promoted',[]) if v]
            record.update(extracted=found,retained=promoted,promoted=promoted,reason='' if promoted else decisions.get('reason','Not promoted'))
    encoded=json.dumps(evidence,ensure_ascii=True)
    while len(encoded.encode())>MAX_OUTPUT:
        if evidence['visible_text']:
            evidence['visible_text']=evidence['visible_text'][:max(0,len(evidence['visible_text'])//2)];evidence['evidence_text_truncated']=True
        elif evidence['links']:evidence['links'].pop();evidence['links_truncated']=True
        elif evidence['emails']:evidence['emails'].pop();evidence['emails_truncated']=True
        else: break
        evidence['structured_contact_bytes']=len(json.dumps(evidence['structured_contact_evidence'],ensure_ascii=True).encode())
        encoded=json.dumps(evidence,ensure_ascii=True)
    path=path_for(folder,lead_id,original_url);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:f.write(encoded)
    return path,evidence

class ObservedResponse:
    """Tee only bytes already requested by caller; never calls read itself."""
    def __init__(self,response,callback):self.inner=response;self.callback=callback;self.data=bytearray();self.overflow=False
    def __getattr__(self,name):return getattr(self.inner,name)
    def read(self,n=-1):
        data=self.inner.read(n);remaining=500000-len(self.data);self.data.extend(data[:remaining]);self.overflow|=len(data)>remaining;return data
    def close(self):
        try:self.inner.close()
        finally:
            try:self.callback(bytes(self.data),self.overflow)
            except Exception:self.capture_failed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

class EvidenceOpener:
    """Install around an existing public-page transport, never a search/auth client.
    callback_factory receives only URL/status/type/length; never headers or keys.
    """
    def __init__(self,inner,callback_factory):self.inner=inner;self.callback_factory=callback_factory
    def open(self,request,timeout):
        response=self.inner.open(request,timeout=timeout)
        typ=response.headers.get_content_type()
        if typ!='text/html':return response
        metadata={'http_status':getattr(response,'status',None),'content_type':typ,'total_bytes_available':response.headers.get('Content-Length')}
        return ObservedResponse(response,self.callback_factory(request.full_url,metadata))

def instrument_public_fetcher(fetcher,folder,lead_id,run_id):
    """Opt-in attachment; preserves production fetch/read return values.
    Use a per-lead fetcher/context. Existing caches can be backfilled separately.
    """
    def callback_factory(url,metadata):
        def save(raw,overflow):
            meta=dict(metadata,run_id=run_id,truncation=overflow or len(raw)>=500000,source_verification_status='PENDING',source_fetch_artifact='existing-public-response')
            capture(folder,lead_id,url,url,raw,meta)
        return save
    # Place observer below bounded HTML transformation when present.
    transport=fetcher.opener
    if hasattr(transport,'inner'):
        transport.inner=EvidenceOpener(transport.inner,callback_factory)
    else:fetcher.opener=EvidenceOpener(transport,callback_factory)
    return fetcher
