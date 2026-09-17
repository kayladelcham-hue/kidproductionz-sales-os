import React,{useEffect,useState} from 'react'; import {createRoot} from 'react-dom/client'; import './styles.css'; import {api,campaignApi,uploadCampaign,authApi,Queue,QueueItem} from './api';
import logo from './assets/kidproductionz-logo.png'; import {ScoreBadge,GradeBadge,RouteBadge,PriorityBadge,StatusBadge} from './badges'; import {dailyQuote} from './data/salesQuotes';
const nav=['Overview','Up Next','Lead Generator','Daily Queue','Prospects','Campaigns','Runs','Settings'];

const prettyLabel=(value:any)=>{
  const raw=String(value??'').trim();
  if(!raw)return '';
  return raw
    .replace(/_/g,' ')
    .replace(/\b\w/g,c=>c.toUpperCase());
};

function ScheduleWhen({value}:{value:any}){
  const raw=String(value||'').trim();

  if(!raw){
    return <div className="event-when"><span className="event-day">Schedule</span><span className="event-time">TBD</span></div>;
  }

  const d=new Date(raw);

  if(Number.isNaN(d.getTime())){
    return <div className="event-when"><span className="event-time">{raw}</span></div>;
  }

  const day=d.toLocaleDateString(undefined,{
    weekday:'short',
    month:'short',
    day:'numeric'
  });

  const time=d.toLocaleTimeString(undefined,{
    hour:'numeric',
    minute:'2-digit'
  });

  return <div className="event-when">
    <span className="event-day">{day}</span>
    <span className="event-time">{time}</span>
  </div>;
}

