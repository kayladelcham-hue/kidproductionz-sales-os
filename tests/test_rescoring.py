import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import database_v2 as db
from app.api.icp import score_lead
from app.api.models import Base, Campaign, IcpProfile, LeadScoreHistory, LeadSignal, Prospect, User
from app.api.rescoring import extract_signals, rescore, router


PROFILE = {
    "offer": "Short-form content",
    "target_industries": ["Boutique hotel"],
    "business_types": ["Hospitality"],
    "geography": ["Florida", "FL"],
    "buyer_roles": ["Owner", "Marketing Director"],
    "problems_solved": ["Weak video content"],
    "positive_signals": ["new location", "launch", "expansion"],
    "need_signals": ["active promotion"],
}


@pytest.fixture
def rescoring_db(tmp_path, monkeypatch):
    engine=create_engine("sqlite:///"+str(tmp_path/"rescoring.db"),connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(db,"SessionLocal",sessions)
    with sessions.begin() as session:
        user=User(email="owner@example.com",name="Owner",password_hash="x",status="ACTIVE")
        session.add(user);session.flush()
        campaign=Campaign(slug="manual",name="Manual",owner_id=user.id)
        session.add(campaign);session.flush()
        session.add(IcpProfile(user_id=user.id,profile_json=json.dumps(PROFILE),weights_json="{}",version=1,completed=1))
        lead=Prospect(campaign_id=campaign.id,name="Harbor House",website="https://harbor.example",social="https://instagram.com/harborhouse",city="Tampa",state="FL",lead_source="MANUAL",icp_score=55,icp_priority="REVIEW")
        old=Prospect(campaign_id=campaign.id,name="Old Lead",city="Tampa",state="FL",created_at="2024-01-01T00:00:00+00:00")
        session.add_all([lead,old]);session.flush();ids={"user":user.id,"lead":lead.id,"old":old.id}
    return sessions,ids


def test_single_manual_lead_refresh_uses_website_evidence_and_history(rescoring_db):
    sessions,ids=rescoring_db
    html="Harbor House is a boutique hotel in Tampa. Our new location is now open with a premium guest experience."
    result=rescore(ids["lead"],ids["user"],ids["user"],True,fetcher=lambda _:html)
    assert result["new_score"]>result["previous_score"]
    assert result["score_delta"]==result["new_score"]-55
    assert "WEBSITE" in result["sources_used"]
    assert all(item["evidence_text"] for item in result["evidence"])
    with sessions() as session:
        assert session.scalar(select(LeadScoreHistory)).trigger_type=="MANUAL"
        assert session.scalars(select(LeadSignal)).all()


def test_social_enrichment_is_evidence_based(rescoring_db):
    _,ids=rescoring_db
    result=rescore(ids["lead"],ids["user"],ids["user"],True,fetcher=lambda url:"New service launch. Reserve your spot at our upcoming event." if "instagram" in url else "Harbor House")
    social=[item for item in result["evidence"] if item["source_type"]=="SOCIAL"]
    assert {item["signal_type"] for item in social}>={"LAUNCH","EVENT"}
    assert all(item["confidence"]=="HIGH" for item in social)


def test_failed_enrichment_is_unknown_and_does_not_create_negative_signal(rescoring_db):
    _,ids=rescoring_db
    result=rescore(ids["lead"],ids["user"],ids["user"],True,fetcher=lambda _:(_ for _ in ()).throw(ValueError("Platform unavailable")))
    assert result["enrichment_errors"]
    assert not any("unavailable" in risk.casefold() for risk in result["risks"])
    assert not result["evidence"]


def test_missing_contact_is_missing_information_not_a_risk():
    result=score_lead({"name":"Unknown business","city":"Tampa","state":"FL"},PROFILE)
    assert "A contact path has not been identified yet" in result["missing_information"]
    assert "No usable contact path" not in result["risks"]


def test_direct_negative_evidence_can_disqualify(rescoring_db):
    _,ids=rescoring_db
    result=rescore(ids["lead"],ids["user"],ids["user"],True,fetcher=lambda _:"Harbor House is permanently closed for business.")
    assert result["new_score"]<=49
    assert any("closed" in risk.casefold() for risk in result["risks"])


def test_current_icp_version_is_recorded_and_changes_future_rescore(rescoring_db):
    sessions,ids=rescoring_db
    first=rescore(ids["lead"],ids["user"],ids["user"],False)
    with sessions.begin() as session:
        profile=session.scalar(select(IcpProfile));profile.profile_json=json.dumps({**PROFILE,"geography":["California"]});profile.version=2
    second=rescore(ids["lead"],ids["user"],ids["user"],False)
    assert first["icp_version"]==1 and second["icp_version"]==2
    assert second["new_score"]<=49


def test_historical_lead_can_be_rescored_without_enrichment(rescoring_db):
    sessions,ids=rescoring_db
    result=rescore(ids["old"],ids["user"],ids["user"],False)
    assert result["history_id"]
    with sessions() as session:
        assert session.get(Prospect,ids["old"]).last_scored_at


def test_low_confidence_evidence_is_not_fed_into_scoring(rescoring_db):
    sessions,ids=rescoring_db
    with sessions.begin() as session:
        session.add(LeadSignal(prospect_id=ids["lead"],signal_type="RUMOR",signal_value="new location",polarity="POSITIVE",source_type="SOCIAL",source_url="https://example.test",evidence_text="Unverified mention",confidence="LOW"))
    with_low=rescore(ids["lead"],ids["user"],ids["user"],False)
    with sessions.begin() as session:
        session.execute(__import__("sqlalchemy").delete(LeadSignal))
    without=rescore(ids["lead"],ids["user"],ids["user"],False)
    assert with_low["new_score"]==without["new_score"]


def test_extracted_signals_always_include_source_and_confidence():
    signals=extract_signals("We are hiring for our new location.","WEBSITE","https://example.com",PROFILE)
    assert signals
    assert all(item["source_url"] and item["source_type"] and item["confidence"] for item in signals)


def test_confirmed_batch_rescoring_returns_change_summary(rescoring_db):
    _,ids=rescoring_db
    app=FastAPI()
    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id=ids["user"]
        return await call_next(request)
    app.include_router(router)
    response=TestClient(app).post("/api/prospects/rescore-batch",json={"prospect_ids":[ids["lead"],ids["old"]],"confirmed":True})
    assert response.status_code==200
    body=response.json()
    assert body["completed"]==2
    assert body["moved_up"]+body["moved_down"]+body["stayed_similar"]==2
