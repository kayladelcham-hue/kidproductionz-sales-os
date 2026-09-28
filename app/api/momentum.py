"""Event-based KP Momentum. Rewards outcomes, never page views or clicks."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from . import database_v2 as db
from .models import MomentumEvent

EVENT_POINTS={
    "lead_reviewed":5,
    "qualified_lead_contacted":10,
    "followup_completed":15,
    "reply_received":20,
    "meeting_booked":30,
    "proposal_sent":50,
    "deal_won":100,
    "daily_mission_completed":25,
}
LEVELS=[("Starter",0),("Prospector",100),("Pipeline Builder",300),("Conversation Starter",750),("Deal Maker",1500),("Closer",3000),("Rainmaker",6000)]
MISSION={"qualified_contacts":8,"meetings":1}

def award(user_id:int,event_type:str,idempotency_key:str,prospect_id:int|None=None,metadata:dict|None=None,quality_score:float|None=None):
    if event_type not in EVENT_POINTS:raise ValueError("Unknown Momentum event")
    points=EVENT_POINTS[event_type]
    if event_type=="qualified_lead_contacted" and (quality_score is None or quality_score<65):points=5
    try:
        with db.session_scope() as s:
            row=MomentumEvent(user_id=user_id,prospect_id=prospect_id,event_type=event_type,points=points,idempotency_key=idempotency_key,metadata_json=json.dumps(metadata or {}))
            s.add(row);s.flush()
    except IntegrityError:
        return {"awarded":False,"points":0,"event_type":event_type}
    result={"awarded":True,"points":points,"event_type":event_type}
    if event_type!="daily_mission_completed" and summary(user_id)["mission"]["complete"]:
        bonus=award(user_id,"daily_mission_completed",f"daily_mission_completed:{user_id}:{datetime.now(timezone.utc).date().isoformat()}")
        result["mission_complete"]=bool(bonus.get("awarded"));result["bonus_points"]=bonus.get("points",0)
    return result

def level_for(total:int):
    current=LEVELS[0];following=None
    for item in LEVELS:
        if total>=item[1]:current=item
        elif following is None:following=item;break
    return {"name":current[0],"floor":current[1],"next_name":following[0] if following else None,"next_at":following[1] if following else None,"remaining":max(0,following[1]-total) if following else 0}

def summary(user_id:int):
    now=datetime.now(timezone.utc);today=now.date().isoformat();week_start=(now.date()-timedelta(days=now.weekday())).isoformat()
    with db.SessionLocal() as s:
        events=list(s.execute(select(MomentumEvent).where(MomentumEvent.user_id==user_id).order_by(MomentumEvent.id.desc())).scalars())
    total=sum(e.points for e in events)
    today_events=[e for e in events if str(e.created_at)[:10]==today]
    week_events=[e for e in events if str(e.created_at)[:10]>=week_start]
    contacts=sum(e.event_type=="qualified_lead_contacted" for e in today_events)
    meetings=sum(e.event_type=="meeting_booked" for e in today_events)
    mission_complete=contacts>=MISSION["qualified_contacts"] and meetings>=MISSION["meetings"]
    active_days=len({str(e.created_at)[:10] for e in week_events if e.event_type!="daily_mission_completed"})
    return {"total":total,"level":level_for(total),"mission":{"contacts":contacts,"contacts_target":MISSION["qualified_contacts"],"meetings":meetings,"meetings_target":MISSION["meetings"],"complete":mission_complete},"selling_rhythm":{"active_days":active_days},"recent":[{"event_type":e.event_type,"points":e.points,"created_at":e.created_at} for e in events[:10]],"config":{"event_points":EVENT_POINTS,"levels":[{"name":n,"threshold":t} for n,t in LEVELS],"mission":MISSION}}
