import React,{useEffect,useRef,useState} from 'react';
import {api} from './api';
import {BusinessHero} from './BusinessHero';
import {businessLink} from './DiscoveryCard';
export function contactChannels(row:any){return [businessLink(row.website)&&'Website',String(row.phone||'').replace(/\D/g,'').length>=7&&'Phone',/^[^@\s?&#]+@[^@\s?&#]+\.[^@\s?&#]+$/.test(row.email||'')&&'Email',businessLink(row.social)&&'Social'].filter(Boolean) as string[]}
/** Only saved, explicitly qualified records with listed contact paths are eligible. */
export function ReadyToContact({businesses,onOpen,onFind,campaign}:{campaign?:string;businesses:any[];onOpen:(row:any,draft:boolean)=>Promise<void>;onFind:()=>void}){
 const row=businesses.find(r=>r.saved&&r.decision==='QUALIFIED'&&r.prospect_id&&contactChannels(r).length);const [busy,setBusy]=useState(false),[error,setError]=useState(''),[nextAction,setNextAction]=useState(''),[actionError,setActionError]=useState(false);const lock=useRef(false);
 useEffect(()=>{let active=true;setNextAction('');setActionError(false);if(campaign&&row)api.followUps(campaign).then(records=>{if(active)setNextAction(records.find(r=>r.id===row.prospect_id)?.next_action?.action||'')}).catch(()=>{if(active)setActionError(true)});return()=>{active=false}},[campaign,row?.prospect_id]);
 const open=async(draft:boolean)=>{if(lock.current||!row)return;lock.current=true;setBusy(true);setError('');try{await onOpen(row,draft)}catch(e:any){setError(e.message||'Could not open this contact. Try again.')}finally{lock.current=false;setBusy(false)}};
 return <aside className="kp-ready-contact" aria-label="Ready to contact"><h3>Ready to contact</h3>{row?<><div className="kp-ready-identity"><BusinessHero business={row} compact/><div><h4>{row.name||row.company}</h4><p>{contactChannels(row).join(' · ')}</p><small>Listed · unverified</small></div></div>{(nextAction||typeof row.next_action==='string'&&row.next_action)&&<p>{nextAction||row.next_action}</p>}{actionError&&<small>Next action unavailable. Check contact details.</small>}<div className="kp-ready-actions"><button disabled={busy} onClick={()=>open(false)}>View contact</button><button disabled={busy} onClick={()=>open(true)}>Draft a message</button></div></>:<><p>Find a fit to start a conversation.</p><button onClick={onFind}>Find a business</button></>}{error&&<p role="alert">{error}</p>}</aside>
}
