"""V5O dry-run bridge into frozen local scoring only."""
import argparse,csv,json
from pathlib import Path
from v5e_execution_adapter import build
from v5f_input_adapter import validate
from scoring import evaluate
def run(root,campaign,source):
 spec=build(root,campaign); manifest=validate(root,campaign,source)
 if manifest.get('status')!='ACCEPTED_FOR_PROCESSING': raise ValueError('Input rejected')
 rows=[]
 with open(source,encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   rows.append({'name':r.get('name',''),'city':r.get('city',''),'state':r.get('state',''),'category':r.get('category',''),'phone':r.get('phone',''),'email':r.get('email',''),'website':r.get('website',''),'domain':r.get('website',''),'social':r.get('instagram',''),'other_contact':'','status':'','permanently_closed':'','temporarily_closed':'','rating':None,'reviews':None,'visual':'','visual_evidence':'','ownership':'','ownership_evidence':'','owner':''})
 cfg=json.loads((root/'config/ideal_client_profile.json').read_text(encoding='utf-8')); results=[evaluate(r,cfg) for r in rows]
 return {'campaign_id':campaign,'input_row_count':len(rows),'qualification_results':results,'qualified_count':sum(not r['rejection_reasons'] and not r['review_reasons'] for r in results),'disqualified_count':sum(bool(r['rejection_reasons'] or r['review_reasons']) for r in results),'safety':{'dry_run':True,'hubspot_writes':False,'outbound':False,'network':False}}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--campaign',required=True);a.add_argument('--input',required=True);a.add_argument('--dry-run',action='store_true');x=a.parse_args();print(json.dumps(run(Path(__file__).resolve().parents[1],x.campaign,x.input),indent=2))
