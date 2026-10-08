from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from app.api import database_v2 as db
from app.api.models import Base,Campaign,Prospect
from app.api.campaign_targets import resolve_target

@pytest.fixture
def target_db(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'targets.db'),connect_args={'check_same_thread':False,'timeout':30})
    Base.metadata.create_all(engine);monkeypatch.setattr(db,'SessionLocal',sessionmaker(bind=engine,expire_on_commit=False));monkeypatch.setattr(db,'engine',engine)
    return engine

def test_automatic_market_reuse_names_and_ownership(target_db):
    a=resolve_target(1,'Restaurant','Atlanta','GA')
    assert a['name']=='Atlanta Restaurants'
    assert resolve_target(1,' restaurants ',' ATLANTA ','ga')['id']==a['id']
    assert resolve_target(2,'Restaurant','Atlanta','GA')['id']!=a['id']
    assert resolve_target(1,'Hair salons','Orlando','FL')['name']=='Orlando Hair Salons'
    db.update_campaign(a['slug'],{'name':'My custom name'},1)
    assert resolve_target(1,'restaurants','Atlanta','GA')['name']=='My custom name'

def test_existing_campaign_records_never_moved(target_db):
    old=db.create_campaign({'slug':'custom','name':'My market','owner_id':1,'category':'Hair salon','city':'Orlando','state':'FL'})
    with db.session_scope() as s:
        s.add(Prospect(campaign_id=old['id'],name='Real saved business',notes='Keep notes'))
    assert resolve_target(1,'Hair salons','Orlando','FL')['id']==old['id']
    other=resolve_target(1,'Restaurant','Atlanta','GA')
    with db.SessionLocal() as s:
        row=s.execute(select(Prospect)).scalar_one();assert row.campaign_id==old['id'];assert row.notes=='Keep notes';assert other['id']!=old['id']

def test_concurrent_market_claim_creates_one_campaign(target_db):
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows=list(pool.map(lambda _:resolve_target(1,'Restaurants','Atlanta','GA'),range(12)))
    assert len({r['id'] for r in rows})==1
    with db.SessionLocal() as s:assert s.scalar(select(func.count()).select_from(Campaign))==1

def test_invalid_target_creates_nothing(target_db):
    with pytest.raises(ValueError):resolve_target(1,'Restaurant','Atlanta','Georgia')
    with db.SessionLocal() as s:assert s.scalar(select(func.count()).select_from(Campaign))==0

def test_selected_matching_campaign_is_respected_without_name_matching(target_db):
    a=resolve_target(1,'Restaurant','Atlanta','GA')
    manual=db.create_campaign({'slug':'manually_named','name':'Custom restaurant search','owner_id':1,'category':'Restaurants','city':'Atlanta','state':'GA'})
    assert resolve_target(1,'Restaurant','Atlanta','GA',manual['slug'])['id']==manual['id']
    other=db.create_campaign({'slug':'another_owner','name':'Same name','owner_id':2,'category':'Restaurants','city':'Atlanta','state':'GA'})
    assert resolve_target(1,'Restaurant','Atlanta','GA',other['slug'])['id']==a['id']
