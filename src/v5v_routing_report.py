"""Deterministic human-readable V5U routing report."""
import json
def build(routing_doc):
 rows=[];routes={};matches=diff=na=0
 for f in routing_doc['fixtures']:
  c=f['comparisons']; matches+=sum(x['classification']=='MATCH' for x in c);diff+=sum(x['classification']=='DIFFERENT' for x in c);na+=sum(x['classification']=='NOT_APPLICABLE' for x in c); route=f['v5']['route'];routes[route]=routes.get(route,0)+1
  rows.append({'fixture_id':f['fixture_id'],'campaign_id':f['campaign_id'],'input_summary':f.get('input_summary',{}),'scoring_summary':f.get('scoring_summary',{}),'route':route,'route_reason':f['v5'].get('reason',''),'direct_frozen_routing':f['direct'],'v5u_routing':f['v5'],'field_comparisons':c,'equivalent':all(x['classification']!='DIFFERENT' for x in c)})
 return {'report_version':'1.0','fixtures':rows,'summary':{'total_fixtures':len(rows),'route_counts':{k:routes.get(k,0) for k in ('CALL_FIRST','EMAIL_FIRST','DM_FIRST','RESEARCH')},'MATCH':matches,'DIFFERENT':diff,'NOT_APPLICABLE':na,'overall_routing_equivalence_status':'EQUIVALENT' if diff==0 else 'NOT_EQUIVALENT'}}
