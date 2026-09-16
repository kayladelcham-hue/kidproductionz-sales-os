from __future__ import annotations
import os, json
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, select, update, func, text
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, Campaign, Prospect, Run, QueueItem, CrmState, Upload, ExternalAction, CalendarEvent, EmailActivity, GoogleConnection, AppSetting

def _url():
    u=os.getenv('DATABASE_URL','sqlite:///data/kidproductionz.db')
    if u.startswith('postgresql://'): u='postgresql+psycopg://'+u[len('postgresql://'):]
    if not (u.startswith('sqlite:///') or u.startswith('postgresql+psycopg://')): raise RuntimeError(f'Unsupported DATABASE_URL scheme: {u.split(":",1)[0]}')
    return u
DATABASE_URL=_url()
_kw={'connect_args':{'check_same_thread':False}} if DATABASE_URL.startswith('sqlite:///') else {}
engine=create_engine(DATABASE_URL, future=True, **_kw)
SessionLocal=sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
@contextmanager
def session_scope():
    s=SessionLocal()
    try: yield s; s.commit()
    except Exception: s.rollback(); raise
    finally: s.close()
def connect(): return engine.connect()
def init_db(): Base.metadata.create_all(bind=engine)
def _dict(obj):
    if obj is None:return None
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}
def seed_campaigns(config_dir=None): return 0
def persist_upload(metadata):
    with session_scope() as s: s.merge(Upload(**{k:v for k,v in metadata.items() if k in Upload.__table__.columns.keys()}))
def update_sales_activity(prospect_id,status=None,notes=None,booked_value=None):
    with session_scope() as s:
        p=s.get(Prospect,prospect_id)
        if not p:return None
        if status is not None:p.sales_status=status
        if notes is not None:p.notes=notes
        if booked_value is not None:p.booked_value=booked_value
        return _dict(p)
def activity_metrics():
    with SessionLocal() as s:
        rows = s.execute(
            select(Prospect.sales_status, func.count())
            .group_by(Prospect.sales_status)
        ).all()

        counts = {str(k or 'UNKNOWN'): int(v) for k, v in rows}

        booked_revenue = s.execute(
            select(func.coalesce(func.sum(Prospect.booked_value), 0))
            .where(Prospect.sales_status == 'BOOKED')
        ).scalar_one()

        queue_count = s.execute(
            select(func.count())
            .select_from(Prospect)
            .where(
                Prospect.grade == 'B / Qualified',
                Prospect.sales_status == 'NOT_CONTACTED'
            )
        ).scalar_one()

        return {
            'queue': int(queue_count or 0),
            'attempted_or_contacted': (
                counts.get('ATTEMPTED', 0) +
                counts.get('CONTACTED', 0)
            ),
            'replies': counts.get('REPLIED', 0),
            'consultations_set': counts.get('CONSULTATION_SET', 0),
            'booked': counts.get('BOOKED', 0),
            'booked_revenue': float(booked_revenue or 0),
        }
def ensure_queue_item(item,campaign):
    with session_scope() as s:
        q=s.execute(select(QueueItem).where(QueueItem.run_id==item.get('run_id'),QueueItem.prospect_id==item.get('prospect_id'))).scalar_one_or_none()
        if q:return _dict(q)
        q=QueueItem(**{k:v for k,v in item.items() if k in QueueItem.__table__.columns.keys()}); s.add(q); s.flush(); return _dict(q)
def persist_crm_state(prospect_id,result):
    with session_scope() as s:
        q=s.execute(select(CrmState).where(CrmState.prospect_id==prospect_id)).scalar_one_or_none()
        vals={k:v for k,v in result.items() if k in CrmState.__table__.columns.keys() and k!='id'}; vals['prospect_id']=prospect_id
        if q:
            for k,v in vals.items(): setattr(q,k,v)
        else:s.add(CrmState(**vals))
def get_crm_state(prospect_id):
    with SessionLocal() as s:return _dict(s.execute(select(CrmState).where(CrmState.prospect_id==prospect_id)).scalar_one_or_none())
def log_external_action(prospect_id,action_type,metadata=None):
    with session_scope() as s:s.add(ExternalAction(prospect_id=prospect_id,action_type=action_type,metadata_json=json.dumps(metadata) if metadata is not None else None))
def list_campaigns():
    with SessionLocal() as s:return [_dict(x) for x in s.execute(select(Campaign).order_by(Campaign.name)).scalars()]
def list_prospects(campaign=None):
    with SessionLocal() as s:
        q=select(Prospect).order_by(Prospect.id)
        if campaign:q=q.join(Campaign,Prospect.campaign_id==Campaign.id).where(Campaign.slug==campaign)
        return [_dict(x) for x in s.execute(q).scalars()]
def get_campaign(slug):
    with SessionLocal() as s:return _dict(s.execute(select(Campaign).where(Campaign.slug==slug)).scalar_one_or_none())
def create_campaign(data):
    with session_scope() as s:
        c=Campaign(**{k:v for k,v in data.items() if k in Campaign.__table__.columns.keys() and k!='id'}); s.add(c); s.flush(); return _dict(c)
def update_campaign(slug,data):
    with session_scope() as s:
        c=s.execute(select(Campaign).where(Campaign.slug==slug)).scalar_one_or_none()
        if not c:return None
        for k,v in data.items():
            if k in Campaign.__table__.columns.keys() and k!='id':setattr(c,k,v)
        s.flush(); return _dict(c)
def get_settings(prefix=None):
    with SessionLocal() as s:
        q=select(AppSetting)
        if prefix:q=q.where(AppSetting.key.like(prefix+'%'))
        return {x.key:x.value for x in s.execute(q).scalars()}
def save_settings(values):
    with session_scope() as s:
        for k,v in values.items():
            x=s.get(AppSetting,k)
            if x:x.value=str(v)
            else:s.add(AppSetting(key=k,value=str(v)))
def save_google_connection(data):
    with session_scope() as s:
        x=s.get(GoogleConnection,1)
        vals={k:v for k,v in data.items() if k in GoogleConnection.__table__.columns.keys() and k!='id'}
        if x:
            for k,v in vals.items():setattr(x,k,v)
        else:s.add(GoogleConnection(id=1,**vals))
def load_google_connection():
    with SessionLocal() as s:return _dict(s.get(GoogleConnection,1))
def clear_google_connection():
    with session_scope() as s:
        x=s.get(GoogleConnection,1)
        if x:s.delete(x)
__all__=['engine','SessionLocal','session_scope','Base','init_db','seed_campaigns','persist_upload','update_sales_activity','activity_metrics','ensure_queue_item','persist_crm_state','get_crm_state','log_external_action','connect','list_campaigns','list_prospects','get_campaign','create_campaign','update_campaign','get_settings','save_settings','save_google_connection','load_google_connection','clear_google_connection']

