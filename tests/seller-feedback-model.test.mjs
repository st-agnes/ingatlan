import test from 'node:test';
import assert from 'node:assert/strict';
import {createModel,STORAGE_KEY} from '../dist/model.js';
import {FEEDBACK_OPTIONS} from '../dist/feedback.js';
const START='2026-11-10T12:00:00.000Z',END='2026-11-24T12:00:00.000Z';
const REQUEST='11111111-1111-4111-8111-111111111111',NEXT='22222222-2222-4222-8222-222222222222';
const clone=value=>JSON.parse(JSON.stringify(value));
function fixture(edit=()=>{}){
 const values=new Map();let fail=false,time=START;
 const storage={getItem:key=>values.get(key)||null,setItem:(key,value)=>{if(fail)throw Error('full');values.set(key,value);}};
 const seed=createModel(storage,()=>time);seed.buyDemoCredits(100);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));edit(raw);storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 return {storage,model:createModel(storage,()=>time),at:value=>{time=value;},fail:value=>{fail=value;},reload:()=>createModel(storage,()=>time),raw:()=>JSON.parse(storage.getItem(STORAGE_KEY)),
  edit:fn=>{const next=JSON.parse(storage.getItem(STORAGE_KEY));fn(next);storage.setItem(STORAGE_KEY,JSON.stringify(next));}};
}
function buyerFixture(edit=()=>{}){
 return fixture(raw=>{
  const template=raw.properties.find(item=>item.id==='p1'),search=raw.searches.find(item=>item.id==='own-s1');
  raw.properties=Array.from({length:65},(_,index)=>({...clone(template),id:'ad-'+index,ownerId:'u1'}));
  raw.properties.push({...clone(template),id:'own-ad',ownerId:'me'});
  raw.searches=[{...search,id:'own-s1',ownerId:'me'},{...clone(search),id:'own-s2',ownerId:'me'}];raw.active={kind:'search',id:'own-s1'};
  raw.decisions=[];raw.matches=[];raw.ledger=[];raw.notifications=[];
  raw.feedbackPackages=[{id:'campaign',propertyId:'ad-19',ownerId:'u1',requestId:REQUEST,size:10,receivedCount:0,enabled:true,createdAt:START,expiresAt:END,refundedAt:null,refundedCredits:0}];
  raw.feedbackInvitations=[];raw.propertyImpressions=[];for(const user of raw.users)user.feedbackPassCounter=0;
  edit(raw);
 });
}
const card=(id,searchId='own-s1')=>({pair:{propertyId:id,searchId}});
const pass=(model,id,searchId)=>model.decide(card(id,searchId),false);
function promptAtTwenty(t){for(let i=0;i<19;i++)assert.equal(pass(t.model,'ad-'+i).feedbackPrompt,null);return pass(t.model,'ad-19').feedbackPrompt;}

test('legacy v3 reads add feedback collections without rewriting existing saved business data',()=>{
 const t=fixture(raw=>{for(const key of ['feedbackPackages','feedbackInvitations','propertyImpressions'])delete raw[key];for(const user of raw.users)delete user.feedbackPassCounter;});
 const before=t.storage.getItem(STORAGE_KEY),state=t.model.getState();
 assert.equal(state.user.feedbackPassCounter,0);assert.equal(t.model.pendingFeedback(),null);assert.equal(t.model.getPropertyInsights('own-p1').stats.uniqueViewers,0);
 assert.equal(t.storage.getItem(STORAGE_KEY),before);assert.equal(state.credits,t.raw().credits);
});

