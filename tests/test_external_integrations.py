import os, time
from app.api import google_service
from app.api.database import log_external_action, connect

def test_oauth_url_has_minimal_scopes(monkeypatch):
 monkeypatch.setenv("GOOGLE_CLIENT_ID","client"); u=google_service.authorization_url(); assert "gmail.send" in u and "calendar.events" in u
def test_refresh_failure_marks_auth_error(monkeypatch):
 monkeypatch.setenv("GOOGLE_CALENDAR_ENABLED","true"); monkeypatch.setattr(google_service,"load_google_connection",lambda:{"access_token":"old","refresh_token":"r","expires_at":0,"status":"CONNECTED"}); monkeypatch.setattr(google_service.urllib.request,"urlopen",lambda *a,**k: (_ for _ in ()).throw(OSError("bad"))); state={}; monkeypatch.setattr(google_service,"save_google_connection",lambda x: state.update(x))
 try: google_service._token()
 except RuntimeError: pass
 assert state["status"]=="AUTH_ERROR"
def test_action_logging_persists():
 from app.api.database_v2 import init_db, create_campaign, persist_generated_prospects, list_prospects
 init_db();create_campaign({'slug':'external_test','name':'External Test'})
 persist_generated_prospects('external_test',[{'name':'Synthetic Lead','city':'Orlando','state':'FL'}])
 pid=list_prospects('external_test')[0]['id']
 log_external_action(pid,"EMAIL_DRAFTED",{"x":"y"})
 with connect() as c: assert c.exec_driver_sql("select action_type from external_action where prospect_id=?",(pid,)).fetchone()[0]=="EMAIL_DRAFTED"
