import unittest,json
from pathlib import Path
from v5v_routing_report import build
class V5V(unittest.TestCase):
 def test_report(self):
  d=json.loads((Path('validation_outputs/v5_equivalence/routing_v1.json')).read_text());r=build(d);self.assertEqual(r['summary']['total_fixtures'],15);self.assertEqual(r['summary']['DIFFERENT'],0);self.assertEqual(r['summary']['overall_routing_equivalence_status'],'EQUIVALENT')
if __name__=='__main__':unittest.main()
