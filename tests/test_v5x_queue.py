import unittest
from pathlib import Path
from v5x_queue import build
class V5X(unittest.TestCase):
 def test_queue_and_research(self):
  r={'fixture_id':'a','score':80,'category_tier':'primary','rating':4.5,'reviews':30,'phone':'1','email':'','social':'','route':'CALL_FIRST'};q=build(Path(__file__).parents[1],'orlando_beauty',[r,{'fixture_id':'b','route':'RESEARCH'}]);self.assertEqual(q['summary']['daily_queue_count'],1);self.assertEqual(q['summary']['research_count'],1)
if __name__=='__main__':unittest.main()
