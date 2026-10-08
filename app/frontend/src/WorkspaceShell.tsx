import React from 'react';
import {CampaignPicker} from './CampaignPicker';
import {Icon,pageName} from './AppExperience';

const destinations=[{page:'Home',label:'Discover',icon:'search'},{page:'Saved',label:'Saved',icon:'bookmark'},{page:'Up Next',label:'Contact',icon:'phone'},{page:'Profile',label:'Profile',icon:'profile'}];
type Props={page:string;onNavigate:(page:string)=>void;campaign:string;campaigns:any[];onCampaign:(id:string)=>void;onCreated?:(id:string,rows:any[])=>void;menuOpen:boolean;onMenu:()=>void;blocked:boolean;children:React.ReactNode};
export function WorkspaceShell({page,onNavigate,campaign,campaigns,onCampaign,onCreated,menuOpen,onMenu,blocked,children}:Props){
 const home=page==='Home'||page==='Lead Generator';
 const navigation=(mobile=false)=><nav className={mobile?'bottom-nav':'kp-primary-nav'} aria-label={mobile?'Mobile workspace':'Workspace'} inert={blocked}>{destinations.map(d=><button key={d.page} aria-label={d.label} aria-current={(page===d.page||(d.page==='Home'&&['Prospects','Lead Generator'].includes(page)))?'page':undefined} onClick={()=>onNavigate(d.page)}><Icon name={d.icon}/><span>{d.label}</span></button>)}</nav>;
 return <div id="kp-sales-app" className={`shell kp-ui ${home?'kp-discovery-home':''}`}>
  <a className="kp-skip-link" href="#kp-main">Skip to content</a>
  <aside className="kp-sidebar" inert={blocked}><div className="kp-wordmark"><img src="/kp-logo.png" alt="KP"/><span>SALES OS</span></div>{navigation()}<div className="kp-sidebar-footer"><div className="kp-wave" aria-hidden="true"/><p>Find businesses.<br/>Start conversations.<br/>Create what’s next.</p></div></aside>
  <main id="kp-main" className="kp-main" inert={blocked} tabIndex={-1}><header className="kp-topbar"><div className="kp-mobile-wordmark"><img src="/kp-logo.png" alt="KP"/><span>SALES OS</span></div>{!home&&page!=='Saved'&&<h1>{pageName(page)}</h1>}{!home&&!['Saved','Profile'].includes(page)&&<div className="kp-campaign"><CampaignPicker campaign={campaign} campaigns={campaigns} onCampaign={onCampaign} onCreated={onCreated}/></div>}<button className="kp-profile-toggle" aria-label="Open your profile" onClick={()=>onNavigate('Profile')}><Icon name="profile"/></button><button className="kp-menu-toggle" aria-label="Open navigation" aria-expanded={menuOpen} onClick={onMenu}><Icon name="menu"/></button></header>{children}</main>{navigation(true)}
 </div>;
}
