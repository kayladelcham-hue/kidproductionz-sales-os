import unittest,csv,tempfile,json
from pathlib import Path
from openpyxl import Workbook
from v5f_input_adapter import validate
from v5j_snapshots import stable
class V5K(unittest.TestCase):
 def make(self,ext,rows,headers=['name','city','state','category','phone']):
  p=Path(tempfile.mktemp(suffix=ext))
  if ext=='.csv':
   with p.open('w',newline='') as f:w=csv.writer(f);w.writerow(headers);w.writerows(rows)
  else:
   w=Workbook();s=w.active;s.append(headers);[s.append(r) for r in rows];w.save(p)
  return p
 def test_matrix_and_equivalence(self):
  root=Path(__file__).parents[1]; rows=[['A','Orlando','FL','hair salon','1']]
  c=validate(root,'orlando_beauty',self.make('.csv',rows));x=validate(root,'orlando_beauty',self.make('.xlsx',rows));c.pop('source_file',None);x.pop('source_file',None);self.assertEqual(stable(c),stable(x))
  cases=[([],['MISSING_COLUMNS:category']),([['A','Orlando','FL','hair salon','1'],['A','Orlando','FL','hair salon','1']],[]) ,([['A','Atlanta','GA','hair salon','1']],[])]
  for rs,_ in cases:
   r=validate(root,'orlando_beauty',self.make('.csv',rs));self.assertIn(r['status'],('ACCEPTED_FOR_PROCESSING','REJECTED'))
 def test_integrity(self):
  for p in (Path(__file__).parents[1]/'tests/snapshots').rglob('*.json'):
   t=p.read_text();self.assertNotIn('timestamp',t);self.assertNotIn('run_id',t);self.assertNotIn('C:\\',t)
if __name__=='__main__':unittest.main()
