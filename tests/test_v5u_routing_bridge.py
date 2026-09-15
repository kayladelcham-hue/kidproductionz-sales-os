import unittest
from pathlib import Path
from v5u_routing_bridge import run
class V5U(unittest.TestCase):
 def test_local_routing_equivalence(self):
  r={'name':'A','city':'Orlando','state':'FL','category':'hair salon','phone':'1','email':'','website':'','domain':'','social':'','other_contact':'','status':'','permanently_closed':'','temporarily_closed':'','rating':None,'reviews':None,'visual':'','visual_evidence':'','ownership':'','ownership_evidence':'','owner':''}
  out=run(Path(__file__).parents[1],[{'fixture_id':'f','campaign_id':'orlando_beauty','record':r}]);self.assertEqual(out['summary']['overall_status'],'EQUIVALENT')
if __name__=='__main__':unittest.main()
