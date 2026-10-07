import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.api import database_v2 as db, discovery as d, outscraper_service, request_context
from app.api.models import Base, Campaign, Prospect, User

CRITERIA={'industry':'Hair salon','city':'Orlando','state':'FL','limit':10}
BUSINESS={'name':'Synthetic Salon','category':'Hair salon','city':'Orlando','state':'FL','place_id':'synthetic-1','website':'https://salon.example','phone':'5550100'}

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('KIDPRODUCTIONZ_AUTH_MODE','cloud')
    engine=create_engine('sqlite:///'+str(tmp_path/'workflow.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False,autoflush=False)
    monkeypatch.setattr(db,'engine',engine);monkeypatch.setattr(db,'SessionLocal',sessions)
    with sessions.begin() as s:
        s.add_all([User(id=1,email='owner@example.com',name='Owner',password_hash='test'),User(id=2,email='other@example.com',name='Other',password_hash='test')])
        s.add_all([Campaign(id=1,slug='test',name='Test',owner_id=1),Campaign(id=2,slug='other',name='Other',owner_id=2)])
    app=FastAPI()
    @app.middleware('http')
    async def context(request:Request,call_next):
        token=request_context.user_id.set(int(request.headers.get('test-owner','1')))
        try:return await call_next(request)
        finally:request_context.user_id.reset(token)
    app.include_router(d.router)
    monkeypatch.setattr(outscraper_service,'search_google_maps',lambda *a,**k:{'leads':[BUSINESS]})
    with TestClient(app) as c:yield c,sessions
    engine.dispose()

def search(c,**criteria):
    r=c.post('/api/discovery/searches',json={'campaign':'test','criteria':{**CRITERIA,**criteria}})
    assert r.status_code==200,r.text
    return r.json()

def decision(c,bid,value='QUALIFIED',revision=0,**kw):
    return c.patch(f'/api/discovery/businesses/{bid}/qualification',json={'decision':value,'revision':revision,'reason':'Looks useful for my offer','notes':'Check website first',**kw})

def test_full_persistent_search_decision_save_outreach_and_undo(client):
    c,sessions=client
    assert c.put('/api/discovery/target',json=CRITERIA).status_code==200
    assert c.get('/api/discovery/target').json()['criteria']['city']=='Orlando'
    found=search(c);bid=found['businesses'][0]['id']
    assert c.get(f"/api/discovery/searches/{found['id']}").json()['criteria']==found['criteria']
    assert c.patch(f"/api/discovery/searches/{found['id']}",json={'saved':True}).status_code==200
    assert c.get('/api/discovery/searches?campaign_slug=test').json()[0]['saved']
    assert c.post(f'/api/discovery/businesses/{bid}/save').status_code==409
    q=decision(c,bid).json()
    loaded=c.get(f'/api/discovery/businesses/{bid}').json()
    assert loaded['decision']=='QUALIFIED' and loaded['notes']=='Check website first' and len(loaded['history'])==1
    saved=c.post(f'/api/discovery/businesses/{bid}/save').json()
    assert c.post(f'/api/discovery/businesses/{bid}/save').json()['prospect_id']==saved['prospect_id']
    assert search(c)['businesses'][0]['id']==bid
    assert len(c.get('/api/discovery/saved?campaign_slug=test').json())==1
    with sessions() as s:assert s.scalar(select(func.count()).select_from(Prospect))==1
    draft=c.post('/api/discovery/explain',json={'campaign':'test','business_ids':[bid],'question':'Draft a first message.'}).json()
    assert 'Synthetic Salon' in draft['draft'] and '[your product or service]' in draft['draft'] and 'Nothing has been sent' in draft['reply']
    assert c.post(f'/api/discovery/businesses/{bid}/outreach').status_code==200
    assert c.get('/api/discovery/outreach?campaign_slug=test').json()==[saved['prospect_id']]
    undo=c.post(f'/api/discovery/businesses/{bid}/undo',json={'event_id':q['undo_event'],'revision':q['revision']})
    assert undo.json()['decision']=='UNREVIEWED' and undo.json()['saved']
    assert c.get('/api/discovery/outreach?campaign_slug=test').json()==[]

def test_owner_isolation_every_record_route(client):
    c,_=client;found=search(c);bid=found['businesses'][0]['id'];sid=found['id'];headers={'test-owner':'2'}
    for url in [f'/api/discovery/businesses/{bid}',f'/api/discovery/searches/{sid}','/api/discovery/saved?campaign_slug=test','/api/discovery/searches?campaign_slug=test']:
        assert c.get(url,headers=headers).status_code==404
    for action in ['save','outreach','undo']:
        assert c.post(f'/api/discovery/businesses/{bid}/{action}',headers=headers,json={'event_id':1,'revision':0}).status_code==404
    assert decision(c,bid).status_code==200
    assert c.patch(f'/api/discovery/businesses/{bid}/qualification',headers=headers,json={'decision':'QUALIFIED','revision':1,'reason':'x'}).status_code==404
    assert c.get('/api/discovery/target',headers={'test-owner':'0'}).status_code==401

def test_partial_duplicates_empty_and_exact_provider_request(client,monkeypatch):
    c,_=client;calls=[]
    def provider(*args):
        calls.append(args);return {'leads':[BUSINESS,BUSINESS,{},dict(BUSINESS,name='Other',place_id='other',city='Miami')]}
    monkeypatch.setattr(outscraper_service,'search_google_maps',provider)
    found=search(c,min_rating=4,min_reviews=10)
    assert calls==[('Hair salon in Orlando, FL',10,'Hair salon')]
    assert found['status']=='PARTIAL' and found['duplicates']==1 and found['skipped']==1 and len(found['businesses'])==2
    assert found['businesses'][0]['assessment']['label']=='Needs evidence'
    assert found['businesses'][1]['assessment']['label']=='Outside criteria'
    monkeypatch.setattr(outscraper_service,'search_google_maps',lambda *a:{'leads':[]})
    assert search(c)['businesses']==[]

def test_failure_persists_criteria_and_retry_id_is_idempotent(client,monkeypatch):
    c,_=client;sid=str(uuid.uuid4());body={'id':sid,'campaign':'test','criteria':CRITERIA}
    from fastapi import HTTPException
    monkeypatch.setattr(outscraper_service,'search_google_maps',lambda *a:(_ for _ in ()).throw(HTTPException(503,'Server discovery key is missing')))
    assert c.post('/api/discovery/searches',json=body).status_code==503
    failed=c.get(f'/api/discovery/searches/{sid}').json()
    assert failed['status']=='FAILED' and failed['criteria']['city']=='Orlando' and 'key' in failed['error']
    assert c.post('/api/discovery/searches',json=body).json()['id']==sid

def test_optimistic_conflicts_and_old_undo_rejected(client):
    c,_=client;bid=search(c)['businesses'][0]['id']
    first=decision(c,bid).json()
    assert decision(c,bid,revision=0).status_code==409
    assert decision(c,bid,value='DISQUALIFIED',revision=1).status_code==200
    assert c.post(f'/api/discovery/businesses/{bid}/undo',json={'event_id':first['undo_event'],'revision':2}).status_code==409
    assert c.post(f'/api/discovery/businesses/{bid}/save').status_code==409

def test_bulk_saves_only_individual_fit_decisions(client,monkeypatch):
    c,_=client
    monkeypatch.setattr(outscraper_service,'search_google_maps',lambda *a:{'leads':[BUSINESS,dict(BUSINESS,name='Second',place_id='two')]})
    rows=search(c)['businesses'];decision(c,rows[0]['id'])
    result=c.post('/api/discovery/save-qualified',json={'business_ids':[r['id'] for r in rows]}).json()
    assert result[0]['result']['saved'] and result[1]['error']
    assert c.get(f"/api/discovery/businesses/{rows[1]['id']}").json()['decision']=='UNREVIEWED'

def test_legacy_real_record_preserved_and_deduped(client):
    c,sessions=client
    with sessions.begin() as s:
        p=Prospect(campaign_id=1,name=BUSINESS['name'],city='Orlando',state='FL',notes='Original notes',sales_status='CONTACTED');s.add(p);s.flush();pid=p.id
    assert c.get('/api/discovery/saved?campaign_slug=test').json()[0]['id']==f'legacy:{pid}'
    bid=search(c)['businesses'][0]['id'];decision(c,bid)
    assert c.post(f'/api/discovery/businesses/{bid}/save').json()['prospect_id']==pid
    with sessions() as s:
        assert s.get(Prospect,pid).notes=='Original notes' and s.get(Prospect,pid).sales_status=='CONTACTED'

def test_malformed_and_unsupported_data_stays_unknown():
    q=d.assessment({**BUSINESS,'website':'http://[','rating':'bad','reviews':'NaN','minimum_budget':500}, {**CRITERIA,'min_rating':4,'min_reviews':10,'website_required':True},{'minimum_budget':500,'company_size':'Small'})
    assert q['label']=='Needs evidence'
    assert all(x['status']=='UNKNOWN' for x in q['criteria'] if x['criterion'] in ['Minimum rating','Minimum review count','Website available','Minimum budget','Company size'])
    assert 'website' not in q['contact_paths']


def test_query_category_is_not_recorded_evidence():
    row=outscraper_service.normalize_place({'name':'Unknown business','city':'Orlando','state':'FL'},'Hair salon')
    q=d.assessment(row,CRITERIA)
    assert q['criteria'][0]['status']=='UNKNOWN'
    assert q['label']=='Needs evidence'


def test_first_use_skye_help_does_not_require_a_campaign(client):
    c,_=client
    response=c.post('/api/discovery/explain',json={'campaign':'not-created','question':'Find potential customers for what I sell.'})
    assert response.status_code==200 and 'Help me figure this out' in response.json()['reply']

def test_industry_matches_whole_words():
    assert d.assessment({'category':'Carpet store'}, {'industry':'Car'})['criteria'][0]['status']=='MISMATCH'


def test_local_desktop_saved_records_remain_accessible(client,monkeypatch):
    c,sessions=client;monkeypatch.setenv('KIDPRODUCTIONZ_AUTH_MODE','local')
    with sessions.begin() as s:
        s.add(Campaign(id=3,slug='local',name='Local',owner_id=None))
        p=Prospect(campaign_id=3,name='Local saved business',notes='Keep local notes');s.add(p);s.flush();pid=p.id
    headers={'test-owner':'0'}
    assert c.get('/api/discovery/target',headers=headers).status_code==200
    assert c.get('/api/discovery/saved?campaign_slug=local',headers=headers).json()[0]['prospect_id']==pid
    assert c.post(f'/api/discovery/legacy/{pid}/review',headers=headers).status_code==200


def test_concurrent_searches_and_saves_do_not_duplicate(client):
    c,sessions=client
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:search(c),range(3)))
    ids={r['businesses'][0]['id'] for r in results}
    assert len(ids)==1
    bid=ids.pop();assert decision(c,bid).status_code==200
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:c.post(f'/api/discovery/businesses/{bid}/save'),range(3)))
    assert all(r.status_code==200 for r in results)
    assert len({r.json()['prospect_id'] for r in results})==1
    with sessions() as s:assert s.scalar(select(func.count()).select_from(Prospect))==1

