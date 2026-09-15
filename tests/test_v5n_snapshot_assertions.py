import unittest,json
from pathlib import Path
from v5j_snapshots import assert_snapshot
class V5N(unittest.TestCase):
 def test_mismatch_contains_diff(self):
  p=Path('tests/snapshots/v5_manifests/valid_orlando.json'); original=p.read_text();
  try:
   with self.assertRaisesRegex(AssertionError,'valid_orlando_csv'): assert_snapshot({'campaign_id':'wrong'},p,'valid_orlando_csv')
  finally:self.assertEqual(p.read_text(),original)
 def test_identical_quiet(self):
  p=Path('tests/snapshots/v5_manifests/valid_orlando.json'); assert_snapshot(json.loads(p.read_text()),p,'valid_orlando_csv')
if __name__=='__main__':unittest.main()
