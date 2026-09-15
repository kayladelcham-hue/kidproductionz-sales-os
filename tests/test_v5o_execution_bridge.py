import unittest,csv,tempfile
from pathlib import Path
from v5o_execution_bridge import run
class V5O(unittest.TestCase):
 def test_dry_run(self):
  root=Path(__file__).parents[1];p=Path(tempfile.mktemp(suffix='.csv'));p.write_text('name,city,state,category,phone\nA,Orlando,FL,hair salon,1\n');r=run(root,'orlando_beauty',p);self.assertEqual(r['input_row_count'],1);self.assertFalse(r['safety']['hubspot_writes'])
if __name__=='__main__':unittest.main()
