"""HubSpot handoff planning. No network or write operations are implemented."""
from dataclasses import dataclass,asdict
from typing import Any

SYNC_STATES=('NOT_SYNCED','READY_TO_SYNC','SYNCED','SYNC_FAILED','REVIEW_REQUIRED')
@dataclass(frozen=True)
class SyncPlan:
    prospect: dict
    existing_matches: dict
    proposed_operations: list[str]
    warnings: list[str]
    pipeline: str='KidProductionz Sales Cycle'
    stage: str='New Prospect'
    association_plan: dict|None=None
    sync_status: str='READY_TO_SYNC'
def decision(prospect:dict)->dict:
    # Preparation only: existing IDs are accepted as input, never invented.
    matches={k:prospect[k] for k in ('hubspot_contact_id','hubspot_company_id','hubspot_deal_id') if prospect.get(k)}
    warnings=[]
    if not prospect.get('email') and not prospect.get('phone') and not prospect.get('hubspot_contact_id'): warnings.append('No trusted contact identifier supplied')
    # A persisted contact without a deal is a safe partial CREATE_NEW retry.
    if prospect.get('hubspot_deal_id') and not prospect.get('hubspot_contact_id'): warnings.append('A trusted contact ID is required for this guarded execution path')
    if warnings: decision_type='REVIEW_REQUIRED'; status='REVIEW_REQUIRED'
    elif prospect.get('hubspot_contact_id') and not prospect.get('hubspot_deal_id'):
        decision_type='CREATE_NEW'; status='READY_TO_SYNC'
    elif matches: decision_type='UPDATE_EXISTING'; status='READY_TO_SYNC'
    else: decision_type='CREATE_NEW'; status='READY_TO_SYNC'
    ops=['Search for existing contact','Search for existing company']
    if status=='READY_TO_SYNC': ops += (['Create contact/company/deal only after explicit approval'] if decision_type=='CREATE_NEW' else ['Reuse trusted records','Associate deal to intended contact','Verify exactly one intended contact association'])
    out=asdict(SyncPlan(prospect={k:prospect.get(k) for k in ('name','email','phone','website')},existing_matches=matches,proposed_operations=ops,warnings=warnings,association_plan={'target':'CONTACT','required_count':1},sync_status=status)); out['decision_type']=decision_type; out['review_reason']=warnings[0] if warnings else None; return out
def preview(prospect:dict)->dict:
    return decision(prospect)
