"""V5B read-only campaign execution planner."""
import argparse,json
from pathlib import Path
from v5a_config import load
PLAN_VERSION='1.0'
def plan(root,campaign):
 cfg=load(root,campaign)
 return {'plan_version':PLAN_VERSION,'schema_version':cfg['schema_version'],'campaign_id':cfg['campaign_id'],'name':cfg['name'],'market':cfg['market'],'categories':cfg['categories'],'icp':cfg.get('icp'),'scoring':cfg['scoring'],'routing':cfg.get('routing'),'discovery':cfg.get('discovery'),'enrichment':cfg.get('enrichment'),'queue':cfg['queue'],'crm':cfg['crm'],'output':cfg['output'],'features':cfg['features'],'source_config_files':['config/defaults/base.json',f'config/campaigns/{campaign}.json'],'resolved_defaults_vs_overrides':{'defaults':'config/defaults/base.json','overrides':f'config/campaigns/{campaign}.json'}}
def equivalence(p):
 vals={'qualification_threshold':('scoring.qualification_threshold',65),'v3_enabled':('features.v3_enabled',False),'v4_frozen':('features.v4_frozen',True),'queue_daily_limit':('queue.daily_limit',50)}; out={}
 for k,(path,current) in vals.items():
  cur=p; 
  for part in path.split('.'): cur=cur.get(part,{}) if isinstance(cur,dict) else {}
  out[k]={'status':'MATCH' if cur==current else 'DIFFERENT','planned':cur,'frozen':current}
 out['service_area_filter']={'status':'NOT_YET_MAPPED'}
 return out
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--campaign',required=True);a=ap.parse_args();root=Path(__file__).resolve().parents[1];p=plan(root,a.campaign);p['equivalence']=equivalence(p);print(json.dumps(p,indent=2))
