import React,{useEffect,useState} from 'react'; import {createRoot} from 'react-dom/client'; import './styles.css'; import {api,campaignApi,uploadCampaign,authApi,Queue,QueueItem} from './api';
import logo from './assets/kidproductionz-logo.png'; import {ScoreBadge,GradeBadge,RouteBadge,PriorityBadge,StatusBadge} from './badges'; import {dailyQuote} from './data/salesQuotes';
const nav=['Overview','Campaigns','Prospects','Daily Queue','Runs','Settings','Up Next'];
function UpNext({campaign}:{campaign:string}){
  const {data,error}=useQueue(campaign);
  const [idx,setIdx]=useState(0);
  const [selected,setSelected]=useState<any>(null);
  const [openEmail,setOpenEmail]=useState(false);
  const [lastAction,setLastAction]=useState<any>(null);
  const [undoing,setUndoing]=useState(false);

  useEffect(()=>{
    setIdx(0);
    setSelected(null);
    setOpenEmail(false);
    setLastAction(null);
  },[campaign]);

  const items=((data?.daily_queue||[]) as any[])
    .map((x:any,i:number)=>({...x,__i:i}))
    .filter((x:any)=>!['BOOKED','NOT_INTERESTED','FOLLOW_UP'].includes(x.sales_status))
    .sort((a:any,b:any)=>{
      const r=(p:any)=>({P1:1,P2:2,P3:3}[p]||9);
      return r(a.priority)-r(b.priority)||a.__i-b.__i
    });

  const current=items[idx];

  const moveNext=()=>{
    setIdx(i=>Math.min(i+1,Math.max(0,items.length-1)))
  };

  const skip=()=>{
    if(!current)return;
    setLastAction({
      type:'SKIP',
      idx,
      prospect:current,
      message:`Skipped ${current.business_name||current.name||current.business||'prospect'}`
    });
    moveNext();
  };

  const markAttempted=async()=>{
    if(!current)return;

    const previousStatus=current.sales_status||'NOT_CONTACTED';

    if(current.prospect_id){
      try{
        await api.activity(current.prospect_id,{status:'ATTEMPTED'});
      }catch{
        return;
      }
    }

    setLastAction({
      type:'ATTEMPTED',
      idx,
      prospect:current,
      previousStatus,
      message:`Marked ${current.business_name||current.name||current.business||'prospect'} attempted`
    });

    moveNext();
  };

  const savedAndNext=()=>{
    if(!current)return;

    setLastAction({
      type:'SAVED',
      idx,
      prospect:current,
      message:`Saved ${current.business_name||current.name||current.business||'prospect'}`
    });

    setSelected(null);
    setOpenEmail(false);
    moveNext();
  };

  const undo=async()=>{
    if(!lastAction||undoing)return;

    setUndoing(true);

    try{
      if(
        lastAction.type==='ATTEMPTED' &&
        lastAction.prospect?.prospect_id
      ){
        await api.activity(
          lastAction.prospect.prospect_id,
          {status:lastAction.previousStatus||'NOT_CONTACTED'}
        );
      }

      setIdx(lastAction.idx);
      setLastAction(null);
    }finally{
      setUndoing(false);
    }
  };

  if(error)return <div className="card empty">API unavailable</div>;
  if(!data)return <div className="card empty">Loading queue...</div>;
  if(!current)return <div className="card empty"><h2>You're caught up.</h2></div>;

  const name=current.business_name||current.name||current.business||'-';

  return <div className="up-next">

    {lastAction&&
      <div className="notice">
        {lastAction.message}
        {' '}
        <button onClick={undo} disabled={undoing}>
          {undoing?'Undoing...':'Undo'}
        </button>
      </div>
    }

    <div className="card up-next-card">
      <p className="eyebrow">UP NEXT - #{current.queue_position??idx+1}</p>
      <h2>{name}</h2>

      <div className="badges">
        <ScoreBadge value={current.score}/>
        <GradeBadge value={current.grade}/>
        <PriorityBadge value={current.priority}/>
        <RouteBadge value={current.route}/>
      </div>

      <p className="muted">{current.route_reason||''}</p>

      <div className="actions">
        <a href={current.phone?`tel:${current.phone}`:'#'}>Call</a>

        <button onClick={()=>{
          setSelected(current);
          setOpenEmail(true);
        }}>Email</button>

        <a href={current.website||'#'} target="_blank" rel="noreferrer">
          Website
        </a>

        <button onClick={()=>{
          setSelected(current);
          setOpenEmail(false);
        }}>Open Prospect</button>

        <button onClick={skip}>Skip</button>
        <button onClick={markAttempted}>Mark Attempted</button>
        <button onClick={()=>{
          setSelected(current);
          setOpenEmail(false);
        }}>Save & Next</button>
      </div>
    </div>

    <h3>Coming Up</h3>

    {items.slice(idx+1,idx+5).map((x:any,i:number)=>
      <div className="card coming-up" key={x.prospect_id||i}>
        <b>{x.business_name||x.name||x.business||'-'}</b>
        <span>#{x.queue_position??idx+i+2} - {x.priority||''}</span>
      </div>
    )}

    {selected&&
      <ProspectDrawer
        item={selected}
        initialEmailOpen={openEmail}
        onClose={()=>{
          setSelected(null);
          setOpenEmail(false);
        }}
        onNext={savedAndNext}
      />
    }
  </div>
}

