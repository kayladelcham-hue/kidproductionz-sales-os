from pathlib import Path
import os
import json
import sys
import logging
ROOT=Path(__file__).resolve().parents[2]

def _load_local_env():
    """Load simple project .env values without overriding explicit process env."""
    env_path=ROOT/'.env'
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        key=key.strip()
        value=value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key]=value

_load_local_env()
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import tempfile, uuid, shutil
import logging, re
import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from datetime import datetime
from zoneinfo import ZoneInfo
import re as _re
from pydantic import BaseModel
from .hubspot_service import preview
from . import hubspot_sync_service
from .hubspot_client import HubSpotClient
from . import google_service
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db, seed_campaigns, persist_upload, update_sales_activity, activity_metrics, ensure_queue_item, persist_crm_state, get_crm_state, log_external_action, connect, list_campaigns, list_prospects, get_campaign, create_campaign, update_campaign, get_settings, save_settings
logger=logging.getLogger(__name__)
def _safe_error_message(message:str)->str:
    message=re.sub(r'(?i)(token|authorization|api[_ -]?key|password|secret)\s*[=:]\s*[^\s,;]+',r'\1=[REDACTED]',message)
    return message[:500]
app=FastAPI(title='KidProductionz Sales OS',version='1.0')

# Private single-user session foundation. Local desktop mode remains deliberately
# frictionless; cloud mode opts into cookie-authenticated API access.
_AUTH_COOKIE = 'kidproductionz_session'
_sessions: set[str] = set()
_csrf_tokens: dict[str, str] = {}
def _auth_required() -> bool:
    return os.getenv('KIDPRODUCTIONZ_AUTH_MODE', 'local').lower() not in ('local', 'disabled', 'off')

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if _auth_required() and request.url.path.startswith('/api/') and request.url.path not in ('/api/health','/api/auth/login','/api/auth/me','/api/auth/logout','/api/google/oauth/callback'):
            token = request.cookies.get(_AUTH_COOKIE)
            if not token or token not in _sessions:
                return JSONResponse({'detail':'Authentication required'}, status_code=401)
            if request.method in ('POST','PUT','PATCH','DELETE') and request.url.path not in ('/api/auth/login','/api/auth/logout'):
                if not token or request.headers.get('X-CSRF-Token') != _csrf_tokens.get(token):
                    return JSONResponse({'detail':'CSRF validation failed'}, status_code=403)
        return await call_next(request)
app.add_middleware(AuthMiddleware)

class LoginRequest(BaseModel):
    username: str = ''
    password: str

@app.post('/api/auth/login')
def auth_login(req: LoginRequest):
    expected_user=os.getenv('KIDPRODUCTIONZ_AUTH_USERNAME','admin')
    expected_password=os.getenv('KIDPRODUCTIONZ_AUTH_PASSWORD','')
    if not expected_password or not secrets.compare_digest(req.username or expected_user, expected_user) or not secrets.compare_digest(req.password, expected_password):
        raise HTTPException(401, 'Invalid credentials')
    token=secrets.token_urlsafe(32); _sessions.add(token)
    response=JSONResponse({'authenticated':True,'username':expected_user})
    response.set_cookie(_AUTH_COOKIE, token, httponly=True, samesite='lax', secure=os.getenv('APP_ENV','').lower() in ('production','cloud'))
    return response

@app.post('/api/auth/logout')
def auth_logout(request):
    token=request.cookies.get(_AUTH_COOKIE)
    if token: _sessions.discard(token)
    response=JSONResponse({'authenticated':False}); response.delete_cookie(_AUTH_COOKIE); return response

@app.get('/api/auth/me')
def auth_me(request):
    if not _auth_required(): return {'authenticated':True,'mode':'local'}
    token=request.cookies.get(_AUTH_COOKIE)
    return {'authenticated':bool(token and token in _sessions)}

@app.get('/api/auth/csrf')
def auth_csrf(request):
    if not _auth_required(): return {'csrf_token':'local-mode'}
    token=request.cookies.get(_AUTH_COOKIE)
    if not token or token not in _sessions: raise HTTPException(401, 'Authentication required')
    value=_csrf_tokens.setdefault(token, secrets.token_urlsafe(24))
    return {'csrf_token':value}
