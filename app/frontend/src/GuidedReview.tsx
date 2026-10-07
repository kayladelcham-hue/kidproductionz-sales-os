import React, {useEffect, useRef, useState} from 'react';
import {api} from './api';
import {BusinessHero} from './BusinessHero';
import {FocusCarousel} from './FocusCarousel';

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
  const [loadAttempt,setLoadAttempt]=useState(0);
  const [loading,setLoading] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [skye,setSkye] = useState<any>(null);
  const [retrySave,setRetrySave] = useState(false);
  const [undo,setUndo] = useState<any>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const current = round[index];
  const previousBusiness=businesses.find(x=>x.id===round[index-1]);
  const nextBusiness=businesses.find(x=>x.id===round[index+1]);
  const latest = businesses.find(x=>x.id===current);
  const completedInRound=round.filter(id=>businesses.some(row=>row.id===id&&row.decision!=='UNREVIEWED')).length;
  const savedFit=[...businesses].reverse().find(row=>row.saved&&row.decision==='QUALIFIED');
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
  },[current,searchId,loadAttempt]);

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
    <div className="dw-mission-bar"><div className="dw-mission-skye"><img src="/avatars/skye.png" alt="Skye"/><div><strong>SKYE</strong><p>{current?'Let’s check what fits and what we still need to know.':'Your choices are saved. Let’s choose the next step.'}</p></div></div><div className="dw-mission-progress"><div><small>THIS ROUND</small><b>{round.length?`Review ${round.length} businesses`:'Your review is saved'}</b></div><ol aria-label="Recorded decisions in this round">{round.map(id=>{const done=businesses.some(row=>row.id===id&&row.decision!=='UNREVIEWED');return <li key={id} className={done?'is-done':''}><span aria-hidden="true">{done?'✓':''}</span><span className="dw-sr-only">{businesses.find(row=>row.id===id)?.name}: {done?'reviewed':'not reviewed'}</span></li>})}</ol><div><b>{round.length?`${completedInRound} of ${round.length}`:`${reviewed} reviewed`}</b><small>Every decision counts.</small></div></div></div>
    {error&&<p role="alert">{error}</p>}

    {loading&&<p role="status">Opening the next business…</p>}
    {current&&!loading&&!business&&<button onClick={()=>setLoadAttempt(x=>x+1)}>Try opening this business again</button>}
    {current&&<FocusCarousel activeKey={index} onPrevious={!busy&&index>0?()=>setIndex(index-1):undefined} onNext={!busy&&index+1<round.length?()=>setIndex(index+1):undefined} previous={previousBusiness?{label:'Just reviewed',title:previousBusiness.name,summary:[previousBusiness.category,previousBusiness.city].filter(Boolean).join(' · '),business:previousBusiness}:undefined} next={nextBusiness?{label:'Coming next',title:nextBusiness.name,summary:[nextBusiness.category,nextBusiness.city].filter(Boolean).join(' · '),business:nextBusiness}:{label:'After this card',title:'Choose your next step',summary:'Your decisions stay saved'}}><article className="dw-guided-card">{loading||business?.id!==current?<div role="status" className="dw-card-loading"><span>✦ Skye</span><h3>{latest?.name||'Opening the next business…'}</h3><p>Getting the recorded evidence…</p></div>:<>
      <BusinessHero business={business}/>
      <h3 ref={heading} tabIndex={-1}>{business.name}</h3>
      <p>{business.category||'Business type not recorded'} · {[business.city,business.state].filter(Boolean).join(', ')||'Location not recorded'}</p>
      <div className="dw-card-evidence">
       <div className="dw-evidence-row"><span aria-hidden="true">⌕</span><p><b>{business.assessment?.label==='Outside criteria'?'Check the fit':'Matches recorded'}</b>: {business.assessment?.matches?.slice(0,3).map((x:string)=>x.replace(/^Industry:/,'Business type:')).join(' · ')||'No match is confirmed yet.'}</p></div>
       <div className="dw-evidence-row is-contact"><span aria-hidden="true">↗</span><p><b>Contact</b>: {business.assessment?.contact_paths?.length?`${business.assessment.contact_paths.join(', ')} listed · unverified`:'Not recorded yet'}</p></div>
       <div className="dw-evidence-row is-unknown"><span aria-hidden="true">?</span><p><b>Still unknown</b>: {business.assessment?.missing_information?.slice(0,2).join(' · ')||'Review the full evidence below'}</p></div>
       {business.assessment?.criteria?.filter((x:any)=>x.status==='MISMATCH').map((x:any)=><div className="dw-evidence-row is-mismatch" key={x.criterion}><span aria-hidden="true">!</span><p><b>Doesn’t match</b>: {x.criterion} — {x.value} (you asked for {x.target}).</p></div>)}
      </div><p className="dw-buying-note">ⓘ A match does not mean they want to buy.</p>
      <details><summary>Evidence, Skye’s explanation, and notes</summary><button disabled={busy} onClick={explain}>Skye, walk me through this business</button>
      {skye&&<div className="dw-skye-guide" aria-live="polite"><strong><img className="dw-inline-skye" src="/avatars/skye.png" alt=""/>Skye</strong>{skye.businesses?.map((row:any)=><div key={row.id}><p>What matches: {row.known.join(' · ')||'No match confirmed.'}</p><p>What to check: {row.missing.join(' · ')}</p><p>My suggestion: {labels[row.suggested_decision]}. {row.explanation}</p>{row.sources.map((source:any)=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a>)}</div>)}</div>}
        <button onClick={()=>onOpen(business)}>See evidence and ask Skye</button>
        {link(business.website)&&<a href={link(business.website)} target="_blank" rel="noreferrer">Check their website ↗</a>}
        <label>Anything to remember? (optional)<textarea maxLength={3000} value={notes} onChange={e=>setNotes(e.target.value)}/></label>
      </details>
    </>}</article></FocusCarousel>}
    {current&&business?.id===current&&!loading&&<div className="dw-decision-dock" role="group" aria-label="Does this look worth contacting?"><div className="dw-actions dw-verdicts">{['QUALIFIED','NEEDS_RESEARCH','DISQUALIFIED'].map(outcome=><button key={outcome} className={outcome==='QUALIFIED'?'dw-primary':outcome==='NEEDS_RESEARCH'?'dw-not-sure':''} disabled={busy||retrySave} onClick={()=>choose(outcome)}><span aria-hidden="true">{outcome==='QUALIFIED'?'👍':outcome==='NEEDS_RESEARCH'?'?':'×'}</span>{labels[outcome]}</button>)}</div><p>Decisions save automatically.{undo&&<button disabled={busy} onClick={undoLast}>Undo last decision</button>}</p>{retrySave&&<button className="dw-primary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{await api.discoverySave(business.id);await finish(business.id,'QUALIFIED');}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>Retry saving this business</button>}</div>}
    <div className="dw-review-foot">{notice&&<div className="dw-celebration" role="status" key={`${index}-${notice}`}><b>✦ Decision saved</b><p>{notice}</p></div>}{savedFit&&<button className="dw-saved-next" onClick={()=>onOpen(savedFit)}><b>Saved a fit?</b><span>Check the website or prepare a first message for {savedFit.name}.</span><span aria-hidden="true">→</span></button>}</div>
    {!current&&undo&&<button disabled={busy} onClick={undoLast}>Undo last decision</button>}
    {!current&&<div className="dw-round-complete">
      <h3 ref={heading} tabIndex={-1}>{businesses.length?'Nice work. What’s next?':'No businesses came back from this search.'}</h3>
      <p>{businesses.length?`You’ve reviewed ${reviewed} businesses in this search and saved ${saved}. Your decisions are saved.`:'Try a different business type or location. We won’t change your search for you.'}</p>
      <div className="dw-actions">
        {remaining.length>0&&<button className="dw-primary" onClick={()=>{setRound(remaining.slice(0,5).map(x=>x.id));setIndex(0);setUndo(null);setNotice('');}}>Review {Math.min(5,remaining.length)} more</button>}
        {businesses.filter(x=>x.saved).slice(0,3).map(row=><button key={row.id} onClick={()=>onOpen(row)}><span>Next steps</span><span className="dw-next-business">{row.name}</span></button>)}
        <button onClick={onBrowse}>View all businesses</button>
        <button onClick={onNewSearch}>Start another search</button>
      </div>
    </div>}
  </section>;
}
