import React,{useState} from 'react';
import {FocusCarousel} from './FocusCarousel';
import {BusinessHero} from './BusinessHero';
import {FitSignals} from './FitSignals';
/** Browse saved records without changing decisions or initiating outreach. */
export function SavedBusinessCarousel({businesses,onOpen,onFull}:{businesses:any[];onOpen:(row:any)=>void;onFull?:(row:any)=>void}){
 const [position,setPosition]=useState(0);
 if(!businesses.length)return null;
 const index=Math.min(position,businesses.length-1),row=businesses[index];
 const preview=(offset:number)=>{if(businesses.length<2)return undefined;const business=businesses[(index+offset+businesses.length)%businesses.length];return {label:'Saved business',title:business.name||business.company,summary:[business.category,business.city].filter(Boolean).join(' · '),business}};
 return <section className="kp-saved-carousel" aria-label="Saved businesses"><p className="kp-saved-position" role="status">✓ Saved · {index+1} of {businesses.length}</p><FocusCarousel activeKey={row.id} previous={preview(-1)} next={preview(1)} onPrevious={businesses.length>1?()=>setPosition((index-1+businesses.length)%businesses.length):undefined} onNext={businesses.length>1?()=>setPosition((index+1)%businesses.length):undefined}><article className="dw-guided-card"><BusinessHero business={row}/><h3>{row.name||row.company}</h3><p>{[row.category,[row.city,row.state].filter(Boolean).join(', ')].filter(Boolean).join(' · ')||'Details not recorded'}</p><FitSignals compact assessment={row.assessment||{}}/><button className="dw-primary kp-saved-open" onClick={()=>onOpen(row)}>Next step <span aria-hidden="true">→</span></button>{onFull&&<details><summary>More options</summary><button onClick={()=>onFull(row)}>Open full saved record</button></details>}</article></FocusCarousel></section>;
}
