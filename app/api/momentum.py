"""Event-based KP Momentum. Rewards outcomes, never page views or clicks."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
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
    "weekly_goal_completed":50,
    "personal_record_set":0,
    "selling_session_completed":0,
}
LEVELS=[("Starter",0),("Prospector",100),("Pipeline Builder",300),("Conversation Starter",750),("Deal Maker",1500),("Closer",3000),("Rainmaker",6000)]
MISSION={"qualified_contacts":8,"meetings_stretch":1,"reward":25}
WEEKLY_GOAL={"meaningful_moves":40,"reward":50}
MEANINGFUL_EVENTS={"qualified_lead_contacted","followup_completed","reply_received","meeting_booked","proposal_sent","deal_won"}
UNLOCKS=[
    {"threshold":100,"name":"Outreach template pack","description":"More ways to start a relevant conversation."},
    {"threshold":300,"name":"Pitch-angle prompts","description":"Additional coaching for stronger lead angles."},
    {"threshold":750,"name":"Focused Power Hour","description":"Timed, distraction-light selling sessions."},
    {"threshold":1500,"name":"Sales playbooks","description":"Deeper guidance for active opportunities."},
    {"threshold":3000,"name":"Advanced lead insights","description":"More context for prioritizing strong opportunities."},
]

def award(user_id:int,event_type:str,idempotency_key:str,prospect_id:int|None=None,metadata:dict|None=None,quality_score:float|None=None):
    if event_type not in EVENT_POINTS:raise ValueError("Unknown Momentum event")
    points=EVENT_POINTS[event_type]
    if event_type=="qualified_lead_contacted" and (quality_score is None or quality_score<65):points=5
    try:
        with db.session_scope() as s:
            row=MomentumEvent(user_id=user_id,prospect_id=prospect_id,event_type=event_type,points=points,idempotency_key=idempotency_key,metadata_json=json.dumps(metadata or {}),created_at=datetime.now(timezone.utc).isoformat())
            s.add(row);s.flush()
    except IntegrityError:
        return {"awarded":False,"points":0,"event_type":event_type}
    result={"awarded":True,"points":points,"event_type":event_type}
    if event_type not in {"daily_mission_completed","weekly_goal_completed","personal_record_set","selling_session_completed"}:
        progress=summary(user_id)
        if progress["mission"]["complete"]:
            bonus=award(user_id,"daily_mission_completed",f"daily_mission_completed:{user_id}:{datetime.now(timezone.utc).date().isoformat()}")
            result["mission_complete"]=bool(bonus.get("awarded"));result["bonus_points"]=bonus.get("points",0)
        if progress["weekly_goal"]["complete"]:
            weekly=award(user_id,"weekly_goal_completed",f"weekly_goal_completed:{user_id}:{progress['weekly_goal']['week_start']}")
            result["weekly_goal_complete"]=bool(weekly.get("awarded"));result["weekly_bonus_points"]=weekly.get("points",0)
    return result

def level_for(total:int):
    current=LEVELS[0];following=None
    for item in LEVELS:
        if total>=item[1]:current=item
        elif following is None:following=item;break
    return {"name":current[0],"floor":current[1],"next_name":following[0] if following else None,"next_at":following[1] if following else None,"remaining":max(0,following[1]-total) if following else 0}

def _date(value):return str(value or "")[:10]

def _metadata(event):
    try:return json.loads(event.metadata_json or "{}")
    except (TypeError,ValueError):return {}

def _records(events):
    contact_days=Counter(_date(event.created_at) for event in events if event.event_type=="qualified_lead_contacted")
    week_days=defaultdict(set)
    for event in events:
        if event.event_type in MEANINGFUL_EVENTS and _date(event.created_at):
            try:day=datetime.fromisoformat(_date(event.created_at)).date()
            except ValueError:continue
            week=(day-timedelta(days=day.weekday())).isoformat();week_days[week].add(day.isoformat())
    won_values=[float(_metadata(event).get("deal_value") or 0) for event in events if event.event_type=="deal_won"]
    records=[{"name":"Best contact day","value":max(contact_days.values(),default=0),"detail":"qualified leads contacted in one day"},{"name":"Best selling rhythm","value":max((len(days) for days in week_days.values()),default=0),"detail":"active days in one week"}]
    for name,event_type in [("First reply","reply_received"),("First meeting","meeting_booked"),("First proposal","proposal_sent"),("First won deal","deal_won")]:
        if any(event.event_type==event_type for event in events):records.append({"name":name,"value":1,"detail":"Milestone reached"})
    if won_values and max(won_values)>0:records.append({"name":"Highest-value win","value":max(won_values),"detail":"verified deal value","currency":True})
    return records

def summary(user_id:int):
    now=datetime.now(timezone.utc);today=now.date().isoformat();week_start=(now.date()-timedelta(days=now.weekday())).isoformat()
    with db.SessionLocal() as s:
        events=list(s.execute(select(MomentumEvent).where(MomentumEvent.user_id==user_id).order_by(MomentumEvent.id.desc())).scalars())
    total=sum(e.points for e in events)
    today_events=[e for e in events if str(e.created_at)[:10]==today]
    week_events=[e for e in events if str(e.created_at)[:10]>=week_start]
    contacts=sum(e.event_type=="qualified_lead_contacted" for e in today_events);meetings=sum(e.event_type=="meeting_booked" for e in today_events)
    mission_complete=contacts>=MISSION["qualified_contacts"]
    meaningful=[event for event in week_events if event.event_type in MEANINGFUL_EVENTS];counts=Counter(event.event_type for event in meaningful)
    active_days=len({_date(event.created_at) for event in meaningful});records=_records(events);best=max([active_days]+[int(record["value"]) for record in records if record["name"]=="Best selling rhythm"])
    unlock=next((item for item in UNLOCKS if total<item["threshold"]),None)
    return {"total":total,"level":level_for(total),"mission":{"contacts":contacts,"contacts_target":MISSION["qualified_contacts"],"meetings":meetings,"meetings_target":MISSION["meetings_stretch"],"moves_remaining":max(0,MISSION["qualified_contacts"]-contacts),"reward":MISSION["reward"],"complete":mission_complete},"weekly_goal":{"week_start":week_start,"meaningful_moves":len(meaningful),"target":WEEKLY_GOAL["meaningful_moves"],"remaining":max(0,WEEKLY_GOAL["meaningful_moves"]-len(meaningful)),"reward":WEEKLY_GOAL["reward"],"complete":len(meaningful)>=WEEKLY_GOAL["meaningful_moves"],"contacts":counts["qualified_lead_contacted"],"followups":counts["followup_completed"],"replies":counts["reply_received"],"meetings":counts["meeting_booked"],"proposals":counts["proposal_sent"],"wins":counts["deal_won"]},"selling_rhythm":{"active_days":active_days,"best_week":best},"personal_records":records,"recent":[{"event_type":e.event_type,"points":e.points,"created_at":e.created_at,"metadata":_metadata(e)} for e in events[:20]],"next_unlock":{**unlock,"remaining":max(0,unlock["threshold"]-total)} if unlock else None,"unlocks":[{**item,"unlocked":total>=item["threshold"]} for item in UNLOCKS],"config":{"event_points":EVENT_POINTS,"levels":[{"name":n,"threshold":t} for n,t in LEVELS],"mission":MISSION,"weekly_goal":WEEKLY_GOAL}}
