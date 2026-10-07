import React,{useEffect,useState} from 'react';

function logoUrl(value:unknown){
  try{const url=new URL(String(value||''));return ['https:','http:'].includes(url.protocol)&&!url.username?url.href:undefined}catch{return undefined}
}
function industryIcon(category:string){
  const text=category.toLowerCase();
  if(/restaurant|cafe|café|food|bakery|bar\b/.test(text))return '🍽️';
  if(/salon|hair|barber/.test(text))return '✂️';
  if(/dental|dentist/.test(text))return '🦷';
  if(/real estate|property|realtor/.test(text))return '🏡';
  if(/hotel|hospitality|lodging/.test(text))return '🏨';
  if(/photograph|video|film/.test(text))return '📸';
  if(/fitness|gym|yoga/.test(text))return '💪';
  if(/retail|shop|store/.test(text))return '🛍️';
  if(/cleaning/.test(text))return '✨';
  return '🏢';
}

/** A record-provided logo or a clearly identified decorative industry avatar. */
export function BusinessHero({business,compact=false}:{business:any;compact?:boolean}){
  const url=logoUrl(business.logo_url);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{setFailed(false)},[business.id,url]);
  const hasLogo=!!url&&!failed;
  return <div className={`dw-business-hero ${compact?'is-compact':''}`}>
    <div className="dw-hero-halo" aria-hidden="true"/>
    <div className="dw-floating-avatar">
      {hasLogo?<img src={url} alt={`${business.name} logo from its record`} referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>:<span role="img" aria-label={`${business.category||'Business'} industry icon`}>{industryIcon(String(business.category||''))}</span>}
    </div>
    <small>{hasLogo?'Logo from business record':'Industry icon'}</small>
  </div>;
}
