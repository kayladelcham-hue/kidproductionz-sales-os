import {BusinessHero} from './BusinessHero';
import React from 'react';
type Preview={label:string;title:string;summary?:string;business?:any};
type Props={review?:boolean;activeKey:string|number;children:React.ReactNode;previous?:Preview;next?:Preview;onPrevious?:()=>void;onNext?:()=>void};
function SideCard({card,side}:{card?:Preview;side:string}){return <div className={`kp-carousel-preview kp-carousel-${side}`} aria-hidden="true" inert>{card?.business?<><BusinessHero business={card.business} compact/><h3>{card.title}</h3><p>{card.summary}</p></>:<><img className="kp-preview-skye" src="/avatars/skye.png" alt=""/><small>{card?.label||'Your guide'}</small><h3>{card?.title||'One step at a time'}</h3><p>{card?.summary||'Skye helps you check each business before you decide.'}</p></>}</div>}
/** Adjacent cards are inert previews. Browsing never assigns a decision. */
export function FocusCarousel({review=false,activeKey,children,previous,next,onPrevious,onNext}:Props){
 const handleKey=(e:React.KeyboardEvent<HTMLDivElement>)=>{if(e.target!==e.currentTarget||e.altKey||e.metaKey||e.ctrlKey)return;if(e.key==='ArrowLeft'&&onPrevious){e.preventDefault();onPrevious()}if(e.key==='ArrowRight'&&onNext){e.preventDefault();onNext()}};
 return <div className={`kp-carousel ${review?'is-review is-deck':''}`} role="region" aria-roledescription="carousel" aria-label="Guided discovery cards" tabIndex={0} onKeyDown={handleKey}><div className="kp-carousel-stage"><SideCard card={previous} side="previous"/><div className="kp-carousel-active" key={activeKey} role="group" aria-roledescription="slide">{children}</div>{(!review||next)&&<SideCard card={next} side="next"/>}</div><div className="kp-carousel-controls"><button aria-label="Previous card" disabled={!onPrevious} onClick={onPrevious}>‹</button><span className="kp-sr-only">Use the arrows to browse businesses</span><button aria-label="Next card" disabled={!onNext} onClick={onNext}>›</button></div></div>;
}
