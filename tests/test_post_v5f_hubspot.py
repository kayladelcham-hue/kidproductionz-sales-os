from app.api.hubspot_service import preview
from app.api.hubspot_client import HubSpotClient

def test_preview_with_email_is_ready_without_writes():
    r=preview({'name':'Example','email':'owner@example.com'})
    assert r['sync_status']=='READY_TO_SYNC'
    assert r['decision_type']=='CREATE_NEW'
    assert any('Create' in op and 'explicit approval' in op for op in r['proposed_operations'])
    assert not any('id' in str(v).lower() for v in r['existing_matches'].values())

def test_preview_without_identifier_requires_review():
    r=preview({'name':'Example'})
    assert r['sync_status']=='REVIEW_REQUIRED'
    assert r['warnings']

def test_existing_ids_are_preserved():
    r=preview({'name':'Example','hubspot_contact_id':'123','hubspot_deal_id':'456'})
    assert r['existing_matches']=={'hubspot_contact_id':'123','hubspot_deal_id':'456'}
    assert r['sync_status']=='READY_TO_SYNC'
    assert r['decision_type']=='UPDATE_EXISTING'

def test_create_payloads_without_network(monkeypatch):
    monkeypatch.setenv('HUBSPOT_PIPELINE_ID', 'pipeline-internal-test')
    monkeypatch.setenv('HUBSPOT_STAGE_ID', 'stage-internal-test')
    c=HubSpotClient(token='x',base_url='http://example.invalid')
    seen=[]; c._request=lambda method,path,payload=None: seen.append((method,path,payload)) or {'id':'10'}
    assert c.create_contact({'name':'Salon','email':'a@b.com','phone':'1'})['id']=='10'
    assert c.create_deal({'name':'Salon'})['id']=='10'
    assert [x[1] for x in seen]==['/crm/v3/objects/contacts','/crm/v3/objects/deals']
