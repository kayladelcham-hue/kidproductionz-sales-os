import React from 'react';
import {Icon} from './AppExperience';

/** Recorded evidence only; these tiles never imply buying intent. */
export function FitSignals({assessment,compact=false}:{assessment?:any;compact?:boolean}){
 const evidence=assessment||{};
 const matches=evidence.matches||[],contacts=evidence.contact_paths||[],unknowns=evidence.missing_information||[];
 return <dl className={`kp-fit-signals ${compact?'is-compact':''}`}>
  <div className="is-fit"><dt><Icon name="search"/>Match</dt><dd>
   {evidence.label==='Outside criteria'?'Check the fit':matches.length?`${matches.length} match${matches.length===1?'':'es'}`:'Not confirmed'}
   <small>{matches[0]||'Evidence needed'}</small>
  </dd></div>
  <div className="is-contact"><dt><Icon name="people"/>Contact</dt><dd>
   {contacts.length?contacts.join(' + '):'Not listed'}
   <small>{contacts.length?'Unverified':'No contact details recorded'}</small>
  </dd></div>
  <div className="is-unknown"><dt><span aria-hidden="true">?</span>Missing</dt><dd>
   {unknowns.length?`${unknowns.length} to check`:'Review evidence'}
   <small>{unknowns[0]||'Check the full business details'}</small>
  </dd></div>
 </dl>;
}
