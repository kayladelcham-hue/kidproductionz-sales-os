import json,tempfile,unittest,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from discovery_providers import FixtureProvider,CachedProvider,ProviderError,ProviderRequired,live_provider
ROOT=Path(__file__).resolve().parents[1]
class DiscoveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cfg=json.loads((ROOT/'config/discovery_config.json').read_text())
        self.provider=FixtureProvider({'Business Orlando':[{'url':'https://example.com','title':'Business'}]}, {'https://example.com':{'text':'Business'}})
        self.cached=CachedProvider(self.provider,self.cfg,self.temp.name,sleep=lambda seconds:None)
    def test_fixture_search(self):self.assertEqual(self.cached.search_business('Business Orlando')[0]['url'],'https://example.com')
    def test_query_cache(self):
        self.cached.search_business('Business Orlando');self.cached.search_business(' Business   Orlando ')
        self.assertEqual(self.cached.cache_hits,1);self.assertEqual(self.cached.queries_executed,1)
    def test_page_cache(self):
        self.cached.fetch_public_page('https://example.com');self.cached.fetch_public_page('https://example.com')
        self.assertEqual(self.cached.cache_hits,1)
    def test_budget(self):
        self.cfg['query_budget']=1;self.cached.search_business('a')
        with self.assertRaises(ProviderError):self.cached.search_business('b')
    def test_failure_no_retry(self):
        self.provider.searches['bad']=RuntimeError('secret')
        with self.assertRaises(ProviderError) as e:self.cached.search_business('bad')
        self.assertNotIn('secret',str(e.exception));self.assertEqual(len(self.provider.calls),1)
        self.assertEqual(self.cached.search_business('good'),[])
    def test_inaccessible(self):
        with self.assertRaises(ProviderError):self.cached.fetch_public_page('https://missing.example')
    def test_no_guessed_results(self):self.assertEqual(self.cached.search_business('unknown'),[])
    def test_live_disabled(self):
        with self.assertRaises(ProviderRequired):live_provider(self.cfg)
    def test_no_network_capability(self):
        import ast
        tree=ast.parse((ROOT/'src/discovery_providers.py').read_text())
        imports=[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        self.assertFalse(set(imports)&{'requests','socket','http','smtplib','urllib'})
    def test_production_unchanged(self):
        for path,digest in json.loads((ROOT/'tests/v4c_regression_manifest.json').read_text()).items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)
if __name__=='__main__':unittest.main()
