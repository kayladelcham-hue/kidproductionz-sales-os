import json
from pathlib import Path
from v5u_routing_bridge import run
from v5v_routing_report import build
from v5w_routing_views import write

def test_views(tmp_path):
 root=Path(__file__).parents[1]
 inputs=json.loads((root/'tests/fixtures/v5_logical_inputs.json').read_text())
 report=build(run(root,[{'fixture_id':x['fixture_id'],'campaign_id':x['campaign_id'],'record':{'name':'','city':'','state':'','category':'','phone':'','email':'','website':'','domain':'','social':'','other_contact':'','status':'','permanently_closed':'','temporarily_closed':'','rating':None,'reviews':None,'visual':'','visual_evidence':'','ownership':'','ownership_evidence':'','owner':'',**x}} for x in inputs]))
 source=tmp_path/'routing.json';source.write_text(json.dumps(report))
 mp,cp,n=write(source,tmp_path)
 assert n==15 and 'CALL_FIRST' in mp.read_text() and cp.exists()
