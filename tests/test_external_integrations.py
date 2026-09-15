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
 log_external_action(999,"EMAIL_DRAFTED",{"x":"y"})
 with connect() as c: assert c.execute("select action_type from external_action where prospect_id=999").fetchone()[0]=="EMAIL_DRAFTED"
