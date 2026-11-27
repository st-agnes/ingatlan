/** Shared presentation for expressing interest; billing still uses ordinary decisions. */
export const INTEREST_LABEL = 'Vegyük fel a kapcsolatot!';
export const PASS_LABEL = 'Nem az igazi';
export const INTEREST_SENT_MESSAGE = 'Elküldtük érdeklődésedet! Most a másik félen a sor, hogy felvegyétek a kapcsolatot.';

const escapeAttribute = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

/** A telephone handset and a separate message bubble remain legible at button size. */
export function interestIconMarkup(className = '') {
  return `<svg${className ? ` class="${escapeAttribute(className)}"` : ''} data-icon="contact" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path data-part="phone" d="M8.5 13.5a12 12 0 0 0 3.9 3.1l1.4-1.4a1 1 0 0 1 1.1-.2l3 1.3a1 1 0 0 1 .6.9V20a1 1 0 0 1-1.1 1A16 16 0 0 1 2 5.6 1 1 0 0 1 3 4.5h2.7a1 1 0 0 1 .9.6l1.3 3a1 1 0 0 1-.2 1.1l-1.4 1.4a12 12 0 0 0 2.2 2.9Z"/><path data-part="message" d="M12 2h9a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-4l-3 2v-2h-2a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1ZM14 5h5M14 8h3"/></svg>`;
}

/** One shared two-choice presentation for discovery, listing pages and incoming interests. */
export function decisionDockMarkup({className='',passAction='pass',likeAction='like',data={},passData={},likeData={},
  passClass='',likeClass='',disabled=false,passDisabled=disabled,likeDisabled=disabled,decision=null,cost=0,
  message='',messageClass='',label='Döntés a hirdetésről'}={}) {
  const selected=['liked','passed'].includes(decision)?decision:null,terminal=!!selected;
  const charge=Number.isFinite(Number(cost))?Math.max(0,Number(cost)):0;
  const attributes=values=>Object.entries(values).filter(([key])=>/^[a-z][a-z0-9-]*$/.test(key))
    .map(([key,value])=>` data-${key}="${escapeAttribute(value)}"`).join('');
  const button=(liked,action,extra,extraClass,unavailable)=>`<button type="button" class="decision${liked?' like':''}${extraClass?' '+escapeAttribute(extraClass):''}${selected===(liked?'liked':'passed')?' is-selected':''}" data-action="${escapeAttribute(action)}"${attributes({...data,...extra})} aria-label="${escapeAttribute(liked?INTEREST_LABEL+(charge?', '+charge+' kredit':''):PASS_LABEL)}" aria-pressed="${selected===(liked?'liked':'passed')}"${unavailable||terminal?' disabled':''}>${liked?interestIconMarkup():'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M6 18 18 6"/></svg>'}</button>`;
  return `<div class="decision-dock${className?' '+escapeAttribute(className):''}" role="group" aria-label="${escapeAttribute(label)}"${selected?` data-decision="${selected}"`:''}>${message?`<p class="decision-dock-message${messageClass?' '+escapeAttribute(messageClass):''}" role="status">${escapeAttribute(message)}</p>`:''}<div class="card-actions">${button(false,passAction,passData,passClass,passDisabled)}${button(true,likeAction,likeData,likeClass,likeDisabled)}</div><div class="decision-labels"><span class="decision-pass-caption"><span>${PASS_LABEL}</span>${selected==='passed'?'<small class="decision-choice-mark">Ezt választottad</small>':''}</span><span class="decision-like-caption"><span>${INTEREST_LABEL}</span>${charge?`<small>${charge} kredit</small>`:''}${selected==='liked'?'<small class="decision-choice-mark">Ezt választottad</small>':''}</span></div></div>`;
}