logger = logging.getLogger(__name__)
if getattr(sys, 'frozen', False):
    BUNDLE_ROOT = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)).resolve()
else:
    BUNDLE_ROOT = ROOT
FRONTEND_DIST=BUNDLE_ROOT/'app'/'frontend'/'dist'
logger.info('frontend resolution frozen=%s bundle_root=%s frontend_dist=%s frontend_index=%s frontend_index_exists=%s', getattr(sys, 'frozen', False), BUNDLE_ROOT, FRONTEND_DIST, FRONTEND_DIST/'index.html', (FRONTEND_DIST/'index.html').exists())
ARTIFACT_ROOT=Path(os.getenv('KIDPRODUCTIONZ_ARTIFACT_ROOT', str(ROOT/'validation_outputs')))
if (FRONTEND_DIST/'assets').exists(): app.mount('/assets',StaticFiles(directory=FRONTEND_DIST/'assets'),name='assets')
try:
    logger.info('database initialization begin')
    init_db(); logger.info('database initialization complete')
    logger.info('artifact setup begin'); seed_campaigns(ROOT/'config'/'campaigns'); logger.info('artifact setup complete')
except Exception:
    # An empty/unavailable local DB must not prevent read-only API startup.
    pass
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'], allow_methods=['GET','POST','OPTIONS'], allow_headers=['*'])
def read_json(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError: raise HTTPException(404,'Artifact not found')
    except (ValueError,OSError): raise HTTPException(422,'Artifact unreadable')
def latest_versioned(directory:Path, prefix:str):
    candidates=[]
    for p in directory.glob(prefix+'_v*.json'):
        m=_re.fullmatch(_re.escape(prefix)+r'_v(\d+)\.json',p.name)
        if m: candidates.append((int(m.group(1)),p))
    return max(candidates,key=lambda x:x[0])[1] if candidates else None
@app.get('/api/health')
def health(): return {'app':'ok','database':'ok','frontend':'ok' if (FRONTEND_DIST/'index.html').exists() else 'missing','hubspot_configured':bool(os.getenv('HUBSPOT_ACCESS_TOKEN')),'google_configured':bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))}
@app.get('/api/campaigns')
def campaigns():
    out=[]
    configs={p.stem:read_json(p) for p in sorted((ROOT/'config/campaigns').glob('*.json'))}
    for row in list_campaigns():
        cfg=configs.get(row['slug'])
        if cfg:
            cfg={**cfg,'status':row.get('status') or ('ACTIVE' if row.get('active') else 'PAUSED'),'daily_queue_limit':row.get('daily_queue_limit') or cfg.get('queue',{}).get('daily_limit',50)}
        else:
            cfg={'campaign_id':row['slug'],'name':row['name'],'market':json.loads(row.get('market') or '{}'),'categories':[row.get('category')] if row.get('category') else [],'description':row.get('description') or '','daily_queue_limit':row.get('daily_queue_limit') or 50,'status':row.get('status') or ('ACTIVE' if row.get('active') else 'PAUSED'),'created_at':row.get('created_at'),'updated_at':row.get('updated_at')}
        out.append(cfg)
    return out

class CampaignCreate(BaseModel):
    campaign_id: str
    name: str
    city: str
    state: str
    category: str
    description: str = ''
    daily_queue_limit: int = 50
    status: str = 'ACTIVE'

class CampaignPatch(BaseModel):
    name: str|None = None; city: str|None = None; state: str|None = None; category: str|None = None; description: str|None = None; daily_queue_limit: int|None = None; status: str|None = None

def _campaign_payload(row):
    return {'campaign_id':row['slug'],'name':row['name'],'city':row.get('city') or '','state':row.get('state') or '','category':row.get('category') or '','description':row.get('description') or '','daily_queue_limit':row.get('daily_queue_limit') or 50,'status':row.get('status') or ('ACTIVE' if row.get('active') else 'PAUSED'),'created_at':row.get('created_at'),'updated_at':row.get('updated_at')}

