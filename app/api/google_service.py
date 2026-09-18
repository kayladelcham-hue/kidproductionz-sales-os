import base64,email.message,json,os,time,urllib.parse,urllib.request,urllib.error,logging
from .database_v2 import save_google_connection,load_google_connection,clear_google_connection
SCOPES=(
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.calendarlist.readonly',
)
logger=logging.getLogger(__name__)
def status():
 if os.getenv('GOOGLE_CALENDAR_ENABLED','false').lower()!='true' and os.getenv('GMAIL_ENABLED','false').lower()!='true': return 'DISABLED'
 return (load_google_connection() or {}).get('status','NOT_CONNECTED')
def authorization_url():
 cid=os.getenv('GOOGLE_CLIENT_ID');
 if not cid: raise ValueError('Google OAuth is not configured')
 return 'https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode({'client_id':cid,'redirect_uri':os.getenv('GOOGLE_REDIRECT_URI','http://127.0.0.1:8000/api/google/oauth/callback'),'response_type':'code','scope':' '.join(SCOPES),'access_type':'offline','prompt':'consent','state':'kidproductionz'})
def callback(code):
 if not code: raise ValueError('OAuth code is required')
 body=urllib.parse.urlencode({'code':code,'client_id':os.getenv('GOOGLE_CLIENT_ID',''),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET',''),'redirect_uri':os.getenv('GOOGLE_REDIRECT_URI','http://127.0.0.1:8000/api/google/oauth/callback'),'grant_type':'authorization_code'}).encode(); req=urllib.request.Request('https://oauth2.googleapis.com/token',data=body,method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
 with urllib.request.urlopen(req,timeout=10) as r: d=json.loads(r.read().decode())
 save_google_connection({'access_token':d['access_token'],'refresh_token':d.get('refresh_token'),'expires_at':time.time()+float(d.get('expires_in',3600)),'scope':d.get('scope',''),'status':'CONNECTED'}); return {'status':'CONNECTED'}
def disconnect(): clear_google_connection()
def _token():
    c=load_google_connection() or {}
    if not c.get('access_token'): raise RuntimeError('Google is not connected')
    if c.get('expires_at') is not None and float(c['expires_at']) <= time.time() and c.get('refresh_token'):
        body=urllib.parse.urlencode({'client_id':os.getenv('GOOGLE_CLIENT_ID',''),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET',''),'refresh_token':c['refresh_token'],'grant_type':'refresh_token'}).encode()
        req=urllib.request.Request('https://oauth2.googleapis.com/token',data=body,method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(req,timeout=10) as r: d=json.loads(r.read().decode())
            c.update(access_token=d['access_token'],expires_at=time.time()+float(d.get('expires_in',3600)),status='CONNECTED'); save_google_connection(c)
        except Exception:
            c['status']='AUTH_ERROR'; save_google_connection(c); raise RuntimeError('Google token refresh failed')
    return c['access_token']
def _post(url,payload):
 req=urllib.request.Request(url,data=json.dumps(payload).encode(),method='POST',headers={'Authorization':'Bearer '+_token(),'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read().decode())
def send_gmail(to,subject,body):
 m=email.message.EmailMessage(); m['To']=to; m['Subject']=subject; m.set_content(body); raw=base64.urlsafe_b64encode(m.as_bytes()).decode().rstrip('='); return _post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',{'raw':raw})
def reschedule_calendar_event(event_id, event):
    url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events/' + urllib.parse.quote(event_id, safe='')
    req = urllib.request.Request(url, data=json.dumps(event).encode(), method='PATCH',
          headers={'Authorization': 'Bearer ' + _token(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())

def create_calendar_event(event):
    try:
        return _post('https://www.googleapis.com/calendar/v3/calendars/primary/events',event)
    except urllib.error.HTTPError as exc:
        try: detail=json.loads(exc.read().decode())
        except Exception: detail={'message':str(exc)}
        safe={k:detail.get(k) for k in ('error','message','status','reason') if k in detail}
        logger.error('Google Calendar create failed status=%s response=%s payload=%s token_refreshed=%s',exc.code,safe,{k:v for k,v in event.items() if k not in ('access_token','refresh_token')},False)
        raise
    except Exception as exc:
        logger.exception('Google Calendar create failed type=%s message=%s payload=%s token_refreshed=%s',type(exc).__name__,str(exc),{k:v for k,v in event.items() if k not in ('access_token','refresh_token')},False)
        raise
def upcoming_calendar_events(limit=10):
    token = _token()
    headers = {'Authorization': 'Bearer ' + token}

    # Read every calendar visible to the connected Google account.
    req = urllib.request.Request(
        'https://www.googleapis.com/calendar/v3/users/me/calendarList',
        headers=headers,
    )

    with urllib.request.urlopen(req, timeout=10) as r:
        calendar_data = json.loads(r.read().decode())

    calendars = calendar_data.get('items', [])
    time_min = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    events = []

    for calendar in calendars:
        calendar_id = calendar.get('id')
        if not calendar_id:
            continue

        url = (
            'https://www.googleapis.com/calendar/v3/calendars/'
            + urllib.parse.quote(calendar_id, safe='')
            + '/events?'
            + urllib.parse.urlencode({
                'maxResults': limit,
                'singleEvents': 'true',
                'orderBy': 'startTime',
                'timeMin': time_min,
            })
        )

        try:
            event_req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(event_req, timeout=10) as r:
                data = json.loads(r.read().decode())

            for x in data.get('items', []):
                events.append({
                    'id': x.get('id'),
                    'calendar_id': calendar_id,
                    'calendar_name': calendar.get('summary', ''),
                    'title': x.get('summary', ''),
                    'start': (x.get('start') or {}).get('dateTime')
                             or (x.get('start') or {}).get('date'),
                    'end': (x.get('end') or {}).get('dateTime')
                           or (x.get('end') or {}).get('date'),
                    'location': x.get('location', ''),
                    'html_link': x.get('htmlLink'),
                })

        except Exception:
            # One inaccessible/shared calendar should not break the schedule.
            continue

    events.sort(key=lambda x: str(x.get('start') or ''))

    # Avoid duplicates if the same event is visible through multiple calendars.
    seen = set()
    unique = []

    for event in events:
        key = (event.get('id'), event.get('start'))
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)

    return unique[:limit]

