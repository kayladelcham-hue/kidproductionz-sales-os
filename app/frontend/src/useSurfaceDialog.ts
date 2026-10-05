import {useEffect,useRef} from 'react';

/** Trap keyboard focus, inert background siblings, and restore the trigger.
 * Walk the ancestor path so dialogs can remain inside the existing page tree. */
export function useSurfaceDialog(open:boolean,close:()=>void){
 const ref=useRef<HTMLDivElement>(null),closeRef=useRef(close);closeRef.current=close;
 useEffect(()=>{
  const el=ref.current;if(!open||!el)return;
  const previous=document.activeElement as HTMLElement|null;
  const inerted:Array<[HTMLElement,boolean]>=[];
  let branch:HTMLElement=el;
  while(branch.parentElement&&branch!==document.body){
   for(const sibling of Array.from(branch.parentElement.children))if(sibling!==branch&&sibling instanceof HTMLElement){inerted.push([sibling,sibling.inert]);sibling.inert=true}
   branch=branch.parentElement;
  }
  const targets=()=>Array.from(el.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(item=>item.getClientRects().length>0&&!item.closest('[inert]'));
  (targets().find(item=>!item.classList.contains('lc-modal-backdrop'))||targets()[0])?.focus();
  const key=(event:KeyboardEvent)=>{
   if(el.closest('[inert]'))return;
   if(event.key==='Escape'){event.preventDefault();closeRef.current()}
   if(event.key==='Tab'){const items=targets(),first=items[0],last=items[items.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}}
  };
  document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('keydown',key);inerted.forEach(([item,value])=>{item.inert=value});if(previous?.isConnected&&!previous.closest('[inert]'))previous.focus()};
 },[open]);
 return ref;
}