@app.post('/api/campaigns')
def campaign_create(req: CampaignCreate):
    if not req.campaign_id.strip() or not req.name.strip() or not req.city.strip() or not req.state.strip() or not req.category.strip(): raise HTTPException(422,'Required campaign fields are missing')
    if req.status not in ('ACTIVE','PAUSED','ARCHIVED') or req.daily_queue_limit < 1: raise HTTPException(422,'Invalid campaign settings')
    try: return _campaign_payload(create_campaign(req.model_dump()))
    except ValueError as exc: raise HTTPException(409,str(exc))

@app.get('/api/campaigns/{campaign_id}')
def campaign_detail(campaign_id:str):
    row=get_campaign(campaign_id)
    if not row: raise HTTPException(404,'Campaign not found')
    return _campaign_payload(row)

@app.patch('/api/campaigns/{campaign_id}')
def campaign_patch(campaign_id:str, req: CampaignPatch):
    data=req.model_dump(exclude_unset=True)
    if data.get('status') and data['status'] not in ('ACTIVE','PAUSED','ARCHIVED'): raise HTTPException(422,'Invalid campaign status')
    try: row=update_campaign(campaign_id,data)
    except (ValueError,TypeError): raise HTTPException(422,'Invalid campaign settings')
    if not row: raise HTTPException(404,'Campaign not found')
    return _campaign_payload(row)
@app.get('/api/runs')
def runs():
    return [read_json(p) for p in sorted((ARTIFACT_ROOT/'v5_runs').glob('*/run_v*.json')) if _re.fullmatch(r'run_v\d+\.json',p.name)]
@app.get('/api/runs/{run_id}')
def run_detail(run_id:str):
    matches=list((ARTIFACT_ROOT/'v5_runs').glob(f'*/{run_id}.json'))
    if not matches: raise HTTPException(404,'Run not found')
    return read_json(matches[0])
@app.get('/api/queue')
def queue(campaign='orlando_beauty'):
    path=latest_versioned(ARTIFACT_ROOT/'v5_queue'/campaign,'daily_queue')
    if not path: return {'campaign_id':campaign,'daily_queue':[],'deferred':[],'research':[],'ineligible':[],'summary':{'total_candidates':0,'daily_queue_count':0,'deferred_count':0,'research_count':0,'ineligible_count':0},'safety':{}}
    doc=read_json(path)
    for section in ('daily_queue','deferred','research','ineligible'):
        doc[section]=[ensure_queue_item(x,campaign) for x in doc.get(section,[])]
    return doc
@app.get('/api/prospects')
def prospects(campaign='orlando_beauty'): return list_prospects(campaign)
class SalesActivity(BaseModel):
    status:str|None=None; notes:str|None=None; booked_value:float|None=None
@app.get('/api/metrics')
def metrics(): return activity_metrics()
@app.patch('/api/prospects/{prospect_id}/activity')
def prospect_activity(prospect_id:int, activity:SalesActivity):
    try: return update_sales_activity(prospect_id, activity.status, activity.notes, activity.booked_value)
    except ValueError as exc: raise HTTPException(400,str(exc))
    except KeyError: raise HTTPException(404,'Prospect not found')
class ExternalAction(BaseModel):
    prospect_id:int; action_type:str; metadata:dict|None=None
@app.post('/api/prospects/{prospect_id}/external-action')
def external_action(prospect_id:int, action:ExternalAction):
    if action.prospect_id!=prospect_id: raise HTTPException(400,'Prospect ID mismatch')
    if action.action_type not in {'CALL_OPENED','EMAIL_DRAFTED','EMAIL_SENT','SOCIAL_OPENED','WEBSITE_OPENED','BOOKING_LINK_COPIED','CALENDAR_EVENT_CREATED','HUBSPOT_OPENED'}: raise HTTPException(400,'Invalid action type')
    log_external_action(prospect_id,action.action_type,action.metadata); return {'status':'LOGGED'}
