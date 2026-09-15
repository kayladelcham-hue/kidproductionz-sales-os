import unittest,io,sys,json
from pathlib import Path
from email.message import Message
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v4e_bounded import BoundedFetcher,BoundedResponse
from enrichment_sources import FixtureProvider
from enrichment_pipeline import enrich
class Stream(io.BytesIO):
 def __init__(self,b,typ='text/html'):
  super().__init__(b);self.headers=Message();self.headers['Content-Type']=typ;self.status=200;self.sizes=[]
 def read(self,n=-1):self.sizes.append(n);return super().read(n)
class BoundedTests(unittest.TestCase):
 def setUp(self):
  self.cfg=json.loads(Path('config/enrichment_config.json').read_text());self.owner=BoundedFetcher(self.cfg,'test',1000,100)
 def parse(self,b,typ='text/html'):
  stream=Stream(b,typ);out=BoundedResponse(stream,'https://example.com',self.owner,'page').read(500001);return out,stream
 def test_early_email(self):self.assertIn(b'mailto:info@example.com',self.parse(b'<a href="mailto:info@example.com">Email</a>'+b'x'*2000)[0])
 def test_early_social(self):self.assertIn(b'instagram.com/example',self.parse(b'<a href="https://instagram.com/example">IG</a>'+b'x'*2000)[0])
 def test_late_data_absent(self):self.assertNotIn(b'mailto:',self.parse(b'x'*1000+b'<a href="mailto:late@example.com">x</a>')[0])
 def test_cutoff(self):
  _,s=self.parse(b'x'*2000);self.assertEqual(s.tell(),1000);self.assertTrue(all(0<n<=100 for n in s.sizes))
 def test_provenance(self):
  self.parse(b'x'*2000);p=self.owner.provenance['https://example.com'];self.assertEqual(p['bytes_inspected'],1000);self.assertTrue(p['truncation']);self.assertEqual(p['run_id'],'test')
 def test_small_page(self):
  out,_=self.parse(b'<p>Example Orlando</p>');self.assertIn(b'Example Orlando',out);self.assertFalse(self.owner.provenance['https://example.com']['truncation'])
 def test_nonhtml_not_partial(self):
  out,_=self.parse(b'x'*500002,'text/plain');self.assertEqual(len(out),500001);self.assertFalse(self.owner.provenance)
 def test_hidden_excluded(self):
  out,_=self.parse(b'<script><a href="mailto:bad@example.com">x</a></script><div hidden><a href="mailto:no@example.com">x</a></div>');self.assertNotIn(b'mailto:',out)
 def test_identity_still_required(self):
  out,_=self.parse(b'<a href="mailto:info@example.com">Email</a>')
  r=enrich({'name':'Other','city':'Orlando','phone':'4075552345','website':'https://example.com'},FixtureProvider({'https://example.com':out.decode()}),self.cfg,'r','t');self.assertEqual(r['enrichment_status'],'REVIEW');self.assertEqual(r['enriched_email'],'')
 def test_cannot_raise_limit(self):
  with self.assertRaises(ValueError):BoundedFetcher(self.cfg,'r',500001)
if __name__=='__main__':unittest.main()
