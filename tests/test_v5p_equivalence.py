import unittest,csv,tempfile,json
from pathlib import Path
from v5o_execution_bridge import run
from scoring import evaluate
class V5P(unittest.TestCase):
 def fixture(self,city,state,cat,phone='1',website=''):
  p=Path(tempfile.mktemp(suffix='.csv'));p.write_text(f'name,city,state,category,phone,website\nTest,{city},{state},{cat},{phone},{website}\n');return p
 def direct(self,row):
  cfg=json.loads((Path(__file__).parents[1]/'config/ideal_client_profile.json').read_text()); base={'name':'Test','city':row[0],'state':row[1],'category':row[2],'phone':row[3],'website':row[4],'domain':row[4],'email':'','social':'','other_contact':'','status':'','permanently_closed':'','temporarily_closed':'','rating':None,'reviews':None,'visual':'','visual_evidence':'','ownership':'','ownership_evidence':'','owner':''};return evaluate(base,cfg)
 def test_orlando_atlanta_row_equivalence(self):
  root=Path(__file__).parents[1]
  for campaign,city,state in [('orlando_beauty','Orlando','FL'),('atlanta_beauty','Atlanta','GA')]:
   p=self.fixture(city,state,'hair salon'); bridge=run(root,campaign,p)['qualification_results'][0]; direct=self.direct((city,state,'hair salon','1',''))
   for k in ('score','raw_score','grade','score_explanation','flags','normalized_category','market','rejection_reasons','review_reasons'): self.assertEqual(bridge[k],direct[k],k)
 def test_edge_cases_repeat_deterministic(self):
  root=Path(__file__).parents[1];p=self.fixture('Orlando','FL','warehouse club');a=run(root,'orlando_beauty',p);b=run(root,'orlando_beauty',p);self.assertEqual(a,b)
if __name__=='__main__':unittest.main()