class CalendarRequest(BaseModel):
    prospect_id:int; title:str|None=None; consultation_start:str; consultation_end:str; timezone:str|None=None; location:str|None=None; notes:str|None=None; attendee_email:str|None=None; confirmed:bool=False
def _calendar_dt(value:str, timezone_name:str)->datetime:
    try: dt=datetime.fromisoformat(value)
    except ValueError: raise HTTPException(400,'Invalid calendar datetime')
    try: zone=ZoneInfo(timezone_name or 'UTC')
    except Exception: raise HTTPException(400,'Invalid calendar timezone')
    return dt.replace(tzinfo=zone) if dt.tzinfo is None else dt.astimezone(zone)
@app.post('/api/integrations/calendar/preview')
def calendar_preview(req:CalendarRequest):
    start=_calendar_dt(req.consultation_start,req.timezone or 'UTC'); end=_calendar_dt(req.consultation_end,req.timezone or 'UTC')
    if end<=start: raise HTTPException(400,'Calendar end must be after start')
    return {'status':'READY_TO_CREATE','title':req.title or 'KidProductionz Consultation','prospect_id':req.prospect_id,'consultation_start':start.isoformat(timespec='seconds'),'consultation_end':end.isoformat(timespec='seconds'),'timezone':req.timezone or 'UTC','location':req.location,'notes':req.notes,'attendee_email':req.attendee_email}
@app.post('/api/integrations/calendar/create')
def calendar_create(req:CalendarRequest):
    if not req.confirmed: raise HTTPException(400,'Explicit confirmation required')
    if os.getenv('GOOGLE_CALENDAR_ENABLED','false').lower()!='true': raise HTTPException(403,'Google Calendar is disabled')
    try:
        start=_calendar_dt(req.consultation_start,req.timezone or 'UTC'); end=_calendar_dt(req.consultation_end,req.timezone or 'UTC')
        if end<=start: raise HTTPException(400,'Calendar end must be after start')
        tz=req.timezone or 'UTC'; event_doc={'summary':req.title or 'KidProductionz Consultation','start':{'dateTime':start.isoformat(timespec='seconds'),'timeZone':tz},'end':{'dateTime':end.isoformat(timespec='seconds'),'timeZone':tz}}
        if req.notes: event_doc['description']=req.notes
        if req.location: event_doc['location']=req.location
        if req.attendee_email: event_doc['attendees']=[{'email':req.attendee_email}]
        event=google_service.create_calendar_event(event_doc)
        log_external_action(req.prospect_id,'CALENDAR_EVENT_CREATED',{'calendar_event_id':event.get('id')})
        with connect() as c: c.execute('INSERT INTO calendar_event(prospect_id,provider,calendar_event_id,event_url,consultation_start,consultation_end) VALUES(?,?,?,?,?,?)',(req.prospect_id,'GOOGLE',event.get('id'),event.get('htmlLink'),req.consultation_start,req.consultation_end))
        return {'status':'CREATED','calendar_event_id':event.get('id'),'event_url':event.get('htmlLink')}
    except Exception as exc: raise HTTPException(503,detail={'provider':'GOOGLE_CALENDAR','stage':'event_create','message':_safe_error_message(str(exc))})
class GmailRequest(BaseModel):
    prospect_id:int; to:str|None=None; subject:str; body:str; confirmed:bool=False
@app.post('/api/integrations/gmail/send')
def gmail_send(req:GmailRequest):
    if not req.to: raise HTTPException(400,'Prospect email is unavailable')
    if not req.confirmed: raise HTTPException(400,'Explicit confirmation required')
    if os.getenv('GMAIL_ENABLED','false').lower()!='true': raise HTTPException(403,'Gmail is disabled')
    try:
        result=google_service.send_gmail(req.to,req.subject,req.body); log_external_action(req.prospect_id,'EMAIL_SENT',{'provider_message_id':result.get('id')})
        with connect() as c: c.execute('INSERT INTO email_activity(prospect_id,provider,provider_message_id,recipient,subject) VALUES(?,?,?,?,?)',(req.prospect_id,'GMAIL',result.get('id'),req.to,req.subject))
        return {'status':'SENT','provider_message_id':result.get('id')}
    except Exception as exc: raise HTTPException(503,detail={'provider':'GMAIL','stage':'send','message':_safe_error_message(str(exc))})
