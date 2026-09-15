"""Opt-in redirect adapter with offline PSL and unchanged bounded extraction."""
import re
from pathlib import Path
from urllib.parse import urlsplit,urljoin,urldefrag
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from v4f_validate import FragmentFetcher
from v4d_verification import FetchFailure

RULES=set(line.strip() for line in (Path(__file__).resolve().parents[1]/'config/v4g_public_suffix_list.dat').read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('//'))
def registrable(host):
    labels=host.lower().rstrip('.').encode('idna').decode().split('.')
    best=1
    for i in range(len(labels)):
        suffix='.'.join(labels[i:])
        if '!'+suffix in RULES:return '.'.join(labels[-(len(labels)-i):])
        if suffix in RULES:best=max(best,len(labels)-i)
        if i+1<len(labels) and '*.'+'.'.join(labels[i+1:]) in RULES:best=max(best,len(labels)-i)
    return '.'.join(labels[-best-1:]) if len(labels)>best else ''
BLOCKED={'bit.ly','t.co','tinyurl.com','instagram.com','facebook.com','tiktok.com','doubleclick.net','googleadservices.com'}
def policy(source,target):
    a=urlsplit(source);b=urlsplit(target);ha=a.hostname or '';hb=b.hostname or ''
    relation='same-host' if ha==hb else 'same-registrable-domain' if registrable(ha) and registrable(ha)==registrable(hb) else 'cross-domain'
    reason=''
    if b.scheme not in ('http','https') or b.username or b.password or b.port not in (None,80,443):reason='UNSAFE_URL'
    elif a.scheme=='https' and b.scheme=='http':reason='HTTPS_DOWNGRADE'
    elif registrable(hb) in BLOCKED:reason='DISALLOWED_DOMAIN'
    elif re.search(r'(^|[/._-])(login|signin|sign-in|auth|oauth|sso|tracking|redirect)([/._-]|$)',b.path.lower()) or re.search(r'(^|[&?])(token|session|auth|code)=',b.query,re.I):reason='AUTH_OR_TRACKING_DESTINATION'
    elif relation=='cross-domain':reason='CROSS_DOMAIN_UNCORROBORATED'
    return relation,reason

class Capture:
    def __init__(self,inner,owner):self.inner=inner;self.owner=owner
    def open(self,request,timeout):
        try:return self.inner.open(request,timeout=timeout)
        except HTTPError as e:
            self.owner.location=e.headers.get('Location') if e.headers else None
            raise

class RedirectFetcher(FragmentFetcher):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.redirects=[];self.redirect_diagnostics=[];self.final_urls={};self.location=None
        self.opener.inner=Capture(self.opener.inner,self)
    def _get(self,url,stage):
        original=url;visited={url};hops=0
        while True:
            self.location=None
            try:
                html=super()._get(url,stage);self.final_urls[original]=url;return html
            except FetchFailure as failure:
                if failure.detail['code']!='REDIRECT_BLOCKED':raise
                location=self.location
                target=urldefrag(urljoin(url,location))[0] if location else ''
                relation,reason=policy(url,target) if target else ('unknown','MISSING_LOCATION')
                if target in visited:reason='REDIRECT_LOOP'
                if hops>=3:reason='REDIRECT_HOP_LIMIT'
                entry=dict(original_requested_url=original,stage=stage,source_url=url,http_status=failure.detail['http_status'],location_header=location or '',destination_url=target,classification=relation,followed=False,blocking_reason=reason)
                entry.update(target_scheme=urlsplit(target).scheme if target else '', target_hostname=urlsplit(target).hostname if target else '', source_hostname=urlsplit(url).hostname or '', source_registrable_domain=registrable(urlsplit(url).hostname or ''), target_registrable_domain=registrable(urlsplit(target).hostname or '') if target else '', hop_number=hops+1, redirect_limit_remaining=max(0,3-hops), hostname_validation='performed', dns_resolution_attempted='unknown', safety_result='unknown', decision='BLOCKED')
                self.redirects.append(entry)
                self.redirect_diagnostics.append(dict(entry))
                if reason:raise FetchFailure(reason,url,stage)
                if stage=='page':
                    p=urlsplit(target);origin=p.scheme+'://'+p.netloc
                    try:
                        if origin not in self.robots:
                            robot=RobotFileParser();robot.parse(self._get(origin+'/robots.txt','robots').splitlines());self.robots[origin]=robot
                        if not self.robots[origin].can_fetch(self.cfg['user_agent'],target):raise FetchFailure('ROBOTS_BLOCKED',target,stage)
                    except FetchFailure as e:entry['blocking_reason']=e.detail['code'];raise
                entry['followed']=True;entry['decision']='FOLLOWED';self.redirect_diagnostics[-1].update(followed=True,decision='FOLLOWED');hops+=1;visited.add(target);url=target
