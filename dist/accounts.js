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

/** Professional accounts discover private counterparties; private accounts can see both. */
export function canInteract(typeA,typeB) {
  return normalizeAccountType(typeA)!=='agent'||normalizeAccountType(typeB)!=='agent';
}
export const REPORT_REASON_OPTIONS = Object.freeze([
  Object.freeze({value:'suspected_agent',label:'Ingatlanközvetítő'}),
  Object.freeze({value:'misleading_content',label:'Hamis, megtévesztő tartalom'}),
  Object.freeze({value:'other_violation',label:'Egyéb szabálytalanság'})
]);
export function normalizeReportReason(value) {
  const reason=value==null?'suspected_agent':typeof value==='string'?value.trim():'';
  if(!REPORT_REASON_OPTIONS.some(option=>option.value===reason))throw new Error('Válassz egy érvényes jelentési okot.');
  return reason;
}
export function getReportReasons(ownerAccountType) {
  return normalizeAccountType(ownerAccountType)==='agent'?REPORT_REASON_OPTIONS.filter(option=>option.value!=='suspected_agent'):REPORT_REASON_OPTIONS;
}
export function normalizeIncomingPagination({offset=0,limit=50}={}) {
  if(!Number.isInteger(offset)||offset<0||offset>1000000||!Number.isInteger(limit)||limit<1||limit>100)throw new Error('Érvénytelen lapozási paraméter.');
  return {offset,limit};
}
