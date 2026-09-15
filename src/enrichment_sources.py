"""Bounded public-page provider. GET only, robots-aware, no redirects or retries."""
import hashlib,json,time,socket,ipaddress
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

class SourceUnavailable(Exception): pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args): return None

class FixtureProvider:
    def __init__(self,pages): self.pages=pages; self.calls=[]
    def fetch(self,url):
        self.calls.append(url)
        value=self.pages.get(url)
        if isinstance(value,Exception): raise value
        if value is None: raise SourceUnavailable('Fixture unavailable')
        return value

class PublicProvider:
    def __init__(self,cfg,cache):
        self.cfg=cfg; self.cache=Path(cache); self.requests=0; self.last=0
        self.opener=build_opener(NoRedirect());self.robots={}
    def _get(self,url):
        p=urlsplit(url)
        if p.scheme not in ('http','https') or p.username or p.password or p.port not in (None,80,443):
            raise SourceUnavailable('Unsafe URL')
        try:
            addresses=socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80))
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise SourceUnavailable('Non-public address')
        except OSError: raise SourceUnavailable('DNS unavailable') from None
        if self.requests>=self.cfg['max_requests']: raise SourceUnavailable('Request budget exhausted')
        time.sleep(max(0,self.cfg['pace_seconds']-(time.monotonic()-self.last)))
        self.requests+=1;self.last=time.monotonic()
        try:
            with self.opener.open(Request(url,headers={'User-Agent':self.cfg['user_agent']},method='GET'),timeout=self.cfg['timeout_seconds']) as r:
                if r.headers.get_content_type() not in ('text/html','text/plain'): raise SourceUnavailable('Unsupported content')
                raw=r.read(self.cfg['max_bytes']+1)
                if len(raw)>self.cfg['max_bytes']: raise SourceUnavailable('Page too large')
                return raw.decode('utf-8',errors='replace')
        except Exception: raise SourceUnavailable('Source inaccessible; no bypass or retry attempted') from None
    def fetch(self,url):
        key=hashlib.sha256(url.encode()).hexdigest();path=self.cache/(key+'.json')
        if path.exists():
            cached=json.loads(path.read_text())
            if time.time()-cached['at']<self.cfg['cache_hours']*3600:return cached['html']
        p=urlsplit(url);origin=p.scheme+'://'+p.netloc
        if origin not in self.robots:
            robots=RobotFileParser();robots.parse(self._get(origin+'/robots.txt').splitlines());self.robots[origin]=robots
        if not self.robots[origin].can_fetch(self.cfg['user_agent'],url): raise SourceUnavailable('Robots disallows access')
        html=self._get(url)
        self.cache.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'url':url,'at':time.time(),'html':html}))
        return html