@app.get('/api/integrations/status')
def integrations_status():
    return {'calendar_enabled':os.getenv('GOOGLE_CALENDAR_ENABLED','false').lower()=='true','gmail_enabled':os.getenv('GMAIL_ENABLED','false').lower()=='true','google_status':google_service.status(),'booking_url':os.getenv('BOOKING_URL',''),'hubspot_portal_id':os.getenv('HUBSPOT_PORTAL_ID',''),'automatic_actions':False}

@app.get('/api/settings/hubspot')
def hubspot_settings():
    return {'configured':bool(os.getenv('HUBSPOT_ACCESS_TOKEN')),'token_present':bool(os.getenv('HUBSPOT_ACCESS_TOKEN')),'portal_id':os.getenv('HUBSPOT_PORTAL_ID',''),'pipeline_id':os.getenv('HUBSPOT_PIPELINE_ID',''),'stage_id':os.getenv('HUBSPOT_STAGE_ID',''),'write_enabled':os.getenv('HUBSPOT_WRITE_ENABLED','false').lower()=='true'}

@app.post('/api/settings/hubspot/test')
def hubspot_settings_test():
    try:
        HubSpotClient().get_contact('0')
    except Exception as exc:
        if '404' not in str(exc): raise HTTPException(503,'HubSpot connection test failed safely')
    return {'status':'CONNECTED'}

class HubSpotSettings(BaseModel):
    access_token:str|None=None; portal_id:str=''; pipeline_id:str=''; stage_id:str=''; write_enabled:bool=False

@app.post('/api/settings/hubspot')
def save_hubspot_settings(req:HubSpotSettings):
    path=Path(os.getenv('APP_ENV_FILE', str(ROOT/'.env'))); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): shutil.copy2(path, path.with_name(path.name+'.bak.'+datetime.now().strftime('%Y%m%d%H%M%S')))
    values={'HUBSPOT_PORTAL_ID':req.portal_id,'HUBSPOT_PIPELINE_ID':req.pipeline_id,'HUBSPOT_STAGE_ID':req.stage_id,'HUBSPOT_WRITE_ENABLED':str(req.write_enabled).lower()}
    if req.access_token and '•' not in req.access_token: values['HUBSPOT_ACCESS_TOKEN']=req.access_token
    lines=path.read_text(encoding='utf-8').splitlines() if path.exists() else []; keys={k for k in values}; out=[l for l in lines if not any(l.startswith(k+'=') for k in keys)]; out += [f'{k}={v}' for k,v in values.items()]; path.write_text('\n'.join(out)+'\n',encoding='utf-8'); os.environ.update(values)
    return hubspot_settings()

@app.get('/api/settings/booking')
def booking_settings():
    s=get_settings('booking_'); return {'configured':bool(s.get('booking_url')),'provider':s.get('booking_provider',''),'booking_url':s.get('booking_url',''),'default_duration':int(s.get('booking_default_duration','30')),'default_title':s.get('booking_default_title','')}
class BookingSettings(BaseModel):
    provider:str=''; booking_url:str=''; default_duration:int=30; default_title:str=''
@app.post('/api/settings/booking')
def save_booking_settings(req:BookingSettings):
    from urllib.parse import urlparse
    u=urlparse(req.booking_url) if req.booking_url else None
    if req.booking_url and u.scheme not in ('http','https') or req.default_duration<1: raise HTTPException(422,'Invalid booking settings')
    save_settings({'booking_provider':req.provider,'booking_url':req.booking_url,'booking_default_duration':str(req.default_duration),'booking_default_title':req.default_title}); return booking_settings()
