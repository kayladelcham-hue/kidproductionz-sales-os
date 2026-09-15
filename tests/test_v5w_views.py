import unittest,json
from pathlib import Path
from v5w_routing_views import write
class V5W(unittest.TestCase):
 def test_views(self):
  root=Path(__file__).parents[1];mp,cp,n=write(root/'validation_outputs/v5_routing/canonical_routing_v1.json',root/'validation_outputs/v5_routing');self.assertEqual(n,15);self.assertIn('CALL_FIRST',mp.read_text())
if __name__=='__main__':unittest.main()
