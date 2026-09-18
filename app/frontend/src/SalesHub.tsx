import React, {useEffect, useState} from 'react';
import {api} from './api';

const statuses=['NOT_CONTACTED','ATTEMPTED','CONTACTED','REPLIED','FOLLOW_UP','CONSULTATION_SET','BOOKED','NOT_INTERESTED'];
const label=(s:string)=>s.replace(/_/g,' ');
const localDate=(v:string)=>{if(!v)return '';const d=new Date(v);if(Number.isNaN(d.getTime()))return '';return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)};

export function AddProspect({campaign}:{campaign:string}){
  const [form,setForm]=useState({name:'',phone:'',email:'',notes:''});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const save=async(e:React.FormEvent)=>{e.preventDefault();setBusy(true);setMessage('');try{await api.manualProspect({campaign,...form});setForm({name:'',phone:'',email:'',notes:''});setMessage('Prospect saved. Find them in Prospects and the Follow-Up / Schedule Hub.')}catch(e:any){setMessage(e.message)}finally{setBusy(false)}};
  return <form className="card sales-hub-form" onSubmit={save}><h2>Add Prospect</h2><p>Met someone in person? Save their details in {campaign}.</p>
    <label>Name / business<input required maxLength={200} autoComplete="name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
    <label>Phone<input type="tel" autoComplete="tel" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
    <label>Email<input type="email" autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
    <label>Notes (optional)<textarea maxLength={4000} placeholder="Where you met, what to discuss next…" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>
    <p className="muted">Name and phone or email required. Saved as Contacted for qualification review.</p>
    <button disabled={busy||!form.name.trim()||!(form.phone.trim()||form.email.trim())}>{busy?'Saving…':'Save Prospect'}</button><p role="status">{message}</p></form>;
}

function HubItem({p,campaign,refresh,onOpen}:{p:any;campaign:string;refresh:()=>void;onOpen:(p:any)=>void}){
  const [status,setStatus]=useState(p.sales_status),[notes,setNotes]=useState(p.notes||'');
  const [action,setAction]=useState(p.next_action.action||''),[due,setDue]=useState(localDate(p.next_action.due_at||''));
  const [event,setEvent]=useState<any>(null),[start,setStart]=useState(''),[end,setEnd]=useState('');
  const [preview,setPreview]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const tz=Intl.DateTimeFormat().resolvedOptions().timeZone;
  const save=async()=>{setBusy(true);setError('');try{await api.nextAction(p.id,{campaign,status,notes,action,due_at:due?new Date(due).toISOString():null});refresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  const move=async(confirmed:boolean)=>{setBusy(true);setError('');try{const x=await api.reschedule(event.id,{campaign,start,end,timezone:tz,confirmed});if(confirmed){setEvent(null);setPreview(null);refresh()}else setPreview(x)}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  return <article className="card sales-hub-form"><h2>{p.name}</h2><div className="actions">{p.phone&&<a href={`tel:${p.phone}`}>Call</a>}{p.email&&<a href={`mailto:${p.email}`}>Email</a>}<button onClick={()=>onOpen({...p,prospect_id:p.id})}>Prospect details / schedule</button></div>
    <label>Status<select value={status} onChange={e=>setStatus(e.target.value)}>{statuses.map(s=><option key={s}>{s}</option>)}</select></label>
    <label>Next action<input maxLength={500} value={action} onChange={e=>setAction(e.target.value)}/></label>
    <label>Follow-up time ({tz})<input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label>
    <label>Notes<textarea maxLength={4000} value={notes} onChange={e=>setNotes(e.target.value)}/></label><button disabled={busy} onClick={save}>Save next action</button>
    {p.events.map((ev:any)=><div className="preview" key={ev.id}><p>Consultation: {ev.consultation_start?new Date(ev.consultation_start).toLocaleString():'Time unavailable'}</p>{ev.event_url&&<a target="_blank" rel="noreferrer" href={ev.event_url}>Open in Calendar</a>} <button disabled={busy} onClick={()=>{setEvent(ev);setStart(localDate(ev.consultation_start));setEnd(localDate(ev.consultation_end));setPreview(null)}}>Reschedule</button></div>)}
    {event&&<div className="preview"><label>Start ({tz})<input type="datetime-local" value={start} onChange={e=>{setStart(e.target.value);setPreview(null)}}/></label><label>End<input type="datetime-local" value={end} onChange={e=>{setEnd(e.target.value);setPreview(null)}}/></label><button disabled={busy||!start||!end} onClick={()=>move(false)}>Preview reschedule</button>{preview&&<><p>{new Date(preview.start).toLocaleString()} – {new Date(preview.end).toLocaleString()}</p><button disabled={busy} onClick={()=>move(true)}>Confirm Google Calendar reschedule</button></>}<button disabled={busy} onClick={()=>{setEvent(null);setPreview(null)}}>Cancel</button></div>}
    <p role="alert">{error}</p></article>;
}

export function FollowUpHub({campaign,onOpen}:{campaign:string;onOpen:(p:any)=>void}){
  const [rows,setRows]=useState<any[]|null>(null),[error,setError]=useState(''),[filter,setFilter]=useState('All');
  const load=()=>api.followUps(campaign).then(setRows).catch((e:any)=>setError(e.message));
  useEffect(()=>{let active=true;api.followUps(campaign).then(x=>{if(active)setRows(x)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[campaign]);
  const time=(p:any)=>p.next_action.due_at||p.events[p.events.length-1]?.consultation_start||'';
  const visible=(rows||[]).filter(p=>filter==='All'||p.sales_status===filter).sort((a,b)=>(Date.parse(time(a))||Infinity)-(Date.parse(time(b))||Infinity));
  return <div><div className="card"><h2>Follow-Up / Schedule Hub</h2><p>Follow-ups and consultations for {campaign}.</p><label>Show<select value={filter} onChange={e=>setFilter(e.target.value)}><option>All</option>{statuses.map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label><button onClick={load}>Refresh</button></div><p role="alert">{error}</p>{rows===null?<p>Loading…</p>:visible.length?visible.map(p=><HubItem key={p.id+JSON.stringify(p)} p={p} campaign={campaign} refresh={load} onOpen={onOpen}/>):<div className="card empty">No follow-ups or consultations to show.</div>}</div>;
}
