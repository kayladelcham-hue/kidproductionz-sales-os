import unittest,json
from pathlib import Path
from v5v_routing_report import build
from v5u_routing_bridge import run
class V5V(unittest.TestCase):
 def test_report(self):
  root=Path(__file__).parents[1]; inputs=json.loads((root/'tests/fixtures/v5_logical_inputs.json').read_text()); d=run(root,[{'fixture_id':x['fixture_id'],'campaign_id':x['campaign_id'],'record':{'name':'','city':'','state':'','category':'','phone':'','email':'','website':'','domain':'','social':'','other_contact':'','status':'','permanently_closed':'','temporarily_closed':'','rating':None,'reviews':None,'visual':'','visual_evidence':'','ownership':'','ownership_evidence':'','owner':'',**x}} for x in inputs]);r=build(d);self.assertEqual(r['summary']['total_fixtures'],15);self.assertEqual(r['summary']['DIFFERENT'],0);self.assertEqual(r['summary']['overall_routing_equivalence_status'],'EQUIVALENT')
if __name__=='__main__':unittest.main()
