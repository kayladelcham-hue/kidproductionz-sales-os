"""V5A versioned campaign configuration loader with deliberate inheritance."""
import json
from pathlib import Path
ALLOWED={'schema_version','campaign_id','name','market','categories','icp','scoring','routing','discovery','enrichment','crm','queue','output','features'}
def _merge(a,b):
 out=dict(a)
 for k,v in b.items(): out[k]=_merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else v
 return out
def load(root,campaign_id='default'):
 root=Path(root); base=json.loads((root/'config/defaults/base.json').read_text(encoding='utf-8'))
 path=root/'config/campaigns'/f'{campaign_id}.json'
 if campaign_id=='default':
  override={}
 elif path.exists():
  override=json.loads(path.read_text(encoding='utf-8'))
 else:
  # User-created campaigns are persisted in SQLite rather than as source files.
  # Convert their small editable surface into the same inherited runtime shape.
  try:
   from app.api.database import get_campaign
   row=get_campaign(campaign_id)
  except Exception:
   row=None
  if not row: raise FileNotFoundError(f'Unknown campaign: {campaign_id}')
  try: stored_market=json.loads(row.get('market') or '{}')
  except (TypeError,ValueError): stored_market={}
  override={'campaign_id':campaign_id,'name':row.get('name') or campaign_id,
            'market':{'active':stored_market.get('active',True),
                      'cities':stored_market.get('cities') or [row.get('city','')],
                      'states':stored_market.get('states') or [row.get('state','')]},
            'categories':{'configured':[row.get('category','')]},
            'queue':{'daily_limit':int(row.get('daily_queue_limit') or 50)}}
 unknown=set(override)-ALLOWED
 if unknown: raise ValueError('Unknown campaign fields: '+','.join(sorted(unknown)))
 if override.get('campaign_id',campaign_id)!=campaign_id: raise ValueError('campaign_id mismatch')
 result=_merge(base,override)
 profile=json.loads((root/'config/ideal_client_profile.json').read_text(encoding='utf-8'))
 if isinstance(result.get('market'),dict) and result['market'].get('markets'): result['market']['markets']=profile['markets']
 if isinstance(result.get('categories'),dict) and result['categories'].get('profile'): result['categories']=profile['categories']
 if isinstance(result.get('icp'),str): result['icp']=profile.get('primary_qualification',{})
 return result
