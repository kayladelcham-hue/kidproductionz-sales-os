import {BusinessHero} from './BusinessHero';
import React, {useState} from 'react';

type Preview={label:string;title:string;summary?:string;business?:any};
type Props={activeKey:string|number;children:React.ReactNode;previous?:Preview;next?:Preview;onPrevious?:()=>void;onNext?:()=>void};

/** Side cards preview real stages/records; only the centered card is interactive. */
export function FocusCarousel({activeKey,children,previous,next,onPrevious,onNext}:Props){
  const [motion,setMotion]=useState({key:activeKey,backwards:false});
  let backwards=motion.backwards;
  if(motion.key!==activeKey){
    backwards=typeof activeKey==='number'&&typeof motion.key==='number'&&activeKey<motion.key;
    setMotion({key:activeKey,backwards});
  }
  const preview=(card:Preview,side:string)=><div className={`dw-carousel-peek dw-carousel-${side}`} aria-hidden="true">
    <div className="dw-peek-art">{card.business?<BusinessHero business={card.business} compact/>:<img src="/avatars/skye.png" alt=""/>}</div>{!card.business&&<small>{card.label}</small>}<h3>{card.title}</h3>{card.summary&&<p>{card.summary}</p>}
    {card.business&&<div className="dw-peek-evidence"><p>Matches: {card.business.assessment?.matches?.slice(0,2).join(' · ')||'Not confirmed'}</p><p>Contact: {card.business.assessment?.contact_paths?.join(', ')||'Not recorded'}</p><p>Still unknown: {card.business.assessment?.missing_information?.[0]||'Review the evidence'}</p></div>}
  </div>;
  return <div className="dw-focus-carousel">
    {preview(previous||{label:'Your guide',title:'Meet Skye',summary:'One question at a time. Your choices shape the search.'},'previous')}
    {next&&preview(next,'next')}
    <div className={`dw-carousel-active ${backwards?'is-backwards':''}`} key={activeKey}>{children}</div>
    <button className="dw-carousel-arrow dw-carousel-prev-arrow" aria-label="Previous card" disabled={!onPrevious} onClick={onPrevious}>‹</button>
    <button className="dw-carousel-arrow dw-carousel-next-arrow" aria-label="Next card" disabled={!onNext} onClick={onNext}>›</button>
  </div>;
}