test('package purchase is owner-only, charged once, validates size/key/balance and prevents overlapping periods',()=>{
 const t=fixture(),m=t.model,before=m.getState().credits;
 for(const size of [0,1,9,11,100,'10'])assert.throws(()=>m.buyFeedbackPackage('own-p1',size,REQUEST));
 assert.throws(()=>m.buyFeedbackPackage('own-p1',10,'bad'));assert.throws(()=>m.buyFeedbackPackage('p1',10,REQUEST),/nem található/);
 const bought=m.buyFeedbackPackage('own-p1',10,REQUEST);assert.equal(bought.charged,10);assert.equal(bought.credits,before-10);assert.equal(bought.package.enabled,true);assert.equal(bought.package.expiresAt,END);
 assert.equal(m.buyFeedbackPackage('own-p1',10,REQUEST).charged,0);assert.equal(m.getState().credits,before-10);
 assert.throws(()=>m.buyFeedbackPackage('own-p1',20,REQUEST),/azonosítót/);assert.throws(()=>m.buyFeedbackPackage('own-p1',10,NEXT),/aktív/);
 assert.equal(m.getPropertyInsights('own-p1').activePackage.id,bought.package.id);assert.equal(m.getState().ledger.filter(item=>item.feedbackPackageId===bought.package.id).length,1);
 assert.equal(typeof m.setFeedbackEnabled,'undefined','Packages cannot be paused or resumed by their owner.');
 const poor=fixture(raw=>{raw.credits=9;});const prior=poor.storage.getItem(STORAGE_KEY);assert.throws(()=>poor.model.buyFeedbackPackage('own-p1',10,REQUEST),/elegendő/);assert.equal(poor.storage.getItem(STORAGE_KEY),prior);
});

test('legacy paused packages remain continuously eligible without changing their charge or expiry',()=>{
 const t=fixture(),bought=t.model.buyFeedbackPackage('own-p1',10,REQUEST),balance=t.model.getState().credits;
 t.edit(raw=>{raw.feedbackPackages[0].enabled=false;});const saved=t.storage.getItem(STORAGE_KEY),again=t.reload(),page=again.getPropertyInsights('own-p1');
 assert.equal(page.activePackage.enabled,true);assert.equal(page.activePackage.status,'active');assert.equal(page.activePackage.id,bought.package.id);assert.equal(page.activePackage.expiresAt,END);
 assert.equal(again.getState().credits,balance);assert.equal(again.getState().ledger.filter(item=>item.feedbackPackageId===bought.package.id).length,1);assert.equal(t.storage.getItem(STORAGE_KEY),saved,'Reading a legacy package does not rewrite saved business data.');
 const buyer=buyerFixture(raw=>{raw.feedbackPackages[0].enabled=false;});assert.ok(promptAtTwenty(buyer),'A legacy disabled flag cannot suppress the next ordinary eligible request.');
 t.at(END);assert.equal(again.getPropertyInsights('own-p1').activePackage,null);assert.equal(again.getState().credits,balance+10);assert.equal(again.getState().ledger.filter(item=>item.refundedFeedbackPackageId===bought.package.id).length,1);
});

test('failed package storage cannot debit credits or leave a package or ledger entry behind',()=>{
 const t=fixture(),before=t.model.getState();t.fail(true);assert.throws(()=>t.model.buyFeedbackPackage('own-p1',10,REQUEST),/tárhelye/);t.fail(false);
 assert.deepEqual(t.model.getState(),before);assert.equal(t.model.getPropertyInsights('own-p1').packages.length,0);
});

test('only an explicitly displayed eligible property counts, once per person across active search profiles',()=>{
 const t=buyerFixture(),m=t.model,stored=t.storage.getItem(STORAGE_KEY);m.feed();m.recommendations();assert.equal(t.storage.getItem(STORAGE_KEY),stored,'Background feed reads are not impressions');
 assert.deepEqual(m.recordImpression('ad-0','own-s1'),{recorded:true});assert.deepEqual(m.recordImpression('ad-0','own-s1'),{recorded:false});
 m.activate('search','own-s2');assert.deepEqual(m.recordImpression('ad-0','own-s2'),{recorded:false});assert.equal(t.raw().propertyImpressions.length,1);
 assert.throws(()=>m.recordImpression('ad-1','own-s1'));assert.throws(()=>m.recordImpression('own-ad','own-s2'));
 t.edit(raw=>{raw.properties.find(item=>item.id==='ad-1').locationId='city:Debrecen';});const again=t.reload();assert.throws(()=>again.recordImpression('ad-1','own-s2'));assert.equal(t.raw().propertyImpressions.length,1);
});

