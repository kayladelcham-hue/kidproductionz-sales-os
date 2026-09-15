import unittest,json,io,tempfile,sys
from pathlib import Path
from unittest.mock import patch,Mock
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from discovery_brave import BraveProvider
from discovery_providers import ProviderError,FixtureProvider,CachedProvider
from discovery_queries import queries
from discovery_identity import verify
from discovery_pipeline import discover
from discovery_handoff import inspect_verified
ROOT=Path(__file__).resolve().parents[1]
class BraveTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'config/discovery_brave_config.json').read_text())
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'synthetic-key'}):self.b=BraveProvider(self.cfg,self.temp.name)
        self.b.opener=Mock()
        self.row={'lead_id':'1','name':'Example','city':'Orlando','state':'FL','phone':'4075552345'}
    def response(self,value):self.b.opener.open.return_value=io.BytesIO(json.dumps(value).encode())
    def test_normalization(self):
        self.response({'type':'search','web':{'results':[{'url':'https://example.com','title':'Example','description':'snippet'}]}})
        r=self.b.search_business('query',5)[0]
        self.assertEqual(r['rank'],1);self.assertEqual(r['provider'],'brave');self.assertEqual(r['snippet'],'snippet')
        self.assertEqual(self.b.opener.open.call_args.args[0].get_method(),'GET')
    def test_missing_key(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ProviderError):BraveProvider(self.cfg,self.temp.name)
    def test_http_errors_redacted(self):
        for code in (401,429,500):
            self.b.opener.open.side_effect=HTTPError('url',code,'synthetic-key',{},io.BytesIO(b'synthetic-key'))
            with self.assertRaises(ProviderError) as err:self.b.search_business('q',5)
            self.assertNotIn('synthetic-key',str(err.exception));self.assertIn(str(code),str(err.exception))
    def test_malformed(self):
        self.response({'web':{'results':'bad'}})
        with self.assertRaises(ProviderError):self.b.search_business('q',5)
    def test_zero(self):
        self.response({'type':'search'});self.assertEqual(self.b.search_business('q',5),[])
    def test_key_echo_redacted(self):
        self.response({'type':'search','web':{'results':[{'url':'https://example.com','title':'synthetic-key'}]}})
        self.assertNotIn('synthetic-key',str(self.b.search_business('q',5)))
    def test_cache(self):
        self.response({'type':'search'})
        c=CachedProvider(self.b,self.cfg,self.temp.name)
        c.search_business('q');c.search_business('q');self.assertEqual(self.b.api_requests,1)
    def test_budget(self):
        self.b.api_requests=30
        with self.assertRaises(ProviderError):self.b.search_business('q',5)
        self.b.opener.open.assert_not_called()
    def test_queries(self):self.assertEqual(queries(self.row),queries(self.row));self.assertEqual(len(queries(self.row)),3)
    def test_snippet_not_identity(self):self.assertNotEqual(verify(self.row,'https://example.com',{'snippet':'Example Orlando 4075552345'})['candidate_status'],'VERIFIED')
    def test_phone_conflict(self):self.assertEqual(verify(self.row,'https://example.com',{'html':'Example Orlando 407-555-9999'})['candidate_status'],'REJECTED')
    def test_verified(self):self.assertEqual(verify(self.row,'https://example.com',{'html':'Example Orlando FL 407-555-2345'})['candidate_status'],'VERIFIED')
    def test_shared(self):self.assertEqual(verify(self.row,'https://booksy.com/example',{'html':'Example Orlando 407-555-2345'})['candidate_status'],'REVIEW')
    def test_social_crosslink(self):
        p={'html':'Example Orlando 407-555-2345'}
        self.assertEqual(verify(self.row,'https://instagram.com/example',p)['candidate_status'],'LIKELY')
        self.assertEqual(verify(self.row,'https://instagram.com/example',p,'https://example.com')['candidate_status'],'VERIFIED')
    def test_early_stop_dedupe_handoff(self):
        q=queries(self.row)[0];r={'url':'https://example.com','title':'Example'}
        f=FixtureProvider({q:[r,r]},{'https://example.com':{'html':'Example Orlando 407-555-2345'}})
        c=CachedProvider(f,self.cfg,Path(self.temp.name)/'cache',sleep=lambda n:None)
        result=discover([self.row],c,self.cfg,Path(self.temp.name)/'out')
        self.assertEqual(result['queries_executed'],1);self.assertEqual(result['verified_candidate_count'],1)
        data=json.loads((Path(result['output_directory'])/'v4b_candidate_input.json').read_text())
        self.assertEqual(data[0]['original_lead'],self.row);self.assertEqual(len(data[0]['verified_candidates']),1)
    def test_likely_handoff_blocked(self):
        item={'original_lead':self.row,'verified_candidates':[{'url':'https://example.com','evidence':{'candidate_status':'LIKELY'}}]}
        self.assertEqual(inspect_verified(item,None,{},'r','t'),[])
if __name__=='__main__':unittest.main()
