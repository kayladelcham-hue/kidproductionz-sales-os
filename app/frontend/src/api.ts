const BASE=import.meta.env.VITE_API_BASE_URL||(import.meta.env.DEV?'http://127.0.0.1:8000':'');
export type QueueItem={id?:number;prospect_id?:number;queue_position?:number|string;fixture_id?:string;lead_id?:string;name?:string;business?:string;score?:number;grade?:string;route?:string;route_reason?:string;priority?:string;queue_status?:string;sales_status?:string;notes?:string;booked_value?:number;last_activity_at?:string;phone?:string;email?:string;social?:string;website?:string};
export type Queue={campaign_id:string;queue_limit:number;summary:Record<string,number>;daily_queue:QueueItem[];deferred:QueueItem[];research:QueueItem[];ineligible:QueueItem[];safety:Record<string,boolean>};
let csrfToken: string | null = null;
async function get<T>(path:string):Promise<T>{const r=await fetch(`${BASE}${path}`,{credentials:'include'});if(!r.ok)throw new Error(`API_${r.status}`);return r.json()}
async function ensureCsrf():Promise<string>{
  if (csrfToken) return csrfToken;
  const r=await fetch(`${BASE}/api/auth/csrf`,{credentials:'include'});
  if(!r.ok) throw new Error(`CSRF_${r.status}`);
  const data=await r.json();
  csrfToken=data.csrf_token || data.token || '';
  if(!csrfToken) throw new Error('CSRF_TOKEN_MISSING');
  return csrfToken;
}
async function post<T>(path:string,body:any,retry=true):Promise<T>{
  const headers:Record<string,string>={'Content-Type':'application/json'};
  const protectedRequest=!['/api/auth/login','/api/auth/logout','/api/auth/signup'].includes(path);

  if(protectedRequest){
    headers['X-CSRF-Token']=await ensureCsrf();
  }

  const r=await fetch(`${BASE}${path}`,{
    method:'POST',
    headers,
    credentials:'include',
    body:JSON.stringify(body)
  });

  if(r.status===403 && protectedRequest && retry){
    csrfToken=null;
    return post<T>(path,body,false);
  }

  if(!r.ok){
    let message=`API_${r.status}`;

    try{
      const data=await r.json();
      const detail=data?.detail;

      if(typeof detail==='string'){
        message=detail;
      }else if(Array.isArray(detail)){
        message=detail.map((x:any)=>{
          const where=Array.isArray(x.loc)?x.loc.join('.'):'request';
          return `${where}: ${x.msg||'Invalid value'}`;
        }).join(' | ');
      }else if(detail?.message){
        message=detail.message;
      }
    }catch{}

    throw new Error(message);
  }

  return r.json();
}
async function mutate<T>(path:string,method:'PATCH'|'PUT'|'DELETE',body?:any):Promise<T>{
  const headers:Record<string,string>={'X-CSRF-Token':await ensureCsrf()};
  if(body!==undefined) headers['Content-Type']='application/json';
  const r=await fetch(`${BASE}${path}`,{method,headers,credentials:'include',body:body===undefined?undefined:JSON.stringify(body)});
  if(r.status===403){csrfToken=null;throw new Error('CSRF_403');}
  if(!r.ok)throw new Error(`API_${r.status}`);return r.json()
}
export const authApi={me:()=>get<any>('/api/auth/me'),login:async(username:string,password:string)=>{const r=await fetch(BASE+'/api/auth/login',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});if(!r.ok){const text=await r.text();throw new Error(text||'Login failed')}return r.json()},logout:()=>post<any>('/api/auth/logout',{})};
export const api={
aiChat:(body:any)=>post<any>('/api/ai/chat',body),
manualProspect:(body:any)=>post<any>('/api/prospects/manual',body),followUps:(campaign:string)=>get<any[]>(`/api/follow-ups?campaign=${encodeURIComponent(campaign)}`),nextAction:(id:number,body:any)=>post<any>(`/api/prospects/${id}/next-action`,body),reschedule:(id:number,body:any)=>post<any>(`/api/follow-ups/events/${id}/reschedule`,body),
outscraperPreview:(body:{query:string;limit:number;category?:string})=>post<any>('/api/leads/outscraper/preview',body),outscraperQualifyPreview:(body:any)=>post<any>('/api/leads/outscraper/qualify-preview',body),outscraperGenerate:(body:any)=>post<any>('/api/leads/outscraper/generate',body),calendarUpcoming:()=>get<any>('/api/integrations/calendar/upcoming'),googleStatus:()=>get<any>('/api/google/status'),googleOAuthStart:()=>get<any>('/api/google/oauth/start'),googleDisconnect:()=>post<any>('/api/google/disconnect',{}),calendarPreview:(body:any)=>post<any>('/api/integrations/calendar/preview',body),calendarCreate:(body:any)=>post<any>('/api/integrations/calendar/create',body),gmailSend:(body:any)=>post<any>('/api/integrations/gmail/send',body),integrations:()=>get<any>('/api/integrations/status'),hubspotSettings:()=>get<any>('/api/settings/hubspot'),hubspotSettingsTest:()=>post<any>('/api/settings/hubspot/test',{}),saveHubspotSettings:(b:any)=>post<any>('/api/settings/hubspot',b),bookingSettings:()=>get<any>('/api/settings/booking'),saveBookingSettings:(b:any)=>post<any>('/api/settings/booking',b),logAction:(prospect_id:number,action_type:string,metadata:any={})=>post<any>(`/api/prospects/${prospect_id}/external-action`,{prospect_id,action_type,metadata}),batchPreview:(campaign:string)=>post<any>('/api/hubspot/batch-preview',{campaign}),batchSync:(body:any)=>post<any>('/api/hubspot/batch-sync',body),activity:(id:number,body:any)=>mutate<any>(`/api/prospects/${id}/activity`,'PATCH',body),metrics:(campaign?:string)=>get<any>(`/api/metrics${campaign?`?campaign=${encodeURIComponent(campaign)}`:''}`),queue:(campaign='orlando_beauty')=>get<Queue>(`/api/queue?campaign=${encodeURIComponent(campaign)}`),prospects:(campaign='orlando_beauty')=>get<QueueItem[]>(`/api/prospects?campaign=${encodeURIComponent(campaign)}`),runs:()=>get<any[]>('/api/runs'),run:(id:string)=>get<any>(`/api/runs/${encodeURIComponent(id)}`),campaigns:()=>get<any>('/api/campaigns'),campaignCreate:(body:any)=>post<any>('/api/campaigns',body),campaignDelete:(id:string)=>fetch(`${BASE}/api/campaigns/${encodeURIComponent(id)}`,{method:'DELETE'}).then(async r=>{if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||`API_${r.status}`)}return r.json()}),campaignUpdate:(id:string,body:any)=>fetch(`${BASE}/api/campaigns/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{if(!r.ok)throw new Error(`API_${r.status}`);return r.json()}),hubspotStatus:()=>get<any>('/api/hubspot/status'),previewSync:(p:any)=>post<any>('/api/hubspot/preview-sync',p),sync:(p:any)=>post<any>('/api/hubspot/sync',p)};
export const campaignApi={preview:(body:any)=>post<any>('/api/campaigns/run-preview',body),run:(body:any)=>post<any>('/api/campaigns/run',body)};
export async function uploadCampaign(file:File){const fd=new FormData();fd.append('file',file);const r=await fetch(`${BASE}/api/campaigns/upload`,{method:'POST',body:fd});if(!r.ok)throw new Error(`UPLOAD_${r.status}`);return r.json()}



