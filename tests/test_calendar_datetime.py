from app.api.main import _calendar_dt
def test_calendar_datetime_rfc3339():
 d=_calendar_dt("2026-09-15T03:39","America/New_York"); assert d.isoformat(timespec="seconds")=="2026-09-15T03:39:00-04:00"
def test_calendar_dst():
 assert _calendar_dt("2026-01-15T03:39","America/New_York").utcoffset().total_seconds()==-18000
