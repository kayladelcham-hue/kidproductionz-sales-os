import React from 'react';
import {Icon,pageName} from './AppExperience';

const destinations=[{page:'Home',label:'Home',icon:'home'},{page:'Prospects',label:'Potential customers',icon:'people'},{page:'Up Next',label:'Contact',icon:'sell'},{page:'Leads',label:'Pipeline',icon:'queue'},{page:'More',label:'More',icon:'menu'}];
type Props={page:string;onNavigate:(page:string)=>void;campaign:string;campaigns:any[];onCampaign:(id:string)=>void;menuOpen:boolean;onMenu:()=>void;blocked:boolean;children:React.ReactNode};
export function WorkspaceShell({page,onNavigate,campaign,campaigns,onCampaign,menuOpen,onMenu,blocked,children}:Props){
 const home=page==='Home'||page==='Lead Generator';
 const navigation=(mobile=false)=><nav className={mobile?'bottom-nav':'kp-primary-nav'} aria-label={mobile?'Mobile workspace':'Workspace'} inert={blocked}>{destinations.map(d=><button key={d.page} aria-label={d.label} aria-current={page===d.page?'page':undefined} onClick={()=>onNavigate(d.page)}><Icon name={d.icon}/><span>{mobile&&d.page==='Prospects'?'Find':mobile&&d.page==='Leads'?'Deals':d.label}</span></button>)}</nav>;
 return <div id="kp-sales-app" className={`shell kp-ui ${home?'kp-discovery-home':''}`}>
  <a className="kp-skip-link" href="#kp-main">Skip to content</a>
  <aside className="kp-sidebar" inert={blocked}><div className="kp-wordmark"><img src="/kp-logo.png" alt="KP"/><span>SALES OS</span></div>{navigation()}<div className="kp-sidebar-footer"><div className="kp-wave" aria-hidden="true"/><p>Find businesses.<br/>Start conversations.<br/>Create what’s next.</p></div></aside>
  <main id="kp-main" className="kp-main" inert={blocked} tabIndex={-1}><header className="kp-topbar"><div className="kp-mobile-wordmark"><img src="/kp-logo.png" alt="KP"/><span>SALES OS</span></div>{!home&&<h1>{pageName(page)}</h1>}{!home&&<label className="kp-campaign"><span className="kp-sr-only">Current campaign</span><select value={campaign} onChange={e=>onCampaign(e.target.value)}>{campaigns.map(c=><option key={c.campaign_id} value={c.campaign_id}>{c.name||c.campaign_id}</option>)}</select></label>}<button className="kp-menu-toggle" aria-label="Open navigation" aria-expanded={menuOpen} onClick={onMenu}><Icon name="menu"/></button></header>{children}</main>{navigation(true)}
 </div>;
}
