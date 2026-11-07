import test from 'node:test';
import assert from 'node:assert/strict';
import {ACCOUNT_TYPE_OPTIONS,normalizeAccountType,likeCost} from '../dist/accounts.js';

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
