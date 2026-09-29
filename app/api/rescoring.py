"""User-controlled ICP rescoring with bounded public evidence enrichment."""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser

from fastapi import APIRouter, HTTPException, Request as ApiRequest
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from . import database_v2 as db
from .icp import score_lead
from .models import Campaign, LeadScoreHistory, LeadSignal, Prospect

router = APIRouter(prefix="/api")
MAX_BYTES = 500_000
USER_AGENT = "KP-Sales-OS-Evidence/1.0"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class VisiblePage(HTMLParser):
    def __init__(self, html: str):
        super().__init__(); self.parts=[]; self.hidden=0
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"): self.hidden=max(0,self.hidden-1)
    def handle_data(self, data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())
    @property
    def text(self):
        return re.sub(r"\s+", " ", " ".join(self.parts))[:80_000]


class RescoreRequest(BaseModel):
    refresh: bool = False


class BatchRescoreRequest(BaseModel):
    prospect_ids: list[int] = Field(default_factory=list, max_length=100)
    campaign: str | None = None
    refresh: bool = False
    confirmed: bool = False


RULES = [
    ("EXPANSION", "Recent expansion", r"\b(new|second|third|additional)\s+(location|property|office|studio)|\bexpan(?:d|ding|sion)\b"),
    ("HIRING", "Hiring activity", r"\b(?:we(?:'re| are) hiring|join our team|careers|job openings?)\b"),
    ("LAUNCH", "Recent launch", r"\b(?:now open|grand opening|newly opened|launch(?:ed|ing)?|new service|new product)\b"),
    ("EVENT", "Current event activity", r"\b(?:upcoming event|tickets? available|event calendar|reserve your spot)\b"),
    ("PROMOTION", "Active promotion", r"\b(?:limited time|special offer|book now|promotion|seasonal offer)\b"),
    ("PREMIUM", "Premium positioning", r"\b(?:luxury|boutique|premium|bespoke|exclusive)\b"),
    ("MULTI_LOCATION", "Multiple locations", r"\b(?:our locations|locations near|visit our .* locations)\b"),
]
NEGATIVE_RULES = [
    ("CLOSED", "Business reports that it is closed", r"\b(?:permanently closed|closed for business|ceased operations)\b"),
]


def _owner(request: ApiRequest):
    return getattr(request.state, "user_id", None)


def _user(request: ApiRequest):
    return _owner(request) or 0


def _safe_url(value: str | None) -> str | None:
    if not value: return None
    raw=value.strip()
    if not re.match(r"^https?://", raw, re.I): raw="https://"+raw
    p=urlsplit(raw)
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password or p.port not in (None,80,443): return None
    return raw


def fetch_public_text(url: str) -> str:
    """Fetch one public HTML page. No login, redirect, retry, or access-control bypass."""
    safe=_safe_url(url)
    if not safe: raise ValueError("Unsupported or invalid URL")
    p=urlsplit(safe)
    try:
        addresses=socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=="https" else 80))
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Website does not resolve to a public address")
    except OSError as exc:
        raise ValueError("Website is unavailable") from exc
    opener=build_opener(NoRedirect())
    origin=f"{p.scheme}://{p.netloc}"
    robots=RobotFileParser()
    try:
        try:
            with opener.open(Request(origin+"/robots.txt",headers={"User-Agent":USER_AGENT}),timeout=5) as response:
                robots.parse(response.read(100_000).decode("utf-8",errors="replace").splitlines())
            if not robots.can_fetch(USER_AGENT,safe): raise ValueError("Website access is disallowed by robots.txt")
        except HTTPError as exc:
            if exc.code != 404: raise ValueError("Website access policy could not be verified") from exc
        with opener.open(Request(safe,headers={"User-Agent":USER_AGENT}),timeout=8) as response:
            if response.headers.get_content_type() not in ("text/html","text/plain"): raise ValueError("Website did not return readable public text")
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES: raise ValueError("Website page is too large to inspect safely")
            return VisiblePage(raw.decode("utf-8",errors="replace")).text
    except ValueError: raise
    except Exception as exc: raise ValueError("Public page could not be read") from exc


