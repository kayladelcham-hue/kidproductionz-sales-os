"""Provider-neutral discovery boundary. No live search provider selected."""
from typing import Protocol
import copy,json,time,hashlib
from pathlib import Path

class ProviderError(RuntimeError): pass
class ProviderRequired(ProviderError): pass

class DiscoveryProvider(Protocol):
    provider_id: str
    def search_business(self,query: str,limit: int)->list[dict]: ...
    def fetch_public_page(self,url: str)->dict: ...

class FixtureProvider:
    provider_id='fixture'
    def __init__(self,searches=None,pages=None):
        self.searches=searches or {};self.pages=pages or {};self.calls=[]
    def search_business(self,query,limit):
        self.calls.append(('search',query))
        value=self.searches.get(query,[])
        if isinstance(value,Exception):raise ProviderError('Fixture search failed')
        return copy.deepcopy(value[:limit])
    def fetch_public_page(self,url):
        self.calls.append(('fetch',url))
        value=self.pages.get(url)
        if value is None or isinstance(value,Exception):raise ProviderError('Fixture page inaccessible')
        return copy.deepcopy(value)

class CachedProvider:
    """Caches query/page evidence; never treats search snippets as verified identity.

    Future live adapters must enforce GET-only public access, robots, timeout,
    byte limits and redirect/address safety. This wrapper does not enable one.
    """
    def __init__(self,provider,cfg,cache,clock=time.time,sleep=time.sleep):
        self.provider=provider;self.cfg=cfg;self.cache=Path(cache);self.clock=clock;self.sleep=sleep
        self.queries_executed=0;self.cache_hits=0;self.provider_requests=0;self.last=None
    def _call(self,kind,key,operation):
        digest=hashlib.sha256(json.dumps([self.provider.provider_id,kind,key],sort_keys=True).encode()).hexdigest()
        path=self.cache/(digest+'.json')
        if path.exists():
            try:
                cached=json.loads(path.read_text())
                if 0<=self.clock()-cached['at']<self.cfg['cache_hours']*3600:
                    self.cache_hits+=1;return cached['value']
            except (ValueError,KeyError,TypeError):pass
        if kind=='search' and self.queries_executed>=self.cfg['query_budget']:raise ProviderError('Query budget exhausted')
        if self.last is not None:self.sleep(max(0,self.cfg['pace_seconds']-(self.clock()-self.last)))
        self.last=self.clock();self.provider_requests+=1
        if kind=='search':self.queries_executed+=1
        try:value=operation()
        except Exception:raise ProviderError('Provider failed; no automatic retry') from None
        self.cache.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'at':self.clock(),'value':value}))
        return value
    def search_business(self,query,limit=None):
        query=' '.join(query.split())
        limit=self.cfg['results_per_query'] if limit is None else limit
        if not query or type(limit) is not int or not 1<=limit<=self.cfg['results_per_query']:raise ProviderError('Invalid query or result limit')
        value=self._call('search',[query,limit],lambda:self.provider.search_business(query,limit))
        if not isinstance(value,list) or len(value)>limit:raise ProviderError('Malformed search results')
        return value
    def fetch_public_page(self,url):
        return self._call('page',url,lambda:self.provider.fetch_public_page(url))

def live_provider(cfg):
    raise ProviderRequired('Live discovery is disabled pending explicit search-provider approval')