def test_exclusions_remain_in_qualification_criteria():
    q=d.assessment(BUSINESS,CRITERIA,{'excluded_geographies':['Orlando, FL']})
    assert q['label']=='Outside criteria'
    assert q['criteria'][-1]['status']=='MISMATCH'


def test_interrupted_search_does_not_poll_forever(client):
    c,sessions=client;sid=str(uuid.uuid4())
    with sessions.begin() as s:s.add(d.Search(id=sid,owner_id=1,campaign_id=1,criteria_json=json.dumps(CRITERIA),profile_json='{}',created_at='2020-01-01T00:00:00+00:00'))
    result=c.get(f'/api/discovery/searches/{sid}').json()
    assert result['status']=='FAILED' and 'criteria are saved' in result['error']


def test_guided_round_all_decisions_persist_and_fit_saves_once(client,monkeypatch):
    c,sessions=client
    monkeypatch.setattr(outscraper_service,'search_google_maps',lambda *a:{'leads':[dict(BUSINESS,name=f'Synthetic {i}',place_id=f'guided-{i}') for i in range(3)]})
    rows=search(c)['businesses'];events=[]
    for row,outcome in zip(rows,['QUALIFIED','NEEDS_RESEARCH','DISQUALIFIED']):
        response=decision(c,row['id'],value=outcome)
        assert response.status_code==200
        events.append(response.json())
        if outcome=='QUALIFIED':
            assert c.post(f"/api/discovery/businesses/{row['id']}/save").status_code==200
            assert c.post(f"/api/discovery/businesses/{row['id']}/save").status_code==200
    loaded=c.get(f"/api/discovery/searches/{c.get('/api/discovery/searches?campaign_slug=test').json()[0]['id']}").json()['businesses']
    assert len([r for r in loaded if r['decision']!='UNREVIEWED'])==3
    assert len([r for r in loaded if r['saved']])==1
    last=events[-1]
    assert c.post(f"/api/discovery/businesses/{rows[-1]['id']}/undo",json={'event_id':last['undo_event'],'revision':last['revision']}).json()['decision']=='UNREVIEWED'
    with sessions() as s:assert s.scalar(select(func.count()).select_from(Prospect))==1


def test_skye_guidance_uses_the_current_search_profile_snapshot(client):
    c,_=client
    db.save_icp_profile(1,{'minimum_budget':1000},{},True)
    found=search(c);bid=found['businesses'][0]['id']
    db.save_icp_profile(1,{'minimum_budget':0},{},True)
    explanation=c.post('/api/discovery/explain',json={'campaign':'test','search_id':found['id'],'business_ids':[bid],'question':'Why does this business fit?'}).json()
    assert 'Minimum budget is not confirmed' in explanation['businesses'][0]['missing']