test('statistics count people rather than profiles and conversion only among displayed viewers',()=>{
 const t=fixture(raw=>{
  const search=raw.searches[0];raw.searches=['u1','u1','u2','u3','u5'].map((ownerId,index)=>({...clone(search),id:'query-'+index,ownerId}));
  raw.decisions=[0,1,2].map(index=>({id:'buy-'+index,actorKind:'search',propertyId:'own-p1',searchId:'query-'+index,liked:true}));
  raw.decisions.push(...[0,2,3].map(index=>({id:'sell-'+index,actorKind:'property',propertyId:'own-p1',searchId:'query-'+index,liked:true})));
  raw.matches=[0,1,4].map(index=>({id:'pair-'+index,propertyId:'own-p1',searchId:'query-'+index}));
  raw.propertyImpressions=[{propertyId:'own-p1',viewerUserId:'u1'},{propertyId:'own-p1',viewerUserId:'u2'}];
 });
 assert.deepEqual(t.model.getPropertyInsights('own-p1').stats,{uniqueViewers:2,buyerLikes:2,sellerLikes:3,matchedViewers:1,matchRate:50});
 assert.throws(()=>t.model.getPropertyInsights('p1'));t.model.deleteEntity('property','own-p1');assert.equal(t.model.getPropertyInsights('own-p1').stats.uniqueViewers,2);
});

test('a buyer receives at most one durable request per twenty new passes and declining is not feedback',()=>{
 const t=buyerFixture(),prompt=promptAtTwenty(t);assert.ok(prompt);assert.equal(prompt.title,'Segíts Péternek egy visszajelzéssel');assert.equal(prompt.options.length,8);
 assert.equal(t.raw().users.find(user=>user.id==='me').feedbackPassCounter,0);assert.equal(t.reload().pendingFeedback().id,prompt.id);
 const before=t.model.getState().credits;assert.deepEqual(t.model.answerFeedback(prompt.id,'decline'),{accepted:false,alreadyAnswered:false});assert.equal(t.model.pendingFeedback(),null);
 assert.deepEqual(t.model.answerFeedback(prompt.id,'lighting'),{accepted:false,alreadyAnswered:true});assert.equal(t.raw().feedbackPackages[0].receivedCount,0);assert.equal(t.model.getState().credits,before);
 for(let i=20;i<39;i++)assert.equal(pass(t.model,'ad-'+i).feedbackPrompt,null);
 t.edit(raw=>{raw.feedbackPackages.push({...clone(raw.feedbackPackages[0]),id:'campaign-2',propertyId:'ad-39',requestId:NEXT});});
 const second=t.reload();assert.ok(pass(second,'ad-39').feedbackPrompt);assert.equal(t.raw().feedbackInvitations.length,2);
});

test('one human cannot be invited twice by the same campaign after declining, expiring or changing profiles',()=>{
 for(const outcome of ['decline','expire','other']){
  const t=buyerFixture(),prompt=promptAtTwenty(t);
  if(outcome==='expire')t.at('2026-11-10T12:16:00.000Z');else t.model.answerFeedback(prompt.id,outcome);
  t.edit(raw=>{raw.users.find(user=>user.id==='me').feedbackPassCounter=20;raw.active={kind:'search',id:'own-s2'};});
  assert.equal(pass(t.reload(),'ad-19','own-s2').feedbackPrompt,null);assert.equal(t.raw().feedbackInvitations.length,1);
 }
});

test('valid responses count once, remain anonymous to the seller, and survive legacy flags, archive and reload',()=>{
 const t=buyerFixture(),prompt=promptAtTwenty(t);t.edit(raw=>{raw.feedbackPackages[0].enabled=false;raw.properties.find(item=>item.id==='ad-19').archived=true;});
 const buyer=t.reload();assert.equal(buyer.pendingFeedback().id,prompt.id);assert.deepEqual(buyer.answerFeedback(prompt.id,'layout'),{accepted:true,alreadyAnswered:false});
 assert.deepEqual(buyer.answerFeedback(prompt.id,'other'),{accepted:true,alreadyAnswered:true});assert.equal(t.raw().feedbackPackages[0].receivedCount,1);
 t.edit(raw=>{raw.userId='u1';raw.active={kind:'property',id:'ad-19'};});const owner=t.reload(),insights=owner.getPropertyInsights('ad-19');
 assert.equal(insights.feedback.total,1);assert.equal(insights.feedback.items[0].reason,'layout');assert.equal(insights.feedback.reasonCounts.find(item=>item.reason==='layout').count,1);
 assert.deepEqual(Object.keys(insights.feedback.items[0]).sort(),['createdAt','id','label','reason']);assert.doesNotMatch(JSON.stringify(insights.feedback),/buyerId|searchId|decisionId|anna@example|Nagy Anna/);
 assert.throws(()=>owner.answerFeedback(prompt.id,'other'),/nem található/);assert.throws(()=>buyer.answerFeedback(prompt.id,'not-a-choice'));
});

