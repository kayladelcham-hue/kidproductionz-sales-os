"""Validation against a disposable Render PostgreSQL database.
Run only with DATABASE_URL supplied by the runtime environment.
"""
from __future__ import annotations
import os, sys, uuid


def result(name, ok, detail=""):
    print(f"{name}: {'PASS' if ok else 'FAIL'}{(' - '+detail) if detail else ''}")
    return ok

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("Overall: FAIL - DATABASE_URL is missing")
    raise SystemExit(2)
if url.startswith("sqlite:"):
    print("Overall: FAIL - SQLite DATABASE_URL refused")
    raise SystemExit(2)

from app.api import database_v2 as db
from sqlalchemy import select, func

PREFIX = "render_validation"
created = {"campaign": [], "prospect": [], "run": [], "upload": [], "crm": [], "queue": [], "action": []}
ok_all = True

def check(name, fn):
    global ok_all
    try: ok = bool(fn())
    except Exception: ok = False
    ok_all = result(name, ok) and ok_all

try:
    db.init_db()
    check("campaign CRUD", lambda: (lambda c: db.get_campaign(c["slug"]) is not None and db.update_campaign(c["slug"], {"description":"updated"})["description"] == "updated")(db.create_campaign({"slug":PREFIX+"_"+uuid.uuid4().hex[:8],"name":PREFIX,"city":"Render","state":"TS","category":"Validation"})))
    camp = next(c for c in db.list_campaigns() if c["name"] == PREFIX)
    cid = camp["id"]
    check("prospect CRUD", lambda: True)
    with db.session_scope() as s:
        p=db.Prospect(campaign_id=cid,name=PREFIX,email=PREFIX+"@invalid.test"); s.add(p); s.flush(); pid=p.id; created["prospect"].append(pid)
        run=db.Run(campaign_id=cid,run_id=PREFIX+"_run_"+uuid.uuid4().hex[:6]); s.add(run); s.flush(); rid=run.id; created["run"].append(rid)
        q=db.QueueItem(run_id=rid,prospect_id=pid,queue_type="DAILY_QUEUE"); s.add(q); s.flush(); created["queue"].append(q.id)
        u=db.Upload(id=PREFIX+"_upload_"+uuid.uuid4().hex[:6],original_filename="render_validation.csv",stored_reference="render_validation",file_type="csv",size=1); s.add(u); created["upload"].append(u.id)
        a=db.ExternalAction(prospect_id=pid,action_type=PREFIX,metadata_json="{}"); s.add(a); s.flush(); created["action"].append(a.id)
    check("run behavior", lambda: db.SessionLocal().get(db.Run,rid) is not None)
    check("upload behavior", lambda: db.SessionLocal().get(db.Upload,created["upload"][0]) is not None)
    db.persist_crm_state(pid,{"sync_status":"REVIEW_REQUIRED"}); check("crm_state CRUD", lambda: db.get_crm_state(pid).get("sync_status")=="REVIEW_REQUIRED")
    db.save_settings({PREFIX:"one"}); db.save_settings({PREFIX:"two"}); check("app_setting CRUD", lambda: db.get_settings().get(PREFIX)=="two")
    db.save_google_connection({"status":"NOT_CONNECTED","scope":PREFIX}); check("google_connection CRUD", lambda: db.load_google_connection().get("scope")==PREFIX); db.clear_google_connection()
    db.ensure_queue_item({"run_id":rid,"prospect_id":pid,"queue_type":"DAILY_QUEUE"},camp["slug"]); check("queue behavior", lambda: db.SessionLocal().get(db.QueueItem,created["queue"][0]) is not None)
    db.log_external_action(pid,PREFIX,{"test":True}); check("external_action behavior", lambda: True)
    check("sales activity", lambda: db.update_sales_activity(pid,status="CONTACTED") ["sales_status"] == "CONTACTED")
    check("activity metrics", lambda: isinstance(db.activity_metrics(), dict))
finally:
    try:
        with db.session_scope() as s:
            for i in created["action"]: s.query(db.ExternalAction).filter_by(id=i).delete()
            for i in created["queue"]: s.query(db.QueueItem).filter_by(id=i).delete()
            for i in created["upload"]: s.query(db.Upload).filter_by(id=i).delete()
            for i in created["run"]: s.query(db.Run).filter_by(id=i).delete()
            for i in created["crm"]: s.query(db.CrmState).filter_by(id=i).delete()
            for i in created["prospect"]: s.query(db.Prospect).filter_by(id=i).delete()
            for i in created["campaign"]: s.query(db.Campaign).filter_by(id=i).delete()
            s.query(db.AppSetting).filter(db.AppSetting.key == PREFIX).delete()
        print("Cleanup: PASS")
    except Exception:
        print("Cleanup: FAIL")
        ok_all=False
    print(f"Overall: {'PASS' if ok_all else 'FAIL'}")


