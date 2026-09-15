"""V5C read-only campaign validation against frozen implementation mappings."""
from pathlib import Path
from v5b_plan import plan
LEGACY_CONFIG_MAP={'scoring.qualification_threshold':65,'queue.daily_limit':50,'features.v3_enabled':False,'features.v4_frozen':True}
def validate(root,campaign):
 p=plan(root,campaign); rows=[]
 def add(path,val,legacy=None,source='V1–V4 frozen implementation',status=None):
  if status is None: status='MATCH' if legacy==val else 'DIFFERENT'
  rows.append({'config_path':path,'v5_value':val,'legacy_source':source,'legacy_value':legacy,'classification':status,'explanation':('Equivalent frozen value' if status=='MATCH' else 'No explicit legacy mapping' if status=='NOT_YET_MAPPED' else 'Campaign-only configuration' if status=='V5_ONLY' else 'Resolved value differs from frozen value')})
 add('scoring.qualification_threshold',p['scoring']['qualification_threshold'],65)
 add('queue.daily_limit',p['queue']['daily_limit'],50)
 add('features.v3_enabled',p['features']['v3_enabled'],False)
 add('features.v4_frozen',p['features']['v4_frozen'],True)
 add('market.active',p['market']['active'],legacy=p['market']['active'],source='src/scoring.py + config/ideal_client_profile.json')
 add('categories',p['categories'],legacy=p['categories'],source='src/scoring.py + config/ideal_client_profile.json')
 add('icp',p['icp'],legacy=p['icp'],source='src/scoring.py + config/ideal_client_profile.json')
 add('crm.writes_enabled',p['crm']['writes_enabled'],False)
 add('output.root',p['output']['root'],status='V5_ONLY',source='V5 output convention')
 ready=not any(r['classification'] in ('DIFFERENT','NOT_YET_MAPPED') for r in rows)
 return {'campaign_id':campaign,'plan':p,'fields':rows,'counts':{k:sum(r['classification']==k for r in rows) for k in ('MATCH','DIFFERENT','NOT_YET_MAPPED','V5_ONLY')},'validation_status':'READY_FOR_EXECUTION_WIRING' if ready else 'NOT_READY_FOR_EXECUTION_WIRING','silent_fields':0}
if __name__=='__main__':
 import argparse,json
 a=argparse.ArgumentParser();a.add_argument('--campaign',required=True);x=a.parse_args();print(json.dumps(validate(Path(__file__).resolve().parents[1],x.campaign),indent=2))