@app.get('/api/google/status')
def google_status(): return {'status':google_service.status(),'calendar_enabled':os.getenv('GOOGLE_CALENDAR_ENABLED','false').lower()=='true','gmail_enabled':os.getenv('GMAIL_ENABLED','false').lower()=='true'}
@app.get('/api/google/oauth/start')
def google_oauth_start():
    try: return {'authorization_url':google_service.authorization_url()}
    except ValueError as exc:
        diagnostics = {
            'google_client_id_present': bool(os.getenv('GOOGLE_CLIENT_ID')),
            'google_client_secret_present': bool(os.getenv('GOOGLE_CLIENT_SECRET')),
            'google_redirect_uri_present': bool(os.getenv('GOOGLE_REDIRECT_URI')),
            'google_redirect_uri': os.getenv('GOOGLE_REDIRECT_URI') or None,
            'gmail_enabled': os.getenv('GMAIL_ENABLED','false').lower() == 'true',
            'google_calendar_enabled': os.getenv('GOOGLE_CALENDAR_ENABLED','false').lower() == 'true',
        }
        message = _safe_error_message(str(exc))
        logger.warning('Google OAuth start unavailable message=%s diagnostics=%s', message, diagnostics)
        raise HTTPException(503, detail={'code':'GOOGLE_OAUTH_UNAVAILABLE','message':message,'diagnostics':diagnostics})
@app.get('/api/google/oauth/callback')
def google_oauth_callback(code:str=''):
    try: return google_service.callback(code)
    except ValueError as exc: raise HTTPException(400,str(exc))
@app.post('/api/google/disconnect')
def google_disconnect(): google_service.disconnect(); return {'status':'NOT_CONNECTED'}
@app.get('/api/integrations/calendar/upcoming')
def calendar_upcoming():
    if os.getenv('GOOGLE_CALENDAR_ENABLED','false').lower()!='true': return {'events':[],'status':'DISABLED'}
    try: return {'events':google_service.upcoming_calendar_events(),'status':'CONNECTED'}
    except Exception as exc: return {'events':[],'status':'UNAVAILABLE','error':_safe_error_message(str(exc))}
class ProspectInput(BaseModel):
    prospect_id:int|None=None; name:str|None=None; email:str|None=None; phone:str|None=None; website:str|None=None
    hubspot_contact_id:str|None=None; hubspot_company_id:str|None=None; hubspot_deal_id:str|None=None
    confirmed: bool|None=None

class HubSpotBatchRequest(BaseModel):
    campaign: str = 'orlando_beauty'
    prospect_ids: list[int] = []
    confirmed: bool = False
@app.get('/api/hubspot/status')
def hubspot_status():
    enabled=os.getenv('HUBSPOT_WRITE_ENABLED','false').lower()=='true'
    return {'connection_status':'CONTROLLED_READS','write_mode':'ENABLED_CONFIRMATION_REQUIRED' if enabled else 'DISABLED','writes_enabled':enabled,'campaign_execution_enabled':os.getenv('CAMPAIGN_EXECUTION_ENABLED','false').lower()=='true','safety_mode':'READ_ONLY','automatic_sync':'DISABLED','feature_flag':f'HUBSPOT_WRITE_ENABLED={str(enabled).lower()}'}
@app.post('/api/hubspot/preview-sync')
def preview_sync(prospect:ProspectInput): return preview(prospect.model_dump())

@app.post('/api/hubspot/batch-preview')
def hubspot_batch_preview(req: HubSpotBatchRequest):
    """Read-only preview for the current daily queue."""
    rows=queue(req.campaign).get('daily_queue',[])
    out=[]; counts={k:0 for k in ('CREATE_NEW','UPDATE_EXISTING','NO_CHANGE','REVIEW_REQUIRED','ALREADY_SYNCED','ERROR')}
    for row in rows:
        pid=row.get('prospect_id'); data=dict(row)
        if pid:
            state=get_crm_state(pid) or {}
            for k in ('hubspot_contact_id','hubspot_company_id','hubspot_deal_id'):
                if not data.get(k) and state.get(k): data[k]=state[k]
        try:
            p=preview(data); dtype=p.get('decision_type','ERROR')
            if data.get('hubspot_contact_id') and data.get('hubspot_deal_id') and p.get('sync_status')=='READY_TO_SYNC': dtype='ALREADY_SYNCED'
            counts[dtype]=counts.get(dtype,0)+1
            out.append({'prospect_id':pid,'name':data.get('name') or data.get('business'),'phone':data.get('phone'),'email':data.get('email'),'decision_type':dtype,'sync_status':p.get('sync_status'),'warnings':p.get('warnings',[]),'review_reason':p.get('review_reason'),'hubspot_contact_id':data.get('hubspot_contact_id'),'hubspot_deal_id':data.get('hubspot_deal_id')})
        except Exception as exc:
            counts['ERROR']+=1; out.append({'prospect_id':pid,'name':data.get('name') or data.get('business'),'decision_type':'ERROR','warnings':[type(exc).__name__]})
    return {'campaign':req.campaign,'counts':counts,'rows':out,'selected_default':[x['prospect_id'] for x in out if x.get('prospect_id') and x['decision_type'] in ('CREATE_NEW','UPDATE_EXISTING')]}

