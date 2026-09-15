import unittest,json
from pathlib import Path
from v5f_input_adapter import validate
from v5j_snapshots import stable
class V5J(unittest.TestCase):
 def test_snapshot_matches_and_is_stable(self):
  root=Path(__file__).parents[1];m=validate(root,'orlando_beauty',root/'tests/fixtures/v5_inputs/valid_orlando.csv');m.pop('source_file',None);m['processing_status']=m.pop('status');s=json.loads((root/'tests/snapshots/v5_manifests/valid_orlando.json').read_text());self.assertEqual(stable(m),s)
 def test_no_machine_paths_or_volatile_fields(self):
  p=Path(__file__).parents[1]/'tests/snapshots/v5_manifests/valid_orlando.json';t=p.read_text();self.assertNotIn('\\',t);self.assertNotIn('timestamp',t);self.assertNotIn('run_id',t)
if __name__=='__main__':unittest.main()
