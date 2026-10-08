"""Resolve owner-scoped target markets without modifying existing campaigns or records."""
import hashlib
import re
import unicodedata
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from . import database_v2 as db
from .models import Campaign

def normalized(value):
    return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', str(value or '')).casefold()).strip()

def industry_key(value):
    text=normalized(value)
    return {'restaurants':'restaurant','hair salons':'hair salon','cafes':'cafe','dental clinics':'dental clinic','retail stores':'retail store','real estate agencies':'real estate agency'}.get(text,text)

def target_key(industry,city,state):
    return (industry_key(industry),normalized(city),normalized(state))

def resolve_target(owner_id,industry,city,state,preferred_campaign=None):
    key=target_key(industry,city,state)
    if not all(key) or not re.fullmatch(r'[A-Za-z]{2}',state.strip()):
        raise ValueError('Enter a business type, city and two-letter state.')
    slug='market_'+hashlib.sha256(f'{owner_id}|{key!r}'.encode()).hexdigest()[:32]
    def matching(session):
        rows=session.execute(select(Campaign).where(Campaign.owner_id==owner_id).order_by(Campaign.id)).scalars()
        matches=[r for r in rows if target_key(r.category,r.city,r.state)==key and r.status!='ARCHIVED']
        return next((r for r in matches if r.slug==preferred_campaign),matches[0] if matches else None)
    try:
        with db.session_scope() as session:
            row=matching(session)
            if row:return db._dict(row)
            label={'restaurant':'Restaurants','hair salon':'Hair Salons','cafe':'Cafés','dental clinic':'Dental Clinics','retail store':'Retail Stores','real estate agency':'Real Estate Agencies'}.get(key[0],industry.strip().title())
            row=Campaign(owner_id=owner_id,slug=slug,name=f'{city.strip().title()} {label}',category=industry.strip(),city=city.strip(),state=state.strip().upper(),daily_queue_limit=50,status='ACTIVE')
            session.add(row);session.flush();return db._dict(row)
    except IntegrityError:
        # Unique slug is the atomic market claim. Losing requests roll back all writes.
        with db.SessionLocal() as session:
            row=matching(session)
            if row:return db._dict(row)
        raise ValueError('This target campaign is archived or its targeting changed. Choose an existing campaign or create one manually.')
