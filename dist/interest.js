/** Shared presentation for expressing interest; billing still uses ordinary decisions. */
export const INTEREST_LABEL = 'Érdeklődöm';
export const PASS_LABEL = 'Nem az igazi';
export const INTEREST_SENT_MESSAGE = 'Elküldtük érdeklődésedet! Most a másik félen a sor, hogy felvegyétek a kapcsolatot.';

const escapeAttribute = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

/** A telephone handset and a separate message bubble remain legible at button size. */
export function interestIconMarkup(className = '') {
  return `<svg${className ? ` class="${escapeAttribute(className)}"` : ''} data-icon="contact" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path data-part="phone" d="M8.5 13.5a12 12 0 0 0 3.9 3.1l1.4-1.4a1 1 0 0 1 1.1-.2l3 1.3a1 1 0 0 1 .6.9V20a1 1 0 0 1-1.1 1A16 16 0 0 1 2 5.6 1 1 0 0 1 3 4.5h2.7a1 1 0 0 1 .9.6l1.3 3a1 1 0 0 1-.2 1.1l-1.4 1.4a12 12 0 0 0 2.2 2.9Z"/><path data-part="message" d="M12 2h9a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-4l-3 2v-2h-2a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1ZM14 5h5M14 8h3"/></svg>`;
}
