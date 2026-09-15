import unittest,sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v4f_validate import FragmentFetcher
from v4e_bounded import BoundedFetcher
class FragmentTests(unittest.TestCase):
 def setUp(self):self.f=FragmentFetcher(json.loads(Path('config/enrichment_config.json').read_text()),'test')
 def fake(self,url):self.f.pages[url]='html';return 'html'
 def test_fragments_single_fetch(self):
  with patch.object(BoundedFetcher,'fetch',side_effect=self.fake) as m:
   self.f.fetch('https://example.com/contact');self.f.fetch('https://example.com/contact#form')
   self.assertEqual(self.f.fragment_duplicates,1)
   self.assertEqual(self.f.aliases[-1]['original_url'],'https://example.com/contact#form')
   self.assertEqual(m.call_args.args[0],'https://example.com/contact')
 def test_query_and_path_distinct(self):
  with patch.object(BoundedFetcher,'fetch',side_effect=self.fake):
   for u in ('https://example.com/a?x=1','https://example.com/a?x=2','https://example.com/b'):self.f.fetch(u)
  self.assertEqual(len(self.f.pages),3);self.assertEqual(self.f.fragment_duplicates,0)
if __name__=='__main__':unittest.main()
