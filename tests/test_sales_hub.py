import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api import database_v2 as db, sales_hub as hub
from app.api.models import Base, CalendarEvent, ExternalAction

@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'hub.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db, 'SessionLocal', sessionmaker(bind=engine, expire_on_commit=False))
    db.create_campaign({'slug': 'one', 'name': 'One'})
    db.create_campaign({'slug': 'two', 'name': 'Two'})
    app = FastAPI()
    app.include_router(hub.router)
    return TestClient(app)

def add(client, **kwargs):
    return client.post('/api/prospects/manual', json=dict(campaign='one', name='Street prospect', phone='407-555-0100', **kwargs))

def test_intake_dedupe_queue_and_campaign(client):
    response = add(client, notes='Met at a cafe')
    assert response.status_code == 200
    p = db.list_prospects('one')[0]
    assert p['queue'] == 'RESEARCH' and p['sales_status'] == 'CONTACTED'
    assert p['notes'] == 'Met at a cafe'
    assert add(client).status_code == 409
    assert client.post('/api/prospects/manual', json={'campaign':'one','name':'Other','email':'HELLO@example.com'}).status_code == 200
    assert client.post('/api/prospects/manual', json={'campaign':'one','name':'Other again','email':'hello@EXAMPLE.com'}).status_code == 409
    assert client.post('/api/prospects/manual', json={'campaign':'two','name':'Other','phone':'4075550100'}).status_code == 200
    assert len(db.list_prospects('one')) == 2
    assert client.post('/api/prospects/manual', json={'campaign':'missing','name':'Other','phone':'4075550100'}).status_code == 404
    assert client.post('/api/prospects/manual', json={'campaign':'one','name':'  '}).status_code == 400

def test_next_action_scoping_and_hub(client):
    pid = add(client).json()['id']
    payload = {'campaign':'two','status':'FOLLOW_UP','notes':'Call tomorrow','action':'Call','due_at':'2026-09-19T10:00:00-04:00'}
    assert client.post(f'/api/prospects/{pid}/next-action', json=payload).status_code == 404
    payload['campaign'] = 'one'
    assert client.post(f'/api/prospects/{pid}/next-action', json=payload).status_code == 200
    row = client.get('/api/follow-ups?campaign=one').json()[0]
    assert row['next_action']['due_at'] == '2026-09-19T14:00:00+00:00'
    assert row['notes'] == 'Call tomorrow'
    assert client.get('/api/follow-ups?campaign=two').json() == []
    assert db.list_prospects('one')[0]['queue'] == 'RESEARCH'
    payload['due_at'] = '2026-09-19T10:00'
    assert client.post(f'/api/prospects/{pid}/next-action', json=payload).status_code == 400

def test_reschedule_preview_gates_failure_and_success(client, monkeypatch):
    pid = add(client).json()['id']
    with db.session_scope() as s:
        e = CalendarEvent(prospect_id=pid, provider='GOOGLE', calendar_event_id='remote-id', consultation_start='2026-09-19T10:00:00+00:00')
        s.add(e); s.flush(); eid = e.id
    calls = []
    monkeypatch.setattr(hub.google_service, 'reschedule_calendar_event', lambda *args: calls.append(args))
    body = {'campaign':'one','start':'2026-09-20T10:00','end':'2026-09-20T10:30','timezone':'America/New_York'}
    path = f'/api/follow-ups/events/{eid}/reschedule'
    assert client.post(path, json=body).json()['status'] == 'PREVIEW'
    assert calls == []
    body['confirmed'] = True
    monkeypatch.setenv('GOOGLE_CALENDAR_ENABLED', 'false')
    assert client.post(path, json=body).status_code == 403
    monkeypatch.setenv('GOOGLE_CALENDAR_ENABLED', 'true')
    body['campaign'] = 'two'
    assert client.post(path, json=body).status_code == 404
    body['campaign'] = 'one'
    def fail(*args): raise RuntimeError('provider failed')
    monkeypatch.setattr(hub.google_service, 'reschedule_calendar_event', fail)
    assert client.post(path, json=body).status_code == 503
    with db.SessionLocal() as s:
        assert s.get(CalendarEvent, eid).consultation_start == '2026-09-19T10:00:00+00:00'
    monkeypatch.setattr(hub.google_service, 'reschedule_calendar_event', lambda *args: calls.append(args))
    assert client.post(path, json=body).status_code == 200
    assert calls[0][0] == 'remote-id'
    assert calls[0][1]['start']['dateTime'].endswith('-04:00')
    assert db.list_prospects('one')[0]['sales_status'] == 'CONSULTATION_SET'
    assert len(client.get('/api/follow-ups?campaign=one').json()[0]['events']) == 1

def test_cloud_auth_and_csrf(client, monkeypatch):
    from app.api.main import app
    monkeypatch.setenv('KIDPRODUCTIONZ_AUTH_MODE', 'cloud')
    monkeypatch.setenv('KIDPRODUCTIONZ_AUTH_USERNAME', 'test-user')
    monkeypatch.setenv('KIDPRODUCTIONZ_AUTH_PASSWORD', 'test-password')
    cloud = TestClient(app)
    body = {'campaign':'one','name':'Cloud prospect','phone':'4075550123'}
    assert cloud.post('/api/prospects/manual', json=body).status_code == 401
    assert cloud.post('/api/auth/login', json={'username':'test-user','password':'test-password'}).status_code == 200
    assert cloud.post('/api/prospects/manual', json=body).status_code == 403
    token = cloud.get('/api/auth/csrf').json()['csrf_token']
    assert cloud.post('/api/prospects/manual', json=body, headers={'X-CSRF-Token':token}).status_code == 200