function App(){const [page,setPage]=useState('Overview');const [mobileMenuOpen,setMobileMenuOpen]=useState(false);const [campaign,setCampaign]=useState('orlando_beauty');const [campaigns,setCampaigns]=useState<any[]>([]);const loadCampaigns=()=>api.campaigns().then((x:any)=>{const rows=Array.isArray(x)?x:(x.campaigns||[]);setCampaigns(rows);if(rows.length&&!rows.some(c=>c.campaign_id===campaign))setCampaign(rows[0].campaign_id)}).catch(()=>setCampaigns([]));useEffect(()=>{loadCampaigns()},[]);return <div className="shell"><aside><div className="brand"><img src={logo}/><div><b>KidProductionz</b><small>Sales OS</small></div></div><nav>{nav.map(n=><button key={n} className={page===n?'active':''} onClick={()=>setPage(n)}>{n}</button>)}</nav><div className="safe"><span/>All systems read-only</div></aside><main><header><button className="mobile-menu-btn" aria-label="Open navigation" aria-expanded={mobileMenuOpen} onClick={()=>setMobileMenuOpen(true)}>☰</button><div><p className="eyebrow">KIDPRODUCTIONZ SALES OS</p><h1>{page}</h1></div><select value={campaign} onChange={e=>setCampaign(e.target.value)}>{campaigns.map(c=><option key={c.campaign_id} value={c.campaign_id}>{c.name||c.campaign_id}</option>)}</select></header>{page==='Overview'?<Overview campaign={campaign} onNavigate={setPage}/>:page==='Daily Queue'?<QueuePage campaign={campaign}/>:page==='Up Next'?<UpNext campaign={campaign}/>:page==='Prospects'?<Prospects campaign={campaign}/>:page==='Campaigns'?<Campaigns campaign={campaign} onChanged={loadCampaigns} onSelect={setCampaign}/>:page==='Runs'?<Runs/>:<Settings campaign={campaign}/>}{mobileMenuOpen&&<><div className="mobile-menu-backdrop" onClick={()=>setMobileMenuOpen(false)}/><aside className="mobile-menu-drawer"><button aria-label="Close navigation" className="mobile-menu-close" onClick={()=>setMobileMenuOpen(false)}>×</button>{["Overview","Up Next","Daily Queue","Prospects","Campaigns","Runs","Settings"].map(n=><button key={n} onClick={()=>{setPage(n);setMobileMenuOpen(false)}}>{n}</button>)}</aside></>} </main><div className="bottom-nav">{[["Home","Overview"],["Up Next","Up Next"],["Queue","Daily Queue"],["Prospects","Prospects"],["More","Settings"]].map(([l,v])=><button key={l} onClick={()=>setPage(v)}>{l}</button>)}</div></div>}
function useQueue(campaign:string){const [data,setData]=useState<Queue|null>(null);const [error,setError]=useState(false);useEffect(()=>{setData(null);setError(false);api.queue(campaign).then(setData).catch(()=>setError(true))},[campaign]);return {data,error}}
function QueueTable({items,onSelect}:{items:QueueItem[];onSelect?:(item:QueueItem)=>void}){return <div className="table-wrap"><table><thead><tr><th>Position</th><th>Business</th><th>Score</th><th>Grade</th><th>Route</th><th>Priority</th><th>Reason</th></tr></thead><tbody>{(items||[]).map((x:any,i:number)=><tr key={x.prospect_id||x.lead_id||x.fixture_id||i} onClick={()=>onSelect?.(x)}><td>{x.queue_position??i+1}</td><td><b>{x.business_name||x.name||x.business||'-'}</b></td><td><ScoreBadge value={x.score}/></td><td><GradeBadge value={x.grade}/></td><td><RouteBadge value={x.route}/></td><td><PriorityBadge value={x.priority}/></td><td>{x.route_reason||'-'}</td></tr>)}</tbody></table></div>}
function Overview({campaign,onNavigate}:{campaign:string;onNavigate?:(p:string)=>void}){const {data,error}=useQueue(campaign);const [m,setM]=useState<any>(null);const [me,setMe]=useState(false);const [calendar,setCalendar]=useState<any>(null);const [calendarLoading,setCalendarLoading]=useState(true);const load=()=>{setMe(false);api.metrics(campaign).then(setM).catch(()=>setMe(true))};useEffect(()=>{load()},[campaign]);useEffect(()=>{api.calendarUpcoming().then(setCalendar).catch(()=>setCalendar({status:'UNAVAILABLE',events:[]})).finally(()=>setCalendarLoading(false))},[]);const metrics=[['In Queue',m?.queue],['Attempted / Contacted',m?.attempted_or_contacted],['Replies',m?.replies],['Consultations',m?.consultations_set],['Booked',m?.booked],['Booked Revenue',m?`$${Number(m.booked_revenue||0).toFixed(2)}`:undefined]];return <><div className="hero"><div><p className="eyebrow">TODAY'S OPERATING VIEW</p><h2>Build momentum, one thoughtful conversation at a time.</h2><p className="muted">Your validated local campaign workspace.</p><p className="daily-quote">{dailyQuote()}</p><button className="continue-selling" onClick={()=>onNavigate?.("Up Next")}>Continue Selling</button><small className="eyebrow">DAILY SALES FOCUS</small></div><div className="date">READ-ONLY<br/><b>DRY RUN</b></div></div>{error&&<div className="notice">API unavailable. Start the local API to load campaign artifacts.</div>}<div className="metrics">{metrics.map(([l,v])=><div className="card metric" key={l}><span>{l}</span><strong>{me?'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â':v??'ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦'}</strong><small>{me?'Metrics unavailable':'From saved sales activity'}</small></div>)}</div><div className="grid"><div className="card"><h3>Today's Queue</h3>{data?<>
<div className="overview-queue-desktop">
  <QueueTable items={data.daily_queue}/>
</div>
<div className="overview-queue-mobile">
  {data.daily_queue.slice(0,3).map((x:any,i:number)=>
    <div className="overview-queue-card" key={x.prospect_id||x.lead_id||i}>
      <b>{x.business_name||x.name||x.business||'-'}</b>
      <div className="badges">
        <ScoreBadge value={x.score}/>
        <GradeBadge value={x.grade}/>
        <PriorityBadge value={x.priority}/>
        <RouteBadge value={x.route}/>
      </div>
      <small className="muted">{x.route_reason||''}</small>
    </div>
  )}
  <div className="actions">
    <button onClick={()=>onNavigate?.('Up Next')}>Continue Selling</button>
    <button onClick={()=>onNavigate?.('Daily Queue')}>View Full Queue</button>
  </div>
</div>
</>:<div className="empty small">Loading queueÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div>}</div><div><div className="card schedule"><div className="section-head"><h3>Today's Schedule</h3><button onClick={()=>{setCalendarLoading(true);api.calendarUpcoming().then(setCalendar).catch(()=>setCalendar({status:"UNAVAILABLE",events:[]})).finally(()=>setCalendarLoading(false))}}>Refresh</button></div>{calendarLoading?<div className="skeleton-list"><div className="skeleton"/><div className="skeleton"/></div>:calendar?.status==='UNAVAILABLE'||calendar?.status==='DISABLED'?<p className="muted">Calendar unavailable.</p>:calendar?.events?.length?calendar.events.map((e:any)=><div className="event" key={e.id}><b>{e.start||'-'}</b><span>{e.title||'Untitled event'}</span>{e.location&&<small>{e.location}</small>}{e.html_link&&<a href={e.html_link} target="_blank" rel="noreferrer">Open in Google Calendar</a>}</div>):<p className="muted">Your calendar is clear.</p>}</div><div className="card"><h3>Campaign Safety</h3><div className="status"><i/> Configuration validated<br/><i/> Dry Run ON<br/><i/> Automatic Network Actions OFF<br/><i/> HubSpot Writes OFF<br/><i/> Automatic Outbound OFF</div></div></div></div></>}function QueuePage({campaign}:{campaign:string}){const {data,error}=useQueue(campaign);const [batch,setBatch]=useState<any>(null);const [selected,setSelected]=useState<number[]>([]);const [confirmBatch,setConfirmBatch]=useState(false);const [running,setRunning]=useState(false);const [search,setSearch]=useState('');const [grade,setGrade]=useState('All');const [priority,setPriority]=useState('All');const [route,setRoute]=useState('All');const [sales,setSales]=useState('All');const [hubspot,setHubspot]=useState('All');const [category,setCategory]=useState('All');const [city,setCity]=useState('All');const [open,setOpen]=useState({DAILY_QUEUE:true,DEFERRED:false,RESEARCH:false,INELIGIBLE:false});if(error)return <div className="card empty"><h2>API unavailable</h2></div>;if(!data)return <div className="card empty">Loading queue...</div>;const all=[...data.daily_queue,...data.deferred,...data.research,...data.ineligible];const values=(k:string)=>Array.from(new Set(all.map((x:any)=>x[k]).filter(Boolean))).sort();const filtered=(items:any[])=>items.filter((x:any)=>{const n=(x.name||x.business||'').toLowerCase();const g=String(x.grade||'');return(!search||n.includes(search.toLowerCase()))&&(grade==='All'||(grade==='B'&&g==='B')||(grade==='C'&&g==='C')||(grade==='Reject'&&!['B','C'].includes(g)))&&(priority==='All'||x.priority===priority)&&(route==='All'||x.route===route)&&(sales==='All'||(x.sales_status||'NOT_CONTACTED')===sales)&&(hubspot==='All'||(hubspot==='Synced'?x.hubspot_sync_status==='SYNCED':hubspot==='Failed'?x.hubspot_sync_status==='SYNC_FAILED':hubspot==='Review Required'?x.hubspot_sync_status==='REVIEW_REQUIRED':x.hubspot_sync_status!=='SYNCED'))&&(category==='All'||x.category===category)&&(city==='All'||x.city===city)});const sections=[['DAILY_QUEUE',data.daily_queue,'Daily Queue'],['DEFERRED',data.deferred,'Deferred'],['RESEARCH',data.research,'Research'],['INELIGIBLE',data.ineligible,'Ineligible']];const reset=()=>{setSearch('');setGrade('All');setPriority('All');setRoute('All');setSales('All');setHubspot('All');setCategory('All');setCity('All')};const previewBatch=()=>api.batchPreview(campaign).then(x=>{setBatch(x);setSelected(x.selected_default||[]);setConfirmBatch(false)});const executeBatch=()=>{setRunning(true);api.batchSync({campaign,prospect_ids:selected,confirmed:true}).then(x=>setBatch({...batch,results:x.results,summary:x.summary})).finally(()=>{setRunning(false);setConfirmBatch(false)})};return <div className="queue-sections"><div className="card"><div className="filter"><input placeholder="Search businesses" value={search} onChange={e=>setSearch(e.target.value)}/><select value={grade} onChange={e=>setGrade(e.target.value)}><option>All</option><option value="B">B / Qualified</option><option value="C">C / Review</option><option value="Reject">Reject/Hold</option></select><select value={priority} onChange={e=>setPriority(e.target.value)}><option>All</option>{['P1','P2','P3'].map(x=><option key={x}>{x}</option>)}</select><select value={route} onChange={e=>setRoute(e.target.value)}><option>All</option>{values('route').map(x=><option key={x}>{x}</option>)}</select><select value={sales} onChange={e=>setSales(e.target.value)}><option>All</option>{['NOT_CONTACTED','ATTEMPTED','CONTACTED','REPLIED','CONSULTATION_SET','FOLLOW_UP','NOT_INTERESTED','BOOKED'].map(x=><option key={x}>{x}</option>)}</select><select value={category} onChange={e=>setCategory(e.target.value)}><option>All</option>{values('category').map(x=><option key={x}>{x}</option>)}</select><select value={city} onChange={e=>setCity(e.target.value)}><option>All</option>{values('city').map(x=><option key={x}>{x}</option>)}</select><button onClick={reset}>Reset Filters</button><button onClick={previewBatch} disabled={!data.daily_queue.length}>Sync Queue to HubSpot</button></div>{batch&&<div className="preview modal-enter"><h3>HubSpot Batch Preview</h3><p>Create New: {batch.counts?.CREATE_NEW||0} Ãƒâ€š |  Update Existing: {batch.counts?.UPDATE_EXISTING||0} Ãƒâ€š |  Review: {batch.counts?.REVIEW_REQUIRED||0}</p><button onClick={()=>setSelected(batch.selected_default||[])}>Select All Safe</button><button onClick={()=>setSelected([])}>Clear Selection</button>{!batch.results&&!confirmBatch&&<button disabled={!selected.length} onClick={()=>setConfirmBatch(true)}>Continue ({selected.length})</button>}{confirmBatch&&<div><p>Confirm HubSpot Batch Sync: {selected.length} selected.</p><button onClick={executeBatch} disabled={running}>{running?'Syncing...':'Confirm HubSpot Batch Sync'}</button><button onClick={()=>setConfirmBatch(false)}>Cancel</button></div>}{batch.results&&batch.results.map((r:any)=><p key={r.prospect_id}>{r.prospect_id}: {r.sync_status}</p>)}</div>}</div>{sections.map(([key,items,title])=>{const visible=filtered(items as any[]);const expanded=(open as any)[key as string];return <div className="card" key={key as string}><button className="section-toggle" onClick={()=>setOpen(x=>({...x,[key as string]:!expanded}))}>{expanded?'v':'>'} {title} ({visible.length} / {(items as any[]).length})</button>{expanded&&(visible.length?<QueueTable items={visible}/>:<p className="muted">No prospects match the current filters.</p>)}</div>})}</div>}
function Prospects({campaign}:{campaign:string}){const [data,setData]=useState<QueueItem[]|null>(null);const [error,setError]=useState(false);const [q,setQ]=useState('');const [selected,setSelected]=useState<QueueItem|null>(null);useEffect(()=>{setData(null);setError(false);api.prospects(campaign).then((response:any)=>setData(Array.isArray(response)?response:(Array.isArray(response?.prospects)?response.prospects:[]))).catch(()=>setError(true))},[campaign]);if(error)return <div className="card empty"><h2>API unavailable</h2></div>;const rows=(data||[]).filter(x=>(x.name||x.business||'').toLowerCase().includes(q.toLowerCase()));return <div className="prospects"><div className="card"><div className="filter"><input placeholder="Search businesses" value={q} onChange={e=>setQ(e.target.value)}/></div>{data===null?<div className="empty">Loading prospectsÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div>:<QueueTable items={rows} onSelect={setSelected}/>}</div>{selected&&<ProspectDrawer item={selected} onClose={()=>setSelected(null)}/>}</div>}
function ProspectDrawer({item,onClose,onNext,initialEmailOpen=false}:{item:QueueItem;onClose:()=>void;onNext?:()=>void;initialEmailOpen?:boolean}){const [status,setStatus]=useState((item as any).sales_status||'NOT_CONTACTED');const [notes,setNotes]=useState((item as any).notes||'');const [value,setValue]=useState((item as any).booked_value??'');const [saving,setSaving]=useState(false);const [message,setMessage]=useState('');const [crm,setCrm]=useState<any>(null);const [integrations,setIntegrations]=useState<any>(null);const [emailOpen,setEmailOpen]=useState(initialEmailOpen);const [calendarOpen,setCalendarOpen]=useState(false);const [subject,setSubject]=useState('KidProductionz Introduction');const [body,setBody]=useState('Hi, I would love to connect about content opportunities.');const [emailTo,setEmailTo]=useState(item.email||'');const [calendarTitle,setCalendarTitle]=useState(`KidProductionz Consultation  ${item.name||item.business||''}`);const [calendarStart,setCalendarStart]=useState('');const [calendarEnd,setCalendarEnd]=useState('');const [calendarTimezone,setCalendarTimezone]=useState('America/New_York');const [calendarLocation,setCalendarLocation]=useState('');const [calendarNotes,setCalendarNotes]=useState('');const [calendarAttendee,setCalendarAttendee]=useState(item.email||'');const [calendarPreview,setCalendarPreview]=useState<any>(null);const [integrationError,setIntegrationError]=useState('');const [preview,setPreview]=useState<any>(null);const [syncing,setSyncing]=useState(false);const [confirm,setConfirm]=useState(false);const statuses=['NOT_CONTACTED','ATTEMPTED','CONTACTED','REPLIED','CONSULTATION_SET','FOLLOW_UP','NOT_INTERESTED','BOOKED'];useEffect(()=>{api.hubspotStatus().then(setCrm).catch(()=>setCrm({writes_enabled:false}));api.integrations().then(setIntegrations).catch(()=>setIntegrations({}))},[]);const save=async(next=false)=>{if(!item.prospect_id){setMessage('Activity tracking unavailable for this prospect.');return}setSaving(true);setMessage('');try{await api.activity(item.prospect_id,{status,notes,booked_value:value===''?null:Number(value)});setMessage('Saved');if(next){if(onNext)onNext();else onClose()}}catch(e){setMessage('Could not save activity. Your changes remain here.')}finally{setSaving(false)}};const beginSync=()=>{setSyncing(true);api.previewSync(item).then(setPreview).catch(()=>setPreview({sync_status:'REVIEW',warnings:['Preview unavailable'],proposed_operations:[]})).finally(()=>setSyncing(false))};const doSync=()=>{setConfirm(false);setSyncing(true);api.sync({...item,confirmed:true}).then(r=>{setPreview(r);setMessage(r.sync_status==='SYNCED'?'HubSpot: Synced':'HubSpot sync failed')}).catch(()=>setMessage('HubSpot sync failed')).finally(()=>setSyncing(false))};const copy=()=>navigator.clipboard?.writeText(`Hey ${item.name||item.business||'there'}, IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢m Kayla with KidProductionz. I came across your brand and would love to share a couple content ideas if youÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢re open to it.`).then(()=>setMessage('Message copied'));return <div className="card drawer"><button onClick={onClose}>Close</button><h2>{item.name||item.business}</h2><p>Score {item.score??'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'} Ãƒâ€š |  {item.grade||'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'} Ãƒâ€š |  {item.route||'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}</p><h3>Sales Activity</h3><label>Sales Status<select value={status} onChange={e=>setStatus(e.target.value)}>{statuses.map(x=><option key={x}>{x}</option>)}</select></label><label>Notes<textarea value={notes} onChange={e=>setNotes(e.target.value)}/></label><label>Booked Value ($)<input type="number" min="0" step="0.01" value={value} onChange={e=>setValue(e.target.value)}/></label><div className="actions">{item.phone&&<a href={`tel:${item.phone}`}>Call</a>}{item.email&&<a href={`mailto:${item.email}`}>Email</a>}{item.social&&<a href={item.social} target="_blank" rel="noreferrer">Social</a>}{item.website&&<a href={item.website} target="_blank" rel="noreferrer">Website</a>}<button onClick={copy}>Copy Message</button></div><button onClick={()=>save(false)} disabled={saving||!item.prospect_id}>{saving?'SavingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦':'Save'}</button> <button onClick={()=>save(true)} disabled={saving||!item.prospect_id}>{saving?'SavingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦':'Save & Next'}</button>{message&&<p className="muted">{message}</p>}{integrationError&&<p className="notice">{integrationError}</p>}<h3>Actions</h3><div className="actions">{item.phone&&<a href={`tel:${item.phone}`} onClick={()=>api.logAction(item.prospect_id!,'CALL_OPENED')}>Call</a>}<button onClick={()=>{setEmailOpen(true);api.logAction(item.prospect_id!,'EMAIL_DRAFTED')}}>Draft Email</button>{item.website&&<a href={item.website} target="_blank" rel="noreferrer" onClick={()=>api.logAction(item.prospect_id!,'WEBSITE_OPENED')}>Website</a>}{item.social&&<a href={item.social} target="_blank" rel="noreferrer" onClick={()=>api.logAction(item.prospect_id!,'SOCIAL_OPENED')}>Social</a>}{integrations?.booking_url&&<><a href={integrations.booking_url} target="_blank" rel="noreferrer">Open Booking Link</a><button onClick={()=>navigator.clipboard?.writeText(integrations.booking_url).then(()=>api.logAction(item.prospect_id!,'BOOKING_LINK_COPIED'))}>Copy Booking Link</button></>}<button onClick={()=>setCalendarOpen(true)}>Schedule Consultation</button></div>{calendarOpen&&<div className="preview modal-enter"><label>Title<input value={calendarTitle} onChange={e=>{setCalendarTitle(e.target.value);setCalendarPreview(null)}}/></label><label>Start<input type="datetime-local" value={calendarStart} onChange={e=>{setCalendarStart(e.target.value);setCalendarPreview(null)}}/></label><label>End<input type="datetime-local" value={calendarEnd} onChange={e=>{setCalendarEnd(e.target.value);setCalendarPreview(null)}}/></label><label>Duration (minutes)<input type="number" min="15" defaultValue="30"/></label><label>Timezone<input value={calendarTimezone} onChange={e=>setCalendarTimezone(e.target.value)}/></label><label>Location<input value={calendarLocation} onChange={e=>setCalendarLocation(e.target.value)}/></label><label>Notes<textarea value={calendarNotes} onChange={e=>setCalendarNotes(e.target.value)}/></label><label>Attendee email<input value={calendarAttendee} onChange={e=>setCalendarAttendee(e.target.value)}/></label><button onClick={()=>{if(!calendarTitle||!calendarStart||!calendarEnd||calendarEnd<=calendarStart){setIntegrationError('Enter a valid title, start, and end time.');return}api.calendarPreview({prospect_id:item.prospect_id,title:calendarTitle,consultation_start:calendarStart,consultation_end:calendarEnd,timezone:calendarTimezone,location:calendarLocation,notes:calendarNotes,attendee_email:calendarAttendee,confirmed:false}).then(x=>{setCalendarPreview(x);setIntegrationError('')}).catch(e=>{console.error(e);setIntegrationError('Calendar preview failed: '+(e.message||'Unable to preview'))})}}>Preview</button>{calendarPreview&&<><p>Preview ready: {calendarPreview.title||calendarTitle}</p><button onClick={()=>api.calendarCreate({prospect_id:item.prospect_id,title:calendarTitle,consultation_start:calendarStart,consultation_end:calendarEnd,timezone:calendarTimezone,location:calendarLocation,notes:calendarNotes,attendee_email:calendarAttendee,confirmed:true}).then(x=>{setCalendarOpen(false);setMessage('Consultation Scheduled');if(x.event_url)setIntegrationError('Event created: '+x.event_url)}).catch(e=>{console.error(e);setIntegrationError('Calendar creation failed: '+(e.message||'Unable to create'))})}>Confirm Create Event</button></>}<button onClick={()=>setCalendarOpen(false)}>Cancel</button></div>}{emailOpen&&<div className="preview modal-enter"><label>Recipient email<input value={emailTo} onChange={e=>setEmailTo(e.target.value)} /></label><input value={subject} onChange={e=>setSubject(e.target.value)}/><textarea value={body} onChange={e=>setBody(e.target.value)}/><button disabled={!emailTo.trim()} onClick={()=>api.gmailSend({prospect_id:item.prospect_id,to:emailTo,subject,body,confirmed:true}).then(()=>{setEmailOpen(false);setMessage('Email sent')}).catch(e=>{console.error(e);setIntegrationError('Email failed: '+(e.message||'Unable to send'))})}>Confirm Send</button><button onClick={()=>setEmailOpen(false)}>Cancel</button></div>}<h3>HubSpot</h3><p>Association verified: {String((item as any).association_verified??preview?.association_verified??false)}</p><p>Last synced: {(item as any).last_synced_at||''}</p><p>Last warning/error: {(item as any).last_sync_error||''}</p><p>Status: {preview?.sync_status==='SYNCED'?'Synced':preview?.sync_status||((item as any).hubspot_sync_status||'Not synced')}</p>{preview?.hubspot_contact_id&&<p>Contact ID: {preview.hubspot_contact_id} {integrations?.hubspot_portal_id&&<a href={`https://app.hubspot.com/contacts/${integrations.hubspot_portal_id}/contact/${preview.hubspot_contact_id}`} target="_blank" rel="noreferrer" onClick={()=>api.logAction(item.prospect_id!,'HUBSPOT_OPENED')}>Open Contact</a>}</p>}{preview?.hubspot_deal_id&&<p>Deal ID: {preview.hubspot_deal_id} {integrations?.hubspot_portal_id&&<a href={`https://app.hubspot.com/contacts/${integrations.hubspot_portal_id}/deal/${preview.hubspot_deal_id}`} target="_blank" rel="noreferrer" onClick={()=>api.logAction(item.prospect_id!,'HUBSPOT_OPENED')}>Open Deal</a>}</p>}{crm?.writes_enabled&&item.prospect_id?<button onClick={beginSync} disabled={syncing}>{syncing?'LoadingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦':'Sync to HubSpot'}</button>:<p className="muted">HubSpot sync is currently disabled.</p>}{preview&&preview.sync_status!=='SYNCED'&&crm?.writes_enabled&&<div className="preview modal-enter"><p>Planned action: {preview.proposed_operations?.join(', ')||preview.sync_status}</p><button onClick={()=>setConfirm(true)}>Confirm HubSpot Sync</button><button onClick={()=>setPreview(null)}>Cancel</button></div>}{confirm&&<div className="preview modal-enter"><p>Confirm this HubSpot sync?</p><button onClick={doSync}>Confirm HubSpot Sync</button><button onClick={()=>setConfirm(false)}>Cancel</button></div>}</div>}function Campaigns({campaign,onChanged,onSelect}:{campaign:string;onChanged?:()=>void;onSelect?:(id:string)=>void}){const [items,setItems]=useState<any[]|null>(null);const [upload,setUpload]=useState<any>(null);const [sheet,setSheet]=useState('');const [preview,setPreview]=useState<any>(null);const [exec,setExec]=useState(false);const [confirmRun,setConfirmRun]=useState(false);const [editing,setEditing]=useState<any>(null);const [form,setForm]=useState<any>({name:'',campaign_id:'',city:'',state:'',category:'',description:'',daily_queue_limit:50,status:'ACTIVE'});const refresh=()=>api.campaigns().then((x:any)=>{const rows=Array.isArray(x)?x:(x.campaigns||[]);setItems(rows);return rows}).catch(()=>{setItems([]);return []});useEffect(()=>{refresh();api.hubspotStatus().then(x=>setExec(Boolean(x.campaign_execution_enabled))).catch(()=>setExec(false))},[]);useEffect(()=>{setUpload(null);setPreview(null);setSheet('')},[campaign]);const slug=(v:string)=>v.toLowerCase().trim().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');const openCreate=()=>{setEditing({});setForm({name:'',campaign_id:'',city:'',state:'',category:'',description:'',daily_queue_limit:50,status:'ACTIVE'})};const openEdit=(c:any)=>{setEditing(c);setForm({...c,daily_queue_limit:c.daily_queue_limit||50,status:c.status||'ACTIVE'})};const save=async()=>{if(!form.name||!form.city||!form.state||!form.category){return}const body={...form,campaign_id:form.campaign_id||slug(form.name),daily_queue_limit:Number(form.daily_queue_limit)||50};try{if(editing?.campaign_id)await api.campaignUpdate(editing.campaign_id,body);else await api.campaignCreate(body);setEditing(null);await refresh();onChanged?.()}catch(e){setItems(x=>x||[])}};const remove=async(c:any)=>{
  if((items||[]).length<=1){
    window.alert('At least one campaign is required.');
    return;
  }

  const name=c.name||c.campaign_id;

  const confirmed=window.confirm(
    `Permanently delete "${name}" and all of its prospect, activity, CRM, email, calendar, queue, and run data? This cannot be undone.`
  );

  if(!confirmed)return;

  try{
    await api.campaignDelete(c.campaign_id);
    const rows=await refresh();
    onChanged?.();

    if(c.campaign_id===campaign && rows.length){
      onSelect?.(rows[0].campaign_id);
    }
  }catch(e:any){
    window.alert(e?.message||'Could not delete campaign.');
  }
};if(items===null)return <div className="card empty">Loading campaignsÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div>;const selected=items.find(c=>c.campaign_id===campaign)||items[0];return <div className="campaign-grid"><div className="section-head"><h2>Campaigns</h2><button onClick={openCreate}>+ New Campaign</button></div>{editing&&<div className="card preview modal-enter"><h3>{editing.campaign_id?'Edit Campaign':'New Campaign'}</h3>{[['name','Campaign Name'],['campaign_id','Campaign ID'],['city','City'],['state','State'],['category','Primary Category / Niche']].map(([k,l])=><label key={k}>{l}<input value={form[k]||''} onChange={e=>setForm({...form,[k]:e.target.value})} onBlur={()=>k==='name'&&!form.campaign_id&&setForm({...form,campaign_id:slug(form.name)})}/></label>)}<label>Description<textarea value={form.description||''} onChange={e=>setForm({...form,description:e.target.value})}/></label><label>Daily Queue Limit<input type="number" min="1" value={form.daily_queue_limit} onChange={e=>setForm({...form,daily_queue_limit:e.target.value})}/></label><label>Status<select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option>ACTIVE</option><option>PAUSED</option><option>ARCHIVED</option></select></label><button onClick={save}>Save Campaign</button><button onClick={()=>setEditing(null)}>Cancel</button></div>}{items.map(c=><div className="card campaign" key={c.campaign_id}><p className="eyebrow">CAMPAIGN</p><h2>{c.name||c.campaign_id}</h2><p className="muted">Market: {c.city||c.market?.city||'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}{c.state?`, ${c.state}`:''}</p><p>{c.category||'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'} Ãƒâ€š |  <span className="badge">{c.status||'ACTIVE'}</span></p><p className="muted">Last Run: {c.last_run||'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'} Ãƒâ€š |  Current Queue Count: {c.queue_count??'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}</p><button onClick={()=>onSelect?.(c.campaign_id)}>Open</button><button onClick={()=>openEdit(c)}>Edit</button><button onClick={async()=>{await api.campaignUpdate(c.campaign_id,{status:c.status==='PAUSED'?'ACTIVE':'PAUSED'});refresh();onChanged?.()}}>{c.status==='PAUSED'?'Resume':'Pause'}</button><button onClick={async()=>{await api.campaignUpdate(c.campaign_id,{status:'ARCHIVED'});refresh();onChanged?.()}}>Archive</button><button onClick={()=>remove(c)} disabled={(items||[]).length<=1}>Delete</button></div>)}{selected&&<div className="card campaign"><h3>{selected.name||selected.campaign_id} Run</h3>{!upload&&<p className="muted">No leads have been uploaded for this campaign yet.</p>}<input type="file" accept=".csv,.xlsx" onChange={e=>{const f=e.target.files?.[0];setPreview(null);setSheet('');if(f)uploadCampaign(f).then(x=>{setUpload(x);if(x.sheets?.length===1)setSheet(x.sheets[0])}).catch(()=>setUpload({error:'Upload failed'}))}}/>{upload&&!upload.error&&<p className="muted">{upload.filename} Ãƒâ€š |  {upload.file_type} Ãƒâ€š |  {upload.size} bytes</p>}{upload?.sheets?.length>1&&<select value={sheet} onChange={e=>setSheet(e.target.value)}><option value="">Choose worksheet</option>{upload.sheets.map((s:string)=><option key={s}>{s}</option>)}</select>}<button onClick={()=>campaignApi.preview({campaign:selected.campaign_id,input_file:upload.reference,sheet:sheet||null,dry_run:true}).then(setPreview)} disabled={!upload?.reference||Boolean(upload.sheets?.length>1&&!sheet)}>Preview Run</button>{!selected&&<p className="muted">No leads have been uploaded for this campaign yet.</p>}{preview&&<div className="preview modal-enter"><p>Queue limit: {preview.queue_limit} Ãƒâ€š |  Dry Run: Yes</p>{exec?<><button onClick={()=>setConfirmRun(true)}>Run Campaign</button>{confirmRun&&<button onClick={()=>campaignApi.run({campaign:selected.campaign_id,input_file:upload.reference,sheet:sheet||null,dry_run:true,confirmed:true}).then(setPreview)}>Confirm Run</button>}</>:<p className="muted">Campaign execution is currently disabled.</p>}</div>}</div>}</div>}
function Runs(){const [items,setItems]=useState<any[]|null>(null);useEffect(()=>{api.runs().then(setItems).catch(()=>setItems([]))},[]);return <div className="queue-sections">{items===null?<div className="card empty">Loading runsÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div>:!items.length?<div className="card empty">No run manifests available.</div>:items.map((r,i)=><div className="card" key={i}><h3>{r.campaign_id}</h3><span className="badge">{r.overall_status}</span><p className="muted">Daily Queue: {r.daily_queue_summary?.daily_queue_count??'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'} Ãƒâ€š |  Deferred: {r.daily_queue_summary?.deferred_count??'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}</p></div>)}</div>}
function Settings({campaign}:{campaign:string}){const [i,setI]=useState<any>(null);const [hs,setHs]=useState<any>(null);const [bk,setBk]=useState<any>(null);const [modal,setModal]=useState('');const [msg,setMsg]=useState('');const [hf,setHf]=useState<any>({access_token:'',portal_id:'',pipeline_id:'',stage_id:'',write_enabled:false});const [bf,setBf]=useState<any>({provider:'',booking_url:'',default_duration:30,default_title:''});const load=()=>{api.integrations().then(setI).catch(()=>setI({}));api.hubspotSettings().then((x:any)=>{setHs(x);setHf((f:any)=>({...f,...x,access_token:''}))}).catch(()=>setHs(null));api.bookingSettings().then((x:any)=>{setBk(x);setBf(x)}).catch(()=>setBk(null))};useEffect(load,[]);const saveH=async()=>{try{await api.saveHubspotSettings(hf);setMsg('HubSpot configuration saved.');setModal('');load()}catch{setMsg('Could not save HubSpot configuration.')}};const saveB=async()=>{if(bf.booking_url&&!/^https?:\/\//i.test(bf.booking_url)){setMsg('Enter a valid http or https booking URL.');return}try{await api.saveBookingSettings({...bf,default_duration:Number(bf.default_duration)});setMsg('Booking configuration saved.');setModal('');load()}catch{setMsg('Could not save booking configuration.')}};return <div className="grid"><div className="card"><h3>Campaign Configuration</h3><p>Selected campaign: <b>{campaign}</b></p></div><div className="card"><h3>HubSpot</h3><p>{hs===null?'Connection error':hs?.configured?'Configured':'Not configured'}</p>{hs?.token_present&&<p className="muted">Access token saved</p>}<button onClick={()=>setModal('hubspot')}>Configure HubSpot</button>{modal==='hubspot'&&<div className="preview modal-enter"><label>Access Token<input type="password" placeholder={hs?.token_present?'ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢':''} value={hf.access_token} onChange={e=>setHf({...hf,access_token:e.target.value})}/></label><label>Portal ID<input value={hf.portal_id||''} onChange={e=>setHf({...hf,portal_id:e.target.value})}/></label><label>Pipeline ID<input value={hf.pipeline_id||''} onChange={e=>setHf({...hf,pipeline_id:e.target.value})}/></label><label>Stage ID<input value={hf.stage_id||''} onChange={e=>setHf({...hf,stage_id:e.target.value})}/></label><label><input type="checkbox" checked={!!hf.write_enabled} onChange={e=>setHf({...hf,write_enabled:e.target.checked})}/> Write Enabled</label><button onClick={()=>api.hubspotSettingsTest().then(()=>setMsg('Read-only connection test passed.')).catch(()=>setMsg('Connection test failed.'))}>Test Connection</button><button onClick={saveH}>Save Configuration</button><button onClick={()=>setModal('')}>Cancel</button></div>}</div><div className="card"><h3>Booking</h3><p>{bk?.configured?'Configured':'Not configured'}{bk?.provider&&` Ãƒâ€š |  ${bk.provider}`}</p><button onClick={()=>setModal('booking')}>Configure Booking</button>{modal==='booking'&&<div className="preview modal-enter"><label>Provider / Label<input value={bf.provider||''} onChange={e=>setBf({...bf,provider:e.target.value})}/></label><label>Booking URL<input value={bf.booking_url||''} onChange={e=>setBf({...bf,booking_url:e.target.value})}/></label><label>Default Consultation Duration<input type="number" min="1" value={bf.default_duration||30} onChange={e=>setBf({...bf,default_duration:e.target.value})}/></label><label>Default Meeting Title<input value={bf.default_title||''} onChange={e=>setBf({...bf,default_title:e.target.value})}/></label><button onClick={saveB}>Save Configuration</button><button onClick={()=>setModal('')}>Cancel</button></div>}</div><div className="card"><h3>Google</h3><p>Google: {i?.google_status||'NOT_CONNECTED'}</p><p>Gmail: {i?.gmail_enabled?'Enabled':'Disabled'}  |  Calendar: {i?.calendar_enabled?'Enabled':'Disabled'}</p>{i?.google_status!=='CONNECTED'&&<button onClick={async()=>{try{const r=await fetch('/api/google/oauth/start',{credentials:'include'});if(!r.ok)throw new Error();const d=await r.json();window.location.href=d.authorization_url}catch{setMsg('Could not start Google connection.')}}}>Connect to Google</button>}{i?.google_status==='CONNECTED'&&<>
<p className="muted">Google account connected.</p>
<button onClick={async()=>{
  try{
    await api.googleDisconnect();
    setMsg('Google disconnected.');
    load();
  }catch{
    setMsg('Could not disconnect Google.');
  }
}}>Disconnect Google</button>
</>}</div>{msg&&<div className="notice">{msg}</div>}</div>}
function AuthGate(){const [state,setState]=useState<any>(null);const [user,setUser]=useState('');const [password,setPassword]=useState('');const [error,setError]=useState('');useEffect(()=>{authApi.me().then(data=>setState({authenticated:data.authenticated===true})).catch(()=>setState({authenticated:false}))},[]);if(!state)return <div className="card empty">LoadingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div>;if(state.authenticated===true)return <App/>;const login=async(e:any)=>{e.preventDefault();try{await authApi.login(user,password);const data=await authApi.me();if(data.authenticated===true)setState(data);else setError('Unable to authenticate')}catch{setError('Invalid credentials')}};return <main className="auth-screen"><form className="card" onSubmit={login}><img src={logo} /><h1>KidProductionz Sales OS</h1><p className="muted">Sign in to continue.</p><input aria-label="Username" value={user} onChange={e=>setUser(e.target.value)} placeholder="Username"/><input aria-label="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password"/>{error&&<p className="notice">{error}</p>}<button type="submit">Sign in</button></form></main>}
createRoot(root).render(<AuthGate/>);


