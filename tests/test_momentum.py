from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import database_v2 as db
from app.api.models import Base, MomentumEvent
from app.api.momentum import EVENT_POINTS, LEVELS, award, level_for, summary


def test_momentum_rewards_meaningful_sales_events_only():
    assert "page_view" not in EVENT_POINTS
    assert "button_clicked" not in EVENT_POINTS
    assert EVENT_POINTS["qualified_lead_contacted"] < EVENT_POINTS["meeting_booked"]
    assert EVENT_POINTS["meeting_booked"] < EVENT_POINTS["deal_won"]


def test_levels_report_current_and_next_progress():
    progress = level_for(740)
    assert progress == {
        "name": "Pipeline Builder",
        "floor": 300,
        "next_name": "Conversation Starter",
        "next_at": 750,
        "remaining": 10,
    }
    assert level_for(LEVELS[-1][1] + 100)["next_name"] is None


@pytest.fixture
def momentum_db(tmp_path, monkeypatch):
    engine=create_engine("sqlite:///"+str(tmp_path/"momentum.db"),connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(db,"SessionLocal",sessions)
    return sessions


def test_duplicate_real_world_event_is_awarded_once(momentum_db):
    first=award(7,"qualified_lead_contacted","contact:7:21",21,quality_score=90)
    duplicate=award(7,"qualified_lead_contacted","contact:7:21",21,quality_score=90)
    assert first["awarded"] is True and first["points"]==10
    assert duplicate=={"awarded":False,"points":0,"event_type":"qualified_lead_contacted"}
    with momentum_db() as session:
        assert len(session.scalars(select(MomentumEvent)).all())==1


def test_low_quality_outreach_receives_reduced_reward(momentum_db):
    assert award(3,"qualified_lead_contacted","low-fit",31,quality_score=40)["points"]==5
    assert award(3,"qualified_lead_contacted","good-fit",32,quality_score=82)["points"]==10


def test_daily_mission_uses_controllable_activity_and_rewards_once(momentum_db):
    results=[award(9,"qualified_lead_contacted",f"contact:{index}",index,quality_score=90) for index in range(8)]
    assert results[-1]["mission_complete"] is True
    progress=summary(9)
    assert progress["mission"]["complete"] is True
    assert progress["mission"]["meetings"]==0
    assert progress["mission"]["moves_remaining"]==0
    assert sum(item.event_type=="daily_mission_completed" for item in momentum_db().scalars(select(MomentumEvent)).all())==1


def test_weekly_progress_rhythm_records_and_unlocks_use_stored_events(momentum_db):
    now=datetime.now(timezone.utc)
    with momentum_db.begin() as session:
        session.add_all([
            MomentumEvent(user_id=4,event_type="qualified_lead_contacted",points=10,idempotency_key="a",created_at=(now-timedelta(days=1)).isoformat()),
            MomentumEvent(user_id=4,event_type="reply_received",points=20,idempotency_key="b",created_at=now.isoformat()),
            MomentumEvent(user_id=4,event_type="meeting_booked",points=30,idempotency_key="c",created_at=now.isoformat()),
            MomentumEvent(user_id=4,event_type="proposal_sent",points=50,idempotency_key="d",created_at=now.isoformat()),
            MomentumEvent(user_id=4,event_type="deal_won",points=100,idempotency_key="e",metadata_json='{"deal_value":2500}',created_at=now.isoformat()),
        ])
    progress=summary(4)
    assert progress["weekly_goal"]["meaningful_moves"]==(4 if now.weekday()==0 else 5)
    assert progress["weekly_goal"]["replies"]==1 and progress["weekly_goal"]["proposals"]==1
    assert progress["selling_rhythm"]["active_days"]==(1 if now.weekday()==0 else 2)
    assert any(record["name"]=="Highest-value win" and record["value"]==2500 for record in progress["personal_records"])
    assert progress["next_unlock"]["name"]=="Pitch-angle prompts"


def test_weekly_goal_bonus_is_idempotent(momentum_db):
    with momentum_db.begin() as session:
        now=datetime.now(timezone.utc).isoformat()
        session.add_all([MomentumEvent(user_id=12,event_type="followup_completed",points=15,idempotency_key=f"move:{index}",created_at=now) for index in range(39)])
    result=award(12,"qualified_lead_contacted","fortieth",80,quality_score=90)
    assert result["weekly_goal_complete"] is True and result["weekly_bonus_points"]==50
    duplicate=award(12,"reply_received","after-goal",81)
    assert duplicate["weekly_goal_complete"] is False
    assert sum(item.event_type=="weekly_goal_completed" for item in momentum_db().scalars(select(MomentumEvent)).all())==1
