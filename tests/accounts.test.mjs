import test from 'node:test';
import assert from 'node:assert/strict';
import {ACCOUNT_TYPE_OPTIONS,normalizeAccountType,likeCost,canInteract,REPORT_REASON_OPTIONS,getReportReasons,normalizeReportReason,normalizeIncomingPagination} from '../dist/accounts.js';

test('account choices have stable API codes and unambiguous Hungarian labels',()=>{
 assert.deepEqual(ACCOUNT_TYPE_OPTIONS,[{value:'private',label:'Magánszemély'},{value:'agent',label:'Ingatlanközvetítő'}]);
 assert.ok(Object.isFrozen(ACCOUNT_TYPE_OPTIONS));assert.ok(ACCOUNT_TYPE_OPTIONS.every(Object.isFrozen));
});
test('legacy missing declarations default to private while invalid registration choices fail',()=>{
 for(const value of [undefined,null])assert.equal(normalizeAccountType(value,{strict:true}),'private');
 assert.equal(normalizeAccountType('agent'),'agent');assert.equal(normalizeAccountType(' PRIVATE ',{strict:true}),'private');
 for(const value of ['',false,1,{},'broker','Magánszemély'])assert.throws(()=>normalizeAccountType(value,{strict:true}),/fióktípust/);
 assert.equal(normalizeAccountType('future-unknown-role'),'private');
});
test('pricing depends on the acting account and active entity, without adding agent and seller fees',()=>{
 for(const type of ['private','agent',undefined])assert.equal(likeCost(type,'property'),2);
 assert.equal(likeCost('agent','search'),1);assert.equal(likeCost('private','search'),0);
 assert.equal(likeCost(undefined,'search'),0);assert.equal(likeCost('agent',undefined),0);
});

test('account interaction rules are symmetric and exclude only two declared agents',()=>{
 for(const left of ['private','agent',undefined])for(const right of ['private','agent',undefined])assert.equal(canInteract(left,right),!(left==='agent'&&right==='agent'));
 assert.equal(canInteract(' AGENT ','agent'),false);
});
test('report choices have stable codes and permit disguised-agent reports only for private owners',()=>{
 assert.deepEqual(REPORT_REASON_OPTIONS,[{value:'suspected_agent',label:'A hirdető ingatlanközvetítő'},{value:'misleading_content',label:'Hamis, megtévesztő tartalom'},{value:'no_longer_current',label:'A hirdetés már nem aktuális'},{value:'duplicate_listing',label:'Duplikált hirdetés'},{value:'other_violation',label:'Egyéb szabálytalanság'}]);
 assert.ok(Object.isFrozen(REPORT_REASON_OPTIONS));assert.ok(REPORT_REASON_OPTIONS.every(Object.isFrozen));
 assert.deepEqual(getReportReasons('private'),REPORT_REASON_OPTIONS);assert.deepEqual(getReportReasons('agent'),REPORT_REASON_OPTIONS.slice(1));
 for(const value of [undefined,null])assert.equal(normalizeReportReason(value),'suspected_agent');
 for(const value of ['suspected_agent','misleading_content','other_violation','no_longer_current','duplicate_listing'])assert.equal(normalizeReportReason(value),value);
 for(const value of ['',false,'unknown','Misleading_Content'])assert.throws(()=>normalizeReportReason(value),/jelentési ok/);
});
test('incoming pagination validates bounds without silently truncating or coercing invalid values',()=>{
 assert.deepEqual(normalizeIncomingPagination(),{offset:0,limit:50});assert.deepEqual(normalizeIncomingPagination({offset:1000000,limit:100}),{offset:1000000,limit:100});
 for(const value of [{offset:-1},{offset:1000001},{offset:1.5},{offset:'0'},{limit:0},{limit:101},{limit:1.5},{limit:'10'}])assert.throws(()=>normalizeIncomingPagination(value),/lapozási/);
});
