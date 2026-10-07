"""Server-owned discovery credentials and durable, atomic usage reservations."""
import os
import hashlib
import json
import time
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, select, update

from . import request_context

TIERS = {'beta': 100, 'starter': 250, 'growth': 1000, 'pro': 2500}
metadata = MetaData()
usage = Table('managed_discovery_usage', metadata,
    Column('period', String(7), primary_key=True),
    Column('scope', String(80), primary_key=True),
    Column('records', Integer, nullable=False, default=0),
    Column('cost_micros', Integer, nullable=False, default=0))
cache = Table('managed_discovery_cache', metadata,
    Column('owner_id', Integer, primary_key=True),
    Column('fingerprint', String(64), primary_key=True),
    Column('expires_at', Integer, nullable=False),
    Column('payload', Text, nullable=False))


def cached_search(query, limit, category, result=None):
    """Owner-scoped 15-minute cache so confirming a preview reuses its search."""
    from .database_v2 import engine
    uid = owner()
    fingerprint = hashlib.sha256(json.dumps([period(), query, limit, category]).encode()).hexdigest()
    metadata.create_all(engine)
    with engine.begin() as conn:
        if result is None:
            row = conn.execute(select(cache).where(cache.c.owner_id == uid,
                cache.c.fingerprint == fingerprint, cache.c.expires_at > int(time.time()))).first()
            return json.loads(row.payload) if row else None
        if engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        values = {'expires_at': int(time.time())+900, 'payload': json.dumps(result)}
        conn.execute(insert(cache).values(owner_id=uid, fingerprint=fingerprint, **values)
            .on_conflict_do_update(index_elements=['owner_id', 'fingerprint'], set_=values))
        conn.execute(cache.delete().where(cache.c.expires_at <= int(time.time())))


def owner():
    uid = request_context.user_id.get()
    if not uid:
        raise HTTPException(401, 'Sign in to find leads.')
    return uid


def server_key():
    # Dedicated key takes precedence. Never expose or modify either key in the UI.
    return (os.getenv('KP_OUTSCRAPER_API_KEY') or os.getenv('OUTSCRAPER_API_KEY') or '').strip()


def period():
    return datetime.now(timezone.utc).strftime('%Y-%m')


def limits(uid):
    from .database_v2 import get_settings
    plan = get_settings('discovery:plan:').get(f'discovery:plan:{uid}', 'beta')
    if plan not in TIERS:
        plan = 'beta'
    allowance = int(os.getenv(f'DISCOVERY_{plan.upper()}_MONTHLY_LEADS', str(TIERS[plan])))
    budget = int(Decimal(os.getenv('DISCOVERY_MONTHLY_BUDGET_USD', '50')) * 1000000)
    rate = int(os.getenv('DISCOVERY_COST_MICROS_PER_RECORD', '3000'))
    if allowance < 0 or budget < 0 or rate <= 0:
        raise HTTPException(503, 'Lead discovery configuration needs attention.')
    return plan, allowance, budget, rate


def status():
    from .database_v2 import engine
    uid = owner()
    plan, allowance, budget, rate = limits(uid)
    metadata.create_all(engine)
    with engine.connect() as conn:
        rows = {r.scope: r for r in conn.execute(select(usage).where(
            usage.c.period == period(), usage.c.scope.in_(['global', f'user:{uid}'])))}
    used = rows[f'user:{uid}'].records if f'user:{uid}' in rows else 0
    spent = rows['global'].cost_micros if 'global' in rows else 0
    remaining = max(0, allowance - used)
    available = bool(server_key()) and remaining > 0 and budget - spent >= rate
    return {'configured': bool(server_key()), 'managed': True, 'tier': plan,
            'monthly_limit': allowance, 'used': used, 'remaining': remaining,
            'available': available, 'period': period(),
            'max_per_search': min(100, remaining, max(0, (budget-spent)//rate)),
            'message': 'Lead discovery is included. No API key needed.' if available else
                'Lead discovery is temporarily unavailable.' if not server_key() or budget-spent < rate else
                'Your monthly lead allowance has been used. It resets next month.'}


def reserve(records):
    """Reserve requested records BEFORE network I/O, retaining uncertain failures.

    The dollar budget is an estimate at the configured unit rate, not a vendor
    billing guarantee. Counting requested rather than returned records is conservative.
    """
    from .database_v2 import engine
    uid = owner()
    if not server_key():
        raise HTTPException(503, 'Lead discovery is temporarily unavailable. Contact your workspace admin.')
    _, allowance, budget, rate = limits(uid)
    if records < 1 or records > 100:
        raise HTTPException(422, 'Choose between 1 and 100 leads per search.')
    metadata.create_all(engine)
    month = period()
    if engine.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif engine.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise HTTPException(503, 'Lead discovery database is unsupported.')
    with engine.begin() as conn:
        for scope in ('global', f'user:{uid}'):
            conn.execute(insert(usage).values(period=month, scope=scope, records=0, cost_micros=0)
                         .on_conflict_do_nothing(index_elements=['period', 'scope']))
        # All requests acquire the global row first; rollback releases both reservations.
        global_result = conn.execute(update(usage).where(
            usage.c.period == month, usage.c.scope == 'global',
            usage.c.cost_micros + records*rate <= budget).values(
                records=usage.c.records+records, cost_micros=usage.c.cost_micros+records*rate))
        if global_result.rowcount != 1:
            raise HTTPException(429, 'Lead discovery has reached its shared monthly budget. Try next month or contact your admin.')
        user_result = conn.execute(update(usage).where(
            usage.c.period == month, usage.c.scope == f'user:{uid}',
            usage.c.records+records <= allowance).values(
                records=usage.c.records+records, cost_micros=usage.c.cost_micros+records*rate))
        if user_result.rowcount != 1:
            raise HTTPException(429, 'This search exceeds your remaining monthly lead allowance. Request fewer leads or contact your admin.')
