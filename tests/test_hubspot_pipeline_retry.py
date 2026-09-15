from app.api.hubspot_client import HubSpotClient
from app.api.hubspot_sync_service import execute


def test_deal_requires_internal_pipeline_and_stage(monkeypatch):
    monkeypatch.delenv('HUBSPOT_PIPELINE_ID', raising=False)
    monkeypatch.delenv('HUBSPOT_STAGE_ID', raising=False)
    client = HubSpotClient(token='x')
    try:
        client.create_deal({'name': 'X'})
    except ValueError as exc:
        assert 'HUBSPOT_PIPELINE_ID' in str(exc)
    else:
        assert False


def test_partial_contact_is_reused_and_retry_creates_only_deal(monkeypatch):
    monkeypatch.setenv('HUBSPOT_PIPELINE_ID', 'p1')
    monkeypatch.setenv('HUBSPOT_STAGE_ID', 's1')

    class Client:
        def __init__(self):
            self.contacts = 0
            self.deals = 0
        def create_contact(self, prospect):
            self.contacts += 1
            return {'id': 'new-contact'}
        def create_deal(self, prospect):
            self.deals += 1
            return {'id': 'new-deal'}
        def associate(self, deal, contact): return None
        def verify_association(self, deal, contact): return True

    client = Client()
    result = execute({'name': 'X', 'email': 'x@example.com', 'hubspot_contact_id': 'partial-contact'}, client)
    assert result['sync_status'] == 'SYNCED'
    assert result['hubspot_contact_id'] == 'partial-contact'
    assert result['created_contact'] is False
    assert result['created_deal'] is True
    assert client.contacts == 0
    assert client.deals == 1

