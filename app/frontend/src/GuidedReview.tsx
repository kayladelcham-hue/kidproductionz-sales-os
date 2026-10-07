import React, {useEffect, useRef, useState} from 'react';
import {api} from './api';

const labels: Record<string,string> = {
  QUALIFIED:'Looks like a fit', NEEDS_RESEARCH:'Not sure', DISQUALIFIED:'Not a fit', UNREVIEWED:'Not reviewed',
};
const link = (value: unknown) => {
  try {
    const raw = String(value || '');
    if (!raw) return undefined;
    const url = new URL(/^https?:/i.test(raw) ? raw : `https://${raw}`);
    return ['http:','https:'].includes(url.protocol) && !url.username ? url.href : undefined;
  } catch { return undefined; }
};

type Props = {
  businesses:any[]; campaign:string; searchId:string;
  onUpdated:(row:any)=>void; onOpen:(row:any)=>void;
  onBrowse:()=>void; onNewSearch:()=>void;
};

/** A review round contains actual unreviewed records; every decision counts. */
export function GuidedReview({businesses,campaign,searchId,onUpdated,onOpen,onBrowse,onNewSearch}:Props) {
  const [round,setRound] = useState<number[]>(()=>businesses.filter(x=>x.decision==='UNREVIEWED').slice(0,5).map(x=>x.id));
  const [index,setIndex] = useState(0);
  const [business,setBusiness] = useState<any>(null);
  const [notes,setNotes] = useState('');
  const [loading,setLoading] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [skye,setSkye] = useState<any>(null);
  const [retrySave,setRetrySave] = useState(false);
  const [undo,setUndo] = useState<any>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const current = round[index];
  const latest = businesses.find(x=>x.id===current);
  const reviewed = businesses.filter(x=>x.decision!=='UNREVIEWED').length;
  const saved = businesses.filter(x=>x.saved).length;
  const remaining = businesses.filter(x=>x.decision==='UNREVIEWED');

  useEffect(()=>{
    if (!current) {setBusiness(null);return;}
    let cancelled = false;
    setLoading(true);setError('');setBusiness(null);setRetrySave(false);setSkye(null);
    api.discoveryDetail(current,searchId).then(row=>{
      if (!cancelled) {setBusiness(row);setNotes(row.notes||'');}
    }).catch(e=>{if(!cancelled)setError(e.message||'This business could not load.');})
      .finally(()=>{if(!cancelled)setLoading(false);});
    return ()=>{cancelled=true;};
  },[current,searchId]);

  useEffect(()=>{
    if (business?.id===current && latest && latest.revision!==business.revision) setBusiness(latest);
  },[current,latest?.revision,business?.revision]);

  const explain = async () => {
    if (!business || busy) return;
    setBusy(true);setError('');
    try {setSkye(await api.discoveryExplain({campaign,search_id:searchId,business_ids:[business.id],question:'Why does this business fit? What information is missing?'}));}
    catch(e:any) {setError(e.message||'Skye could not load the recorded evidence.');}
    finally {setBusy(false);}
  };

  useEffect(()=>{if(!loading&&(business||!current))heading.current?.focus();},[current,business?.id,loading]);

  const finish = async (id:number, outcome:string) => {
    const row = await api.discoveryDetail(id,searchId);
    onUpdated(row);setBusiness(row);setRetrySave(false);
    setNotice(outcome==='QUALIFIED' ? 'Looks like a fit. Business saved.' : `${labels[outcome]}. Your decision is saved.`);
    setIndex(value=>value+1);
  };

  const choose = async (outcome:string) => {
    if (!business || busy) return;
    setBusy(true);setError('');
    let decided = false;
    try {
      const result = await api.discoveryDecide(business.id,{
        decision:outcome,reason:`My decision: ${labels[outcome]}.`,notes,revision:business.revision,
      });
      decided = true;
      setBusiness(result);
      setUndo({id:business.id,event_id:result.undo_event,revision:result.revision,index});
      if (outcome==='QUALIFIED') await api.discoverySave(business.id);
      await finish(business.id,outcome);
    } catch (e:any) {
      if (decided) {
        // Keep the recorded decision visible. Never move past a failed save.
        try {const row=await api.discoveryDetail(business.id,searchId);setBusiness(row);onUpdated(row);} catch {}
        setRetrySave(outcome==='QUALIFIED');
      }
      setError(`${decided?'Your decision was saved, but the next step could not finish. ':''}${e.message||'Please try again.'}`);
    } finally {setBusy(false);}
  };

  const undoLast = async () => {
    if (!undo || busy) return;
    setBusy(true);setError('');
    try {
      await api.discoveryUndo(undo.id,{event_id:undo.event_id,revision:undo.revision});
      const row = await api.discoveryDetail(undo.id,searchId);
      onUpdated(row);setBusiness(row);setIndex(undo.index);setUndo(null);setRetrySave(false);
      setNotice(`Decision undone.${row.saved?' The business is still saved; you can review it again.':''}`);
    } catch(e:any) {setError(e.message||'The decision could not be undone.');}
    finally {setBusy(false);}
  };

  return <section className="dw-guided" aria-label="Review businesses one at a time">
    <div className="dw-skye-guide" aria-label="Skye’s guidance"><strong>✦ Skye</strong><p>{current?'Let’s take a look together. Check what matches and what’s missing, then tell me whether this looks worth contacting. Any of the three choices is useful.':businesses.length?'Your choices are saved. We can check a saved business’s website, prepare a first message, or look at a few more businesses.':'This search didn’t bring back any businesses. Let’s try another business type or location—you choose what to change.'}</p></div>
    <p className="dw-step">{current?`Business ${index+1} of ${round.length}`:'Your review is saved'}</p>
    <progress className="dw-progress" max={Math.max(round.length,1)} value={index} aria-label={`${index} of ${round.length} businesses reviewed in this round`}/>
    {notice&&<p role="status" className="dw-celebration">✓ {notice}</p>}
    {error&&<p role="alert">{error}</p>}
    {undo&&<button disabled={busy} onClick={undoLast}>Undo last decision</button>}
    {loading&&<p role="status">Opening the next business…</p>}
    {current&&!loading&&!business&&<button onClick={()=>onOpen(businesses.find(x=>x.id===current))}>Open business details</button>}
    {current&&business&&!loading&&<article className="dw-guided-card" key={business.id}>
      <h3 ref={heading} tabIndex={-1}>{business.name}</h3>
      <p>{business.category||'Business type not recorded'} · {[business.city,business.state].filter(Boolean).join(', ')||'Location not recorded'}</p>
      <button disabled={busy} onClick={explain}>Skye, walk me through this business</button>
      {skye&&<div className="dw-skye-guide" aria-live="polite"><strong>✦ Skye</strong>{skye.businesses?.map((row:any)=><div key={row.id}><p>What matches: {row.known.join(' · ')||'No match is confirmed yet.'}</p><p>What to check: {row.missing.join(' · ')}</p><p>My suggestion: {labels[row.suggested_decision]}. {row.explanation}</p>{row.sources.map((source:any)=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a>)}</div>)}</div>}
      <h4>Why it appeared</h4>
      <p>{business.assessment?.matches?.join(' · ')||'No matching details are confirmed yet.'}</p>
      {business.assessment?.criteria?.filter((x:any)=>x.status==='MISMATCH').map((x:any)=><p key={x.criterion}>Doesn’t match: {x.criterion} — {x.value} (you asked for {x.target}).</p>)}
      <h4>Contact information</h4>
      <p>{business.assessment?.contact_paths?.length?`${business.assessment.contact_paths.join(', ')} available, but not independently verified.`:'No contact information recorded yet.'}</p>
      <h4>What we don’t know</h4>
      <ul>{business.assessment?.missing_information?.map((x:string)=><li key={x}>{x}</li>)}</ul>
      <p>A search match does not mean this business wants to buy.</p>
      <details><summary>Check evidence or add a note</summary>
        <button onClick={()=>onOpen(business)}>See evidence and ask Skye</button>
        {link(business.website)&&<a href={link(business.website)} target="_blank" rel="noreferrer">Check their website ↗</a>}
        <label>Anything to remember? (optional)<textarea maxLength={3000} value={notes} onChange={e=>setNotes(e.target.value)}/></label>
      </details>
      <h4>Does this look worth contacting?</h4>
      <div className="dw-actions dw-verdicts">{['QUALIFIED','NEEDS_RESEARCH','DISQUALIFIED'].map(outcome=><button key={outcome} disabled={busy||retrySave} onClick={()=>choose(outcome)}>{labels[outcome]}</button>)}</div>
      <p>All three choices count as progress. “Looks like a fit” also saves the business.</p>
      {retrySave&&<button className="dw-primary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{await api.discoverySave(business.id);await finish(business.id,'QUALIFIED');}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>Retry saving this business</button>}
    </article>}
    {!current&&<div className="dw-round-complete">
      <h3 ref={heading} tabIndex={-1}>{businesses.length?'Nice work. What’s next?':'No businesses came back from this search.'}</h3>
      <p>{businesses.length?`You’ve reviewed ${reviewed} businesses in this search and saved ${saved}. Your decisions are saved.`:'Try a different business type or location. We won’t change your search for you.'}</p>
      <div className="dw-actions">
        {remaining.length>0&&<button className="dw-primary" onClick={()=>{setRound(remaining.slice(0,5).map(x=>x.id));setIndex(0);setUndo(null);setNotice('');}}>Review up to 5 more</button>}
        {businesses.filter(x=>x.saved).slice(0,3).map(row=><button key={row.id} onClick={()=>onOpen(row)}>Next steps for {row.name}</button>)}
        <button onClick={onBrowse}>View all businesses</button>
        <button onClick={onNewSearch}>Start another search</button>
      </div>
    </div>}
  </section>;
}
