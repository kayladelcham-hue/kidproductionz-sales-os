import React, {useEffect, useRef, useState} from 'react';
import {api} from './api';
import {DiscoveryCard} from './DiscoveryCard';
import {FocusCarousel} from './FocusCarousel';
import {SavedBusinessCarousel} from './SavedBusinessCarousel';

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
  onFocus?:(id:number|undefined)=>void; onUpdated:(row:any)=>void; onOpen:(row:any)=>void;
  onBrowse:()=>void; onNewSearch:()=>void;
};

/** A review round contains actual unreviewed records; every decision counts. */
export function GuidedReview({businesses,campaign,searchId,onFocus,onUpdated,onOpen,onBrowse,onNewSearch}:Props) {
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
  const decisionLock=useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const current = round[index];
  const previousBusiness=round.length>1?businesses.find(x=>x.id===round[(index-1+round.length)%round.length]):undefined;
  const nextBusiness=round.length>1?businesses.find(x=>x.id===round[(index+1)%round.length]):undefined;
  const latest = businesses.find(x=>x.id===current);
  const savedFits=[...businesses].reverse().filter(row=>row.saved&&row.decision==='QUALIFIED');
  const reviewed = businesses.filter(x=>x.decision!=='UNREVIEWED').length;
  const saved = businesses.filter(x=>x.saved).length;
  const remaining = businesses.filter(x=>x.decision==='UNREVIEWED');

  useEffect(()=>{
    if (!current) {setBusiness(null);if(!savedFits.length)onFocus?.(undefined);return;}
    let cancelled = false;
    setLoading(true);setError('');setBusiness(null);setRetrySave(false);setSkye(null);
    api.discoveryDetail(current,searchId).then(row=>{
      if (!cancelled) {setBusiness(row);setNotes(row.notes||'');onFocus?.(row.id);}
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

  useEffect(()=>{if(!loading&&!current)heading.current?.focus();},[current,business?.id,loading]);

  const finish = async (id:number, outcome:string) => {
    const row = await api.discoveryDetail(id,searchId);
    onUpdated(row);setBusiness(row);setRetrySave(false);
    setNotice(outcome==='QUALIFIED' ? 'Looks like a fit. Business saved.' : `${labels[outcome]}. Your decision is saved.`);
    setIndex(value=>value+1);
  };

  const choose = async (outcome:string) => {
    if (!business || busy || retrySave || decisionLock.current) return;
    decisionLock.current=true;setBusy(true);setError('');
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
    } finally {decisionLock.current=false;setBusy(false);}
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
    {round.length>0&&<div className="kp-review-progress"><span>Review {round.length}</span><ol aria-label="Recorded review progress">{round.map(id=><li key={id} className={businesses.some(row=>row.id===id&&row.decision!=='UNREVIEWED')?'is-done':''}><span className="kp-sr-only">{businesses.find(row=>row.id===id)?.name}: {businesses.some(row=>row.id===id&&row.decision!=='UNREVIEWED')?'reviewed':'not reviewed'}</span></li>)}</ol></div>}
    {error&&<p role="alert">{error}</p>}

    {loading&&<p role="status">Loading…</p>}
    {current&&!loading&&!business&&<button onClick={()=>setLoadAttempt(x=>x+1)}>Try again</button>}
    {current&&<FocusCarousel review activeKey={index} onPrevious={!busy&&!retrySave&&round.length>1?()=>setIndex((index-1+round.length)%round.length):undefined} onNext={!busy&&!retrySave&&round.length>1?()=>setIndex((index+1)%round.length):undefined} previous={previousBusiness?{label:'Previous business',title:previousBusiness.name,summary:[previousBusiness.category,previousBusiness.city].filter(Boolean).join(' · '),business:previousBusiness}:undefined} next={nextBusiness?{label:'Coming next',title:nextBusiness.name,summary:[nextBusiness.category,nextBusiness.city].filter(Boolean).join(' · '),business:nextBusiness}:{label:'After this card',title:'Choose your next step',summary:'Your decisions stay saved'}}><div className="dw-guided-card-host">{loading||business?.id!==current?<div role="status" className="dw-card-loading"><span>✦ Skye</span><h3>{latest?.name||'Loading…'}</h3><p></p></div>:<>
      <DiscoveryCard business={business} disabled={busy||retrySave} onDecision={choose}>
      <div className="kp-research-actions"><button disabled={busy} onClick={explain}>✦ Ask Skye</button>
      {skye&&<div className="dw-skye-guide" aria-live="polite"><strong><img className="dw-inline-skye" src="/avatars/skye.png" alt=""/>Skye</strong>{skye.businesses?.map((row:any)=><div key={row.id}><p>What matches: {row.known.join(' · ')||'No match confirmed.'}</p><p>What to check: {row.missing.join(' · ')}</p><p>My suggestion: {labels[row.suggested_decision]}. {row.explanation}</p>{row.sources.map((source:any)=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a>)}</div>)}</div>}
        <button onClick={()=>onOpen(business)}>Open details</button>
        {link(business.website)&&<a href={link(business.website)} target="_blank" rel="noreferrer">🌐 Website</a>}
        <label>📝 Note<textarea disabled={busy||retrySave} maxLength={3000} value={notes} onChange={e=>setNotes(e.target.value)}/></label>
      </div></DiscoveryCard>
    </>}</div></FocusCarousel>}
    {current&&business?.id===current&&!loading&&<div className="dw-decision-dock" role="group" aria-label="Does this look worth contacting?"><div className="dw-actions dw-verdicts">{['DISQUALIFIED','NEEDS_RESEARCH','QUALIFIED'].map(outcome=><button key={outcome} className={outcome==='QUALIFIED'?'dw-primary':outcome==='NEEDS_RESEARCH'?'dw-not-sure':''} disabled={busy||retrySave} onClick={()=>choose(outcome)}><span aria-hidden="true">{outcome==='QUALIFIED'?'✓':outcome==='NEEDS_RESEARCH'?'?':'×'}</span>{labels[outcome]}</button>)}</div><p>Saves automatically.{undo&&<button disabled={busy} onClick={undoLast}>Undo</button>}</p>{retrySave&&<button className="dw-primary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{await api.discoverySave(business.id);await finish(business.id,'QUALIFIED');}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>Retry save</button>}</div>}
    <div className="dw-review-foot">{notice&&<div className="dw-celebration" role="status" key={`${index}-${notice}`}><span aria-hidden="true">✓</span><p>{notice}</p></div>}</div>
    {!current&&savedFits.length>0&&<SavedBusinessCarousel businesses={savedFits} onFocus={onFocus} onOpen={onOpen}/>}
    {!current&&undo&&<button disabled={busy} onClick={undoLast}>Undo</button>}
    {!current&&<div className="dw-round-complete">
      <h3 ref={heading} tabIndex={-1}>{businesses.length?'Nice work. What’s next?':'Nothing found yet.'}</h3>
      <div className="kp-review-totals"><span><b>{reviewed}</b> Reviewed</span><span><b>{saved}</b> Saved</span></div>{!businesses.length&&<p>Try another business type or area.</p>}
      <div className="dw-actions">
        {remaining.length>0&&<button className="dw-primary" onClick={()=>{setRound(remaining.slice(0,5).map(x=>x.id));setIndex(0);setUndo(null);setNotice('');}}>Review {Math.min(5,remaining.length)} more</button>}

        <button onClick={onBrowse}>View all</button>
        <button onClick={onNewSearch}>New search</button>
      </div>
    </div>}
  </section>;
}