def extract_signals(text: str, source_type: str, source_url: str, profile: dict) -> list[dict]:
    clean=re.sub(r"\s+"," ",text).strip(); lower=clean.casefold(); found=[]
    for signal_type,value,pattern in RULES:
        match=re.search(pattern,lower,re.I)
        if match:
            start=max(0,match.start()-70);end=min(len(clean),match.end()+110)
            found.append({"signal_type":signal_type,"signal_value":value,"polarity":"POSITIVE","source_type":source_type,"source_url":source_url,"evidence_text":clean[start:end].strip(),"confidence":"HIGH"})
    for signal_type,value,pattern in NEGATIVE_RULES:
        match=re.search(pattern,lower,re.I)
        if match:
            found.append({"signal_type":signal_type,"signal_value":value,"polarity":"NEGATIVE","source_type":source_type,"source_url":source_url,"evidence_text":clean[max(0,match.start()-60):min(len(clean),match.end()+90)].strip(),"confidence":"HIGH"})
    for target in (profile.get("target_industries") or [])+(profile.get("business_types") or []):
        if target.casefold() in lower and not any(x["signal_type"]=="INDUSTRY" for x in found):
            found.append({"signal_type":"INDUSTRY","signal_value":f"Website confirms {target}","polarity":"POSITIVE","source_type":source_type,"source_url":source_url,"evidence_text":f"The public page directly references “{target}”.","confidence":"HIGH"})
    return found[:20]


def _serialize_signal(row: LeadSignal) -> dict:
    return {column.name:getattr(row,column.name) for column in row.__table__.columns}


def rescore(prospect_id: int, user_id: int, owner_id: int | None, refresh: bool=False, trigger: str="MANUAL", fetcher=fetch_public_text) -> dict:
    profile_row=db.get_icp_profile(user_id)
    if not profile_row or not profile_row.get("completed"):
        raise ValueError("Complete your ICP before rescoring leads")
    now=datetime.now(timezone.utc).isoformat()
    errors=[]; refreshed_sources=[]
    with db.session_scope() as session:
        query=select(Prospect).where(Prospect.id==prospect_id)
        if owner_id is not None: query=query.join(Campaign,Prospect.campaign_id==Campaign.id).where(Campaign.owner_id==owner_id)
        prospect=session.execute(query).scalar_one_or_none()
        if not prospect: raise LookupError("Lead not found")
        previous=float(prospect.icp_score if prospect.icp_score is not None else prospect.score or 0)
        existing=list(session.execute(select(LeadSignal).where(LeadSignal.prospect_id==prospect_id)).scalars())
        if refresh:
            new=[]
            for source_type,url in (("WEBSITE",prospect.website),("SOCIAL",prospect.social)):
                safe=_safe_url(url)
                if not safe:
                    if url: errors.append({"source":source_type,"status":"UNSUPPORTED","message":"The saved URL is not supported."})
                    else: errors.append({"source":source_type,"status":"UNKNOWN","message":f"No {source_type.lower()} URL is saved."})
                    continue
                try:
                    text=fetcher(safe)
                    new.extend(extract_signals(text,source_type,safe,profile_row["profile"]))
                    refreshed_sources.append(source_type)
                except ValueError as exc:
                    errors.append({"source":source_type,"status":"UNAVAILABLE","message":str(exc)})
            if refreshed_sources:
                session.execute(delete(LeadSignal).where(LeadSignal.prospect_id==prospect_id,LeadSignal.source_type.in_(refreshed_sources)))
                existing=[row for row in existing if row.source_type not in refreshed_sources]
                for item in new:
                    row=LeadSignal(prospect_id=prospect_id,detected_at=now,last_verified_at=now,**item);session.add(row);existing.append(row)
                prospect.last_enriched_at=now
        signal_data=[_serialize_signal(row) for row in existing]
        scoring_input=db._dict(prospect)
        supported=[item["signal_value"]+" "+item["evidence_text"] for item in signal_data if item["confidence"] in ("HIGH","MEDIUM")]
        scoring_input["research"]=" ".join(filter(None,[scoring_input.get("research"),*supported]))
        if any(item["signal_type"]=="CLOSED" and item["confidence"]=="HIGH" for item in signal_data): scoring_input["status"]="permanently_closed"
        result=score_lead(scoring_input,profile_row["profile"],profile_row["weights"])
        signal_types={item["signal_type"] for item in signal_data if item["confidence"] in ("HIGH","MEDIUM")}
        if result["disqualifiers"]:
            result["recommended_action"]="Probably not worth your time unless you can verify that the disqualifier is outdated."
        elif "EXPANSION" in signal_types:
            result["recommended_action"]="Reach out now. Lead with their expansion or new location and the clearest result your offer can create."
        elif "LAUNCH" in signal_types:
            result["recommended_action"]="Reach out now and lead with the recent launch."
        elif not (prospect.phone or prospect.email):
            result["recommended_action"]="Find the owner or decision-maker first, then lead with the strongest verified signal."
        elif result["score"]>=80:
            result["recommended_action"]="Reach out now with a specific pitch tied to the strongest ICP match."
        elif not signal_data:
            result["recommended_action"]="Not enough current evidence yet. Keep this lead in review or add a public website before refreshing."
        result["evidence"]=signal_data
        result["enrichment_errors"]=errors
        result["sources_used"]=sorted({item["source_type"] for item in signal_data})
        result["previous_score"]=previous
        result["new_score"]=result["score"]
        result["score_delta"]=round(result["score"]-previous,1)
        result["icp_version"]=profile_row["version"]
        result["scored_at"]=now
        result["last_enriched_at"]=prospect.last_enriched_at
        prospect.icp_score=result["score"];prospect.icp_priority=result["priority"];prospect.icp_version=profile_row["version"]
        prospect.qualification_json=json.dumps(result);prospect.last_scored_at=now;prospect.updated_at=now
        history=LeadScoreHistory(prospect_id=prospect_id,user_id=user_id,previous_score=previous,new_score=result["score"],score_delta=result["score_delta"],icp_version=profile_row["version"],trigger_type=trigger,enrichment_used=int(bool(refresh)),sources_json=json.dumps(result["sources_used"]),explanation_json=json.dumps(result))
        session.add(history);session.flush();result["history_id"]=history.id
        return result


