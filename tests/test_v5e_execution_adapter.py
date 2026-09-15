import unittest
from pathlib import Path
from v5e_execution_adapter import build
class V5E(unittest.TestCase):
 def test_builds_campaigns(self):
  r=build(Path(__file__).parents[1],'orlando_beauty');self.assertEqual(r['validation_status'],'READY_FOR_EXECUTION_WIRING');self.assertFalse(r['safety']['hubspot_writes'])
  self.assertEqual(build(Path(__file__).parents[1],'atlanta_beauty')['campaign_id'],'atlanta_beauty')
 def test_deterministic(self):
  root=Path(__file__).parents[1];self.assertEqual(build(root,'orlando_beauty'),build(root,'orlando_beauty'))
if __name__=='__main__': unittest.main()
