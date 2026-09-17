import React,{useMemo,useState} from 'react';
import {generateOutscraperLeads} from './api';

type Props={
  campaign:string;
  onNavigate?:(page:string)=>void;
};

const STATES=[
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN',
  'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
  'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
  'TX','UT','VT','VA','WA','WV','WI','WY','DC'
];

export default function LeadGenerator({campaign,onNavigate}:Props){
  const [businessType,setBusinessType]=useState('Hair salons');
  const [city,setCity]=useState('');
  const [state,setState]=useState('');
  const [limit,setLimit]=useState(10);
  const [loading,setLoading]=useState(false);
  const [result,setResult]=useState<any>(null);
  const [error,setError]=useState('');

  const query=useMemo(()=>{
    if(!businessType.trim()||!city.trim()||!state.trim())return '';
    return `${businessType.trim()} in ${city.trim()}, ${state.trim()}`;
  },[businessType,city,state]);

  const generate=async()=>{
    setError('');
    setResult(null);

    if(!businessType.trim()){
      setError('Enter a business type.');
      return;
    }

    if(!city.trim()){
      setError('Enter a city.');
      return;
    }

    if(!state){
      setError('Select a state.');
      return;
    }

    if(!campaign){
      setError('Select a campaign first.');
      return;
    }

    const safeLimit=Math.max(1,Math.min(100,Number(limit)||10));

    setLoading(true);

    try{
      const data=await generateOutscraperLeads({
        campaign,
        query,
        limit:safeLimit,
        category:businessType.trim(),
        city:city.trim(),
        state,
        confirmed:true
      });

      setResult(data);
    }catch(err:any){
      const message=
        err?.message||
        'Lead generation failed. Please try again.';

      setError(message);
    }finally{
      setLoading(false);
    }
  };

  const summary=result?.summary||{};

  return (
    <div className="lead-generator-page">

      <section className="lead-generator-hero">
        <p className="eyebrow">PROSPECTING ENGINE</p>
        <h2>Generate qualified leads.</h2>
        <p className="muted">
          Search any U.S. city, qualify businesses against your sales rules,
          remove existing prospects, and add new leads directly to Sales OS.
        </p>
      </section>

      <section className="card lead-generator-card">

        <div className="lead-generator-campaign">
          <span className="lead-generator-label">ACTIVE CAMPAIGN</span>
          <strong>{campaign.replaceAll('_',' ')}</strong>
          <small>
            Generated prospects will be saved to this campaign.
          </small>
        </div>

        <div className="lead-generator-grid">

          <label>
            <span>Business Type</span>
            <input
              value={businessType}
              onChange={e=>setBusinessType(e.target.value)}
              placeholder="Hair salons"
              disabled={loading}
            />
          </label>

          <label>
            <span>City</span>
            <input
              value={city}
              onChange={e=>setCity(e.target.value)}
              placeholder="Atlanta"
              disabled={loading}
            />
          </label>

          <label>
            <span>State</span>
            <select
              value={state}
              onChange={e=>setState(e.target.value)}
              disabled={loading}
            >
              <option value="">Select state</option>
              {STATES.map(x=>
                <option key={x} value={x}>{x}</option>
              )}
            </select>
          </label>

          <label>
            <span>Lead Count</span>
            <input
              type="number"
              min="1"
              max="100"
              value={limit}
              onChange={e=>setLimit(Number(e.target.value))}
              disabled={loading}
            />
          </label>

        </div>

        <div className="lead-generator-query">
          <span>SEARCH</span>
          <strong>{query||'Complete the fields above'}</strong>
        </div>

        <button
          className="lead-generator-submit"
          onClick={generate}
          disabled={loading||!query}
        >
          {loading?'Generating & Qualifying...':'Generate & Qualify Leads'}
        </button>

        <p className="lead-generator-safety">
          No emails or calls are sent automatically.
          Maximum 100 leads per generation.
        </p>

        {error&&
          <div className="notice lead-generator-error">
            {error}
          </div>
        }

      </section>

      {result&&
        <section className="lead-generator-results">

          <div className="lead-generator-success">
            <div>
              <p className="eyebrow">GENERATION COMPLETE</p>
              <h3>Leads added to Sales OS.</h3>
            </div>
            <span>?</span>
          </div>

          <div className="lead-generator-stats">

            <div>
              <strong>{summary.generated??0}</strong>
              <span>Found</span>
            </div>

            <div>
              <strong>{summary.database_duplicates??0}</strong>
              <span>Existing</span>
            </div>

            <div>
              <strong>{summary.saved??0}</strong>
              <span>New</span>
            </div>

            <div>
              <strong>{summary.qualified??0}</strong>
              <span>Qualified</span>
            </div>

            <div>
              <strong>{summary.research??0}</strong>
              <span>Research</span>
            </div>

            <div>
              <strong>{summary.rejected??0}</strong>
              <span>Rejected</span>
            </div>

          </div>

          {Array.isArray(result.saved)&&result.saved.length>0&&
            <div className="card lead-generator-saved">
              <div className="lead-generator-result-head">
                <div>
                  <p className="eyebrow">NEW PROSPECTS</p>
                  <h3>{result.saved.length} added</h3>
                </div>

                <button onClick={()=>onNavigate?.('Prospects')}>
                  View Prospects
                </button>
              </div>

              <div className="lead-generator-list">
                {result.saved.map((lead:any)=>(
                  <div
                    className="lead-generator-lead"
                    key={lead.id}
                  >
                    <div>
                      <strong>{lead.name}</strong>
                      <span>{lead.queue||'PROSPECT'}</span>
                    </div>

                    <b>{lead.score??'-'}</b>
                  </div>
                ))}
              </div>
            </div>
          }

          {Array.isArray(result.duplicates)&&result.duplicates.length>0&&
            <div className="card lead-generator-existing">
              <p className="eyebrow">ALREADY IN SALES OS</p>
              <h3>{result.duplicates.length} duplicates skipped</h3>

              <div className="lead-generator-duplicate-list">
                {result.duplicates.map((name:string,i:number)=>
                  <span key={`${name}-${i}`}>{name}</span>
                )}
              </div>
            </div>
          }

        </section>
      }

    </div>
  );
}
