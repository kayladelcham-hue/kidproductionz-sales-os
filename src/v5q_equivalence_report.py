"""Deterministic, human-reviewable V5O equivalence report."""
import json
FIELDS=('score','raw_score','grade','score_explanation','flags','normalized_category','market','rejection_reasons','review_reasons')
def build(fixtures):
 records=[]; counts={'MATCH':0,'DIFFERENT':0,'NOT_APPLICABLE':0}
 for f in fixtures:
  comps=[]
  for k in FIELDS:
   a=f['direct'].get(k);b=f['bridge'].get(k); c='NOT_APPLICABLE' if a is None and b is None else 'MATCH' if a==b else 'DIFFERENT'; counts[c]+=1; comps.append({'field_name':k,'frozen_value':a,'v5_value':b,'classification':c})
  records.append({'fixture_id':f['fixture_id'],'campaign_id':f['campaign_id'],'input_summary':f.get('input_summary',{}),'direct_frozen_engine_result':f['direct'],'v5o_bridge_result':f['bridge'],'field_comparisons':comps,'status':'PASS' if all(x['classification']!='DIFFERENT' for x in comps) else 'FAIL'})
 return {'report_version':'1.0','fixtures':records,'summary':{'total_fixtures':len(records),'total_fields_compared':sum(counts.values()),**{k:counts[k] for k in counts},'overall_status':'EQUIVALENT' if counts['DIFFERENT']==0 else 'NOT_EQUIVALENT'}}