function UpNext({campaign}:{campaign:string}){
  const {data,error}=useQueue(campaign);
  const [idx,setIdx]=useState(0);
  const [selected,setSelected]=useState<any>(null);
  const [openEmail,setOpenEmail]=useState(false);
  const [lastAction,setLastAction]=useState<any>(null);
  const [undoing,setUndoing]=useState(false);
  const [deferredIds,setDeferredIds]=useState<number[]>([]);

  useEffect(()=>{
    setIdx(0);
    setSelected(null);
    setOpenEmail(false);
    setLastAction(null);
  },[campaign]);

  const items=((data?.daily_queue||[]) as any[])
    .map((x:any,i:number)=>({...x,__i:i}))
    .filter((x:any)=>!['BOOKED','NOT_INTERESTED','FOLLOW_UP'].includes(x.sales_status)&&!deferredIds.includes(x.prospect_id))
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

  const moveLater=async()=>{
    if(!current?.prospect_id)return;
    try{
      await api.defer(current.prospect_id);
      setDeferredIds(x=>[...x,current.prospect_id]);
    }catch{}
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


function LeadGenerator({campaign,onNavigate}:{campaign:string;onNavigate?:(page:string)=>void}){
  const [businessType,setBusinessType]=useState('Hair salons');
  const [city,setCity]=useState('');
  const [state,setState]=useState('');
  const [limit,setLimit]=useState(10);
  const [loading,setLoading]=useState(false);
  const [saving,setSaving]=useState(false);
  const [preview,setPreview]=useState<any>(null);
  const [result,setResult]=useState<any>(null);
  const [error,setError]=useState('');

  const states=[
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID',
    'IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS',
    'MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK',
    'OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV',
    'WI','WY','DC'
  ];

  const query=
    businessType.trim()&&city.trim()&&state
      ? `${businessType.trim()} in ${city.trim()}, ${state}`
      : '';

  const generate=async()=>{
    if(!query||!campaign||loading)return;

    setLoading(true);
    setError('');
    setPreview(null);
    setResult(null);

    try{
      const data=await api.outscraperQualifyPreview({
        campaign,
        query,
        limit:Math.max(1,Math.min(100,Number(limit)||10)),
        category:businessType.trim(),
        city:city.trim(),
        state
      });

      setPreview(data);
    }catch(e:any){
      setError(e?.message||'Lead qualification failed.');
    }finally{
      setLoading(false);
    }
  };

  const qualified=[
    ...((preview?.daily_queue||[]) as any[]),
    ...((preview?.deferred||[]) as any[])
  ];

  const research=(preview?.research||[]) as any[];
  const rejected=(preview?.ineligible||[]) as any[];

  const previewSource=preview?.source_summary||{};

  const confirmAdd=async()=>{
    if(!query||!campaign||saving||!preview||qualified.length===0)return;

    setSaving(true);
    setError('');

    try{
      const data=await api.outscraperGenerate({
        campaign,
        query,
        limit:Math.max(1,Math.min(100,Number(limit)||10)),
        category:businessType.trim(),
        city:city.trim(),
        state,
        confirmed:true
      });

      setResult(data);
      setPreview(null);
    }catch(e:any){
      setError(e?.message||'Could not add leads to Sales OS.');
    }finally{
      setSaving(false);
    }
  };

  const summary=result?.summary||{};

  return <div className="kp-lead-generator">

    <div className="hero">
      <div>
        <p className="eyebrow">PROSPECTING ENGINE</p>
        <h2>Generate qualified leads.</h2>
        <p className="muted">
          Search any U.S. city, qualify prospects, remove duplicates,
          and save new leads directly into Sales OS.
        </p>
      </div>
    </div>

    <div className="card kp-generator-card">

      <div className="kp-generator-campaign">
        <small className="eyebrow">ACTIVE CAMPAIGN</small>
        <b>{prettyLabel(campaign)}</b>
      </div>

      <div className="kp-generator-fields">

        <label>
          <span>Business Type</span>
          <input
            value={businessType}
            disabled={loading||saving||!!preview}
            placeholder="Hair salons"
            onChange={e=>setBusinessType(e.target.value)}
          />
        </label>

        <label>
          <span>City</span>
          <input
            value={city}
            disabled={loading||saving||!!preview}
            placeholder="Atlanta"
            onChange={e=>setCity(e.target.value)}
          />
        </label>

        <label>
          <span>State</span>
          <select
            value={state}
            disabled={loading||saving||!!preview}
            onChange={e=>setState(e.target.value)}
          >
            <option value="">Select state</option>
            {states.map(x=><option key={x} value={x}>{x}</option>)}
          </select>
        </label>

        <label>
          <span>Lead Count</span>
          <input
            type="number"
            min="1"
            max="100"
            value={limit}
            disabled={loading||saving||!!preview}
            onChange={e=>setLimit(Number(e.target.value))}
          />
        </label>

      </div>

      <div className="kp-generator-search">
        <small className="eyebrow">SEARCH</small>
        <b>{query||'Complete the fields above'}</b>
      </div>

      {!preview&&!result&&
        <button
          className="continue-selling kp-generate-button"
          disabled={!query||loading}
          onClick={generate}
        >
          {loading?'Generating & Qualifying...':'Generate & Qualify Leads'}
        </button>
      }

      <p className="muted kp-generator-note">
        Nothing is added until you confirm. No calls or emails are sent automatically.
      </p>

      {error&&<div className="notice">{error}</div>}

    </div>

    {preview&&<div className="kp-generator-results">

      <div className="card">
        <p className="eyebrow">QUALIFICATION PREVIEW</p>
        <h3>Review before adding leads</h3>

        <div className="kp-generator-stats">
          <div>
            <b>{previewSource.received??qualified.length+research.length+rejected.length}</b>
            <span>Found</span>
          </div>

          <div>
            <b>{qualified.length}</b>
            <span>Qualified</span>
          </div>

          <div>
            <b>{research.length}</b>
            <span>Research</span>
          </div>

          <div>
            <b>{rejected.length}</b>
            <span>Rejected</span>
          </div>
        </div>
      </div>

      {qualified.length>0&&
        <div className="card">
          <p className="eyebrow">READY TO ADD</p>
          <h3>{qualified.length} qualified lead{qualified.length===1?'':'s'}</h3>

          <div className="kp-generator-leads">
            {qualified.map((x:any,i:number)=>
              <div
                className="kp-generator-lead"
                key={x.prospect_id||x.lead_id||x.place_id||x.google_id||`${x.name}-${i}`}
              >
                <div>
                  <b>{x.business_name||x.name||x.business||'Prospect'}</b>
                  <small>{x.queue_status||x.queue||'QUALIFIED'}</small>
                </div>

                <strong>{x.score??'-'}</strong>
              </div>
            )}
          </div>
        </div>
      }

      {research.length>0&&
        <div className="card">
          <p className="eyebrow">RESEARCH</p>
          <h3>{research.length} need more information</h3>
          <p className="muted">
            These are shown for transparency and will not be added.
          </p>
        </div>
      }

      {rejected.length>0&&
        <div className="card">
          <p className="eyebrow">NOT QUALIFIED</p>
          <h3>{rejected.length} rejected</h3>
          <p className="muted">
            These will not be added to Sales OS.
          </p>
        </div>
      }

      <div className="card kp-final-confirm">
        <p className="eyebrow">FINAL CONFIRMATION</p>

        <h3>
          Add {qualified.length} qualified lead{qualified.length===1?'':'s'} to Sales OS?
        </h3>

        <p className="muted">
          Existing prospects will still be removed by database deduplication before saving.
        </p>

        <div className="kp-confirm-actions">
          <button
            type="button"
            disabled={saving}
            onClick={()=>setPreview(null)}
          >
            Cancel
          </button>

          <button
            type="button"
            className="continue-selling"
            disabled={saving||qualified.length===0}
            onClick={confirmAdd}
          >
            {saving
              ? 'Adding Leads...'
              : `Add ${qualified.length} Lead${qualified.length===1?'':'s'}`
            }
          </button>
        </div>
      </div>

    </div>}

    {result&&<div className="kp-generator-results">

      <div className="card">
        <p className="eyebrow">GENERATION COMPLETE</p>
        <h3>{summary.saved??0} new leads added</h3>

        <div className="kp-generator-stats">
          <div><b>{summary.generated??0}</b><span>Found</span></div>
          <div><b>{summary.database_duplicates??0}</b><span>Existing</span></div>
          <div><b>{summary.saved??0}</b><span>New</span></div>
          <div><b>{summary.qualified??0}</b><span>Qualified</span></div>
          <div><b>{summary.research??0}</b><span>Research</span></div>
          <div><b>{summary.rejected??0}</b><span>Rejected</span></div>
        </div>
      </div>

      {Array.isArray(result.saved)&&result.saved.length>0&&
        <div className="card">
          <div className="kp-generator-result-head">
            <div>
              <p className="eyebrow">NEW PROSPECTS</p>
              <h3>{result.saved.length} saved</h3>
            </div>

            <div className="kp-confirm-actions">
              <button onClick={()=>{
                setResult(null);
                setPreview(null);
              }}>
                Generate More
              </button>

              <button onClick={()=>onNavigate?.('Prospects')}>
                View Prospects
              </button>
            </div>
          </div>

          <div className="kp-generator-leads">
            {result.saved.map((x:any)=>
              <div className="kp-generator-lead" key={x.id}>
                <div>
                  <b>{x.name}</b>
                  <small>{x.queue||'PROSPECT'}</small>
                </div>
                <strong>{x.score??'-'}</strong>
              </div>
            )}
          </div>
        </div>
      }

      {Array.isArray(result.duplicates)&&result.duplicates.length>0&&
        <div className="card">
          <p className="eyebrow">DUPLICATES SKIPPED</p>
          <h3>{result.duplicates.length} already in Sales OS</h3>
        </div>
      }

    </div>}

  </div>
}

function App(){const [page,setPage]=useState('Overview');const [mobileMenuOpen,setMobileMenuOpen]=useState(false);const [campaign,setCampaign]=useState('orlando_beauty');const [campaigns,setCampaigns]=useState<any[]>([]);const loadCampaigns=()=>api.campaigns().then((x:any)=>{const rows=Array.isArray(x)?x:(x.campaigns||[]);setCampaigns(rows);if(rows.length&&!rows.some(c=>c.campaign_id===campaign))setCampaign(rows[0].campaign_id)}).catch(()=>setCampaigns([]));useEffect(()=>{loadCampaigns()},[]);return <div className="shell"><aside><div className="brand"><img src={logo}/><div><b>KidProductionz</b><small>Sales OS</small></div></div><nav>{nav.map(n=><button key={n} className={page===n?'active':''} onClick={()=>setPage(n)}>{n}</button>)}</nav><div className="safe"><span/>System Ready</div></aside><main><header><button className="mobile-menu-btn" aria-label="Open navigation" aria-expanded={mobileMenuOpen} onClick={()=>setMobileMenuOpen(true)}>â˜°</button><div><p className="eyebrow">KIDPRODUCTIONZ SALES OS</p><h1>{page}</h1></div><select value={campaign} onChange={e=>setCampaign(e.target.value)}>{campaigns.map(c=><option key={c.campaign_id} value={c.campaign_id}>{c.name||c.campaign_id}</option>)}</select></header>{page==='Overview'?<Overview campaign={campaign} onNavigate={setPage}/>:page==='Daily Queue'?<QueuePage campaign={campaign}/>:page==='Up Next'?<UpNext campaign={campaign}/>:page==='Lead Generator'?<LeadGenerator campaign={campaign} onNavigate={setPage}/>:page==='Prospects'?<Prospects campaign={campaign}/>:page==='Campaigns'?<Campaigns campaign={campaign} onChanged={loadCampaigns} onSelect={setCampaign}/>:page==='Runs'?<Runs/>:<Settings campaign={campaign}/>}{mobileMenuOpen&&<><div className="mobile-menu-backdrop" onClick={()=>setMobileMenuOpen(false)}/><aside className="mobile-menu-drawer"><button aria-label="Close navigation" className="mobile-menu-close" onClick={()=>setMobileMenuOpen(false)}>Ã—</button>{["Overview","Up Next","Lead Generator","Daily Queue","Prospects","Campaigns","Runs","Settings"].map(n=><button key={n} onClick={()=>{setPage(n);setMobileMenuOpen(false)}}>{n}</button>)}</aside></>} </main><div className="bottom-nav">{[["Home","Overview"],["Up Next","Up Next"],["Queue","Daily Queue"],["Prospects","Prospects"],["More","Settings"]].map(([l,v])=><button key={l} onClick={()=>setPage(v)}>{l}</button>)}</div></div>}
function useQueue(campaign:string){const [data,setData]=useState<Queue|null>(null);const [error,setError]=useState(false);useEffect(()=>{setData(null);setError(false);api.queue(campaign).then(setData).catch(()=>setError(true))},[campaign]);return {data,error}}
function QueueTable({items,onSelect}:{items:QueueItem[];onSelect?:(item:QueueItem)=>void}){return <div className="table-wrap"><table><thead><tr><th>Position</th><th>Business</th><th>Score</th><th>Grade</th><th>Route</th><th>Priority</th><th>Reason</th></tr></thead><tbody>{(items||[]).map((x:any,i:number)=><tr key={x.prospect_id||x.lead_id||x.fixture_id||i} onClick={()=>onSelect?.(x)}><td>{x.queue_position??i+1}</td><td><b>{x.business_name||x.name||x.business||'-'}</b></td><td><ScoreBadge value={x.score}/></td><td><GradeBadge value={x.grade}/></td><td><RouteBadge value={x.route}/></td><td><PriorityBadge value={x.priority}/></td><td>{x.route_reason||'-'}</td></tr>)}</tbody></table></div>}
function Overview({campaign,onNavigate}:{campaign:string;onNavigate?:(p:string)=>void}){const [mobileQueueIndex,setMobileQueueIndex]=useState(0);const {data,error}=useQueue(campaign);const [m,setM]=useState<any>(null);const [me,setMe]=useState(false);const [calendar,setCalendar]=useState<any>(null);const [calendarLoading,setCalendarLoading]=useState(true);const load=()=>{setMe(false);api.metrics(campaign).then(setM).catch(()=>setMe(true))};useEffect(()=>{setMobileQueueIndex(0)},[campaign]);useEffect(()=>{load()},[campaign]);useEffect(()=>{api.calendarUpcoming().then(setCalendar).catch(()=>setCalendar({status:'UNAVAILABLE',events:[]})).finally(()=>setCalendarLoading(false))},[]);const metrics=[['In Queue',m?.queue],['Attempted / Contacted',m?.attempted_or_contacted],['Replies',m?.replies],['Consultations',m?.consultations_set],['Booked',m?.booked],['Booked Revenue',m?`$${Number(m.booked_revenue||0).toFixed(2)}`:undefined]];return <><div className="hero"><div><p className="eyebrow">TODAY'S SALES VIEW</p><h2>Turn today's pipeline into conversations.</h2><p className="muted">Your priority prospects, activity, and opportunities in one place.</p><p className="daily-quote">{dailyQuote()}</p><div className="overview-actions"><button className="continue-selling" onClick={()=>onNavigate?.("Up Next")}>Continue Selling</button><button className="continue-selling overview-lead-generator" onClick={()=>onNavigate?.("Lead Generator")}>Generate Leads</button></div><small className="eyebrow">TODAY'S FOCUS</small></div><div className="date">READ-ONLY<br/><b>DRY RUN</b></div></div>{error&&<div className="notice">API unavailable. Start the local API to load campaign artifacts.</div>}<div className="metrics">{metrics.map(([l,v])=><div className="card metric" key={l}><span>{l}</span><strong>{me?'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â':v??'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦'}</strong><small>{me?'Metrics unavailable':'Live sales activity'}</small></div>)}</div><div className="grid"><div className="card"><h3>Today's Queue</h3>{data?<>
<div className="overview-queue-desktop">
  <QueueTable items={data.daily_queue}/>
</div>
<div className="overview-queue-mobile">

  {data.daily_queue.length>0&&(()=>{
    const safeIndex=Math.min(
      mobileQueueIndex,
      Math.max(0,data.daily_queue.length-1)
    );

    const x:any=data.daily_queue[safeIndex];

    return <>

      <div className="overview-queue-carousel-head">
        <button
          aria-label="Previous prospect"
          disabled={safeIndex===0}
          onClick={()=>setMobileQueueIndex(i=>Math.max(0,i-1))}
        >
          ?
        </button>

        <span>
          {safeIndex+1} / {data.daily_queue.length}
        </span>

        <button
          aria-label="Next prospect"
          disabled={safeIndex>=data.daily_queue.length-1}
          onClick={()=>setMobileQueueIndex(i=>
            Math.min(data.daily_queue.length-1,i+1)
          )}
        >
          ?
        </button>
      </div>

      <div
        className="overview-queue-card overview-queue-carousel-card"
        key={x.prospect_id||x.lead_id||safeIndex}
      >
        <b>{x.business_name||x.name||x.business||'-'}</b>

        <div className="badges">
          <ScoreBadge value={x.score}/>
          <GradeBadge value={x.grade}/>
          <PriorityBadge value={x.priority}/>
          <RouteBadge value={x.route}/>
        </div>

        <small className="muted">
          {x.route_reason||''}
        </small>
      </div>

    </>
  })()}

  <div className="actions">
    <button onClick={()=>onNavigate?.('Up Next')}>
      Continue Selling
    </button>

    <button onClick={()=>onNavigate?.('Daily Queue')}>
      View Full Queue
    </button>
  </div>

</div>
</>:<div className="empty small">Loading queueÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦</div>}</div><div><div className="card schedule"><div className="section-head"><h3>Today's Schedule</h3><button onClick={()=>{setCalendarLoading(true);api.calendarUpcoming().then(setCalendar).catch(()=>setCalendar({status:"UNAVAILABLE",events:[]})).finally(()=>setCalendarLoading(false))}}>Refresh</button></div>{calendarLoading?<div className="skeleton-list"><div className="skeleton"/><div className="skeleton"/></div>:calendar?.status==='UNAVAILABLE'||calendar?.status==='DISABLED'?<p className="muted">Calendar unavailable.</p>:calendar?.events?.length?calendar.events.map((e:any)=><div className="event" key={e.id}><ScheduleWhen value={e.start}/><span>{e.title||'Untitled event'}</span>{e.location&&<small>{e.location}</small>}{e.html_link&&<a href={e.html_link} target="_blank" rel="noreferrer">Open in Google Calendar</a>}</div>):<p className="muted">Your calendar is clear.</p>}</div><div className="card"><h3>Campaign Safety</h3><div className="status"><i/> Configuration validated<br/><i/> Dry Run ON<br/><i/> Automatic Network Actions OFF<br/><i/> HubSpot Writes OFF<br/><i/> Automatic Outbound OFF</div></div></div></div></>}function QueuePage({campaign}:{campaign:string}){const {data,error}=useQueue(campaign);const [batch,setBatch]=useState<any>(null);const [selected,setSelected]=useState<number[]>([]);const [confirmBatch,setConfirmBatch]=useState(false);const [running,setRunning]=useState(false);const [search,setSearch]=useState('');const [grade,setGrade]=useState('All');const [priority,setPriority]=useState('All');const [route,setRoute]=useState('All');const [sales,setSales]=useState('All');const [hubspot,setHubspot]=useState('All');const [category,setCategory]=useState('All');const [city,setCity]=useState('All');const [queueProspect,setQueueProspect]=useState<QueueItem|null>(null);const [open,setOpen]=useState({DAILY_QUEUE:true,DEFERRED:false,RESEARCH:false,INELIGIBLE:false});if(error)return <div className="card empty"><h2>API unavailable</h2></div>;if(!data)return <div className="card empty">Loading queue...</div>;const all=[...data.daily_queue,...data.deferred,...data.research,...data.ineligible];const values=(k:string)=>Array.from(new Set(all.map((x:any)=>x[k]).filter(Boolean))).sort();const filtered=(items:any[])=>items.filter((x:any)=>{const n=(x.business_name||x.name||x.business||'').toLowerCase();const g=String(x.grade||'');return(!search||n.includes(search.toLowerCase()))&&(grade==='All'||(grade==='B'&&g.startsWith('B'))||(grade==='C'&&g.startsWith('C'))||(grade==='Reject'&&g==='Reject/Hold'))&&(priority==='All'||x.priority===priority)&&(route==='All'||x.route===route)&&(sales==='All'||(x.sales_status||'NOT_CONTACTED')===sales)&&(hubspot==='All'||(hubspot==='Synced'?x.hubspot_sync_status==='SYNCED':hubspot==='Failed'?x.hubspot_sync_status==='SYNC_FAILED':hubspot==='Review Required'?x.hubspot_sync_status==='REVIEW_REQUIRED':x.hubspot_sync_status!=='SYNCED'))&&(category==='All'||x.category===category)&&(city==='All'||x.city===city)});const sections=[['DAILY_QUEUE',data.daily_queue,'Daily Queue'],['DEFERRED',data.deferred,'Deferred'],['RESEARCH',data.research,'Research'],['INELIGIBLE',data.ineligible,'Ineligible']];const reset=()=>{setSearch('');setGrade('All');setPriority('All');setRoute('All');setSales('All');setHubspot('All');setCategory('All');setCity('All')};const previewBatch=()=>api.batchPreview(campaign).then(x=>{setBatch(x);setSelected(x.selected_default||[]);setConfirmBatch(false)});const executeBatch=()=>{setRunning(true);api.batchSync({campaign,prospect_ids:selected,confirmed:true}).then(x=>setBatch({...batch,results:x.results,summary:x.summary})).finally(()=>{setRunning(false);setConfirmBatch(false)})};return <div className="queue-sections"><div className="card"><div className="search-bar"><input type="search" placeholder="Search Daily Queue..." value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="filter"><select value={grade} onChange={e=>setGrade(e.target.value)}><option>All</option><option value="B">B / Qualified</option><option value="C">C / Review</option><option value="Reject">Reject/Hold</option></select><select value={priority} onChange={e=>setPriority(e.target.value)}><option>All</option>{['P1','P2','P3'].map(x=><option key={x}>{x}</option>)}</select><select value={route} onChange={e=>setRoute(e.target.value)}><option>All</option>{values('route').map(x=><option key={x}>{x}</option>)}</select><select value={sales} onChange={e=>setSales(e.target.value)}><option>All</option>{['NOT_CONTACTED','ATTEMPTED','CONTACTED','REPLIED','CONSULTATION_SET','FOLLOW_UP','NOT_INTERESTED','BOOKED'].map(x=><option key={x} value={x}>{prettyLabel(x)}</option>)}</select><select value={category} onChange={e=>setCategory(e.target.value)}><option>All</option>{values('category').map(x=><option key={x}>{x}</option>)}</select><select value={city} onChange={e=>setCity(e.target.value)}><option>All</option>{values('city').map(x=><option key={x}>{x}</option>)}</select><button onClick={reset}>Reset Filters</button><button onClick={previewBatch} disabled={!data.daily_queue.length}>Sync to HubSpot</button></div>{batch&&<div className="preview modal-enter"><h3>HubSpot Sync Preview</h3><p>Create New: {batch.counts?.CREATE_NEW||0} ÃƒÆ’Ã¢â‚¬Å¡ |  Update Existing: {batch.counts?.UPDATE_EXISTING||0} ÃƒÆ’Ã¢â‚¬Å¡ |  Review: {batch.counts?.REVIEW_REQUIRED||0}</p><button onClick={()=>setSelected(batch.selected_default||[])}>Select All Safe</button><button onClick={()=>setSelected([])}>Clear Selection</button>{!batch.results&&!confirmBatch&&<button disabled={!selected.length} onClick={()=>setConfirmBatch(true)}>Continue ({selected.length})</button>}{confirmBatch&&<div><p>Confirm HubSpot Batch Sync: {selected.length} selected.</p><button onClick={executeBatch} disabled={running}>{running?'Syncing...':'Confirm HubSpot Batch Sync'}</button><button onClick={()=>setConfirmBatch(false)}>Cancel</button></div>}{batch.results&&batch.results.map((r:any)=><p key={r.prospect_id}>{r.prospect_id}: {r.sync_status}</p>)}</div>}</div>{sections.map(([key,items,title])=>{const visible=filtered(items as any[]);const expanded=(open as any)[key as string];return <div className="card" key={key as string}><button className={`section-toggle ${expanded?'expanded':''}`} onClick={()=>setOpen(x=>({...x,[key as string]:!expanded}))}><span className="queue-chevron" aria-hidden="true"/><span className="queue-section-title">{title}</span><span className="queue-section-count">{visible.length} / {(items as any[]).length}</span></button>{expanded&&(visible.length?<QueueTable items={visible} onSelect={setQueueProspect}/>:<p className="muted">No prospects match the current filters.</p>)}</div>})}{queueProspect&&<ProspectDrawer item={queueProspect} onClose={()=>setQueueProspect(null)}/>}</div>}
function Prospects({campaign}:{campaign:string}){const [data,setData]=useState<QueueItem[]|null>(null);const [error,setError]=useState(false);const [q,setQ]=useState('');const [selected,setSelected]=useState<QueueItem|null>(null);useEffect(()=>{setData(null);setError(false);api.prospects(campaign).then((response:any)=>setData(Array.isArray(response)?response:(Array.isArray(response?.prospects)?response.prospects:[]))).catch(()=>setError(true))},[campaign]);if(error)return <div className="card empty"><h2>API unavailable</h2></div>;const rows=(data||[]).filter((x:any)=>(x.business_name||x.name||x.business||'').toLowerCase().includes(q.toLowerCase()));return <div className="prospects"><div className="card"><div className="search-bar"><input type="search" placeholder="Search Prospects..." value={q} onChange={e=>setQ(e.target.value)}/></div>{data===null?<div className="empty">Loading prospects...</div>:<QueueTable items={rows} onSelect={setSelected}/>}</div>{selected&&<ProspectDrawer item={selected} onClose={()=>setSelected(null)}/>}</div>}
function ProspectDrawer({item,onClose,onNext,initialEmailOpen=false}:{item:QueueItem;onClose:()=>void;onNext?:()=>void;initialEmailOpen?:boolean}){const prospectId=item.prospect_id??item.id;const [status,setStatus]=useState((item as any).sales_status||'NOT_CONTACTED');const [notes,setNotes]=useState((item as any).notes||'');const [value,setValue]=useState((item as any).booked_value??'');const [saving,setSaving]=useState(false);const [message,setMessage]=useState('');const [crm,setCrm]=useState<any>(null);const [integrations,setIntegrations]=useState<any>(null);const [emailOpen,setEmailOpen]=useState(initialEmailOpen);const [calendarOpen,setCalendarOpen]=useState(false);const [subject,setSubject]=useState('KidProductionz Introduction');const [body,setBody]=useState('Hi, I would love to connect about content opportunities.');const [emailTo,setEmailTo]=useState(item.email||'');const [calendarTitle,setCalendarTitle]=useState(`KidProductionz Consultation - ${(item as any).business_name||item.name||item.business||''}`);const [calendarStart,setCalendarStart]=useState('');const [calendarEnd,setCalendarEnd]=useState('');const [calendarDuration,setCalendarDuration]=useState(30);const [calendarTimezone,setCalendarTimezone]=useState('America/New_York');const [calendarLocation,setCalendarLocation]=useState('');const [calendarNotes,setCalendarNotes]=useState('');const [calendarAttendee,setCalendarAttendee]=useState(item.email||'');const [calendarPreview,setCalendarPreview]=useState<any>(null);const [integrationError,setIntegrationError]=useState('');const [preview,setPreview]=useState<any>(null);const [syncing,setSyncing]=useState(false);const [confirm,setConfirm]=useState(false);

const openAndScroll=(kind:'email'|'calendar')=>{
  if(kind==='email') setEmailOpen(true);
  if(kind==='calendar') setCalendarOpen(true);

  setTimeout(()=>{
    const el=document.getElementById(
      kind==='email'?'prospect-email-section':'prospect-calendar-section'
    );

    el?.scrollIntoView({
      behavior:'smooth',
      block:'start'
    });
  },120);
};const statuses=['NOT_CONTACTED','ATTEMPTED','CONTACTED','REPLIED','CONSULTATION_SET','FOLLOW_UP','NOT_INTERESTED','BOOKED'];useEffect(()=>{api.hubspotStatus().then(setCrm).catch(()=>setCrm({writes_enabled:false}));api.integrations().then(setIntegrations).catch(()=>setIntegrations({}))},[]);const save=async(next=false)=>{if(!prospectId){setMessage('Activity tracking unavailable for this prospect.');return}setSaving(true);setMessage('');try{await api.activity(prospectId,{status,notes,booked_value:value===''?null:Number(value)});setMessage('Saved');if(next){if(onNext)onNext();else onClose()}}catch(e){setMessage('Could not save activity. Your changes remain here.')}finally{setSaving(false)}};const beginSync=()=>{setSyncing(true);api.previewSync(item).then(setPreview).catch(()=>setPreview({sync_status:'REVIEW',warnings:['Preview unavailable'],proposed_operations:[]})).finally(()=>setSyncing(false))};const doSync=()=>{setConfirm(false);setSyncing(true);api.sync({...item,confirmed:true}).then(r=>{setPreview(r);setMessage(r.sync_status==='SYNCED'?'HubSpot: Synced':'HubSpot sync failed')}).catch(()=>setMessage('HubSpot sync failed')).finally(()=>setSyncing(false))};const copy=()=>navigator.clipboard?.writeText(`Hey ${(item as any).business_name||item.name||item.business||'there'}, IÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢m Kayla with KidProductionz. I came across your brand and would love to share a couple content ideas if youÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢re open to it.`).then(()=>setMessage('Message copied'));return <div className="card drawer"><button onClick={onClose}>Close</button><h2>{(item as any).business_name||item.name||item.business}</h2><p>Score {item.score??'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'} ÃƒÆ’Ã¢â‚¬Å¡ |  {item.grade||'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'} ÃƒÆ’Ã¢â‚¬Å¡ |  {item.route||'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'}</p><h3>Sales Activity</h3><label>Sales Status<select value={status} onChange={e=>setStatus(e.target.value)}>{statuses.map(x=><option key={x} value={x}>{prettyLabel(x)}</option>)}</select></label><label>Notes<textarea value={notes} onChange={e=>setNotes(e.target.value)}/></label><label>Booked Value ($)<input type="number" min="0" step="0.01" value={value} onChange={e=>setValue(e.target.value)}/></label><div className="actions">{item.phone&&<a href={`tel:${item.phone}`}>Call</a>}{item.email&&<a href={`mailto:${item.email}`}>Email</a>}{item.social&&<a href={item.social} target="_blank" rel="noreferrer">Social</a>}{item.website&&<a href={item.website} target="_blank" rel="noreferrer">Website</a>}<button onClick={copy}>Copy Message</button></div><button onClick={()=>save(false)} disabled={saving||!prospectId}>{saving?'SavingÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦':'Save'}</button> <button onClick={()=>save(true)} disabled={saving||!prospectId}>{saving?'SavingÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦':'Save & Next'}</button>{message&&<p className="muted">{message}</p>}{integrationError&&<p className="notice">{integrationError}</p>}<h3>Actions</h3><div className="actions">{item.phone&&<a href={`tel:${item.phone}`} onClick={()=>api.logAction(prospectId!,'CALL_OPENED')}>Call</a>}<button onClick={()=>{openAndScroll('email');api.logAction(prospectId!,'EMAIL_DRAFTED')}}>Draft Email</button>{item.website&&<a href={item.website} target="_blank" rel="noreferrer" onClick={()=>api.logAction(prospectId!,'WEBSITE_OPENED')}>Website</a>}{item.social&&<a href={item.social} target="_blank" rel="noreferrer" onClick={()=>api.logAction(prospectId!,'SOCIAL_OPENED')}>Social</a>}{integrations?.booking_url&&<><a href={integrations.booking_url} target="_blank" rel="noreferrer">Open Booking Link</a><button onClick={()=>navigator.clipboard?.writeText(integrations.booking_url).then(()=>api.logAction(prospectId!,'BOOKING_LINK_COPIED'))}>Copy Booking Link</button></>}<button onClick={()=>openAndScroll('calendar')}>Schedule Consultation</button></div>{calendarOpen&&<div id="prospect-calendar-section" className="preview modal-enter"><label>Title<input value={calendarTitle} onChange={e=>{setCalendarTitle(e.target.value);setCalendarPreview(null)}}/></label><label>Start<input type="datetime-local" value={calendarStart} onChange={e=>{const v=e.target.value;setCalendarStart(v);if(v){const d=new Date(v);d.setMinutes(d.getMinutes()+calendarDuration);const pad=(n:number)=>String(n).padStart(2,'0');setCalendarEnd(`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`)}setCalendarPreview(null)}}/></label><label>End<input type="datetime-local" value={calendarEnd} onChange={e=>{setCalendarEnd(e.target.value);setCalendarPreview(null)}}/></label><label>Duration (minutes)<input type="number" min="15" value={calendarDuration} onChange={e=>{const mins=Math.max(15,Number(e.target.value)||30);setCalendarDuration(mins);if(calendarStart){const d=new Date(calendarStart);d.setMinutes(d.getMinutes()+mins);const pad=(n:number)=>String(n).padStart(2,'0');setCalendarEnd(`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`)}setCalendarPreview(null)}}/></label><label>Timezone<input value={calendarTimezone} onChange={e=>setCalendarTimezone(e.target.value)}/></label><label>Location<input value={calendarLocation} onChange={e=>setCalendarLocation(e.target.value)}/></label><label>Notes<textarea value={calendarNotes} onChange={e=>setCalendarNotes(e.target.value)}/></label><label>Attendee email<input value={calendarAttendee} onChange={e=>setCalendarAttendee(e.target.value)}/></label><button onClick={()=>{if(!calendarTitle||!calendarStart||!calendarEnd||calendarEnd<=calendarStart){setIntegrationError('Enter a valid title, start, and end time.');return}api.calendarPreview({prospect_id:prospectId,title:calendarTitle,consultation_start:calendarStart,consultation_end:calendarEnd,timezone:calendarTimezone,location:calendarLocation,notes:calendarNotes,attendee_email:calendarAttendee,confirmed:false}).then(x=>{setCalendarPreview(x);setIntegrationError('')}).catch(e=>{console.error(e);setIntegrationError('Calendar preview failed: '+(e.message||'Unable to preview'))})}}>Preview</button>{calendarPreview&&<><p>Preview ready: {calendarPreview.title||calendarTitle}</p><button onClick={()=>api.calendarCreate({prospect_id:prospectId,title:calendarTitle,consultation_start:calendarStart,consultation_end:calendarEnd,timezone:calendarTimezone,location:calendarLocation,notes:calendarNotes,attendee_email:calendarAttendee,confirmed:true}).then(x=>{setCalendarOpen(false);setStatus('CONSULTATION_SET');setMessage('Consultation Scheduled');if(x.status_warning)setIntegrationError('Event created, but prospect status could not be updated: '+x.status_warning);else if(x.event_url)setIntegrationError('Event created: '+x.event_url)}).catch(e=>{console.error(e);setIntegrationError('Calendar creation failed: '+(e.message||'Unable to create'))})}>Confirm Create Event</button></>}<button onClick={()=>setCalendarOpen(false)}>Cancel</button></div>}{emailOpen&&<div id="prospect-email-section" className="preview modal-enter"><label>Recipient email<input value={emailTo} onChange={e=>setEmailTo(e.target.value)} /></label><input value={subject} onChange={e=>setSubject(e.target.value)}/><textarea value={body} onChange={e=>setBody(e.target.value)}/><button disabled={!emailTo.trim()} onClick={()=>api.gmailSend({prospect_id:prospectId,to:emailTo,subject,body,confirmed:true}).then(()=>{setEmailOpen(false);setMessage('Email sent')}).catch(e=>{console.error(e);setIntegrationError('Email failed: '+(e.message||'Unable to send'))})}>Confirm Send</button><button onClick={()=>setEmailOpen(false)}>Cancel</button></div>}<h3>HubSpot</h3><p>Association verified: {String((item as any).association_verified??preview?.association_verified??false)}</p><p>Last synced: {(item as any).last_synced_at||''}</p><p>Last warning/error: {(item as any).last_sync_error||''}</p><p>Status: {preview?.sync_status==='SYNCED'?'Synced':preview?.sync_status||((item as any).hubspot_sync_status||'Not synced')}</p>{preview?.hubspot_contact_id&&<p>Contact ID: {preview.hubspot_contact_id} {integrations?.hubspot_portal_id&&<a href={`https://app.hubspot.com/contacts/${integrations.hubspot_portal_id}/contact/${preview.hubspot_contact_id}`} target="_blank" rel="noreferrer" onClick={()=>api.logAction(prospectId!,'HUBSPOT_OPENED')}>Open Contact</a>}</p>}{preview?.hubspot_deal_id&&<p>Deal ID: {preview.hubspot_deal_id} {integrations?.hubspot_portal_id&&<a href={`https://app.hubspot.com/contacts/${integrations.hubspot_portal_id}/deal/${preview.hubspot_deal_id}`} target="_blank" rel="noreferrer" onClick={()=>api.logAction(prospectId!,'HUBSPOT_OPENED')}>Open Deal</a>}</p>}{crm?.writes_enabled&&prospectId?<button onClick={beginSync} disabled={syncing}>{syncing?'LoadingÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦':'Sync to HubSpot'}</button>:<p className="muted">HubSpot sync is currently disabled.</p>}{preview&&preview.sync_status!=='SYNCED'&&crm?.writes_enabled&&<div className="preview modal-enter"><p>Planned action: {preview.proposed_operations?.join(', ')||preview.sync_status}</p><button onClick={()=>setConfirm(true)}>Confirm HubSpot Sync</button><button onClick={()=>setPreview(null)}>Cancel</button></div>}{confirm&&<div className="preview modal-enter"><p>Confirm this HubSpot sync?</p><button onClick={doSync}>Confirm HubSpot Sync</button><button onClick={()=>setConfirm(false)}>Cancel</button></div>}</div>}function Campaigns({campaign,onChanged,onSelect}:{campaign:string;onChanged?:()=>void;onSelect?:(id:string)=>void}){const [items,setItems]=useState<any[]|null>(null);const [upload,setUpload]=useState<any>(null);const [sheet,setSheet]=useState('');const [preview,setPreview]=useState<any>(null);const [exec,setExec]=useState(false);const [confirmRun,setConfirmRun]=useState(false);const [editing,setEditing]=useState<any>(null);const [form,setForm]=useState<any>({name:'',campaign_id:'',city:'',state:'',category:'',description:'',daily_queue_limit:50,status:'ACTIVE'});const refresh=()=>api.campaigns().then((x:any)=>{const rows=Array.isArray(x)?x:(x.campaigns||[]);setItems(rows);return rows}).catch(()=>{setItems([]);return []});useEffect(()=>{refresh();api.hubspotStatus().then(x=>setExec(Boolean(x.campaign_execution_enabled))).catch(()=>setExec(false))},[]);useEffect(()=>{setUpload(null);setPreview(null);setSheet('')},[campaign]);const slug=(v:string)=>v.toLowerCase().trim().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');const openCreate=()=>{setEditing({});setForm({name:'',campaign_id:'',city:'',state:'',category:'',description:'',daily_queue_limit:50,status:'ACTIVE'})};const openEdit=(c:any)=>{setEditing(c);setForm({...c,daily_queue_limit:c.daily_queue_limit||50,status:c.status||'ACTIVE'})};const save=async()=>{if(!form.name||!form.city||!form.state||!form.category){return}const body={...form,campaign_id:form.campaign_id||slug(form.name),daily_queue_limit:Number(form.daily_queue_limit)||50};try{if(editing?.campaign_id)await api.campaignUpdate(editing.campaign_id,body);else await api.campaignCreate(body);setEditing(null);await refresh();onChanged?.()}catch(e){setItems(x=>x||[])}};const remove=async(c:any)=>{
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
};if(items===null)return <div className="card empty">Loading campaigns...</div>;const selected=items.find(c=>c.campaign_id===campaign)||items[0];return <div className="campaign-grid"><div className="section-head"><h2>Campaigns</h2><button onClick={openCreate}>+ New Campaign</button></div>{editing&&<div className="card preview modal-enter"><h3>{editing.campaign_id?'Edit Campaign':'New Campaign'}</h3>{[['name','Campaign Name'],['campaign_id','Campaign ID'],['city','City'],['state','State'],['category','Primary Category / Niche']].map(([k,l])=><label key={k}>{l}<input value={form[k]||''} onChange={e=>setForm({...form,[k]:e.target.value})} onBlur={()=>k==='name'&&!form.campaign_id&&setForm({...form,campaign_id:slug(form.name)})}/></label>)}<label>Description<textarea value={form.description||''} onChange={e=>setForm({...form,description:e.target.value})}/></label><label>Daily Queue Limit<input type="number" min="1" value={form.daily_queue_limit} onChange={e=>setForm({...form,daily_queue_limit:e.target.value})}/></label><label>Status<select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option>ACTIVE</option><option>PAUSED</option><option>ARCHIVED</option></select></label><button onClick={save}>Save Campaign</button><button onClick={()=>setEditing(null)}>Cancel</button></div>}{items.map(c=><div className="card campaign" key={c.campaign_id}><p className="eyebrow">CAMPAIGN</p><h2>{c.name||c.campaign_id}</h2><p className="muted campaign-market">Market: <strong>{[c.city||c.market?.city,c.state].filter(Boolean).join(', ')||'Not set'}</strong></p><p className="campaign-meta"><span>{c.category||'Uncategorized'}</span><span className="badge">{c.status||'ACTIVE'}</span></p><p className="muted campaign-stats"><span>Last run: {c.last_run||'Never'}</span><span>Queue: {c.queue_count??0}</span></p><button onClick={()=>onSelect?.(c.campaign_id)}>Open</button><button onClick={()=>openEdit(c)}>Edit</button><button onClick={async()=>{await api.campaignUpdate(c.campaign_id,{status:c.status==='PAUSED'?'ACTIVE':'PAUSED'});refresh();onChanged?.()}}>{c.status==='PAUSED'?'Resume':'Pause'}</button><button onClick={async()=>{await api.campaignUpdate(c.campaign_id,{status:'ARCHIVED'});refresh();onChanged?.()}}>Archive</button><button onClick={()=>remove(c)} disabled={(items||[]).length<=1}>Delete</button></div>)}{selected&&<div className="card campaign"><h3>{selected.name||selected.campaign_id} Run</h3>{!upload&&<p className="muted">No leads have been uploaded for this campaign yet.</p>}<input type="file" accept=".csv,.xlsx" onChange={e=>{const f=e.target.files?.[0];setPreview(null);setSheet('');if(f)uploadCampaign(f).then(x=>{setUpload(x);if(x.sheets?.length===1)setSheet(x.sheets[0])}).catch(()=>setUpload({error:'Upload failed'}))}}/>{upload&&!upload.error&&<p className="muted">{upload.filename} ÃƒÆ’Ã¢â‚¬Å¡ |  {upload.file_type} ÃƒÆ’Ã¢â‚¬Å¡ |  {upload.size} bytes</p>}{upload?.sheets?.length>1&&<select value={sheet} onChange={e=>setSheet(e.target.value)}><option value="">Choose worksheet</option>{upload.sheets.map((s:string)=><option key={s}>{s}</option>)}</select>}<button onClick={()=>campaignApi.preview({campaign:selected.campaign_id,input_file:upload.reference,sheet:sheet||null,dry_run:true}).then(setPreview)} disabled={!upload?.reference||Boolean(upload.sheets?.length>1&&!sheet)}>Preview Run</button>{!selected&&<p className="muted">No leads have been uploaded for this campaign yet.</p>}{preview&&<div className="preview modal-enter"><p>Queue limit: {preview.queue_limit} ÃƒÆ’Ã¢â‚¬Å¡ |  Dry Run: Yes</p>{exec?<><button onClick={()=>setConfirmRun(true)}>Run Campaign</button>{confirmRun&&<button onClick={()=>campaignApi.run({campaign:selected.campaign_id,input_file:upload.reference,sheet:sheet||null,dry_run:true,confirmed:true}).then(setPreview)}>Confirm Run</button>}</>:<p className="muted">Campaign execution is currently disabled.</p>}</div>}</div>}</div>}
function Runs(){const [items,setItems]=useState<any[]|null>(null);useEffect(()=>{api.runs().then(setItems).catch(()=>setItems([]))},[]);return <div className="queue-sections">{items===null?<div className="card empty">Loading runs...</div>:!items.length?<div className="card empty">No run manifests available.</div>:items.map((r,i)=><div className="card" key={i}><h3>{r.campaign_id}</h3><span className="badge">{r.overall_status}</span><p className="muted">Daily Queue: {r.daily_queue_summary?.daily_queue_count??'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'} ÃƒÆ’Ã¢â‚¬Å¡ |  Deferred: {r.daily_queue_summary?.deferred_count??'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'}</p></div>)}</div>}

function InterfaceThemeSettings(){
  const themes=[
    {id:'chrome',name:'Chrome Blue',colors:['#8fd3ff','#4776ff']},
    {id:'violet',name:'Violet',colors:['#d6a8ff','#7c3cff']},
    {id:'emerald',name:'Emerald',colors:['#79f2c0','#00a878']},
    {id:'crimson',name:'Crimson',colors:['#ff8b9a','#d51f45']},
    {id:'gold',name:'Gold',colors:['#ffe29a','#d89b22']},
    {id:'rose',name:'Rose Gold',colors:['#ffd1dc','#c9798f']},
    {id:'ice',name:'Ice',colors:['#d9fbff','#65cfe8']}
  ];

  const [theme,setTheme]=useState(()=>{
    try{
      return localStorage.getItem('kp-interface-theme')||'chrome';
    }catch{
      return 'chrome';
    }
  });

  useEffect(()=>{
    document.documentElement.setAttribute('data-kp-theme',theme);
    try{
      localStorage.setItem('kp-interface-theme',theme);
    }catch{}
  },[theme]);

  return <div className="card kp-interface-settings">
    <p className="eyebrow">INTERFACE</p>
    <h3>Appearance</h3>
    <p className="muted">
      Choose the accent gradient for your Sales OS.
    </p>

    <div className="kp-theme-grid">
      {themes.map(t=>
        <button
          key={t.id}
          type="button"
          className={`kp-theme-option ${theme===t.id?'selected':''}`}
          onClick={()=>setTheme(t.id)}
          aria-pressed={theme===t.id}
        >
          <span
            className="kp-theme-preview"
            style={{
              background:`linear-gradient(135deg, ${t.colors[0]}, ${t.colors[1]})`
            }}
          />
          <span className="kp-theme-name">{t.name}</span>
          {theme===t.id&&<span className="kp-theme-check">?</span>}
        </button>
      )}
    </div>

    <small className="muted kp-theme-save-note">
      Your selection is saved automatically on this device.
    </small>
  </div>
}

function Settings({campaign}:{campaign:string}){const [i,setI]=useState<any>(null);const [hs,setHs]=useState<any>(null);const [bk,setBk]=useState<any>(null);const [modal,setModal]=useState('');const [msg,setMsg]=useState('');const [hf,setHf]=useState<any>({access_token:'',portal_id:'',pipeline_id:'',stage_id:'',write_enabled:false});const [bf,setBf]=useState<any>({provider:'',booking_url:'',default_duration:30,default_title:''});const load=()=>{api.integrations().then(setI).catch(()=>setI({}));api.hubspotSettings().then((x:any)=>{setHs(x);setHf((f:any)=>({...f,...x,access_token:''}))}).catch(()=>setHs(null));api.bookingSettings().then((x:any)=>{setBk(x);setBf(x)}).catch(()=>setBk(null))};useEffect(load,[]);const saveH=async()=>{try{await api.saveHubspotSettings(hf);setMsg('HubSpot configuration saved.');setModal('');load()}catch{setMsg('Could not save HubSpot configuration.')}};const saveB=async()=>{if(bf.booking_url&&!/^https?:\/\//i.test(bf.booking_url)){setMsg('Enter a valid http or https booking URL.');return}try{await api.saveBookingSettings({...bf,default_duration:Number(bf.default_duration)});setMsg('Booking configuration saved.');setModal('');load()}catch{setMsg('Could not save booking configuration.')}};return <div className="grid"><InterfaceThemeSettings/><div className="card"><h3>Campaign Configuration</h3><p>Selected campaign: <b>{campaign}</b></p></div><div className="card"><h3>HubSpot</h3><p>{hs===null?'Connection error':hs?.configured?'Configured':'Not configured'}</p>{hs?.token_present&&<p className="muted">Access token saved</p>}<button onClick={()=>setModal('hubspot')}>Configure HubSpot</button>{modal==='hubspot'&&<div className="preview modal-enter"><label>Access Token<input type="password" placeholder={hs?.token_present?'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¢':''} value={hf.access_token} onChange={e=>setHf({...hf,access_token:e.target.value})}/></label><label>Portal ID<input value={hf.portal_id||''} onChange={e=>setHf({...hf,portal_id:e.target.value})}/></label><label>Pipeline ID<input value={hf.pipeline_id||''} onChange={e=>setHf({...hf,pipeline_id:e.target.value})}/></label><label>Stage ID<input value={hf.stage_id||''} onChange={e=>setHf({...hf,stage_id:e.target.value})}/></label><label><input type="checkbox" checked={!!hf.write_enabled} onChange={e=>setHf({...hf,write_enabled:e.target.checked})}/> Write Enabled</label><button onClick={()=>api.hubspotSettingsTest().then(()=>setMsg('Read-only connection test passed.')).catch(()=>setMsg('Connection test failed.'))}>Test Connection</button><button onClick={saveH}>Save Configuration</button><button onClick={()=>setModal('')}>Cancel</button></div>}</div><div className="card"><h3>Booking</h3><p>{bk?.configured?'Configured':'Not configured'}{bk?.provider&&` ÃƒÆ’Ã¢â‚¬Å¡ |  ${bk.provider}`}</p><button onClick={()=>setModal('booking')}>Configure Booking</button>{modal==='booking'&&<div className="preview modal-enter"><label>Provider / Label<input value={bf.provider||''} onChange={e=>setBf({...bf,provider:e.target.value})}/></label><label>Booking URL<input value={bf.booking_url||''} onChange={e=>setBf({...bf,booking_url:e.target.value})}/></label><label>Default Consultation Duration<input type="number" min="1" value={bf.default_duration||30} onChange={e=>setBf({...bf,default_duration:e.target.value})}/></label><label>Default Meeting Title<input value={bf.default_title||''} onChange={e=>setBf({...bf,default_title:e.target.value})}/></label><button onClick={saveB}>Save Configuration</button><button onClick={()=>setModal('')}>Cancel</button></div>}</div><div className="card"><h3>Google</h3><p>Google: {i?.google_status||'NOT_CONNECTED'}</p><p>Gmail: {i?.gmail_enabled?'Enabled':'Disabled'}  |  Calendar: {i?.calendar_enabled?'Enabled':'Disabled'}</p>{i?.google_status!=='CONNECTED'&&<button onClick={async()=>{try{const r=await fetch('/api/google/oauth/start',{credentials:'include'});if(!r.ok)throw new Error();const d=await r.json();window.location.href=d.authorization_url}catch{setMsg('Could not start Google connection.')}}}>Connect to Google</button>}{i?.google_status==='CONNECTED'&&<>
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
function AuthGate(){const [state,setState]=useState<any>(null);const [user,setUser]=useState('');const [password,setPassword]=useState('');const [error,setError]=useState('');useEffect(()=>{authApi.me().then(data=>setState({authenticated:data.authenticated===true})).catch(()=>setState({authenticated:false}))},[]);if(!state)return <div className="card empty">LoadingÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦</div>;if(state.authenticated===true)return <App/>;const login=async(e:any)=>{e.preventDefault();try{await authApi.login(user,password);const data=await authApi.me();if(data.authenticated===true)setState(data);else setError('Unable to authenticate')}catch{setError('Invalid credentials')}};return <main className="auth-screen"><form className="card" onSubmit={login}><img src={logo} /><h1>KidProductionz Sales OS</h1><p className="muted">Sign in to continue.</p><input aria-label="Username" value={user} onChange={e=>setUser(e.target.value)} placeholder="Username"/><input aria-label="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password"/>{error&&<p className="notice">{error}</p>}<button type="submit">Sign in</button></form></main>}
createRoot(root).render(<AuthGate/>);





