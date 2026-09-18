import React, {useEffect, useState} from 'react';
import {api} from './api';
import './SalesHub.css';

const statuses=['NOT_CONTACTED','ATTEMPTED','CONTACTED','REPLIED','FOLLOW_UP','CONSULTATION_SET','BOOKED','NOT_INTERESTED'];
const label=(s:string)=>s.toLowerCase().replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const localDate=(v:string)=>{if(!v)return '';const d=new Date(v);if(Number.isNaN(d.getTime()))return '';return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)};

export function AddProspect({campaign}:{campaign:string}){
  const [form,setForm]=useState({name:'',phone:'',email:'',notes:''});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const save=async(e:React.FormEvent)=>{e.preventDefault();setBusy(true);setMessage('');try{await api.manualProspect({campaign,...form});setForm({name:'',phone:'',email:'',notes:''});setMessage('Prospect saved. Find them in Prospects and the Follow-Up / Schedule Hub.')}catch(e:any){setMessage(e.message)}finally{setBusy(false)}};
  return <div className="kp-sales"><form className="card sales-hub-form intake-card" onSubmit={save}>
    <div className="sales-intro"><span className="sales-symbol" aria-hidden="true">+</span><div><p className="sales-eyebrow">NEW CONNECTION</p><h2>Keep the conversation going.</h2><p>A name. A way to reach them. You're set.</p></div></div>
    <label>Name or business<input required maxLength={200} placeholder="Who did you meet?" autoComplete="name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
    <div className="sales-field-pair"><label>Phone<input type="tel" placeholder="(407) 555-0100" autoComplete="tel" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
    <label>Email<input type="email" placeholder="name@example.com" autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label></div>
    <p className="sales-hint">Add a phone number or email—either works.</p>
    <details className="sales-notes"><summary>Add a note <span>Optional</span></summary><label><span className="sr-only">Notes</span><textarea maxLength={4000} placeholder="Where you met, what to discuss next…" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label></details>
    <button className="sales-primary" disabled={busy||!form.name.trim()||!(form.phone.trim()||form.email.trim())}>{busy?'Saving…':'Save prospect'}<span aria-hidden="true">→</span></button>
    {message&&<p className="sales-feedback" role="status">{message}</p>}</form></div>;
}

