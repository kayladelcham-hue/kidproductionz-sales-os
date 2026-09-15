"""Opt-in V4D verification; production V1-V4C modules remain unchanged."""
import socket,ssl,time,ipaddress
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from urllib.robotparser import RobotFileParser
from enrichment_sources import SourceUnavailable,NoRedirect
from normalize import url as normalize_url

DIRECTORIES=('trustanalytica.org','trustanalytica.com','yelp.com','yellowpages.com','tripadvisor.com','bbb.org')
BOOKING=('salonlofts.com','booksy.com','vagaro.com','styleseat.com','fresha.com')
def host(value):return (urlsplit(normalize_url(value)).hostname or '').removeprefix('www.')
def belongs(h,domains):return any(h==d or h.endswith('.'+d) for d in domains)
def source_type(candidate,known):
    h=host(candidate)
    for d,t in [('instagram.com','INSTAGRAM'),('facebook.com','FACEBOOK'),('tiktok.com','TIKTOK')]:
        if belongs(h,[d]):return t
    if belongs(h,DIRECTORIES):return 'BUSINESS_DIRECTORY'
    if belongs(h,BOOKING):return 'BOOKING_PLATFORM'
    # Known-site exact host corroboration only; titles/snippets never consulted.
    if h and h==host(known):return 'OFFICIAL_WEBSITE'
    return 'OTHER_PUBLIC_SOURCE'

class FetchFailure(SourceUnavailable):
    def __init__(self,code,url,stage='page',status=None):
        self.detail=dict(code=code,url=url,stage=stage,http_status=status)
        super().__init__(code)

class SafeFetcher:
    def __init__(self,cfg):
        self.cfg=cfg;self.requests=0;self.last=0;self.robots={};self.pages={};self.failures=[]
        self.opener=build_opener(NoRedirect())
    def _get(self,url,stage):
        p=urlsplit(url)
        if p.scheme not in ('https','http') or p.username or p.password or p.port not in (None,80,443):raise FetchFailure('UNSAFE_URL',url,stage)
        try:
            addresses=socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80))
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise FetchFailure('UNSAFE_ADDRESS',url,stage)
        except OSError:raise FetchFailure('CONNECTION_ERROR',url,stage) from None
        if self.requests>=self.cfg['max_requests']:raise FetchFailure('REQUEST_BUDGET_EXHAUSTED',url,stage)
        time.sleep(max(0,self.cfg['pace_seconds']-(time.monotonic()-self.last)))
        self.last=time.monotonic();self.requests+=1
        try:
            with self.opener.open(Request(url,headers={'User-Agent':self.cfg['user_agent']},method='GET'),timeout=self.cfg['timeout_seconds']) as r:
                if r.headers.get_content_type() not in ('text/plain','text/html'):raise FetchFailure('CONTENT_TYPE_UNSUPPORTED',url,stage)
                raw=r.read(self.cfg['max_bytes']+1)
                if len(raw)>self.cfg['max_bytes']:raise FetchFailure('PAGE_TOO_LARGE',url,stage)
                return raw.decode('utf-8',errors='replace')
        except FetchFailure:raise
        except HTTPError as e:
            code=e.code;e.close()
            raise FetchFailure('REDIRECT_BLOCKED' if 300<=code<400 else 'HTTP_'+str(code),url,stage,code) from None
        except (TimeoutError,socket.timeout):raise FetchFailure('TIMEOUT',url,stage) from None
        except ssl.SSLError:raise FetchFailure('TLS_ERROR',url,stage) from None
        except URLError as e:
            code='TLS_ERROR' if isinstance(e.reason,ssl.SSLError) else 'TIMEOUT' if isinstance(e.reason,TimeoutError) else 'CONNECTION_ERROR'
            raise FetchFailure(code,url,stage) from None
        except Exception:raise FetchFailure('OTHER_FETCH_ERROR',url,stage) from None
    def fetch(self,url):
        if url in self.pages:return self.pages[url]
        p=urlsplit(url);origin=p.scheme+'://'+p.netloc
        try:
            if origin not in self.robots:
                robots=RobotFileParser();robots.parse(self._get(origin+'/robots.txt','robots').splitlines());self.robots[origin]=robots
            if not self.robots[origin].can_fetch(self.cfg['user_agent'],url):raise FetchFailure('ROBOTS_BLOCKED',url)
            self.pages[url]=self._get(url,'page');return self.pages[url]
        except FetchFailure as e:self.failures.append(e.detail);raise

def check_candidate(candidate,known,fetcher):
    typ=source_type(candidate,known)
    result=dict(candidate_url=candidate,source_type=typ,fallback_attempted=False,fallback_succeeded=False,failures=[])
    if typ!='OFFICIAL_WEBSITE':
        result['status']='REVIEW';result['reason']='Third-party or uncorroborated domain; not promoted';return result
    try:
        fetcher.fetch(candidate);result.update(status='FETCHED',effective_url=candidate);return result
    except FetchFailure as e:result['failures'].append(e.detail)
    p=urlsplit(candidate);root=p.scheme+'://'+p.netloc+'/'
    # Exact same host is stricter than same registrable domain. Never redirect.
    if root==candidate or not p.path.strip('/') or fallback_blocked(result):return dict(result,status='INACCESSIBLE')
    result['fallback_attempted']=True
    try:
        fetcher.fetch(root);result.update(status='FETCHED',effective_url=root,fallback_succeeded=True)
    except FetchFailure as failure:result['failures'].append(failure.detail);result['status']='INACCESSIBLE'
    return result

def fallback_blocked(result):
    # A failed robots preflight or an access restriction cannot be bypassed via root.
    failure=result['failures'][-1]
    return failure['stage']=='robots' or failure['code'] in ('ROBOTS_BLOCKED','HTTP_401','HTTP_403','HTTP_429','REQUEST_BUDGET_EXHAUSTED','UNSAFE_URL','UNSAFE_ADDRESS')
