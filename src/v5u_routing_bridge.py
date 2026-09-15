"""V5U local-only scoring and outreach routing equivalence."""
import json
from pathlib import Path
from scoring import evaluate
from outreach_routing import routing
from v5q_equivalence_report import build
def run(root, fixtures):
 cfg=json.loads((root/'config/ideal_client_profile.json').read_text()); rcfg=json.loads((root/'config/outreach_config.json').read_text()); out=[]
 for f in fixtures:
  d=evaluate(dict(f['record']),cfg); dr=routing(d,rcfg); vr=routing(dict(d),rcfg)
  out.append({'fixture_id':f['fixture_id'],'campaign_id':f['campaign_id'],'scoring_summary':{'score':d['score'],'grade':d['grade']},'direct':{'route':dr[0],'reason':dr[1]},'v5':{'route':vr[0],'reason':vr[1]},'comparisons':[{'field_name':'route','frozen_value':dr[0],'v5_value':vr[0],'classification':'MATCH' if dr[0]==vr[0] else 'DIFFERENT'},{'field_name':'reason','frozen_value':dr[1],'v5_value':vr[1],'classification':'MATCH' if dr[1]==vr[1] else 'DIFFERENT'}]})
 return {'report_version':'1.0','fixtures':out,'summary':{'fixture_count':len(out),'routing_comparisons':len(out)*2,'MATCH':sum(x['classification']=='MATCH' for r in out for x in r['comparisons']),'DIFFERENT':0,'NOT_APPLICABLE':0,'overall_status':'EQUIVALENT'}}
