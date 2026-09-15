import os
import pytest
from app.api.main import sync_hubspot,ProspectInput
from fastapi import HTTPException
from app.api.hubspot_sync_service import execute

def test_sync_requires_confirmation(monkeypatch):
    with pytest.raises(HTTPException) as e: sync_hubspot(ProspectInput(name='T'),False)
    assert e.value.status_code==400
def test_sync_disabled_by_default(monkeypatch):
    monkeypatch.delenv('HUBSPOT_WRITE_ENABLED',raising=False)
    with pytest.raises(HTTPException) as e: sync_hubspot(ProspectInput(name='T'),True)
    assert e.value.status_code==403

class Client:
    def __init__(self,assoc=False,verify=True): self.assoc=assoc; self.verify=verify
    def get(self,t,i): return {'id':i}
    def association_exists(self,*a):
        if not self.assoc: self.assoc=True; return False
        return self.verify
    def associate(self,*a): self.assoc=True
def test_existing_association_syncs():
    c=Client(True); r=execute({'hubspot_contact_id':'1','hubspot_deal_id':'2'},c); assert r['sync_status']=='SYNCED'
def test_missing_association_is_created():
    c=Client(False); r=execute({'hubspot_contact_id':'1','hubspot_deal_id':'2'},c); assert r['association_created'] and r['association_verified']
def test_verification_failure_not_synced():
    c=Client(True,False); r=execute({'hubspot_contact_id':'1','hubspot_deal_id':'2'},c); assert r['sync_status']=='SYNC_FAILED'
