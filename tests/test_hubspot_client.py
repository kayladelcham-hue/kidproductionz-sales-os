import pytest
from app.api.hubspot_client import HubSpotClient
def test_missing_token_fails(monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN',raising=False)
    with pytest.raises(ValueError): HubSpotClient()
def test_get_and_association_calls(monkeypatch):
    c=HubSpotClient('secret-token'); seen=[]
    def fake(method,path,payload=None,operation=None): seen.append((method,path,payload)); return {'results':[{'toObjectId':'2'}]} if 'associations' in path else {'id':'1'}
    monkeypatch.setattr(c,'_request',fake)
    assert c.get_contact('1')['id']=='1'; assert c.association_exists('3','2'); c.associate('3','2'); assert seen[-1][0:2]==('PUT','/crm/v3/objects/deals/3/associations/contacts/2/3'); assert seen[-1][2] is None
def test_secret_not_in_error(monkeypatch):
    c=HubSpotClient('secret-token'); monkeypatch.setattr(c,'_request',lambda *a: (_ for _ in ()).throw(RuntimeError('HUBSPOT_HTTP_401')))
    with pytest.raises(RuntimeError) as e: c.get_deal('1')
    assert 'secret-token' not in str(e.value)
def test_timeout_is_bounded(monkeypatch):
    c=HubSpotClient('secret-token',timeout=60); assert c.timeout==10
    monkeypatch.setattr(c,'_request',lambda *a: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(TimeoutError): c._request('GET','/x')
