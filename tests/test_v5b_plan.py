import unittest,json
from pathlib import Path
from v5b_plan import plan,equivalence
class V5B(unittest.TestCase):
 def setUp(self): self.root=Path(__file__).parents[1]
 def test_campaigns_and_determinism(self):
  a=plan(self.root,'orlando_beauty');b=plan(self.root,'atlanta_beauty');self.assertEqual(a,plan(self.root,'orlando_beauty'));self.assertEqual(a['campaign_id'],'orlando_beauty');self.assertEqual(b['market']['active'],'atlanta')
 def test_equivalence(self):
  e=equivalence(plan(self.root,'orlando_beauty'));self.assertEqual(e['qualification_threshold']['status'],'MATCH');self.assertEqual(e['service_area_filter']['status'],'NOT_YET_MAPPED')
 def test_invalid(self): self.assertRaises(FileNotFoundError,plan,self.root,'missing')
if __name__=='__main__': unittest.main()
