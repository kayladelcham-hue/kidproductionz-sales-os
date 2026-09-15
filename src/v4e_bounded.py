"""Opt-in bounded HTML adapter for the unchanged V4D/V4B fetch path."""
from html.parser import HTMLParser
from html import escape
from urllib.parse import urljoin,urlsplit
from v4d_verification import SafeFetcher,FetchFailure

class VisibleContactHTML(HTMLParser):
    def __init__(self,base):
        super().__init__();self.base=base;self.stack=[];self.output=[];self.evidence=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);hidden=bool(self.stack and self.stack[-1][1]) or tag in ('script','style','template','noscript') or 'hidden' in a or a.get('aria-hidden')=='true' or any(s in a.get('style','').replace(' ','').lower() for s in ('display:none','visibility:hidden'))
        if tag not in ('br','img','meta','link','input','hr','area','base','embed','source','wbr'):self.stack.append((tag,hidden))
        if hidden:return
        if tag=='a' and a.get('href'):
            raw=a['href'];target=urljoin(self.base,raw);p=urlsplit(target);host=(p.hostname or '').removeprefix('www.')
            allowed=raw.lower().startswith(('mailto:','tel:')) or host in ('instagram.com','facebook.com','tiktok.com') or (p.netloc==urlsplit(self.base).netloc and p.path.rstrip('/').lower() in ('/contact','/contact-us','/about','/about-us'))
            if allowed:
                self.output.append('<a href="'+escape(raw,quote=True)+'"></a>')
                self.evidence.append({'exact_href':raw,'resolved_url':target,'confidence':'UNVERIFIED_REQUIRES_IDENTITY'})
    def handle_endtag(self,tag):
        for n in range(len(self.stack)-1,-1,-1):
            if self.stack[n][0]==tag:self.stack=self.stack[:n];break
    def handle_data(self,data):
        if not (self.stack and self.stack[-1][1]):self.output.append(escape(data))

class BoundedResponse:
    def __init__(self,response,url,owner,stage):self.response=response;self.url=url;self.owner=owner;self.stage=stage;self.headers=response.headers
    def __enter__(self):return self
    def __exit__(self,*args):self.response.close()
    def read(self,size):
        if self.stage!='page' or self.headers.get_content_type()!='text/html':return self.response.read(size)
        cap=self.owner.html_limit;chunks=[];total=0;eof=False
        while total<cap:
            chunk=self.response.read(min(self.owner.chunk_size,cap-total))
            if not chunk:eof=True;break
            chunks.append(chunk);total+=len(chunk)
        raw=b''.join(chunks)
        # Never read an extra byte. At the ceiling, conservatively mark partial.
        truncated=not eof and total==cap
        parser=VisibleContactHTML(self.url);parser.feed(raw.decode('utf-8',errors='replace'))
        clean=' '.join(parser.output).encode('utf-8')
        self.owner.provenance[self.url]=dict(original_url=self.url,http_status=getattr(self.response,'status',200),bytes_inspected=total,truncation=truncated,extraction_method='BOUNDED_VISIBLE_HTML',exact_evidence=parser.evidence,confidence='UNVERIFIED_REQUIRES_V4B',run_id=self.owner.run_id)
        # Escaping can expand text; keep downstream payload within normal bound.
        return clean[:self.owner.cfg['max_bytes']]

class WrappedOpener:
    def __init__(self,inner,owner):self.inner=inner;self.owner=owner
    def open(self,request,timeout):
        response=self.inner.open(request,timeout=timeout)
        return BoundedResponse(response,request.full_url,self.owner,self.owner.stage)

class BoundedFetcher(SafeFetcher):
    def __init__(self,cfg,run_id,html_limit=500000,chunk_size=16384):
        if type(html_limit) is not int or not 1<=html_limit<=cfg['max_bytes']:raise ValueError('HTML bound cannot exceed existing page limit')
        if type(chunk_size) is not int or not 1<=chunk_size<=html_limit:raise ValueError('Invalid chunk size')
        super().__init__(cfg);self.run_id=run_id;self.html_limit=html_limit;self.chunk_size=chunk_size;self.provenance={};self.stage='page'
        self.opener=WrappedOpener(self.opener,self)
    def _get(self,url,stage):
        self.stage=stage
        return super()._get(url,stage)
