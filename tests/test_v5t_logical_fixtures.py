import unittest,json
from pathlib import Path
class V5T(unittest.TestCase):
 def test_fifteen_logical_inputs_no_expected_scores(self):
  rows=json.loads((Path(__file__).parent/'fixtures/v5_logical_inputs.json').read_text());self.assertEqual(len(rows),15)
  for r in rows:
   for forbidden in ('score','grade','score_explanation','flags','market','normalized_category','rejection_reasons','review_reasons'): self.assertNotIn(forbidden,r)
if __name__=='__main__':unittest.main()
