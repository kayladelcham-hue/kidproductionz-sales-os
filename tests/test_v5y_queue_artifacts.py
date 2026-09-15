import unittest,tempfile
from pathlib import Path
from v5x_queue import build
from v5y_queue_artifacts import write
class V5Y(unittest.TestCase):
 def test_artifacts_and_conservation(self):
  root=Path(__file__).parents[1];r={'fixture_id':'a','score':80,'category_tier':'primary','rating':4.5,'reviews':30,'phone':'1','email':'','social':'','route':'CALL_FIRST'};q=build(root,'orlando_beauty',[r,{'fixture_id':'b','route':'RESEARCH'}]);jp,cp,mp=write(q,Path(tempfile.mkdtemp()));self.assertTrue(jp.exists() and cp.exists() and mp.exists());self.assertEqual(len(__import__('json').loads(jp.read_text())['daily_queue'])+len(__import__('json').loads(jp.read_text())['research']),2)
if __name__=='__main__':unittest.main()
