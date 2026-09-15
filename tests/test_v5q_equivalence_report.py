import unittest
from v5q_equivalence_report import build
class V5Q(unittest.TestCase):
 def test_equivalent_and_mismatch(self):
  f={'fixture_id':'f1','campaign_id':'orlando_beauty','direct':{'score':1},'bridge':{'score':1}};self.assertEqual(build([f])['summary']['overall_status'],'EQUIVALENT');f['bridge']['score']=2;self.assertEqual(build([f])['summary']['overall_status'],'NOT_EQUIVALENT')
 def test_all_fields_and_order(self):
  r=build([{'fixture_id':'f','campaign_id':'c','direct':{},'bridge':{}}]);self.assertEqual(len(r['fixtures'][0]['field_comparisons']),9);self.assertEqual(r['fixtures'][0]['field_comparisons'][0]['field_name'],'score')
if __name__=='__main__':unittest.main()
