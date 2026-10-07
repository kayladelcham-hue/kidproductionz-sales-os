"""Persistent, owner-scoped discovery and human qualification. No external writes."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError

from . import database_v2 as db, request_context
from .models import Base, Campaign, Prospect, QueueItem
from .icp import normalize_profile, STATE_NAMES, _geography_matches

router = APIRouter(prefix='/api/discovery')
now = lambda: datetime.now(timezone.utc).isoformat()


class Search(Base):
    __tablename__ = 'discovery_search'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    criteria_json: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='SEARCHING')
    saved: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default='')
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text, default=now)


class Business(Base):
    __tablename__ = 'discovery_business'
    __table_args__ = (UniqueConstraint('owner_id', 'campaign_id', 'identity'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    identity: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    criteria_json: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(24), default='UNREVIEWED')
    reason: Mapped[str] = mapped_column(Text, default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    revision: Mapped[int] = mapped_column(Integer, default=0)
    prospect_id: Mapped[int | None] = mapped_column(Integer)
    outreach: Mapped[int] = mapped_column(Integer, default=0)
    found_at: Mapped[str] = mapped_column(Text, default=now)


class Membership(Base):
    __tablename__ = 'discovery_search_business'
    search_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class DecisionEvent(Base):
    __tablename__ = 'discovery_decision_event'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(Integer, index=True)
    before_json: Mapped[str] = mapped_column(Text)
    after_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=now)


def owner():
    uid = request_context.user_id.get()
    if uid:
        return uid
    if os.getenv('KIDPRODUCTIONZ_AUTH_MODE','local').lower() in ('local','disabled','off'):
        return 0  # Existing desktop mode has one local profile and no account.
    raise HTTPException(401, 'Sign in to find and review potential customers.')


def campaign(slug):
    row = db.get_campaign(slug, owner() or None)
    if not row:
        raise HTTPException(404, 'Campaign not found')
    return row['id']


def norm(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).strip()


def identity(row):
    raw = row.get('place_id') or row.get('google_id') or '|'.join(norm(row.get(k)) for k in ('name', 'city', 'state'))
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_url(value):
    try:
        value = str(value or '').strip()
        if value and not urlsplit(value).scheme:
            value = 'https://' + value
        parsed = urlsplit(value)
        return value if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username else None
    except ValueError:
        return None


def number(value):
    try:
        result = float(value)
        import math
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


@router.get('/target')
def target():
    uid=owner()
    profile=db.get_icp_profile(uid) or {'profile':{},'completed':False,'version':0}
    return {**profile,'user_id':uid,'criteria':json.loads(db.get_settings(f'user:{uid}:discovery:').get(f'user:{uid}:discovery:criteria','{}'))}


def assessment(row, criteria, profile=None):
    """Transparent criteria comparisons; no conversion probabilities or guessed facts."""
    profile = normalize_profile(profile)
    industry = '' if row.get('category_inferred_from_query') else str(row.get('category') or row.get('normalized_category') or '')
    tests = []
    def check(label, target, actual, matches):
        tests.append({'criterion': label, 'target': target or 'Not specified', 'value': actual or 'Unknown',
                      'status': 'NOT_SPECIFIED' if not target else 'UNKNOWN' if not actual else 'MATCH' if matches else 'MISMATCH'})
    check('Industry', criteria.get('industry'), industry, (' '+ ' '.join(x.rstrip('s') for x in norm(criteria.get('industry')).split())+' ') in (' '+' '.join(x.rstrip('s') for x in norm(industry).split())+' '))
    check('City', criteria.get('city'), row.get('city'), norm(criteria.get('city')) == norm(row.get('city')))
    state = str(row.get('state') or '').upper()
    state = next((code for code, name in STATE_NAMES.items() if name.upper() == state), state)
    check('State', criteria.get('state'), state, state == str(criteria.get('state') or '').upper())
    if criteria.get('min_rating'):
        value = number(row.get('rating'))
        check('Minimum rating', str(criteria['min_rating']), str(value) if value is not None else '', value is not None and float(value) >= criteria['min_rating'])
    if criteria.get('min_reviews'):
        value = number(row.get('reviews'))
        check('Minimum review count', str(criteria['min_reviews']), str(value) if value is not None else '', value is not None and float(value) >= criteria['min_reviews'])
    if criteria.get('website_required'):
        check('Website available', 'Required', safe_url(row.get('website')), bool(safe_url(row.get('website'))))
    for label, field in [('Company size', 'company_size'), ('Minimum budget', 'minimum_budget')]:
        if profile.get(field):
            check(label, str(profile[field]), None, False)
    exclusions = profile.get('excluded_industries', [])
    if exclusions:
        match = next((x for x in exclusions if norm(x) in norm(industry)), None)
        tests.append({'criterion': 'Excluded industries', 'target': ', '.join(exclusions), 'value': industry or 'Unknown',
                      'status': 'MISMATCH' if match else 'MATCH' if industry else 'UNKNOWN'})
    excluded_places=profile.get('excluded_geographies',[])
    if excluded_places:
        matches=_geography_matches(row,excluded_places)
        known=bool(row.get('city') and row.get('state'))
        tests.append({'criterion':'Places you do not serve','target':', '.join(excluded_places),'value':', '.join(str(row.get(k) or '') for k in ('city','state')).strip(', ') or 'Unknown',
                      'status':'MISMATCH' if matches else 'MATCH' if known else 'UNKNOWN'})
    if row.get('permanently_closed') or str(row.get('status') or '').lower() in ('closed','permanently_closed'):
        tests.append({'criterion':'Open for business','target':'Open','value':'Listing says permanently closed','status':'MISMATCH'})
    sources = [{'label': 'Business website', 'url': safe_url(row.get('website')), 'checked_at': None}] if safe_url(row.get('website')) else []
    if row.get('place_id'):
        from urllib.parse import quote
        sources.append({'label': 'Google Maps listing', 'url': 'https://www.google.com/maps/search/?api=1&query='+quote(row.get('name','business'))+'&query_place_id='+quote(str(row['place_id'])), 'checked_at': row.get('discovered_at')})
    mismatches = [x for x in tests if x['status'] == 'MISMATCH']
    unknowns = [x['criterion']+' is not confirmed' for x in tests if x['status'] == 'UNKNOWN']
    contacts = [key for key in ('email', 'phone') if row.get(key)] + [key for key in ('website','social') if safe_url(row.get(key))]
    unknowns += ['Decision-maker identity and role are not verified', 'Contact details are from available records and have not been independently verified']
    signals = []
    for field in ('need_signals', 'urgency_signals', 'positive_signals'):
        signals.extend({'signal': x, 'status': 'UNKNOWN', 'evidence': 'No supporting evidence captured'} for x in profile.get(field, []))
    return {'label': 'Outside criteria' if mismatches else 'Needs evidence' if any(x['status']=='UNKNOWN' for x in tests) else 'Matches stated criteria',
            'criteria': tests, 'matches': [x['criterion']+': '+str(x['value']) for x in tests if x['status']=='MATCH'],
            'missing_information': unknowns, 'signals': signals, 'sources': sources,
            'contact_paths': contacts, 'contact_readiness': 'Contact path available · unverified' if contacts else 'No contact path recorded',
            'score_meaning': 'These details match what you asked for. They do not tell us whether this business needs your offer or wants to buy.'}


def business_view(row, criteria=None, profile=None):
    data = json.loads(row.payload_json)
    q = assessment(data, criteria or json.loads(row.criteria_json), profile)
    return {**data, 'id': row.id, 'decision': row.decision, 'reason': row.reason, 'notes': row.notes,
            'revision': row.revision, 'prospect_id': row.prospect_id, 'saved': bool(row.prospect_id),
            'outreach': bool(row.outreach), 'found_at': row.found_at, 'assessment': q}


def owned_business(session, bid, lock=False):
    stmt = select(Business).where(Business.id == bid, Business.owner_id == owner())
    if lock:
        stmt = stmt.with_for_update()
    row = session.execute(stmt).scalar_one_or_none()
    if not row:
        raise HTTPException(404, 'Business not found')
    return row


class Criteria(BaseModel):
    industry: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(pattern=r'^[A-Z]{2}$')
    limit: int = Field(default=10, ge=1, le=100)
    min_rating: float = Field(default=0, ge=0, le=5)
    min_reviews: int = Field(default=0, ge=0, le=1000000)
    website_required: bool = False


class SearchRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), pattern=r'^[a-f0-9-]{36}$')
    campaign: str
    criteria: Criteria


@router.put('/target')
def save_target(req: Criteria):
    uid=owner()
    db.save_settings({f'user:{uid}:discovery:criteria':json.dumps(req.model_dump())})
    return req.model_dump()


def search_view(row):
    status,error=row.status,row.error
    try:
        started=datetime.fromisoformat(row.created_at).replace(tzinfo=timezone.utc)
        if status=='SEARCHING' and (datetime.now(timezone.utc)-started).total_seconds()>180:
            status='FAILED'
            error='This search did not finish. Your criteria are saved. Run a new search to try again; the original request may still count toward your allowance.'
    except (ValueError,TypeError):
        pass
    return {'id': row.id, 'criteria': json.loads(row.criteria_json), 'status': status,
            'saved': bool(row.saved), 'error': error, 'duplicates': row.duplicates,
            'skipped': row.skipped, 'created_at': row.created_at}


@router.get('/searches')
def list_searches(campaign_slug: str):
    cid = campaign(campaign_slug)
    with db.SessionLocal() as session:
        rows = session.execute(select(Search).where(Search.owner_id == owner(), Search.campaign_id == cid).order_by(Search.created_at.desc()).limit(50)).scalars()
        return [search_view(row) for row in rows]


@router.get('/searches/{sid}')
def search_results(sid: str):
    with db.SessionLocal() as session:
        search = session.get(Search, sid)
        if not search or search.owner_id != owner():
            raise HTTPException(404, 'Search not found')
        criteria = json.loads(search.criteria_json)
        rows = session.execute(select(Business).join(Membership, Membership.business_id == Business.id).where(Membership.search_id == sid, Business.owner_id == owner())).scalars()
        return {**search_view(search), 'businesses': [business_view(row, criteria, json.loads(search.profile_json)) for row in rows]}


class SaveSearch(BaseModel):
    saved: bool


@router.patch('/searches/{sid}')
def save_search(sid: str, req: SaveSearch):
    with db.session_scope() as session:
        row = session.get(Search, sid)
        if not row or row.owner_id != owner():
            raise HTTPException(404, 'Search not found')
        row.saved = int(req.saved)
        return search_view(row)


@router.post('/searches')
def run_search(req: SearchRequest):
    uid, cid = owner(), campaign(req.campaign)
    criteria = req.criteria.model_dump()
    profile = (db.get_icp_profile(uid) or {}).get('profile', {})
    try:
        with db.session_scope() as session:
            existing = session.get(Search, req.id)
            if existing:
                if existing.owner_id != uid or existing.campaign_id != cid:
                    raise HTTPException(404, 'Search not found')
                return search_results(existing.id)
            session.add(Search(id=req.id, owner_id=uid, campaign_id=cid, criteria_json=json.dumps(criteria), profile_json=json.dumps(profile)))
    except IntegrityError:
        # A retry can race the original request before its search row is committed.
        return search_results(req.id)
    try:
        from .outscraper_service import search_google_maps
        result = search_google_maps(f"{criteria['industry']} in {criteria['city']}, {criteria['state']}", criteria['limit'], criteria['industry'])
        with db.session_scope() as session:
            search = session.get(Search, req.id)
            search.duplicates = int(result.get('duplicates_removed', 0))
            search.skipped = int(result.get('skipped', 0))
            # Serialize identity creation within this campaign across workers.
            session.execute(update(Campaign).where(Campaign.id == cid).values(active=Campaign.active))
            seen = set()
            for data in result.get('leads', []):
                if not isinstance(data, dict) or not data.get('name'):
                    search.skipped += 1
                    continue
                key = identity(data)
                if key in seen:
                    search.duplicates += 1
                    continue
                seen.add(key)
                row = session.execute(select(Business).where(Business.owner_id == uid, Business.campaign_id == cid, Business.identity == key)).scalar_one_or_none()
                if not row:
                    row = Business(owner_id=uid, campaign_id=cid, identity=key, payload_json=json.dumps({**data, 'discovered_at':result.get('fetched_at') or now()}), criteria_json=json.dumps(criteria))
                    session.add(row); session.flush()
                session.add(Membership(search_id=search.id, business_id=row.id))
            search.status = 'PARTIAL' if search.skipped or result.get('partial') else 'COMPLETE'
        return search_results(req.id)
    except Exception as error:
        message = str(error.detail) if isinstance(error, HTTPException) else 'The provider search failed. Your criteria were preserved. Try again.'
        with db.session_scope() as session:
            row = session.get(Search, req.id); row.status='FAILED'; row.error=message
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(502, message)


@router.get('/businesses/{bid}')
def detail(bid: int, search_id: str | None = None):
    with db.SessionLocal() as session:
        row = owned_business(session, bid)
        profile = (db.get_icp_profile(owner()) or {}).get('profile', {})
        criteria=None
        if search_id:
            search=session.get(Search,search_id)
            membership=session.get(Membership,(search_id,bid))
            if not search or search.owner_id!=owner() or not membership:raise HTTPException(404,'Business not found in this search')
            criteria=json.loads(search.criteria_json);profile=json.loads(search.profile_json)
        history = session.execute(select(DecisionEvent).where(DecisionEvent.business_id==bid).order_by(DecisionEvent.id.desc()).limit(30)).scalars()
        return {**business_view(row, criteria, profile), 'history':[{'id':x.id,'decision':json.loads(x.after_json)['decision'],'reason':json.loads(x.after_json)['reason'],'created_at':x.created_at} for x in history]}


class Decision(BaseModel):
    decision: str = Field(pattern=r'^(QUALIFIED|NEEDS_RESEARCH|DISQUALIFIED|UNREVIEWED)$')
    reason: str = Field(default='', max_length=1000)
    notes: str = Field(default='', max_length=3000)
    revision: int


def snapshot(row):
    return {k:getattr(row,k) for k in ('decision','reason','notes')}


@router.patch('/businesses/{bid}/qualification')
def decide(bid: int, req: Decision):
    if req.decision!='UNREVIEWED' and not req.reason.strip():
        raise HTTPException(422, 'Record why you chose this decision.')
    with db.session_scope() as session:
        row = owned_business(session, bid, True)
        before = snapshot(row)
        result = session.execute(update(Business).where(Business.id==bid, Business.revision==req.revision).values(
            decision=req.decision, reason=req.reason.strip(), notes=req.notes.strip(), revision=req.revision+1))
        if result.rowcount != 1:
            raise HTTPException(409, 'This decision changed in another window. Refresh before correcting it.')
        session.refresh(row)
        event=DecisionEvent(business_id=bid,before_json=json.dumps(before),after_json=json.dumps(snapshot(row)))
        session.add(event); session.flush()
        return {**business_view(row), 'undo_event':event.id}


class Undo(BaseModel):
    event_id: int
    revision: int


@router.post('/businesses/{bid}/undo')
def undo(bid: int, req: Undo):
    with db.session_scope() as session:
        row = owned_business(session,bid,True)
        event=session.get(DecisionEvent,req.event_id)
        latest=session.scalar(select(DecisionEvent.id).where(DecisionEvent.business_id==bid).order_by(DecisionEvent.id.desc()).limit(1))
        if not event or event.business_id!=bid or event.id!=latest or row.revision!=req.revision:
            raise HTTPException(409,'Refresh this business before undoing the decision.')
        before=snapshot(row); previous=json.loads(event.before_json)
        result=session.execute(update(Business).where(Business.id==bid,Business.revision==req.revision).values(**previous,revision=req.revision+1))
        if result.rowcount!=1:raise HTTPException(409,'Decision changed; refresh first.')
        session.refresh(row)
        session.add(DecisionEvent(business_id=bid,before_json=json.dumps(before),after_json=json.dumps(snapshot(row))))
        return business_view(row)


def save_business(session,row):
    if row.decision!='QUALIFIED':raise HTTPException(409,'Choose Looks like a fit before saving this business.')
    # A real campaign row lock serializes deduplication and insert, including SQLite writes.
    session.execute(update(Campaign).where(Campaign.id==row.campaign_id).values(active=Campaign.active))
    if row.prospect_id:return row.prospect_id
    data=json.loads(row.payload_json)
    existing=session.execute(select(Prospect).where(Prospect.campaign_id==row.campaign_id)).scalars()
    external='OUTSCRAPER:'+str(data.get('place_id') or data.get('google_id') or '')
    for prospect in existing:
        same_name=norm(prospect.name)==norm(data.get('name')) and norm(prospect.city)==norm(data.get('city')) and norm(prospect.state)==norm(data.get('state'))
        same_external=external!='OUTSCRAPER:' and prospect.external_key==external
        if same_name or same_external:
            row.prospect_id=prospect.id
            return prospect.id
    fields={k:data.get(k) for k in ('name','email','phone','website','social','category','address','city','state','zip')}
    prospect=Prospect(**fields,campaign_id=row.campaign_id,company=data['name'],queue='RESEARCH',lead_source='DISCOVERY',external_key=external if external!='OUTSCRAPER:' else None)
    session.add(prospect);session.flush();row.prospect_id=prospect.id
    return prospect.id


@router.post('/businesses/{bid}/save')
def save(bid: int):
    with db.session_scope() as session:
        row=owned_business(session,bid,True);save_business(session,row)
        return business_view(row)


class BulkSave(BaseModel):
    business_ids: list[int] = Field(max_length=50)


@router.post('/save-qualified')
def save_qualified(req: BulkSave):
    # Only saves independent QUALIFIED judgments; never assigns a bulk verdict.
    results=[]
    for bid in dict.fromkeys(req.business_ids):
        try:results.append({'id':bid,'result':save(bid)})
        except HTTPException as error:results.append({'id':bid,'error':error.detail})
    return results


@router.post('/businesses/{bid}/outreach')
def begin_outreach(bid: int):
    with db.session_scope() as session:
        row=owned_business(session,bid,True)
        if row.decision!='QUALIFIED':raise HTTPException(409,'Choose Looks like a fit before preparing to contact this business.')
        data=json.loads(row.payload_json)
        if not any(data.get(k) for k in ('phone','email','website','social')):
            raise HTTPException(409,'Find contact information before preparing to contact this business.')
        pid=save_business(session,row)
        prospect=session.get(Prospect,pid)
        prospect.queue='DAILY_QUEUE';row.outreach=1
        # Preserve sales statuses, notes, existing opportunities and activity.
        return {'prospect_id':pid,'decision':row.decision,'outreach':True}


@router.get('/outreach')
def outreach_ids(campaign_slug: str):
    cid=campaign(campaign_slug)
    with db.SessionLocal() as session:
        return [x.prospect_id for x in session.execute(select(Business).where(Business.owner_id==owner(),Business.campaign_id==cid,Business.decision=='QUALIFIED',Business.outreach==1)).scalars() if x.prospect_id]


@router.get('/saved')
def saved(campaign_slug: str):
    cid=campaign(campaign_slug)
    with db.SessionLocal() as session:
        rows=list(session.execute(select(Business).where(Business.owner_id==owner(),Business.campaign_id==cid,Business.prospect_id.is_not(None))).scalars())
        rows=list({r.prospect_id:r for r in rows}.values())
        represented={r.prospect_id for r in rows}
        legacy=[{**db._dict(p),'id':f'legacy:{p.id}','prospect_id':p.id,'saved':True,'decision':'UNREVIEWED','assessment':assessment(db._dict(p),{})} for p in session.execute(select(Prospect).where(Prospect.campaign_id==cid,Prospect.lifecycle_stage=='PROSPECT')).scalars() if p.id not in represented]
        return [business_view(row) for row in rows]+legacy


@router.post('/legacy/{pid}/review')
def review_legacy(pid: int):
    uid=owner()
    with db.session_scope() as session:
        query=select(Prospect).join(Campaign,Campaign.id==Prospect.campaign_id).where(Prospect.id==pid)
        if uid:query=query.where(Campaign.owner_id==uid)
        prospect=session.execute(query).scalar_one_or_none()
        if not prospect:raise HTTPException(404,'Saved lead not found')
        session.execute(update(Campaign).where(Campaign.id==prospect.campaign_id).values(active=Campaign.active))
        row=session.execute(select(Business).where(Business.owner_id==uid,Business.prospect_id==pid)).scalar_one_or_none()
        if not row:
            profile=(db.get_icp_profile(uid) or {}).get('profile',{})
            criteria={'industry':(profile.get('business_types') or profile.get('target_industries') or [''])[0]}
            row=Business(owner_id=uid,campaign_id=prospect.campaign_id,identity=identity({'place_id':'legacy:'+str(pid)}),payload_json=json.dumps(db._dict(prospect)),criteria_json=json.dumps(criteria),prospect_id=pid)
            session.add(row);session.flush()
        return business_view(row)


class Ask(BaseModel):
    business_ids: list[int] = Field(default_factory=list,max_length=5)
    campaign: str
    question: str = Field(max_length=1000)


@router.post('/explain')
def explain(req: Ask):
    owner()
    if not req.business_ids:
        return {'reply':'Start on Home: tell us what you sell, choose a business type and city, then select Find potential customers. If you are unsure who to choose, select Help me figure this out. I use the search you confirm.','businesses':[]}
    cid=campaign(req.campaign)
    rows=[]
    with db.SessionLocal() as session:
        profile=(db.get_icp_profile(owner()) or {}).get('profile',{})
        for bid in req.business_ids:
            row=owned_business(session,bid)
            if row.campaign_id!=cid:raise HTTPException(404,'Business not found in this campaign')
            view=business_view(row,profile=profile);q=view['assessment']
            rows.append({'id':bid,'name':view['name'],'fit':q['label'],'known':q['matches'],'missing':q['missing_information'],'sources':q['sources'],
                         'suggested_decision':'NEEDS_RESEARCH' if q['label']!='Matches stated criteria' else 'QUALIFIED',
                         'explanation':'Check what matches and what we do not know, then choose your own decision. This suggestion has not been saved.'})
    response={'reply':'Here is what matches your search and what we still need to check. Matching your search does not mean a business wants to buy. You choose who looks worth contacting.','businesses':rows}
    if re.search(r'draft.*message',req.question,re.I):
        if len(rows)!=1:
            response['reply']='Open one business so I can help draft a message for it.'
        else:
            offer=profile.get('offer') or '[your product or service]'
            response['draft']=f"Hi {rows[0]['name']} team,\n\nI offer {offer}. Would it be useful if I sent a little more information about how it works?\n\nThanks,\n[your name]"
            response['reply']=response['draft']+'\n\nPlease edit this draft and check the contact details before sending. Nothing has been sent.'
    return response