@router.post("/prospects/{prospect_id}/rescore")
def rescore_one(prospect_id: int, payload: RescoreRequest, request: ApiRequest):
    try: return rescore(prospect_id,_user(request),_owner(request),payload.refresh,"MANUAL_REFRESH" if payload.refresh else "MANUAL")
    except LookupError: raise HTTPException(404,"Lead not found")
    except ValueError as exc: raise HTTPException(422,str(exc))


@router.get("/prospects/{prospect_id}/score-history")
def score_history(prospect_id: int, request: ApiRequest):
    if not db.get_owned_prospect(prospect_id,_owner(request)): raise HTTPException(404,"Lead not found")
    with db.SessionLocal() as session:
        rows=list(session.execute(select(LeadScoreHistory).where(LeadScoreHistory.prospect_id==prospect_id,LeadScoreHistory.user_id==_user(request)).order_by(LeadScoreHistory.id.desc()).limit(20)).scalars())
        return [{**db._dict(row),"sources":json.loads(row.sources_json or "[]"),"explanation":json.loads(row.explanation_json or "{}")} for row in rows]


@router.post("/prospects/rescore-batch")
def rescore_batch(payload: BatchRescoreRequest, request: ApiRequest):
    if not payload.confirmed: raise HTTPException(400,"Explicit confirmation required")
    owner=_owner(request);user=_user(request)
    with db.SessionLocal() as session:
        query=select(Prospect.id).join(Campaign,Prospect.campaign_id==Campaign.id)
        if owner is not None: query=query.where(Campaign.owner_id==owner)
        if payload.prospect_ids: query=query.where(Prospect.id.in_(payload.prospect_ids))
        if payload.campaign: query=query.where(Campaign.slug==payload.campaign)
        ids=list(session.execute(query.limit(100)).scalars())
    if payload.refresh and len(ids)>10:
        raise HTTPException(422,"Refresh & Rescore is limited to 10 selected leads at a time to protect public sites and keep the app responsive. Use Rescore for larger batches.")
    results=[]
    for prospect_id in ids:
        try: results.append({"prospect_id":prospect_id,"status":"COMPLETE",**rescore(prospect_id,user,owner,payload.refresh,"BATCH_REFRESH" if payload.refresh else "BATCH")})
        except Exception as exc: results.append({"prospect_id":prospect_id,"status":"FAILED","error":str(exc)[:200]})
    complete=[x for x in results if x["status"]=="COMPLETE"]
    return {"count":len(results),"completed":len(complete),"failed":len(results)-len(complete),"moved_up":sum(x["score_delta"]>=5 for x in complete),"moved_down":sum(x["score_delta"]<=-5 for x in complete),"stayed_similar":sum(abs(x["score_delta"])<5 for x in complete),"became_high_priority":sum(x["new_score"]>=80 and x["previous_score"]<80 for x in complete),"results":results}