@app.post('/api/hubspot/batch-sync')
def hubspot_batch_sync(req: HubSpotBatchRequest):
    if not req.confirmed: raise HTTPException(400,'Explicit confirmation required')
    if os.getenv('HUBSPOT_WRITE_ENABLED','false').lower()!='true': raise HTTPException(403,'HubSpot writes are disabled')
    if not req.prospect_ids: return {'results':[],'summary':{'synced':0,'failed':0,'review_required':0}}
    try: client=HubSpotClient()
    except ValueError as exc: raise HTTPException(503,detail={'code':'HUBSPOT_CONFIGURATION_ERROR','message':_safe_error_message(str(exc))})
    rows=queue(req.campaign).get('daily_queue',[]); by_id={x.get('prospect_id'):x for x in rows}; results=[]
    for pid in req.prospect_ids:
        row=by_id.get(pid)
        if not row: results.append({'prospect_id':pid,'sync_status':'REVIEW_REQUIRED','errors':['Prospect not in current daily queue']}); continue
        data=dict(row); state=get_crm_state(pid) or {}
        for k in ('hubspot_contact_id','hubspot_company_id','hubspot_deal_id'):
            if not data.get(k) and state.get(k): data[k]=state[k]
        try: result=hubspot_sync_service.execute(data,client)
        except Exception as exc: result={'sync_status':'SYNC_FAILED','errors':[f'{type(exc).__name__}: {exc}']}
        try: persist_crm_state(pid,result)
        except Exception: result.setdefault('warnings',[]).append('Local CRM state persistence failed')
        results.append({'prospect_id':pid,**result})
    return {'campaign':req.campaign,'results':results,'summary':{'synced':sum(r.get('sync_status')=='SYNCED' for r in results),'failed':sum(r.get('sync_status')=='SYNC_FAILED' for r in results),'review_required':sum(r.get('sync_status')=='REVIEW_REQUIRED' for r in results)}}

class CampaignRunInput(BaseModel):
    campaign:str; input_file:str|None=None; sheet:str|None=None; dry_run:bool=True; confirmed:bool=False
@app.post('/api/campaigns/upload')
async def campaign_upload(file:UploadFile=File(...)):
    name=Path(file.filename or '').name
    if Path(name).suffix.lower() not in ('.csv','.xlsx'): raise HTTPException(415,'Only CSV and XLSX files are supported')
    data=await file.read()
    if not data: raise HTTPException(400,'Uploaded file is empty')
    root=Path(tempfile.gettempdir())/'kidproductionz_uploads'; root.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex; ref=root/(token+Path(name).suffix.lower()); ref.write_bytes(data)
    sheets=[]
    if ref.suffix=='.xlsx':
        try:
            from openpyxl import load_workbook
            wb=load_workbook(ref,read_only=True,data_only=True); sheets=wb.sheetnames
        except Exception: raise HTTPException(422,'Invalid XLSX workbook')
    metadata={'id':token,'reference':str(ref),'filename':name,'size':len(data),'file_type':ref.suffix[1:],'sheets':sheets}
    try: persist_upload(metadata)
    except Exception as exc: raise HTTPException(503,'Upload metadata persistence failed')
    return metadata
