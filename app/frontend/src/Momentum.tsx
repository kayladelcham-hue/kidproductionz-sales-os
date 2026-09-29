import React,{useEffect,useState} from 'react';
import {api} from './api';
import './Momentum.css';

const words=(value:string)=>String(value||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());

export function MomentumLine({data,onOpen}:{data:any;onOpen:()=>void}){
 if(!data)return null;return <button className="momentum-line" onClick={onOpen}><b>{data.level?.name||'Starter'}</b><span>{data.total||0} Momentum</span>{data.level?.next_name&&<small>{data.level.remaining} until {data.level.next_name}</small>}</button>
}

export function MomentumPage(){
 const [data,setData]=useState<any>(null);useEffect(()=>{api.momentum().then(setData).catch(()=>setData({total:0,level:{name:'Starter'},mission:{},selling_rhythm:{}}))},[]);if(!data)return <div className="card">Loading your progress…</div>;
 const level=data.level||{},mission=data.mission||{},contacts=Math.min(100,(mission.contacts||0)/Math.max(1,mission.contacts_target||8)*100);
 return <div className="momentum-page"><section className="momentum-hero"><p className="eyebrow">KP MOMENTUM</p><h2>{level.name}</h2><strong>{data.total||0} Momentum</strong>{level.next_name&&<p>{level.remaining} until {level.next_name}</p>}<div className="momentum-level-bar"><i style={{width:`${level.next_at?Math.min(100,((data.total-level.floor)/(level.next_at-level.floor))*100):100}%`}}/></div></section><section className="card momentum-rhythm"><div><p className="eyebrow">SELLING RHYTHM</p><h3>{data.selling_rhythm?.active_days||0} active selling days this week</h3><p>Consistency counts. Missing a day never wipes out your progress.</p></div></section><section className="card momentum-mission"><header><div><p className="eyebrow">TODAY'S MISSION</p><h3>{mission.complete?'Mission complete':'Make the next conversations happen'}</h3></div></header><div><span><b>{mission.contacts||0} / {mission.contacts_target||8}</b> qualified leads contacted</span><div><i style={{width:`${contacts}%`}}/></div></div><div><span><b>{mission.meetings||0} / {mission.meetings_target||1}</b> conversation booked</span><div><i style={{width:`${Math.min(100,(mission.meetings||0)/Math.max(1,mission.meetings_target||1)*100)}%`}}/></div></div></section><section className="momentum-levels"><p className="eyebrow">PROGRESSION</p>{(data.config?.levels||[]).map((item:any)=><div className={(data.total||0)>=item.threshold?'reached':''} key={item.name}><i/><span><b>{item.name}</b><small>{item.threshold} Momentum</small></span></div>)}</section><p className="momentum-note">Momentum rewards qualified outreach and real sales outcomes. It does not reward page views, bulk clicks, or low-quality spam.</p></div>
}

export function MoreHub({onNavigate}:{onNavigate:(page:string)=>void}){
 const items=[['ICP Profile','ICP Profile','Define who is worth pursuing'],['Campaigns','Campaigns','Choose markets and lead searches'],['Calendar','Calendar','Manage follow-ups and meetings'],['Customers','Customers','See relationships and repeat opportunities'],['Sales & Revenue','Sales & Revenue','See booked, closed, and collected value'],['Analytics','Sales & Revenue','Review sales performance'],['Momentum','Momentum','View levels and selling rhythm'],['Runs','Runs','Review lead generation history'],['Settings','Settings','Appearance and connections']];
 return <div className="more-hub"><div><p className="eyebrow">MORE</p><h2>Tools when you need them.</h2><p>Daily selling stays simple. Everything else lives here.</p></div><div className="more-grid">{items.map(([label,page,hint])=><button key={label} onClick={()=>onNavigate(page)}><b>{label}</b><span>{hint}</span><strong>→</strong></button>)}</div></div>
}

export function MomentumToast({event,onDone}:{event:any;onDone:()=>void}){
 useEffect(()=>{const timer=setTimeout(onDone,2200);return()=>clearTimeout(timer)},[onDone]);if(!event?.awarded)return null;
 const message=event.event_type==='meeting_booked'?'LET’S GO. Meeting booked.':event.event_type==='deal_won'?'Closed. 💰':event.event_type==='reply_received'?'They replied 👀':'Another meaningful move made.';
 return <div className="momentum-toast" role="status"><b>{message}</b><span>+{event.points+(event.bonus_points||0)} Momentum</span></div>
}
