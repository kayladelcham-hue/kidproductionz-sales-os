"""V5X local deterministic daily queue builder."""
import json
from pathlib import Path
from outreach_priority import priority
def build(root,campaign,records):
 cfg=json.loads((root/'config/outreach_config.json').read_text());limit=json.loads((root/'config/defaults/base.json').read_text())['queue']['daily_limit']; items=[]
 for r in records:
  route=r.get('route','RESEARCH'); chans={k:r.get(k,'') for k in ('phone','email','social')}; p,reason=priority(r,route,chans,cfg); status='RESEARCH' if route=='RESEARCH' else 'INELIGIBLE' if r.get('rejection_reasons') else 'DAILY_QUEUE';items.append(dict(r,priority=p,priority_reason=reason,queue_status=status))
 eligible=[x for x in items if x['queue_status']=='DAILY_QUEUE'];eligible.sort(key=lambda x:({'P1':0,'P2':1,'P3':2}.get(x['priority'],3),-float(x.get('score') or 0),str(x.get('lead_id',x.get('fixture_id','')))))
 for i,x in enumerate(eligible,1):x['queue_status']='DAILY_QUEUE' if i<=limit else 'DEFERRED';x['queue_position']=i if i<=limit else ''
 return {'version':'1.0','campaign_id':campaign,'queue_limit':limit,'candidates':items,'summary':{'total_candidates':len(items),'daily_queue_count':sum(x['queue_status']=='DAILY_QUEUE' for x in items),'deferred_count':sum(x['queue_status']=='DEFERRED' for x in items),'research_count':sum(x['queue_status']=='RESEARCH' for x in items),'ineligible_count':sum(x['queue_status']=='INELIGIBLE' for x in items)},'safety':{'dry_run':True,'network':False,'hubspot':False,'outbound':False}}