@app.post('/api/campaigns/run-preview')
def campaign_run_preview(req:CampaignRunInput):
    try:
        from v5e_execution_adapter import build
        spec=build(ROOT,req.campaign)
        return {'campaign':req.campaign,'market':spec['market'],'categories':spec['categories'],'input_source':req.input_file,'queue_limit':spec['queue']['daily_limit'],'dry_run':True,'planned_stages':['validation','input_adapter','scoring','routing','queue','artifacts'],'output_location':spec['output'],'warnings':[],'validation_status':spec['validation_status']}
    except Exception as exc: raise HTTPException(400,f'Campaign preview failed: {type(exc).__name__}')
@app.post('/api/campaigns/run')
def campaign_run(req:CampaignRunInput):
    if os.getenv('CAMPAIGN_EXECUTION_ENABLED','false').lower()!='true': raise HTTPException(403,'Campaign execution is currently disabled')
    if not req.confirmed: raise HTTPException(400,'Explicit confirmation required')
    if not req.dry_run: raise HTTPException(400,'Only dry-run execution is permitted')
    if not req.input_file: raise HTTPException(400,'input_file is required')
    try:
        from v5z_campaign_runner import run
        result=run(ROOT,req.campaign,req.input_file,req.sheet,True)
        return {'run_status':result.get('overall_status',result.get('status')),'campaign':req.campaign,'run_id':None,'dry_run':True,'qualified_count':result.get('qualification_scoring_summary',{}).get('qualified_count'),'daily_queue_count':result.get('daily_queue_summary',{}).get('daily_queue_count'),'deferred_count':result.get('daily_queue_summary',{}).get('deferred_count'),'research_count':result.get('daily_queue_summary',{}).get('research_count'),'ineligible_count':result.get('daily_queue_summary',{}).get('ineligible_count'),'artifact_paths':result.get('artifact_references',{}),'warnings':[],'errors':[]}
    except Exception as exc:
        logger.exception('Campaign run failed safely')
        raise HTTPException(422,f'Campaign run failed safely: {type(exc).__name__}: {_safe_error_message(str(exc))}')
@app.post('/api/hubspot/sync')
def sync_hubspot(prospect:ProspectInput, confirmed:bool|None=None):
    """Explicit write gate. Live CRM execution remains disabled until implemented and approved."""
    if not (confirmed if confirmed is not None else prospect.confirmed): raise HTTPException(400,'Explicit confirmation required')
    if os.getenv('HUBSPOT_WRITE_ENABLED','false').lower()!='true': raise HTTPException(403,'HubSpot writes are disabled')
    try: client=HubSpotClient()
    except ValueError as exc:
        logger.exception('HubSpot client configuration failure: type=%s message=%s',type(exc).__name__,_safe_error_message(str(exc)))
        raise HTTPException(503,detail={'code':'HUBSPOT_CONFIGURATION_ERROR','stage':'client_init','status':503,'message':_safe_error_message(str(exc))})
    prospect_data=prospect.model_dump()
    if prospect.prospect_id:
        state=get_crm_state(prospect.prospect_id)
        if state:
            for key in ('hubspot_contact_id','hubspot_company_id','hubspot_deal_id'):
                if not prospect_data.get(key) and state.get(key): prospect_data[key]=state[key]
    result=hubspot_sync_service.execute(prospect_data, client)
    if prospect.prospect_id:
        try: persist_crm_state(prospect.prospect_id, result)
        except Exception: result.setdefault('warnings',[]).append('Local CRM state persistence failed')
    return result

@app.get('/{path:path}')
def spa_fallback(path:str):
    if path.startswith('api/'): raise HTTPException(404,'API route not found')
    candidate=FRONTEND_DIST/path
    if candidate.is_file() and FRONTEND_DIST in candidate.parents: return FileResponse(candidate)
    index=FRONTEND_DIST/'index.html'
    if index.exists(): return FileResponse(index)
    raise HTTPException(404,'Frontend not built')

class _disabled_client:
    def get(self,*a): raise RuntimeError('HubSpot client is not configured')
