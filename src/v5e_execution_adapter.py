"""V5E read-only translation from validated campaign plans to runtime inputs."""
import argparse,json
from pathlib import Path
from v5b_plan import plan
from v5c_validate_plan import validate
def build(root,campaign):
 v=validate(root,campaign)
 if v['validation_status']!='READY_FOR_EXECUTION_WIRING': raise ValueError('Execution wiring blocked: '+json.dumps(v['counts']))
 p=v['plan']; return {'runtime_spec_version':'1.0','campaign_id':campaign,'market':p['market'],'categories':p['categories'],'icp':p['icp'],'scoring':p['scoring'],'routing':p['routing'],'discovery':p['discovery'],'enrichment':p['enrichment'],'queue':p['queue'],'crm':p['crm'],'output':p['output'],'features':p['features'],'safety':{'network_execution':False,'hubspot_reads':False,'hubspot_writes':False,'outbound_actions':False},'validation_status':v['validation_status'],'equivalence':v['fields']}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--campaign',required=True);a.add_argument('--dry-run',action='store_true');x=a.parse_args();root=Path(__file__).resolve().parents[1];print(json.dumps(build(root,x.campaign),indent=2))
