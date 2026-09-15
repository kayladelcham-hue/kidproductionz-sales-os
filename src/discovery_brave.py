"""Brave-specific GET adapter; downstream sees only neutral result fields."""
import os,re,json
from urllib.request import Request,build_opener
from urllib.parse import urlencode
from urllib.error import HTTPError
from discovery_providers import ProviderError
from enrichment_sources import NoRedirect,PublicProvider
class BraveProvider:
    provider_id='brave-v1'
    def __init__(self,cfg,cache):
        self.key=os.environ.get('BRAVE_SEARCH_API_KEY','').strip()
        if not self.key:raise ProviderError('BRAVE_SEARCH_API_KEY is missing; no request sent')
        if not re.fullmatch(r'[A-Za-z0-9._-]+',self.key):raise ProviderError('Malformed Brave API key')
        self.cfg=cfg;self.api_requests=0;self.opener=build_opener(NoRedirect())
        self.public=PublicProvider(dict(max_requests=cfg['max_public_requests'],pace_seconds=cfg['pace_seconds'],timeout_seconds=cfg['timeout_seconds'],max_bytes=cfg['max_page_bytes'],cache_hours=cfg['cache_hours'],user_agent='KidProductionzContactResearch/1.0'),cache)
    def search_business(self,query,limit):
        if not 1<=limit<=self.cfg['max_results_per_query'] or len(query)>600:raise ProviderError('Invalid search bounds')
        if self.api_requests>=self.cfg['query_budget']:raise ProviderError('Brave request budget exhausted')
        req=Request('https://api.search.brave.com/res/v1/web/search?'+urlencode(dict(q=query,count=limit,spellcheck='false',result_filter='web')),headers={'X-Subscription-Token':self.key,'Accept':'application/json'},method='GET')
        self.api_requests+=1
        try:
            with self.opener.open(req,timeout=self.cfg['timeout_seconds']) as response:
                raw=response.read(self.cfg['max_page_bytes']+1)
                if len(raw)>self.cfg['max_page_bytes']:raise ValueError()
                data=json.loads(raw)
            if not isinstance(data,dict) or data.get('type')!='search':raise ValueError()
            results=data.get('web',{}).get('results',[])
            if not isinstance(results,list):raise ValueError()
            normalized=[]
            for rank,r in enumerate(results[:limit],1):
                if not isinstance(r,dict) or not isinstance(r.get('url'),str):raise ValueError()
                normalized.append(dict(url=r['url'],title=str(r.get('title','')),snippet=str(r.get('description','')),rank=rank,provider='brave',query=query))
            # Never persist a credential echoed by an upstream response.
            return json.loads(json.dumps(normalized).replace(self.key,'[REDACTED]'))
        except HTTPError as exc:
            code=exc.code;exc.close()
            raise ProviderError('Brave GET failed: HTTP '+str(code)+'; no retry') from None
        except Exception:raise ProviderError('Brave response/network failure; no retry') from None
    def fetch_public_page(self,url):
        return {'html':self.public.fetch(url),'url':url}
