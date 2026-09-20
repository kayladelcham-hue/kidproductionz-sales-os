from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import database_v2 as db
from app.api.lifecycle import router
from app.api.models import Base, Campaign, Deal, ExternalAction, Prospect, User


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    engine = create_engine(
        'sqlite:///' + str(tmp_path / 'lifecycle.db'),
        connect_args={'check_same_thread': False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, 'SessionLocal', sessions)
    with sessions.begin() as session:
        owner = User(email='owner@example.com', name='Owner', password_hash='x', status='ACTIVE')
        other = User(email='other@example.com', name='Other', password_hash='x', status='ACTIVE')
        session.add_all([owner, other])
        session.flush()
        campaign = Campaign(slug='sales', name='Sales', owner_id=owner.id)
        other_campaign = Campaign(slug='other', name='Other', owner_id=other.id)
        session.add_all([campaign, other_campaign])
        session.flush()
        contact = Prospect(
            campaign_id=campaign.id,
            name='Skye Creator',
            email='skye@example.com',
            lifecycle_stage='PROSPECT',
            sales_status='CONTACTED',
            queue='RESEARCH',
        )
        hidden = Prospect(
            campaign_id=other_campaign.id,
            name='Hidden Creator',
            lifecycle_stage='PROSPECT',
            sales_status='NOT_CONTACTED',
            queue='DAILY_QUEUE',
        )
        session.add_all([contact, hidden])
        session.flush()
        session.add(ExternalAction(prospect_id=contact.id, action_type='CALL_LOGGED', metadata_json='{}'))
        ids = {'owner': owner.id, 'other': other.id, 'contact': contact.id, 'hidden': hidden.id}

    app = FastAPI()

    @app.middleware('http')
    async def identify(request: Request, call_next):
        request.state.user_id = int(request.headers.get('x-test-user', ids['owner']))
        return await call_next(request)

    app.include_router(router)
    return TestClient(app), sessions, ids


def test_conversion_preserves_contact_history_and_owner_scope(lifecycle):
    client, sessions, ids = lifecycle
    response = client.post(
        f"/api/lifecycle/contacts/{ids['contact']}/convert-to-lead",
        json={'opportunity_name': 'Creator package', 'deal_value': 2500},
    )
    assert response.status_code == 200
    deal_id = response.json()['deal']['id']
    with sessions() as session:
        assert session.scalar(select(Prospect).where(Prospect.id == ids['contact'])).lifecycle_stage == 'LEAD'
        assert session.scalar(select(Deal).where(Deal.id == deal_id)).prospect_id == ids['contact']
        assert session.scalar(select(ExternalAction).where(ExternalAction.action_type == 'CALL_LOGGED')) is not None
        assert len(session.scalars(select(Prospect).where(Prospect.email == 'skye@example.com')).all()) == 1

    assert client.get('/api/deals').json()[0]['id'] == deal_id
    assert client.get('/api/deals', headers={'x-test-user': str(ids['other'])}).json() == []
    assert client.get(f'/api/deals/{deal_id}', headers={'x-test-user': str(ids['other'])}).status_code == 404


def test_won_deal_promotes_same_contact_and_keeps_revenue_separate(lifecycle):
    client, sessions, ids = lifecycle
    deal = client.post(
        f"/api/lifecycle/contacts/{ids['contact']}/convert-to-lead",
        json={'deal_value': 3000},
    ).json()['deal']
    assert client.patch(
        f"/api/deals/{deal['id']}",
        json={'stage': 'WON', 'revenue_collected': 900},
    ).status_code == 200
    customer = client.get('/api/lifecycle/contacts?stage=CUSTOMER&campaign=sales').json()[0]
    assert customer['id'] == ids['contact']
    report = client.get('/api/sales-revenue?campaign=sales&period=30d').json()
    assert report['revenue_won'] == 3000
    assert report['revenue_collected'] == 900
    repeat = client.post(
        f"/api/customers/{ids['contact']}/opportunities",
        json={'name': 'Repeat campaign', 'deal_value': 1200},
    )
    assert repeat.status_code == 200
    assert repeat.json()['prospect_id'] == ids['contact']
    with sessions() as session:
        assert len(session.scalars(select(Deal).where(Deal.prospect_id == ids['contact'])).all()) == 2
