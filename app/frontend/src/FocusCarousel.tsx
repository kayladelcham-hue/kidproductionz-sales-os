import React, {useState} from 'react';

type Preview={label:string;title:string;summary?:string};
type Props={activeKey:string|number;children:React.ReactNode;previous?:Preview;next?:Preview};

/** Side cards preview real stages/records; only the centered card is interactive. */
export function FocusCarousel({activeKey,children,previous,next}:Props){
  const [motion,setMotion]=useState({key:activeKey,backwards:false});
  let backwards=motion.backwards;
  if(motion.key!==activeKey){
    backwards=typeof activeKey==='number'&&typeof motion.key==='number'&&activeKey<motion.key;
    setMotion({key:activeKey,backwards});
  }
  const preview=(card:Preview,side:string)=><div className={`dw-carousel-peek dw-carousel-${side}`} aria-hidden="true">
    <span className="dw-carousel-orbit">✦</span><small>{card.label}</small><h3>{card.title}</h3>{card.summary&&<p>{card.summary}</p>}
    <div className="dw-carousel-lines"><i/><i/><i/></div>
  </div>;
  return <div className="dw-focus-carousel">
    {previous&&preview(previous,'previous')}
    {next&&preview(next,'next')}
    <div className={`dw-carousel-active ${backwards?'is-backwards':''}`} key={activeKey}>{children}</div>
  </div>;
}
