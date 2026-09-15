"""Guarded HubSpot execution orchestration. Network client is injected for tests."""
from dataclasses import dataclass

@dataclass
class SyncResult:
    sync_status:str; hubspot_contact_id:str|None=None; hubspot_company_id:str|None=None; hubspot_deal_id:str|None=None
    created_contact:bool=False; created_company:bool=False; created_deal:bool=False; association_created:bool=False; association_verified:bool=False
    warnings:list|None=None; errors:list|None=None

def execute(prospect:dict, client):
    warnings=[]; errors=[]
    from .hubspot_service import decision
    plan=decision(prospect)
    if plan['sync_status']=='REVIEW_REQUIRED':
        return SyncResult('REVIEW_REQUIRED',prospect.get('hubspot_contact_id'),None,prospect.get('hubspot_deal_id'),warnings=plan['warnings'],errors=[]).__dict__
    cid=prospect.get('hubspot_contact_id'); did=prospect.get('hubspot_deal_id')
    if plan.get('decision_type')=='CREATE_NEW':
        try:
            created_contact = False
            if not cid:
                if not hasattr(client,'create_contact'): raise RuntimeError('CREATE_NOT_SUPPORTED')
                contact=client.create_contact(prospect); cid=str(contact.get('id'))
                created_contact = True
            deal=client.create_deal(prospect) if hasattr(client,'create_deal') else {'id':None}; did=str(deal.get('id')) if deal.get('id') else None
            if not cid: raise RuntimeError('CONTACT_CREATE_NO_ID')
            verified=True
            if did and hasattr(client,'associate'): client.associate(did,cid); verified=bool(client.verify_association(did,cid))
            return SyncResult('SYNCED' if verified else 'SYNC_FAILED',cid,None,did,created_contact=created_contact,created_deal=bool(did),association_created=bool(did),association_verified=verified,warnings=[],errors=[] if verified else ['Association verification failed']).__dict__
        except Exception as exc:
            if hasattr(exc,'status'):
                err={'code':f'HUBSPOT_HTTP_{exc.status}','stage':exc.operation,'status':exc.status,**exc.details}
                return SyncResult('SYNC_FAILED',str(cid) if cid else None,None,str(did) if did else None,created_contact=bool(created_contact),created_deal=bool(did),warnings=[],errors=[err]).__dict__
            return SyncResult('SYNC_FAILED',str(cid) if cid else None,None,str(did) if did else None,created_contact=bool(cid),created_deal=bool(did),warnings=[],errors=[f'{type(exc).__name__}: {exc}']).__dict__
    if not cid: return SyncResult('REVIEW_REQUIRED',warnings=['A trusted contact ID is required for this guarded execution path'],errors=[]).__dict__
    if not did: return SyncResult('REVIEW_REQUIRED',hubspot_contact_id=str(cid),warnings=['A trusted deal ID is required for this guarded execution path'],errors=[]).__dict__
    try:
        contact=client.get('CONTACT',str(cid)); deal=client.get('DEAL',str(did))
        if not contact or not deal: return SyncResult('REVIEW_REQUIRED',str(cid),None,str(did),warnings=['Supplied IDs could not be verified'],errors=[]).__dict__
        assoc=client.association_exists(str(did),str(cid))
        created=False
        if not assoc:
            client.associate(str(did),str(cid)); created=True
        verified=bool(client.verify_association(str(did),str(cid)) if hasattr(client,'verify_association') else client.association_exists(str(did),str(cid)))
        return SyncResult('SYNCED' if verified else 'SYNC_FAILED',str(cid),None,str(did),False,False,False,created,verified,warnings,[] if verified else ['Association verification failed']).__dict__
    except Exception as exc:
        # Exception text is retained for diagnosis; credentials are never included by the client.
        return SyncResult('SYNC_FAILED',str(cid),None,str(did),warnings=warnings,errors=[f'{type(exc).__name__}: {exc}']).__dict__
