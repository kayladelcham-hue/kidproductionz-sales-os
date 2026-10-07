import React,{useState} from 'react';
import {createPortal} from 'react-dom';
import {useSurfaceDialog} from './useSurfaceDialog';
import {Icon} from './AppExperience';
/** Secondary tools leave the visual stage and remain reachable in a keyboard-safe dialog. */
export function DiscoveryTools({children}:{children:React.ReactNode}){
 const [open,setOpen]=useState(false);const ref=useSurfaceDialog(open,()=>setOpen(false));
 return <><div className="kp-discovery-utilities"><button onClick={()=>setOpen(true)}><Icon name="search"/>Searches & saved businesses</button></div>{open&&createPortal(<div className="dw-modal" ref={ref} role="dialog" aria-modal="true" aria-labelledby="kp-discovery-tools-title"><section className="dw-detail"><header><h2 id="kp-discovery-tools-title">Your discovery workspace</h2><button aria-label="Close discovery tools" onClick={()=>setOpen(false)}>×</button></header><div onClick={e=>{if((e.target as HTMLElement).closest('button[data-close-tools]'))setOpen(false)}}>{children}</div></section></div>,document.body)}</>;
}
