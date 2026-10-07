import React from 'react';
type Props={progress:any;points:number;ready:number;minutes:number;seconds:number;onMinutes:(n:number)=>void;onStart:()=>void;onEnd:()=>void};
/** Game presentation backed by the existing mission and session records. */
export function ContactMission({progress,points,ready,minutes,seconds,onMinutes,onStart,onEnd}:Props){
 const mission=progress?.mission;
 const target=Number(mission?.contacts_target)||0;
 const done=Math.max(0,Number(mission?.contacts)||0);
 const percent=target?Math.min(100,done/target*100):0;
 const complete=!!mission&&target>0&&done>=target;
 const clock=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
 return <section className={`kp-contact-quest ${complete?'is-complete':''}`} aria-label="Your contact mission">
  <header><div><span className="eyebrow">TODAY’S QUEST</span><h2>{complete?'Mission complete!':'Your next move.'}</h2></div><img src="/avatars/skye.png" alt="Skye"/></header>
  <div className="kp-quest-body"><div className="kp-quest-ring" role={target?'progressbar':'img'} aria-label={target?'Contacts completed today':'Mission progress unavailable'} aria-valuemin={target?0:undefined} aria-valuemax={target||undefined} aria-valuenow={target?Math.min(done,target):undefined} style={{'--quest-progress':`${percent}%`} as React.CSSProperties}><div><span aria-hidden="true">{complete?'🏆':'🎯'}</span><b>{target?`${done}/${target}`:'—'}</b><small>contacts</small></div></div><div className="kp-quest-stats"><div><span aria-hidden="true">⚡</span><b>+{points}</b><small>earned this session</small></div><div><span aria-hidden="true">🏪</span><b>{ready}</b><small>ready to contact</small></div>{mission&&target>0&&<p>{complete?'You did it.':`${Math.max(0,target-done)} to go`}{Number(mission.reward)>0&&!complete&&<span className="kp-quest-reward">🏅 +{mission.reward} on completion</span>}</p>}{!mission&&<p>Progress unavailable</p>}</div></div>
  <div className="kp-quest-timer"><div><span aria-hidden="true">⏱</span><b>{seconds?clock:'Focus sprint'}</b></div>{seconds?<button onClick={onEnd}>End sprint</button>:<div className="kp-sprint-controls"><div role="group" aria-label="Sprint length">{[20,30,60].map(n=><button key={n} aria-pressed={minutes===n} onClick={()=>onMinutes(n)}>{n}<small>min</small></button>)}</div><button className="primary" disabled={!minutes} onClick={onStart}><span aria-hidden="true">▶</span>Start</button></div>}</div>
 </section>;
}