function HubItem({p,campaign,refresh,onOpen}:{p:any;campaign:string;refresh:()=>void;onOpen:(p:any)=>void}){
  const [status,setStatus]=useState(p.sales_status),[notes,setNotes]=useState(p.notes||'');
  const [action,setAction]=useState(p.next_action.action||''),[due,setDue]=useState(localDate(p.next_action.due_at||''));
  const [event,setEvent]=useState<any>(null),[start,setStart]=useState(''),[end,setEnd]=useState('');
  const [preview,setPreview]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const tz=Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [editing,setEditing]=useState(false);
  const nextTime=p.next_action.due_at;
  const overdue=nextTime&&Date.parse(nextTime)<Date.now()&&!['BOOKED','NOT_INTERESTED'].includes(p.sales_status);
  const save=async()=>{setBusy(true);setError('');try{await api.nextAction(p.id,{campaign,status,notes,action,due_at:due?new Date(due).toISOString():null});refresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  const move=async(confirmed:boolean)=>{setBusy(true);setError('');try{const x=await api.reschedule(event.id,{campaign,start,end,timezone:tz,confirmed});if(confirmed){setEvent(null);setPreview(null);refresh()}else setPreview(x)}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  return <article className="card sales-hub-form followup-card"><div className="sales-card-heading"><span className="sales-avatar" aria-hidden="true">{p.name.trim().slice(0,1).toUpperCase()}</span><div><span className="sales-status">{label(p.sales_status)}</span><h2>{p.name}</h2></div></div>
    <div className={`sales-next ${overdue?'sales-overdue':''}`}><span>{overdue?'OVERDUE':'NEXT UP'}</span><p>{p.next_action.action||'Plan your next conversation'}</p><small>{nextTime?new Date(nextTime).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'No follow-up time set'}</small></div>
    <div className="sales-quick-actions">{p.phone&&<a href={`tel:${p.phone}`}>Call</a>}{p.email&&<a href={`mailto:${p.email}`}>Email</a>}<button aria-expanded={editing} onClick={()=>setEditing(!editing)}>{editing?'Close editor':'Update follow-up'}</button><button className="sales-details" onClick={()=>onOpen({...p,prospect_id:p.id})}>Details / schedule →</button></div>
    {editing&&<div className="sales-editor"><label>Status<select value={status} onChange={e=>setStatus(e.target.value)}>{statuses.map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label>
    <label>Next action<input maxLength={500} placeholder="Send proposal, check in, call…" value={action} onChange={e=>setAction(e.target.value)}/></label>
    <label>Follow-up time<input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/><small className="sales-hint">Your timezone: {tz.replace(/_/g,' ')}</small></label>
    <label>Notes<textarea maxLength={4000} value={notes} onChange={e=>setNotes(e.target.value)}/></label><button className="sales-primary" disabled={busy} onClick={save}>{busy?'Saving…':'Save changes'}</button></div>}
    {p.events.map((ev:any)=><div className="sales-consultation" key={ev.id}><div><span className="sales-eyebrow">CONSULTATION</span><p>{ev.consultation_start?new Date(ev.consultation_start).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Time unavailable'}</p>{ev.event_url&&<a target="_blank" rel="noreferrer" href={ev.event_url}>Open calendar ↗</a>}</div><button disabled={busy} onClick={()=>{setEvent(ev);setStart(localDate(ev.consultation_start));setEnd(localDate(ev.consultation_end));setPreview(null)}}>Reschedule</button></div>)}
    {event&&<div className="preview"><label>Start ({tz})<input type="datetime-local" value={start} onChange={e=>{setStart(e.target.value);setPreview(null)}}/></label><label>End<input type="datetime-local" value={end} onChange={e=>{setEnd(e.target.value);setPreview(null)}}/></label><button disabled={busy||!start||!end} onClick={()=>move(false)}>Preview reschedule</button>{preview&&<><p>{new Date(preview.start).toLocaleString()} – {new Date(preview.end).toLocaleString()}</p><button disabled={busy} onClick={()=>move(true)}>Confirm Google Calendar reschedule</button></>}<button disabled={busy} onClick={()=>{setEvent(null);setPreview(null)}}>Cancel</button></div>}
    {error&&<p className="sales-feedback" role="alert">{error}</p>}</article>;
}

export function FollowUpHub({campaign,onOpen}:{campaign:string;onOpen:(p:any)=>void}){
  const [rows,setRows]=useState<any[]|null>(null),[error,setError]=useState(''),[filter,setFilter]=useState('All');
  const load=()=>api.followUps(campaign).then(setRows).catch((e:any)=>setError(e.message));
  useEffect(()=>{let active=true;api.followUps(campaign).then(x=>{if(active)setRows(x)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[campaign]);
  const time=(p:any)=>p.next_action.due_at||p.events[p.events.length-1]?.consultation_start||'';
  const visible=(rows||[]).filter(p=>filter==='All'||p.sales_status===filter).sort((a,b)=>(Date.parse(time(a))||Infinity)-(Date.parse(time(b))||Infinity));
  const overdue=(rows||[]).filter(p=>p.next_action.due_at&&Date.parse(p.next_action.due_at)<Date.now()&&!['BOOKED','NOT_INTERESTED'].includes(p.sales_status)).length;
  return <div className="kp-sales"><div className="sales-hub-intro"><p className="sales-eyebrow">KEEP THINGS MOVING</p><h2>Your next conversations.</h2><p>Follow-ups, meetings, and a clear next step.</p></div><div className="sales-metrics"><div><strong>{rows?.length??'—'}</strong><span>In your hub</span></div><div><strong>{rows===null?'—':overdue}</strong><span>Overdue</span></div><div><strong>{rows===null?'—':rows.filter(p=>p.events.some((e:any)=>Date.parse(e.consultation_start)>Date.now())).length}</strong><span>Upcoming meetings</span></div></div><div className="sales-toolbar"><label><span className="sr-only">Filter by status</span><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="All">All prospects</option>{statuses.map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label><button onClick={load}>Refresh ↻</button></div>{error&&<p className="sales-feedback" role="alert">{error}</p>}{rows===null?<p className="sales-loading">Loading your follow-ups…</p>:visible.length?<div className="sales-hub-list">{visible.map(p=><HubItem key={p.id+JSON.stringify(p)} p={p} campaign={campaign} refresh={load} onOpen={onOpen}/>)}</div>:<div className="card sales-empty"><span className="sales-symbol" aria-hidden="true">✓</span><h2>A little breathing room.</h2><p>No follow-ups match this view.</p></div>}</div>;
}
