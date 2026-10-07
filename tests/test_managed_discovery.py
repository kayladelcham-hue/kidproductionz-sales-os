import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import database_v2 as db, managed_discovery as discovery, request_context, outscraper_service
from app.api.models import Base


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///'+str(tmp_path/'discovery.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    discovery.metadata.create_all(engine)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(db, 'SessionLocal', sessionmaker(bind=engine, expire_on_commit=False))
    monkeypatch.setenv('KP_OUTSCRAPER_API_KEY', 'synthetic-server-key')
    monkeypatch.setenv('DISCOVERY_MONTHLY_BUDGET_USD', '50')
    monkeypatch.setenv('DISCOVERY_COST_MICROS_PER_RECORD', '3000')
    for tier in discovery.TIERS:
        monkeypatch.delenv(f'DISCOVERY_{tier.upper()}_MONTHLY_LEADS', raising=False)
    token = request_context.user_id.set(1)
    yield engine
    request_context.user_id.reset(token)
    engine.dispose()


def test_unconfigured_and_anonymous_never_call_provider(isolated, monkeypatch):
    monkeypatch.delenv('KP_OUTSCRAPER_API_KEY')
    monkeypatch.delenv('OUTSCRAPER_API_KEY', raising=False)
    with pytest.raises(HTTPException) as error:
        discovery.reserve(10)
    assert error.value.status_code == 503
    request_context.user_id.set(0)
    with pytest.raises(HTTPException) as error:
        discovery.status()
    assert error.value.status_code == 401


def test_tiers_and_owner_isolation(isolated):
    discovery.reserve(100)
    assert discovery.status()['remaining'] == 0
    request_context.user_id.set(2)
    db.save_settings({'discovery:plan:2': 'growth'})
    assert discovery.status()['monthly_limit'] == 1000
    assert discovery.status()['used'] == 0


def test_quota_failure_rolls_back_shared_budget(isolated):
    discovery.reserve(100)
    with pytest.raises(HTTPException) as error:
        discovery.reserve(1)
    assert error.value.status_code == 429
    with isolated.connect() as conn:
        assert conn.execute(select(discovery.usage.c.records).where(discovery.usage.c.scope == 'global')).scalar_one() == 100


def test_shared_budget_across_users_and_concurrent_requests(isolated, monkeypatch):
    monkeypatch.setenv('DISCOVERY_MONTHLY_BUDGET_USD', '.03')
    def reserve(uid):
        token = request_context.user_id.set(uid)
        try:
            discovery.reserve(10)
            return True
        except HTTPException as error:
            assert error.status_code == 429
            return False
        finally:
            request_context.user_id.reset(token)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(1,5))) == 1


def test_monthly_reset_and_repeated_limits(isolated, monkeypatch):
    monkeypatch.setattr(discovery, 'period', lambda: '2026-10')
    discovery.reserve(100)
    monkeypatch.setattr(discovery, 'period', lambda: '2026-11')
    assert discovery.status()['remaining'] == 100
    discovery.reserve(10)
    with pytest.raises(HTTPException):
        discovery.reserve(101)


def test_confirmation_cache_is_private_and_avoids_second_charge(isolated, monkeypatch):
    calls = []
    def provider(request, timeout):
        calls.append(request)
        return io.BytesIO(json.dumps({'data': [[{'name':'Synthetic Salon', 'place_id':'test'}]]}).encode())
    monkeypatch.setattr(outscraper_service, 'urlopen', provider)
    first = outscraper_service.search_google_maps('Synthetic salon Orlando', 10)
    second = outscraper_service.search_google_maps('Synthetic salon Orlando', 10)
    assert first == second
    assert len(calls) == 1
    assert discovery.status()['used'] == 10
    request_context.user_id.set(2)
    outscraper_service.search_google_maps('Synthetic salon Orlando', 10)
    assert len(calls) == 2
    assert discovery.status()['used'] == 10


def test_provider_failure_keeps_reservation(isolated, monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(outscraper_service, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='OUTSCRAPER_TIMEOUT'):
        outscraper_service.search_google_maps('Synthetic salon Orlando', 10)
    assert discovery.status()['used'] == 10