test('pending reservations cap the package and an expired reservation releases capacity without counting an answer',()=>{
 const t=buyerFixture(raw=>{raw.feedbackPackages[0].receivedCount=9;raw.users.find(user=>user.id==='me').feedbackPassCounter=19;});
 const first=pass(t.model,'ad-19').feedbackPrompt;assert.ok(first);
 t.edit(raw=>{raw.userId='u3';raw.users.find(user=>user.id==='u3').feedbackPassCounter=19;raw.searches.push({...clone(raw.searches[0]),id:'other-query',ownerId:'u3'});raw.active={kind:'search',id:'other-query'};});
 const other=t.reload();assert.equal(pass(other,'ad-19','other-query').feedbackPrompt,null);assert.equal(t.raw().feedbackInvitations.length,1);
 t.at('2026-11-10T12:16:00.000Z');t.edit(raw=>{raw.searches.push({...clone(raw.searches.find(item=>item.id==='other-query')),id:'second-query'});raw.active={kind:'search',id:'second-query'};});
 const later=t.reload(),second=pass(later,'ad-19','second-query').feedbackPrompt;assert.ok(second);assert.deepEqual(later.answerFeedback(second.id,'lighting'),{accepted:true,alreadyAnswered:false});
 assert.equal(t.raw().feedbackPackages[0].receivedCount,10);assert.equal(later.pendingFeedback(),null);
 t.edit(raw=>{raw.userId='me';});assert.deepEqual(t.reload().answerFeedback(first.id,'other'),{accepted:false,alreadyAnswered:false});assert.equal(t.raw().feedbackPackages[0].receivedCount,10);
});

test('missing responses refund once at fourteen days, notify the owner and allow a new package only after expiry',()=>{
 const t=fixture(),m=t.model,start=m.getState().credits,pkg=m.buyFeedbackPackage('own-p1',10,REQUEST).package;
 t.edit(raw=>{raw.feedbackPackages[0].receivedCount=2;});const again=t.reload();t.at('2026-11-24T11:59:59.999Z');assert.equal(again.getState().credits,start-10);
 t.at(END);const insights=again.getPropertyInsights('own-p1');assert.equal(insights.activePackage,null);assert.equal(insights.packages[0].refundedCredits,8);assert.equal(again.getState().credits,start-2);
 assert.equal(again.notifications().items.filter(item=>item.feedbackPackageId===pkg.id).length,1);assert.equal(again.getState().ledger.filter(item=>item.refundedFeedbackPackageId===pkg.id).length,1);
 assert.equal(t.reload().getState().credits,start-2);assert.equal(again.buyFeedbackPackage('own-p1',10,REQUEST).charged,0);
 assert.equal(again.buyFeedbackPackage('own-p1',20,NEXT).charged,20);assert.equal(again.getPropertyInsights('own-p1').activePackage.size,20);
});

test('completed packages still block replacement until the end and generate no unused-credit refund',()=>{
 const t=fixture();t.model.buyFeedbackPackage('own-p1',10,REQUEST);t.edit(raw=>{raw.feedbackPackages[0].receivedCount=10;});const m=t.reload(),balance=m.getState().credits;
 assert.equal(m.getPropertyInsights('own-p1').activePackage.status,'completed');assert.throws(()=>m.buyFeedbackPackage('own-p1',10,NEXT),/aktív/);
 t.at(END);assert.equal(m.getState().credits,balance);assert.equal(m.notifications().total,0);assert.equal(m.getState().ledger.filter(item=>item.type==='feedback_refund').length,0);
});

test('expired prompts reject late answers and a failed refund commit preserves the original balance and package',()=>{
 const t=buyerFixture(),prompt=promptAtTwenty(t);t.at('2026-11-10T12:16:00.000Z');assert.equal(t.model.pendingFeedback(),null);assert.deepEqual(t.model.answerFeedback(prompt.id,'other'),{accepted:false,alreadyAnswered:false});assert.equal(t.raw().feedbackPackages[0].receivedCount,0);
 const owner=fixture();owner.model.buyFeedbackPackage('own-p1',10,REQUEST);const before=owner.storage.getItem(STORAGE_KEY);owner.at(END);owner.fail(true);assert.throws(()=>owner.model.getState(),/tárhelye/);owner.fail(false);assert.equal(owner.storage.getItem(STORAGE_KEY),before);assert.equal(owner.reload().getState().credits,124);
});
