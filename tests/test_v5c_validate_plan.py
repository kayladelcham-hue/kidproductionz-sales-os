import unittest
from pathlib import Path
from v5c_validate_plan import validate
class V5C(unittest.TestCase):
 def test_reports_all_and_gate(self):
  r=validate(Path(__file__).parents[1],'orlando_beauty');self.assertEqual(r['silent_fields'],0);self.assertEqual(r['validation_status'],'READY_FOR_EXECUTION_WIRING');self.assertEqual(r['counts']['NOT_YET_MAPPED'],0)
 def test_atlanta_deterministic(self):
  root=Path(__file__).parents[1];self.assertEqual(validate(root,'atlanta_beauty'),validate(root,'atlanta_beauty'))
if __name__=='__main__': unittest.main()
