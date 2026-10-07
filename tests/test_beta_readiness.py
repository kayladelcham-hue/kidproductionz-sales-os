import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api import database_v2 as db, main as api, sales_hub as hub
from app.api.models import Base, User

@pytest.fixture
def accounts(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'_auth_attempts',{})
    engine=create_engine('sqlite:///'+str(tmp_path/'beta.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db,'SessionLocal',sessionmaker(bind=engine,expire_on_commit=False))
    monkeypatch.setattr(db,'engine',engine)
    monkeypatch.setenv('KIDPRODUCTIONZ_AUTH_MODE','cloud')
    monkeypatch.setenv('KIDPRODUCTIONZ_BETA_INVITE_CODE','isolated-audit-invite')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('GMAIL_ENABLED','false')
    monkeypatch.setenv('GOOGLE_CALENDAR_ENABLED','false')
    monkeypatch.setenv('HUBSPOT_WRITE_ENABLED','false')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setenv('APP_ENV_FILE',str(tmp_path/'isolated.env'))
    clients=[]
    for label in ['alice','bob']:
        c=TestClient(api.app,raise_server_exceptions=False)
        assert c.post('/api/auth/signup',json={'email':label+'@example.test','password':'IsolatedTestPassword!','invite_code':'isolated-audit-invite'}).status_code==200
        assert c.post('/api/auth/login',json={'username':label+'@example.test','password':'IsolatedTestPassword!'}).status_code==200
        c.headers['X-CSRF-Token']=c.get('/api/auth/csrf').json()['csrf_token']
        db.create_campaign({'slug':label,'name':label,'city':'Orlando','state':'FL','category':'salon'},db.get_user_by_email(label+'@example.test')['id'])
        pid=c.post('/api/prospects/manual',json={'campaign':label,'name':label+' synthetic salon','phone':'4075550100'}).json()['id']
        clients.append((c,pid))
    return clients

def test_signup_login_logout_relogin_and_csrf(accounts):
    a,pid=accounts[0]
    anonymous=TestClient(api.app)
    assert anonymous.get('/api/prospects?campaign=alice').status_code==401
    assert anonymous.post('/api/auth/signup',json={'email':'outsider@example.test','password':'IsolatedTestPassword!','invite_code':'wrong'}).status_code==403
    assert anonymous.post('/api/auth/login',json={'username':'alice@example.test','password':'wrong'}).status_code==401
    assert anonymous.post('/api/auth/signup',json={'email':'alice@example.test','password':'IsolatedTestPassword!','invite_code':'isolated-audit-invite'}).status_code==409
    a.headers.pop('X-CSRF-Token')
    assert a.patch(f'/api/prospects/{pid}/activity',json={'notes':'blocked'}).status_code==403
    assert a.post('/api/auth/logout').status_code==200
    assert a.get('/api/auth/me').json()['authenticated'] is False
    assert a.get('/api/prospects?campaign=alice').status_code==401
    assert a.post('/api/auth/login',json={'username':'alice@example.test','password':'IsolatedTestPassword!'}).status_code==200

def test_lead_notes_followup_and_lifecycle_persist(accounts):
    a,pid=accounts[0]
    assert a.patch(f'/api/prospects/{pid}/activity',json={'status':'FOLLOW_UP','notes':'Call Tuesday'}).status_code==200
    assert a.post(f'/api/prospects/{pid}/next-action',json={'campaign':'alice','status':'FOLLOW_UP','notes':'Confirmed notes','action':'Call','due_at':'2026-10-06T10:00:00-04:00'}).status_code==200
    assert a.get('/api/follow-ups?campaign=alice').json()[0]['notes']=='Confirmed notes'
    assert a.get('/api/prospects?campaign=alice').json()[0]['notes']=='Confirmed notes'
    d=a.post(f'/api/lifecycle/contacts/{pid}/convert-to-lead',json={'deal_value':2500}).json()['deal']
    assert a.patch(f"/api/deals/{d['id']}",json={'stage':'WON','revenue_collected':500}).status_code==200
    report=a.get('/api/sales-revenue?campaign=alice&period=30d').json()
    assert report['revenue_won']==2500 and report['revenue_collected']==500
    a.post('/api/auth/logout');a.post('/api/auth/login',json={'username':'alice@example.test','password':'IsolatedTestPassword!'})
    assert a.get('/api/prospects?campaign=alice').json()[0]['notes']=='Confirmed notes'

def test_cross_user_leads_campaigns_followups_deals_and_ai_denied(accounts):
    a,pid=accounts[0];b,bpid=accounts[1]
    assert [x['campaign_id'] for x in b.get('/api/campaigns').json()]==['bob']
    assert b.get('/api/prospects?campaign=alice').json()==[]
    assert b.get('/api/follow-ups?campaign=alice').json()==[]
    assert b.get('/api/campaigns/alice').status_code==404
    assert b.patch(f'/api/prospects/{pid}/activity',json={'notes':'bad'}).status_code==404
    assert b.post(f'/api/prospects/{pid}/next-action',json={'campaign':'alice','status':'FOLLOW_UP','action':'Call'}).status_code==404
    assert b.post('/api/ai/chat',json={'campaign':'alice','message':'who should I call'}).status_code==404
    d=a.post(f'/api/lifecycle/contacts/{pid}/convert-to-lead',json={'deal_value':2500}).json()['deal']
    assert b.get(f"/api/deals/{d['id']}").status_code==404
    assert b.patch(f"/api/deals/{d['id']}",json={'stage':'WON'}).status_code==404

def test_google_calendar_is_account_scoped(accounts,monkeypatch):
    a,pid=accounts[0];b,_=accounts[1]
    from app.api import request_context
    token=request_context.user_id.set(db.get_user_by_email('alice@example.test')['id'])
    try: db.save_google_connection({'access_token':'SYNTHETIC_ALICE_TOKEN','status':'CONNECTED'})
    finally: request_context.user_id.reset(token)
    monkeypatch.setenv('GOOGLE_CALENDAR_ENABLED','true')
    monkeypatch.setattr(api.google_service,'upcoming_calendar_events',lambda:[{'title':'Alice private synthetic meeting'}] if db.load_google_connection() else [])
    assert a.get('/api/integrations/calendar/upcoming').json()['events']
    assert b.get('/api/integrations/calendar/upcoming').json()['events']==[]
    assert b.get('/api/integrations/calendar/upcoming').json()['status']=='NOT_CONNECTED'

def test_booking_settings_are_account_scoped(accounts):
    a,_=accounts[0];b,_=accounts[1]
    assert a.post('/api/settings/booking',json={'booking_url':'https://example.test/alice','provider':'test'}).status_code==200
    assert b.get('/api/settings/booking').json()['booking_url']!='https://example.test/alice'

def test_nonadmin_cannot_change_shared_hubspot_configuration(accounts):
    a,_=accounts[0];b,_=accounts[1]
    assert b.post('/api/settings/hubspot',json={'portal_id':'synthetic-other-portal'}).status_code==200
    assert b.get('/api/settings/hubspot').json()['portal_id']=='synthetic-other-portal'
    assert a.get('/api/settings/hubspot').json()['portal_id']!='synthetic-other-portal'

def test_inactive_user_cannot_login_or_use_existing_session(accounts):
    a,_=accounts[0]
    with db.SessionLocal.begin() as s:
        u=s.query(User).filter(User.email=='alice@example.test').one();u.status='DISABLED'
    assert a.get('/api/campaigns').status_code==401
    assert a.post('/api/auth/login',json={'username':'alice@example.test','password':'IsolatedTestPassword!'}).status_code==401

def test_hubspot_batch_preview_works(accounts,monkeypatch):
    a,_=accounts[0]
    monkeypatch.setattr(api,'preview',lambda data:{'decision_type':'NO_CHANGE','sync_status':'READY_TO_SYNC'})
    assert a.post('/api/hubspot/batch-preview',json={'campaign':'alice'}).status_code==200

def test_skye_receives_real_priority_queue_and_followup(accounts,monkeypatch):
    a,pid=accounts[0]
    with db.SessionLocal.begin() as s:
        from app.api.models import Prospect
        p=s.get(Prospect,pid);p.queue='DAILY_QUEUE';p.sales_status='FOLLOW_UP'
    assert a.post(f'/api/prospects/{pid}/next-action',json={'campaign':'alice','status':'FOLLOW_UP','notes':'Tuesday','action':'Call','due_at':'2026-10-06T10:00:00-04:00'}).status_code==200
    captured={}
    def fake_chat(**kw): captured.update(kw);return {'reply':'isolated','intent':'QUEUE_ANALYSIS'}
    monkeypatch.setattr(hub.ai_sales_bot,'chat',fake_chat)
    assert a.post('/api/ai/chat',json={'campaign':'alice','message':'Who should I call first?'}).status_code==200
    assert captured['context']['queue']['daily_queue'][0]['id']==pid
    assert captured['context']['follow_ups'][0]['next_action']['action']=='Call'

def test_email_calendar_confirmations_and_provider_calls(accounts,monkeypatch):
    a,pid=accounts[0];b,_=accounts[1]
    calls=[]
    monkeypatch.setattr(api.google_service,'send_gmail',lambda *args:calls.append(('email',args)) or {'id':'synthetic-mail'})
    monkeypatch.setattr(api.google_service,'create_calendar_event',lambda doc:calls.append(('calendar',doc)) or {'id':'synthetic-event','htmlLink':'https://example.test/event'})
    email={'prospect_id':pid,'to':'synthetic@example.test','subject':'Test','body':'Test'}
    assert a.post('/api/integrations/gmail/send',json=email).status_code==400
    email['confirmed']=True
    assert a.post('/api/integrations/gmail/send',json=email).status_code==403
    assert calls==[]
    monkeypatch.setenv('GMAIL_ENABLED','true')
    assert b.post('/api/integrations/gmail/send',json=email).status_code==404
    assert a.post('/api/integrations/gmail/send',json=email).status_code==200
    event={'prospect_id':pid,'consultation_start':'2026-10-06T10:00:00-04:00','consultation_end':'2026-10-06T10:30:00-04:00','timezone':'America/New_York','confirmed':True}
    monkeypatch.setenv('GOOGLE_CALENDAR_ENABLED','true')
    assert a.post('/api/integrations/calendar/create',json=event).status_code==200
    assert [x[0] for x in calls]==['email','calendar']


def test_campaign_creation_api(accounts):
    a,_=accounts[0]
    assert a.post('/api/campaigns',json={'campaign_id':'new_campaign','name':'New Campaign','city':'Orlando','state':'FL','category':'salon'}).status_code==200

def test_google_oauth_callback_requires_authenticated_state(accounts,monkeypatch):
    calls=[]
    monkeypatch.setattr(api.google_service,'callback',lambda code:calls.append(code) or {'status':'CONNECTED'})
    anonymous=TestClient(api.app)
    response=anonymous.get('/api/google/oauth/callback?code=synthetic-code&state=wrong-state')
    assert response.status_code in [400,401,403]
    assert calls==[]

def test_static_file_fallback_rejects_encoded_parent_traversal(accounts,tmp_path,monkeypatch):
    dist=tmp_path/'site'/'dist';dist.mkdir(parents=True)
    (dist/'index.html').write_text('synthetic index')
    (dist.parent/'private-marker.txt').write_text('SYNTHETIC_PRIVATE_DATA')
    monkeypatch.setattr(api,'FRONTEND_DIST',dist)
    c=TestClient(api.app)
    response=c.get('/%2e%2e/private-marker.txt')
    assert 'SYNTHETIC_PRIVATE_DATA' not in response.text

def test_runs_are_owner_scoped(accounts,tmp_path,monkeypatch):
    a,_=accounts[0];b,_=accounts[1]
    monkeypatch.setattr(api,'ARTIFACT_ROOT',tmp_path)
    run=tmp_path/'v5_runs'/'alice';run.mkdir(parents=True)
    (run/'run_v1.json').write_text(json.dumps({'owner':'alice','synthetic_private_artifact':True}))
    assert b.get('/api/runs').json()==[]

def test_production_cookie_security(accounts,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    c=TestClient(api.app,base_url='https://testserver')
    r=c.post('/api/auth/login',json={'username':'alice@example.test','password':'IsolatedTestPassword!'})
    assert r.status_code==200
    cookie=r.headers['set-cookie'].lower()
    assert 'secure' in cookie and 'httponly' in cookie and 'samesite=none' in cookie
    assert c.get('/api/auth/me').json()['authenticated']

def test_csrf_recovers_after_process_cache_reset(accounts):
    a,pid=accounts[0]
    api._csrf_tokens.clear()
    assert a.patch(f'/api/prospects/{pid}/activity',json={'notes':'stale token'}).status_code==403
    a.headers['X-CSRF-Token']=a.get('/api/auth/csrf').json()['csrf_token']
    assert a.patch(f'/api/prospects/{pid}/activity',json={'notes':'refreshed'}).status_code==200

def test_expired_session_is_rejected(accounts):
    a,_=accounts[0]
    from app.api.models import UserSession
    with db.SessionLocal.begin() as s:
        row=s.query(UserSession).filter(UserSession.user_id==db.get_user_by_email('alice@example.test')['id']).one()
        row.expires_at='2000-01-01T00:00:00+00:00'
    assert a.get('/api/auth/me').json()['authenticated'] is False
    assert a.get('/api/campaigns').status_code==401

def test_recovery_code_is_single_use_and_revokes_sessions(accounts):
    a,_=accounts[0];b,_=accounts[1]
    assert a.post('/api/auth/recovery-code',json={'password':'wrong'}).status_code==401
    code=a.post('/api/auth/recovery-code',json={'password':'IsolatedTestPassword!'}).json()['recovery_code']
    anonymous=TestClient(api.app)
    body={'username':'alice@example.test','recovery_code':code,'password':'NewIsolatedPassword!'}
    assert anonymous.post('/api/auth/recover',json={**body,'username':'bob@example.test'}).status_code==400
    assert anonymous.post('/api/auth/recover',json=body).status_code==200
    assert a.get('/api/campaigns').status_code==401
    assert b.get('/api/campaigns').status_code==200
    assert anonymous.post('/api/auth/recover',json=body).status_code==400
    assert anonymous.post('/api/auth/login',json={'username':'alice@example.test','password':'NewIsolatedPassword!'}).status_code==200

def test_authentication_attempts_are_bounded(accounts):
    anonymous=TestClient(api.app)
    for _ in range(15):
        assert anonymous.post('/api/auth/login',json={'username':'rate-test@example.test','password':'wrong'}).status_code==401
    assert anonymous.post('/api/auth/login',json={'username':'rate-test@example.test','password':'wrong'}).status_code==429

def test_oauth_state_binds_account_and_is_single_use(accounts,monkeypatch):
    a,_=accounts[0];b,_=accounts[1]
    calls=[]
    monkeypatch.setattr(api.google_service,'authorization_url',lambda state:'https://example.test/?state='+state)
    monkeypatch.setattr(api.google_service,'callback',lambda code:calls.append(code))
    state=a.get('/api/google/oauth/start').json()['authorization_url'].split('state=')[1]
    assert b.get('/api/google/oauth/callback',params={'code':'mock','state':state},follow_redirects=False).status_code==400
    assert a.get('/api/google/oauth/callback',params={'code':'mock','state':state},follow_redirects=False).status_code==303
    assert a.get('/api/google/oauth/callback',params={'code':'mock','state':state},follow_redirects=False).status_code==400
    assert calls==['mock']

def test_uploads_are_private_and_discovery_is_managed(accounts,monkeypatch):
    a,_=accounts[0];b,_=accounts[1]
    upload=a.post('/api/campaigns/upload',files={'file':('leads.csv',b'name,city,state,category\nTest,Orlando,FL,salon\n','text/csv')})
    assert upload.status_code==200
    ref=upload.json()['reference']
    assert b.post('/api/campaigns/run-preview',json={'campaign':'bob','input_file':ref}).status_code==404
    monkeypatch.setenv('KP_OUTSCRAPER_API_KEY','synthetic-managed-key')
    assert a.post('/api/settings/discovery',json={'api_key':'MOCK_ALICE_KEY'}).status_code==410
    for client in (a,b):
        info=client.get('/api/settings/discovery').json()
        assert info['configured'] and info['managed']
        assert 'synthetic-managed-key' not in str(info)
    bob=db.get_user_by_email('bob@example.test')['id']
    assert b.put(f'/api/admin/discovery/users/{bob}/tier',json={'tier':'pro'}).status_code==403
    with db.session_scope() as session:
        session.get(User,db.get_user_by_email('alice@example.test')['id']).is_admin=1
    assert a.put(f'/api/admin/discovery/users/{bob}/tier',json={'tier':'growth'}).status_code==200
    assert b.get('/api/settings/discovery').json()['monthly_limit']==1000
    assert a.get('/api/settings/discovery').json()['monthly_limit']==100

def test_managed_discovery_routes_enforce_allowances(accounts,monkeypatch):
    import io
    from app.api import outscraper_service
    a,_=accounts[0]
    monkeypatch.setenv('KP_OUTSCRAPER_API_KEY','synthetic-managed-key')
    monkeypatch.setenv('DISCOVERY_MONTHLY_BUDGET_USD','50')
    calls=[]
    def provider(request,timeout):
        calls.append(request)
        return io.BytesIO(b'{"data": []}')
    monkeypatch.setattr(outscraper_service,'urlopen',provider)
    assert a.post('/api/leads/outscraper/preview',json={'query':'synthetic first search','limit':100}).status_code==200
    assert a.post('/api/leads/outscraper/preview',json={'query':'synthetic second search','limit':1}).status_code==429
    assert a.post('/api/leads/outscraper/qualify-preview',json={'campaign':'alice','query':'synthetic third search','limit':1}).status_code==429
    assert len(calls)==1
    assert a.get('/api/settings/discovery').json()['remaining']==0

def test_custom_campaign_preview_and_duplicates(accounts):
    a,_=accounts[0]
    body={'campaign_id':'custom_salon','name':'Custom Salon','city':'Orlando','state':'FL','category':'salon'}
    assert a.post('/api/campaigns',json=body).status_code==200
    assert a.post('/api/campaigns',json=body).status_code==409
    assert a.post('/api/campaigns/run-preview',json={'campaign':'custom_salon'}).status_code==200
    listed=next(c for c in a.get('/api/campaigns').json() if c['campaign_id']=='custom_salon')
    assert (listed['city'],listed['state'],listed['category'])==('Orlando','FL','salon')

def test_run_bundle_persists_account_queue(accounts):
    from app.api import request_context
    from app.api.models import Run
    a,_=accounts[0];b,_=accounts[1]
    uid=db.get_user_by_email('alice@example.test')['id']
    token=request_context.user_id.set(uid)
    try:
        doc={'campaign_id':'alice','run_id':'alice-v1','overall_status':'COMPLETED_DRY_RUN','qualification_scoring_summary':{'qualified_count':1}}
        candidates=[{'name':'Uploaded synthetic lead','phone':'4075550123','city':'Orlando','state':'FL','queue_status':'DAILY_QUEUE','queue_position':1,'route':'CALL_FIRST','priority':'P1','score':80}]
        db.persist_run_bundle(doc,candidates,{'candidates':candidates,'summary':{'daily_queue_count':1}})
    finally: request_context.user_id.reset(token)
    assert any(p['name']=='Uploaded synthetic lead' for p in a.get('/api/queue?campaign=alice').json()['daily_queue'])
    assert b.get('/api/prospects?campaign=alice').json()==[]
    with db.SessionLocal() as session: assert session.query(Run).filter(Run.run_id=='alice-v1').one().campaign_id==db.get_campaign('alice',uid)['id']

def test_health_reports_database_failure(accounts,monkeypatch):
    def unavailable(): raise RuntimeError('synthetic outage')
    monkeypatch.setattr(api,'connect',unavailable)
    assert TestClient(api.app).get('/api/health').status_code==503


def test_beginner_discovery_through_real_auth_csrf_and_queue(accounts,monkeypatch):
    from app.api import outscraper_service
    a,_=accounts[0];b,_=accounts[1]
    monkeypatch.setattr(outscraper_service,'search_google_maps',lambda *args:{'leads':[{'name':'Synthetic fit business','category':'Salon','city':'Orlando','state':'FL','place_id':'synthetic-fit','phone':'5550100'}]})
    criteria={'industry':'Salon','city':'Orlando','state':'FL','limit':10}
    assert a.put('/api/discovery/target',json=criteria).status_code==200
    assert a.put('/api/icp/profile',json={'profile':{'offer':'Website design','business_types':['Salon'],'geography':['Orlando, FL']}}).status_code==200
    result=a.post('/api/discovery/searches',json={'campaign':'alice','criteria':criteria})
    assert result.status_code==200,result.text
    found=result.json();bid=found['businesses'][0]['id']
    assert b.get(f'/api/discovery/businesses/{bid}').status_code==404
    token=a.headers.pop('X-CSRF-Token')
    assert a.patch(f'/api/discovery/businesses/{bid}/qualification',json={'decision':'QUALIFIED','reason':'Fits my search','revision':0}).status_code==403
    a.headers['X-CSRF-Token']=token
    assert a.patch(f'/api/discovery/businesses/{bid}/qualification',json={'decision':'QUALIFIED','reason':'Fits my search','revision':0,'notes':'Check website first'}).status_code==200
    pid=a.post(f'/api/discovery/businesses/{bid}/save').json()['prospect_id']
    assert a.post(f'/api/discovery/businesses/{bid}/outreach').status_code==200
    assert any(row['prospect_id']==pid for row in a.get('/api/queue?campaign=alice').json()['daily_queue'])
    assert a.post('/api/auth/logout').status_code==200
    assert a.post('/api/auth/login',json={'username':'alice@example.test','password':'IsolatedTestPassword!'}).status_code==200
    detail=a.get(f'/api/discovery/businesses/{bid}').json()
    assert detail['decision']=='QUALIFIED' and detail['notes']=='Check website first' and detail['saved']
    assert a.post('/api/discovery/explain',json={'campaign':'alice','business_ids':[bid],'question':'Draft a first message.'}).status_code==403
    a.headers['X-CSRF-Token']=a.get('/api/auth/csrf').json()['csrf_token']
    draft=a.post('/api/discovery/explain',json={'campaign':'alice','business_ids':[bid],'question':'Draft a first message.'}).json()
    assert 'Website design' in draft['draft'] and 'Nothing has been sent' in draft['reply']
