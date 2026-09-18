"""Campaign-scoped manual intake and follow-up actions using existing storage."""
from datetime import datetime, timezone
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from . import database_v2 as db
from .models import Prospect, Campaign, CalendarEvent, ExternalAction
from . import google_service
import os
from zoneinfo import ZoneInfo

router = APIRouter()
STATUSES = {'NOT_CONTACTED', 'ATTEMPTED', 'CONTACTED', 'REPLIED', 'FOLLOW_UP',
            'CONSULTATION_SET', 'BOOKED', 'NOT_INTERESTED'}

def scoped(s, campaign, prospect_id):
    p = s.execute(select(Prospect).join(Campaign, Prospect.campaign_id == Campaign.id)
                  .where(Campaign.slug == campaign, Prospect.id == prospect_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(404, 'Prospect not found in this campaign')
    return p

class ManualProspect(BaseModel):
    campaign: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default='', max_length=60)
    email: str = Field(default='', max_length=254)
    notes: str = Field(default='', max_length=4000)

@router.post('/api/prospects/manual')
def add_prospect(req: ManualProspect):
    name, phone, email = req.name.strip(), req.phone.strip(), req.email.strip().lower()
    if not name or not (phone or email):
        raise HTTPException(400, 'Enter a name and phone or email')
    if phone and len(''.join(c for c in phone if c.isdigit())) < 7:
        raise HTTPException(400, 'Enter a valid phone number')
    if email and ('@' not in email or '.' not in email.rsplit('@', 1)[-1]):
        raise HTTPException(400, 'Enter a valid email')
    if not db.get_campaign(req.campaign):
        raise HTTPException(404, 'Campaign not found')
    result = db.persist_generated_prospects(req.campaign, [{
        'name': name, 'phone': phone, 'email': email, 'queue_status': 'RESEARCH',
        'review_reasons': ['Met in person; review qualification before queueing'],
    }])
    if result['duplicate_count']:
        raise HTTPException(409, 'A matching prospect already exists in this campaign')
    pid = result['inserted'][0]['id']
    db.update_sales_activity(pid, 'CONTACTED', req.notes.strip())
    db.log_external_action(pid, 'MANUAL_PROSPECT_ADDED', {'source': 'IN_PERSON'})
    return {'id': pid, 'campaign': req.campaign, 'queue': 'RESEARCH'}

@router.get('/api/follow-ups')
def follow_ups(campaign: str):
    with db.SessionLocal() as s:
        prospects = s.execute(select(Prospect).join(Campaign, Prospect.campaign_id == Campaign.id)
                              .where(Campaign.slug == campaign)).scalars().all()
        ids = [p.id for p in prospects]
        events = s.execute(select(CalendarEvent).where(CalendarEvent.prospect_id.in_(ids))
                           .order_by(CalendarEvent.id)).scalars().all()
        actions = s.execute(select(ExternalAction).where(ExternalAction.prospect_id.in_(ids),
                             ExternalAction.action_type == 'NEXT_ACTION_UPDATED')
                            .order_by(ExternalAction.id)).scalars().all()
        by_event, by_action = {}, {}
        for e in events:
            by_event.setdefault(e.prospect_id, []).append(db._dict(e))
        for a in actions:
            by_action[a.prospect_id] = json.loads(a.metadata_json or '{}')
        return [dict(db._dict(p), events=by_event.get(p.id, []),
                     next_action=by_action.get(p.id, {})) for p in prospects
                if p.sales_status in {'CONTACTED', 'REPLIED', 'FOLLOW_UP', 'CONSULTATION_SET'}
                or p.id in by_event or by_action.get(p.id, {}).get('due_at')]

class NextAction(BaseModel):
    campaign: str
    status: str
    notes: str = Field(default='', max_length=4000)
    due_at: str | None = None
    action: str = Field(default='', max_length=500)

@router.post('/api/prospects/{prospect_id}/next-action')
def next_action(prospect_id: int, req: NextAction):
    if req.status not in STATUSES:
        raise HTTPException(400, 'Invalid sales status')
    due = None
    if req.due_at:
        try:
            dt = datetime.fromisoformat(req.due_at)
            if dt.tzinfo is None:
                raise ValueError()
            due = dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            raise HTTPException(400, 'Next action needs a valid datetime with timezone')
    with db.session_scope() as s:
        p = scoped(s, req.campaign, prospect_id)
        p.sales_status, p.notes = req.status, req.notes
        p.last_activity_at = datetime.now(timezone.utc).isoformat()
        s.add(ExternalAction(prospect_id=p.id, action_type='NEXT_ACTION_UPDATED',
              metadata_json=json.dumps({'due_at': due, 'action': req.action})))
    return {'status': 'SAVED'}

class Reschedule(BaseModel):
    campaign: str
    start: str
    end: str
    timezone: str = 'UTC'
    confirmed: bool = False

@router.post('/api/follow-ups/events/{event_id}/reschedule')
def reschedule(event_id: int, req: Reschedule):
    try:
        zone = ZoneInfo(req.timezone)
        start, end = datetime.fromisoformat(req.start), datetime.fromisoformat(req.end)
        start = start.replace(tzinfo=zone) if start.tzinfo is None else start.astimezone(zone)
        end = end.replace(tzinfo=zone) if end.tzinfo is None else end.astimezone(zone)
    except Exception:
        raise HTTPException(400, 'Enter valid dates and timezone')
    if end <= start:
        raise HTTPException(400, 'End must be after start')
    with db.session_scope() as s:
        e = s.get(CalendarEvent, event_id)
        if not e:
            raise HTTPException(404, 'Consultation not found')
        p = scoped(s, req.campaign, e.prospect_id)
        if e.provider != 'GOOGLE' or not e.calendar_event_id:
            raise HTTPException(400, 'This consultation cannot be rescheduled through Google')
        if not req.confirmed:
            return {'status': 'PREVIEW', 'start': start.isoformat(), 'end': end.isoformat()}
        if os.getenv('GOOGLE_CALENDAR_ENABLED', 'false').lower() != 'true':
            raise HTTPException(403, 'Google Calendar is disabled')
        try:
            google_service.reschedule_calendar_event(e.calendar_event_id, {
                'start': {'dateTime': start.isoformat(), 'timeZone': req.timezone},
                'end': {'dateTime': end.isoformat(), 'timeZone': req.timezone}})
        except Exception:
            raise HTTPException(503, 'Google Calendar could not reschedule this event')
        e.consultation_start, e.consultation_end = start.isoformat(), end.isoformat()
        p.sales_status = 'CONSULTATION_SET'
        p.last_activity_at = datetime.now(timezone.utc).isoformat()
        s.add(ExternalAction(prospect_id=p.id, action_type='CALENDAR_EVENT_RESCHEDULED',
              metadata_json=json.dumps({'calendar_event_id': e.calendar_event_id,
                                        'start': e.consultation_start, 'end': e.consultation_end})))
    return {'status': 'RESCHEDULED'}
