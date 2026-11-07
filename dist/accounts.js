/** Account declarations and like pricing shared by forms, adapters and the demo. */
export const ACCOUNT_TYPE_OPTIONS = Object.freeze([
  Object.freeze({value:'private',label:'Magánszemély'}),
  Object.freeze({value:'agent',label:'Ingatlanközvetítő'})
]);
export function normalizeAccountType(value,{strict=false}={}) {
  if(value==null)return 'private';
  const result=typeof value==='string'?value.trim().toLowerCase():'';
  if(ACCOUNT_TYPE_OPTIONS.some(option=>option.value===result))return result;
  if(strict)throw new Error('Válassz magánszemély vagy ingatlanközvetítő fióktípust.');
  return 'private';
}
export function likeCost(accountType,kind) {
  return kind==='property'?2:kind==='search'&&normalizeAccountType(accountType)==='agent'?1:0;
}
