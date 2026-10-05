/** Carry the completed card forward while React reveals the next lead immediately.
 * The temporary visual is inert, has no duplicate IDs, and never blocks input. */
export function confirmLeadMotion(card:HTMLElement|null){
 if(!card||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 const box=card.getBoundingClientRect();if(box.width===0||box.height===0)return;
 const ghost=card.cloneNode(true) as HTMLElement;
 ghost.removeAttribute('id');ghost.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));
 ghost.inert=true;ghost.setAttribute('aria-hidden','true');ghost.classList.remove('kp-lead-arrival','kp-is-focused');
 Object.assign(ghost.style,{position:'fixed',left:`${box.left}px`,top:`${box.top}px`,width:`${box.width}px`,height:`${box.height}px`,margin:'0',pointerEvents:'none',zIndex:'1100',overflow:'hidden'});
 // Keep the same scoped styles without inserting into React's managed subtree.
 const layer=document.createElement('div');layer.className='shell kp-motion-layer';layer.setAttribute('aria-hidden','true');layer.inert=true;
 Object.assign(layer.style,{position:'fixed',inset:'0',pointerEvents:'none',background:'transparent',zIndex:'1100'});layer.appendChild(ghost);document.body.appendChild(layer);
 try{
  const animation=ghost.animate([{opacity:1,transform:'translate(0,0) scale(1)'},{opacity:0,transform:'translate(28px,-20px) scale(.97)'}],{duration:280,easing:'cubic-bezier(.2,.8,.2,1)',fill:'forwards'});
  void animation.finished.catch(()=>{}).finally(()=>layer.remove());
 }catch{layer.remove()}
}
