"""Sales lifecycle API built on the existing prospect/contact record."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from . import database_v2 as db
from .models import Campaign, Prospect, Deal, ExternalAction, CalendarEvent, EmailActivity

router = APIRouter(prefix='/api')

LIFECYCLES = {'PROSPECT', 'LEAD', 'CUSTOMER'}
DEAL_STAGES = {'NEW_LEAD', 'CONSULTATION', 'PROPOSAL', 'DECISION', 'WON', 'LOST'}


def owner_id(request: Request):
    return getattr(request.state, 'user_id', None)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def owned_contact_query(user_id, campaign=None):
    query = select(Prospect).join(Campaign, Prospect.campaign_id == Campaign.id)
    if user_id is not None:
        query = query.where(Campaign.owner_id == user_id)
    if campaign:
        query = query.where(Campaign.slug == campaign)
    return query


def owned_contact(s, user_id, contact_id):
    contact = s.execute(
        owned_contact_query(user_id).where(Prospect.id == contact_id)
    ).scalar_one_or_none()
    if not contact:
        raise HTTPException(404, 'Contact not found')
    return contact


def owned_deal(s, user_id, deal_id):
    row = s.execute(
        select(Deal, Prospect, Campaign)
        .join(Prospect, Deal.prospect_id == Prospect.id)
        .join(Campaign, Prospect.campaign_id == Campaign.id)
        .where(Deal.id == deal_id)
        .where(Campaign.owner_id == user_id if user_id is not None else True)
    ).first()
    if not row:
        raise HTTPException(404, 'Deal not found')
    return row


def latest_next_actions(s, ids):
    if not ids:
        return {}
    actions = s.execute(
        select(ExternalAction)
        .where(ExternalAction.prospect_id.in_(ids), ExternalAction.action_type == 'NEXT_ACTION_UPDATED')
        .order_by(ExternalAction.id)
    ).scalars().all()
    result = {}
    for action in actions:
        try:
            result[action.prospect_id] = json.loads(action.metadata_json or '{}')
        except json.JSONDecodeError:
            result[action.prospect_id] = {}
    return result


def serialize_contact(contact, next_action=None):
    data = db._dict(contact)
    data['company'] = contact.company or contact.name
    data['next_action'] = next_action or {}
    return data


@router.get('/lifecycle/contacts')
def contacts(request: Request, stage: str | None = None, campaign: str | None = None):
    normalized = stage.upper() if stage else None
    if normalized and normalized not in LIFECYCLES:
        raise HTTPException(400, 'Invalid lifecycle stage')
    with db.SessionLocal() as s:
        query = owned_contact_query(owner_id(request), campaign)
        if normalized:
            query = query.where(Prospect.lifecycle_stage == normalized)
        rows = s.execute(query.order_by(Prospect.last_activity_at.desc(), Prospect.id.desc())).scalars().all()
        actions = latest_next_actions(s, [row.id for row in rows])
        return [serialize_contact(row, actions.get(row.id)) for row in rows]


@router.get('/lifecycle/contacts/{contact_id}')
def contact_detail(contact_id: int, request: Request):
    with db.SessionLocal() as s:
        contact = owned_contact(s, owner_id(request), contact_id)
        deals = s.execute(select(Deal).where(Deal.prospect_id == contact.id).order_by(Deal.id.desc())).scalars().all()
        actions = s.execute(select(ExternalAction).where(ExternalAction.prospect_id == contact.id).order_by(ExternalAction.id.desc())).scalars().all()
        events = s.execute(select(CalendarEvent).where(CalendarEvent.prospect_id == contact.id).order_by(CalendarEvent.id.desc())).scalars().all()
        emails = s.execute(select(EmailActivity).where(EmailActivity.prospect_id == contact.id).order_by(EmailActivity.id.desc())).scalars().all()
        timeline = []
        for action in actions:
            try:
                metadata = json.loads(action.metadata_json or '{}')
            except json.JSONDecodeError:
                metadata = {}
            timeline.append({'type': action.action_type, 'at': action.created_at, 'metadata': metadata})
        timeline.extend({'type': 'CONSULTATION', 'at': event.consultation_start or event.created_at,
                         'metadata': db._dict(event)} for event in events)
        timeline.extend({'type': 'EMAIL_SENT', 'at': email.sent_at,
                         'metadata': {'recipient': email.recipient, 'subject': email.subject}} for email in emails)
        timeline.sort(key=lambda item: item.get('at') or '', reverse=True)
        return dict(serialize_contact(contact), deals=[db._dict(deal) for deal in deals], timeline=timeline)


class ConvertLead(BaseModel):
    opportunity_name: str = Field(default='', max_length=240)
    deal_value: float | None = Field(default=None, ge=0)
    expected_close: str | None = None
    next_action: str = Field(default='', max_length=500)
    next_action_at: str | None = None


@router.post('/lifecycle/contacts/{contact_id}/convert-to-lead')
def convert_to_lead(contact_id: int, payload: ConvertLead, request: Request):
    with db.session_scope() as s:
        contact = owned_contact(s, owner_id(request), contact_id)
        existing = s.execute(
            select(Deal).where(Deal.prospect_id == contact.id, Deal.status == 'ACTIVE').order_by(Deal.id.desc())
        ).scalars().first()
        contact.lifecycle_stage = 'LEAD' if contact.lifecycle_stage != 'CUSTOMER' else 'CUSTOMER'
        contact.sales_status = 'REPLIED' if contact.sales_status in ('NOT_CONTACTED', 'ATTEMPTED', 'CONTACTED') else contact.sales_status
        contact.last_activity_at = now_iso()
        deal = existing or Deal(
            prospect_id=contact.id,
            name=payload.opportunity_name.strip() or f"{contact.company or contact.name} Opportunity",
            stage='NEW_LEAD', status='ACTIVE'
        )
        deal.deal_value = payload.deal_value
        deal.expected_close = payload.expected_close
        deal.next_action = payload.next_action.strip() or None
        deal.next_action_at = payload.next_action_at
        s.add(deal)
        s.flush()
        s.add(ExternalAction(prospect_id=contact.id, action_type='CONVERTED_TO_LEAD',
                             metadata_json=json.dumps({'deal_id': deal.id, 'stage': deal.stage})))
        return {'contact_id': contact.id, 'deal': db._dict(deal), 'lifecycle_stage': contact.lifecycle_stage}


@router.get('/deals')
def list_deals(request: Request, campaign: str | None = None, status: str | None = None):
    with db.SessionLocal() as s:
        query = (select(Deal, Prospect)
                 .join(Prospect, Deal.prospect_id == Prospect.id)
                 .join(Campaign, Prospect.campaign_id == Campaign.id))
        if owner_id(request) is not None:
            query = query.where(Campaign.owner_id == owner_id(request))
        if campaign:
            query = query.where(Campaign.slug == campaign)
        if status:
            query = query.where(Deal.status == status.upper())
        rows = s.execute(query.order_by(Deal.updated_at.desc(), Deal.id.desc())).all()
        return [dict(db._dict(deal), contact=serialize_contact(contact)) for deal, contact in rows]


@router.get('/deals/{deal_id}')
def deal_detail(deal_id: int, request: Request):
    with db.SessionLocal() as s:
        deal, contact, _ = owned_deal(s, owner_id(request), deal_id)
        detail = contact_detail(contact.id, request)
        return dict(db._dict(deal), contact=serialize_contact(contact), timeline=detail['timeline'])


class DealUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=240)
    stage: str | None = None
    deal_value: float | None = Field(default=None, ge=0)
    revenue_collected: float | None = Field(default=None, ge=0)
    expected_close: str | None = None
    next_action: str | None = Field(default=None, max_length=500)
    next_action_at: str | None = None
    lost_reason: str | None = Field(default=None, max_length=1000)


@router.patch('/deals/{deal_id}')
def update_deal(deal_id: int, payload: DealUpdate, request: Request):
    values = payload.model_dump(exclude_unset=True)
    if 'stage' in values:
        values['stage'] = values['stage'].upper()
        if values['stage'] not in DEAL_STAGES:
            raise HTTPException(400, 'Invalid deal stage')
    with db.session_scope() as s:
        deal, contact, _ = owned_deal(s, owner_id(request), deal_id)
        before = deal.stage
        for key, value in values.items():
            setattr(deal, key, value)
        deal.updated_at = now_iso()
        if deal.stage == 'WON':
            deal.status = 'WON'
            deal.closed_at = deal.closed_at or now_iso()
            contact.lifecycle_stage = 'CUSTOMER'
            contact.customer_since = contact.customer_since or deal.closed_at
            contact.sales_status = 'BOOKED'
            contact.booked_at = contact.booked_at or deal.closed_at
            contact.booked_value = deal.deal_value
        elif deal.stage == 'LOST':
            deal.status = 'LOST'
            deal.closed_at = deal.closed_at or now_iso()
        else:
            deal.status = 'ACTIVE'
            deal.closed_at = None
            if contact.lifecycle_stage == 'PROSPECT':
                contact.lifecycle_stage = 'LEAD'
        contact.last_activity_at = now_iso()
        s.add(ExternalAction(prospect_id=contact.id, action_type='DEAL_UPDATED',
                             metadata_json=json.dumps({'deal_id': deal.id, 'from_stage': before,
                                                       'to_stage': deal.stage, 'next_action': deal.next_action,
                                                       'next_action_at': deal.next_action_at})))
        return db._dict(deal)


class NewOpportunity(BaseModel):
    name: str = Field(default='', max_length=240)
    deal_value: float | None = Field(default=None, ge=0)
    expected_close: str | None = None


@router.post('/customers/{contact_id}/opportunities')
def new_opportunity(contact_id: int, payload: NewOpportunity, request: Request):
    with db.session_scope() as s:
        contact = owned_contact(s, owner_id(request), contact_id)
        if contact.lifecycle_stage != 'CUSTOMER':
            raise HTTPException(400, 'Only customers can start a repeat opportunity')
        deal = Deal(prospect_id=contact.id,
                    name=payload.name.strip() or f"{contact.company or contact.name} Opportunity",
                    stage='NEW_LEAD', status='ACTIVE', deal_value=payload.deal_value,
                    expected_close=payload.expected_close)
        s.add(deal)
        s.flush()
        s.add(ExternalAction(prospect_id=contact.id, action_type='NEW_OPPORTUNITY',
                             metadata_json=json.dumps({'deal_id': deal.id})))
        return db._dict(deal)


def period_start(period: str):
    now = datetime.now(timezone.utc)
    if period == 'week':
        return now - timedelta(days=7)
    if period == 'year':
        return datetime(now.year, 1, 1, tzinfo=timezone.utc)
    if period == 'month':
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return now - timedelta(days=30)


@router.get('/sales-revenue')
def sales_revenue(request: Request, campaign: str | None = None, period: str = '30d'):
    if period not in {'week', 'month', '30d', 'year'}:
        raise HTTPException(400, 'Invalid reporting period')
    with db.SessionLocal() as s:
        query = (select(Deal, Prospect)
                 .join(Prospect, Deal.prospect_id == Prospect.id)
                 .join(Campaign, Prospect.campaign_id == Campaign.id))
        if owner_id(request) is not None:
            query = query.where(Campaign.owner_id == owner_id(request))
        if campaign:
            query = query.where(Campaign.slug == campaign)
        rows = s.execute(query).all()
        start = period_start(period)
        def in_period(value):
            if not value:
                return False
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed >= start
            except ValueError:
                return False
        active = [deal for deal, _ in rows if deal.status == 'ACTIVE']
        won = [deal for deal, _ in rows if deal.status == 'WON' and in_period(deal.closed_at)]
        lost = [deal for deal, _ in rows if deal.status == 'LOST' and in_period(deal.closed_at)]
        decided = len(won) + len(lost)
        table = [dict(db._dict(deal), contact_name=contact.name,
                      company=contact.company or contact.name, lead_source=contact.lead_source)
                 for deal, contact in rows]
        return {
            'period': period,
            'active_pipeline_value': sum(deal.deal_value or 0 for deal in active),
            'revenue_won': sum(deal.deal_value or 0 for deal in won),
            'revenue_collected': sum(deal.revenue_collected or 0 for deal in won),
            'revenue_lost': sum(deal.deal_value or 0 for deal in lost),
            'average_deal_size': (sum(deal.deal_value or 0 for deal in won) / len(won)) if won else 0,
            'close_rate': (len(won) / decided * 100) if decided else 0,
            'deals_won': len(won),
            'deals': table,
        }


@router.get('/home/command-center')
def command_center(request: Request, campaign: str | None = None):
    with db.SessionLocal() as s:
        contacts = s.execute(owned_contact_query(owner_id(request), campaign)).scalars().all()
        ids = [contact.id for contact in contacts]
        actions = latest_next_actions(s, ids)
        deals = s.execute(select(Deal).where(Deal.prospect_id.in_(ids))).scalars().all() if ids else []
        events = s.execute(select(CalendarEvent).where(CalendarEvent.prospect_id.in_(ids))).scalars().all() if ids else []
        now = datetime.now(timezone.utc)
        today = now.date()
        def due(action):
            value = (action or {}).get('due_at')
            if not value:
                return False
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00')).date() <= today
            except ValueError:
                return False
        by_id = {contact.id: contact for contact in contacts}
        followups = [serialize_contact(by_id[cid], action) for cid, action in actions.items()
                     if cid in by_id and due(action)]
        upcoming = []
        for event in events:
            try:
                when = datetime.fromisoformat((event.consultation_start or '').replace('Z', '+00:00'))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                if now <= when <= now + timedelta(days=14):
                    upcoming.append(dict(db._dict(event), contact=serialize_contact(by_id[event.prospect_id])))
            except (ValueError, KeyError):
                pass
        return {
            'prospects_needing_outreach': [serialize_contact(c) for c in contacts
                                            if c.lifecycle_stage == 'PROSPECT' and c.sales_status == 'NOT_CONTACTED'][:8],
            'followups_due': followups[:8],
            'active_leads': sum(1 for c in contacts if c.lifecycle_stage == 'LEAD'),
            'upcoming_consultations': sorted(upcoming, key=lambda e: e.get('consultation_start') or '')[:8],
            'awaiting_decision': [dict(db._dict(d), contact=serialize_contact(by_id[d.prospect_id]))
                                  for d in deals if d.stage == 'DECISION' and d.status == 'ACTIVE'][:8],
            'recently_won': [dict(db._dict(d), contact=serialize_contact(by_id[d.prospect_id]))
                             for d in sorted(deals, key=lambda x: x.closed_at or '', reverse=True)
                             if d.status == 'WON'][:5],
            'pipeline_value': sum(d.deal_value or 0 for d in deals if d.status == 'ACTIVE'),
            'revenue_collected': sum(d.revenue_collected or 0 for d in deals if d.status == 'WON'),
        }
