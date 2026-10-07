import React from 'react';
/** A level map, not a fabricated time series. Thresholds come from the current level. */
export function LevelTrack({total,level}:{total:number;level:any}){
 const floor=Number(level.floor)||0,next=Number(level.next_at)||0;
 const target=next>floor?next:floor;
 const fraction=next>floor?Math.min(1,Math.max(0,(total-floor)/(next-floor))):1;
 const x=36+fraction*328;
 return <section className="kp-level-map" aria-label="Momentum level track"><header><div><span className="eyebrow">LEVEL UP</span><h1>{level.name||'Your progress'}</h1></div><div className="kp-level-points"><span aria-hidden="true">⚡</span><b>{total}</b><small>Momentum</small></div></header><svg viewBox="0 0 400 140" role="img" aria-label={`${total} Momentum. ${level.next_name?`${Math.max(0,target-total)} to ${level.next_name}`:'Top level reached'}`}><path d="M36 72H364" className="kp-level-rail"/><path d={`M36 72H${x}`} className="kp-level-earned"/>{[0,.25,.5,.75,1].map((f,i)=><g key={i}><circle cx={36+f*328} cy="72" r={i===0||i===4?12:7} className={f<=fraction?'is-earned':''}/><text x={36+f*328} y="112" textAnchor="middle">{Math.round(floor+(target-floor)*f)}</text></g>)}<circle cx={x} cy="72" r="17" className="kp-level-player"/><text x={x} y="78" textAnchor="middle" className="kp-level-star">★</text></svg><footer><span>🚩 {level.name||'Current level'}</span><b>{level.next_name?`🏆 ${level.next_name}`:'🏆 Top level'}</b></footer><p>{level.next_name?`${Math.max(0,target-total)} points to go`:'Top level reached'}</p></section>;
}
