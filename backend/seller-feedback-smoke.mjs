/** Seller insights and paid feedback: real API proof against disposable loopback CI only. */
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {mkdir,readFile,writeFile,chmod} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';

const origin=new URL(process.argv[2]||'http://127.0.0.1:3000'),mode=process.argv[3]||'--setup';
if(process.env.CI!=='true'||origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback CI API.');
const fixturePath=resolve('.local/seller-feedback-fixture.json');
const reasons=['insufficient_information','layout','lighting','location','view','incorrect_parameters','other','decline'];
const labels=['Túl kevés információ van megosztva az ingatlanról','Nem tetszik az ingatlan elrendezése','Nem jók a fényviszonyok az ingatlanban','Az ingatlan elhelyezkedése nem szimpatikus','Nem tetszik, vagy nem látszik a képeken a kilátás az ablakokból','Az ingatlan nem felel meg a róla feltüntetett paramétereknek','Egyéb','Nem szeretnék válaszolni'];
async function api(path,{token,method='GET',body,status=200}={}){
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.ok((Array.isArray(status)?status:[status]).includes(response.status),`${method} ${path}: HTTP ${response.status}`);
 const text=await response.text();return response.status>=400||!text?null:JSON.parse(text);
}
async function save(f){await mkdir(dirname(fixturePath),{recursive:true});await writeFile(fixturePath,JSON.stringify(f),{mode:0o600});await chmod(fixturePath,0o600);}
const active=(token,kind,id)=>api('/me/active',{token,method:'PUT',body:{kind,id}});
const insight=(f,key='main',extra='')=>api(`/properties/${f.properties[key].id}/insights${extra}`,{token:f.tokens.seller});
const purchase=(token,p,size,requestId=randomUUID(),status=200)=>api(`/properties/${p.id}/feedback-packages`,{token,method:'POST',body:{size,requestId},status});
const removedToggle=(token,p,enabled)=>api(`/properties/${p.id}/feedback`,{token,method:'PUT',body:{enabled},status:[404,405]});
const answer=(token,id,reason,status=200)=>api(`/feedback/${id}`,{token,method:'POST',body:{reason},status});
const pending=token=>api('/feedback/pending',{token});
const decide=(token,p,s,liked=false,status=200)=>api('/decisions',{token,method:'POST',body:{propertyId:p.id,searchRequestId:s.id,liked},status});
const impression=(token,p,s,status=200)=>api('/impressions',{token,method:'POST',body:{propertyId:p.id,searchRequestId:s.id},status});
const criteria={title:'Pontos otthont keresünk a környéken',locationIds:['city:Kaszaper'],city:'Kaszaper',type:'Lakás',maxPrice:70000000,minArea:40,maxArea:90,minRooms:2,maxRooms:5,balcony:false,elevator:false};
const property={title:'Világos otthon a településen',locationId:'city:Kaszaper',city:'Kaszaper',type:'Lakás',price:55000000,area:65,rooms:3,wholeRooms:3,halfRooms:0,images:[],balcony:false,elevator:false,address:'Private feedback fixture street',description:'Private feedback fixture description'};
const createSearch=(token,title,overrides={})=>api('/searches',{token,method:'POST',body:{...criteria,title,...overrides},status:201});
const createProperty=(token,title)=>api('/properties',{token,method:'POST',body:{...property,title},status:201});
const zeroStats={uniqueViewers:0,buyerLikes:0,sellerLikes:0,matchedViewers:0,matchRate:0};
function assertPrompt(prompt,f,p){
 assert.ok(prompt?.id);assert.equal(prompt.propertyId,p.id);assert.equal(prompt.sellerFirstName,'Péter');
 assert.equal(prompt.title,'Segíts Péternek egy visszajelzéssel');assert.equal(prompt.question,'Miért nem tetszett az ingatlan?');
 assert.deepEqual(prompt.options.map(row=>row.value),reasons);assert.deepEqual(prompt.options.map(row=>row.label),labels);
 assert.ok(Date.parse(prompt.expiresAt)>Date.now());
 const raw=JSON.stringify(prompt);for(const value of ['Nagy Péter',f.emails.seller,f.phone,property.address,property.description])assert.equal(raw.includes(value),false,'Feedback prompts must not expose private seller data');
}
function assertAnonymousFeedback(value){
 if(Array.isArray(value)){value.forEach(assertAnonymousFeedback);return;}
 if(!value||typeof value!=='object')return;
 for(const [key,item]of Object.entries(value)){
  assert.ok(!['buyerId','buyerUserId','viewerUserId','searchId','searchRequestId','decisionId','ownerId','email','phone','contact','name','passwordHash'].includes(key),`Owner feedback exposed ${key}`);
  assertAnonymousFeedback(item);
 }
}
async function passFresh(f,p,title,key='buyer'){
 const s=await createSearch(f.tokens[key],title);await active(f.tokens[key],'search',s.id);
 const result=await decide(f.tokens[key],p,s);assert.equal(result.charged,0);return {result,s};
}
async function afterTwentyPasses(f,p,label){
 let result;
 for(let i=1;i<=20;i++){
  ({result}=await passFresh(f,p,`${label} ${i}`));
  if(i<20)assert.equal(result.feedbackPrompt??null,null,'A new prompt must not appear before about twenty further passes');
 }
 assertPrompt(result.feedbackPrompt,f,p);return result.feedbackPrompt;
}
const stable=page=>({stats:page.stats,feedback:page.feedback,activePackage:page.activePackage,packages:page.packages});

if(mode==='--setup'){
 const suffix=randomUUID(),f={tokens:{},ids:{},emails:{},properties:{},packages:{},requests:{},phone:'+36 30 555 0861'};
 for(const [key,name,accountType]of [['seller','Nagy Péter','private'],['buyer','Kovács Anna','private'],['other','Szabó Eszter','agent']]){
  const email=`feedback-${key}-${suffix}@example.test`,session=await api('/auth/register',{method:'POST',body:{name,email,password:'FeedbackSmoke2026!',phone:f.phone,accountType}});
  f.tokens[key]=session.accessToken;f.ids[key]=session.user.id;f.emails[key]=email;
 }
 for(const key of ['main',...Array.from({length:7},(_,i)=>`reason${i+1}`),'pendingExpiry','plan20','plan50','capacity'])f.properties[key]=await createProperty(f.tokens.seller,`Visszajelzési próba ${key}`);
 f.ownProperty=await createProperty(f.tokens.buyer,'Saját ingatlan a jogosultsági próbához');
 f.otherProperties=[await createProperty(f.tokens.other,'Első utolsókredites próba'),await createProperty(f.tokens.other,'Második utolsókredites próba')];
 f.searchA=await createSearch(f.tokens.buyer,'Első saját keresés');f.searchB=await createSearch(f.tokens.buyer,'Második saját keresés');
 f.otherSearch=await createSearch(f.tokens.other,'Másik ember keresése');f.sellerSearch=await createSearch(f.tokens.seller,'Saját ingatlan kizárása');
 await active(f.tokens.buyer,'search',f.searchA.id);await active(f.tokens.other,'search',f.otherSearch.id);
 const before=await insight(f);assert.deepEqual(before.stats,zeroStats);assert.equal(before.feedback.total,0);assert.equal(before.activePackage,null);
 assert.deepEqual(before.packageSizes,[10,20,50]);assert.equal(before.durationDays,14);assert.equal(before.creditCostPerFeedback,1);
 const feed=await api('/feed',{token:f.tokens.buyer});assert.ok(feed.items.some(row=>row.propertyId===f.properties.main.id));assert.deepEqual((await insight(f)).stats,zeroStats,'Fetching fifty candidates is not an impression');
 await api(`/properties/${f.properties.main.id}/insights`,{status:401});await api(`/properties/${f.properties.main.id}/insights`,{token:f.tokens.buyer,status:404});
 for(const query of ['?offset=-1','?limit=0','?limit=101'])await api(`/properties/${f.properties.main.id}/insights${query}`,{token:f.tokens.seller,status:400});
 const concurrentViews=await Promise.all([impression(f.tokens.buyer,f.properties.main,f.searchA),impression(f.tokens.buyer,f.properties.main,f.searchA)]);assert.equal(concurrentViews.filter(row=>row.recorded).length,1);assert.equal((await impression(f.tokens.buyer,f.properties.main,f.searchA)).recorded,false);
 await impression(f.tokens.buyer,f.properties.main,f.searchB,403);await active(f.tokens.buyer,'search',f.searchB.id);
 assert.equal((await impression(f.tokens.buyer,f.properties.main,f.searchB)).recorded,false,'The same person with two searches is still one viewer');
 await active(f.tokens.buyer,'search',f.searchA.id);await decide(f.tokens.buyer,f.properties.main,f.searchA,true);
 await active(f.tokens.buyer,'search',f.searchB.id);await decide(f.tokens.buyer,f.properties.main,f.searchB,true);
 assert.equal((await impression(f.tokens.other,f.properties.main,f.otherSearch)).recorded,true);
 await active(f.tokens.seller,'search',f.sellerSearch.id);await impression(f.tokens.seller,f.properties.main,f.sellerSearch,400);
 await impression(f.tokens.buyer,f.ownProperty,f.searchB,400);
 for(const overrides of [{locationIds:['city:Makó'],city:'Makó'},{type:'Ház'}]){const s=await createSearch(f.tokens.buyer,'Kizárt paraméter',overrides);await active(f.tokens.buyer,'search',s.id);await impression(f.tokens.buyer,f.properties.main,s,400);}
 await api('/credits/demo-topup',{token:f.tokens.seller,method:'POST',body:{amount:100}});await api('/credits/demo-topup',{token:f.tokens.seller,method:'POST',body:{amount:100}});
 await active(f.tokens.seller,'property',f.properties.main.id);await decide(f.tokens.seller,f.properties.main,f.searchA,true);await decide(f.tokens.seller,f.properties.main,f.searchB,true);
 assert.deepEqual((await insight(f)).stats,{uniqueViewers:2,buyerLikes:1,sellerLikes:2,matchedViewers:1,matchRate:50},'Unique-person conversion must not exceed 100% when one buyer owns several matched searches');
 await purchase(f.tokens.buyer,f.ownProperty,10,randomUUID(),402);await purchase(f.tokens.buyer,f.properties.main,10,randomUUID(),404);
 for(const size of [0,11,51])await purchase(f.tokens.seller,f.properties.main,size,randomUUID(),400);
 await purchase(f.tokens.seller,f.properties.main,10,'not-a-uuid',400);
 for(const [key,size]of [['main',10],...Array.from({length:7},(_,i)=>[`reason${i+1}`,10]),['pendingExpiry',10],['plan20',20],['plan50',50],['capacity',10]]){
  const requestId=randomUUID(),before=(await api('/me',{token:f.tokens.seller})).credits,attempts=await Promise.all(Array.from({length:key==='main'?2:1},()=>purchase(f.tokens.seller,f.properties[key],size,requestId))),result=attempts.find(row=>row.charged===size);
  if(key==='main'){assert.equal(attempts.filter(row=>row.charged===size).length,1);assert.equal(attempts.filter(row=>row.charged===0).length,1);assert.equal(new Set(attempts.map(row=>row.package.id)).size,1);}
  f.packages[key]=result.package;f.requests[key]=requestId;assert.equal(result.charged,size);assert.equal(result.credits,before-size);assert.equal(result.package.size,size);assert.equal(result.package.receivedCount,0);assert.equal(result.package.remaining,size);assert.equal(result.package.enabled,true);
  assert.equal(Date.parse(result.package.expiresAt)-Date.parse(result.package.createdAt),14*86400000);
 }
 const replay=await purchase(f.tokens.seller,f.properties.main,10,f.requests.main);assert.equal(replay.charged,0);assert.equal(replay.package.id,f.packages.main.id);
 await purchase(f.tokens.seller,f.properties.main,20,f.requests.main,409);await purchase(f.tokens.seller,f.properties.plan20,10,f.requests.main,409);
 await Promise.all([purchase(f.tokens.seller,f.properties.main,10,randomUUID(),409),purchase(f.tokens.seller,f.properties.main,20,randomUUID(),409)]);
 const continuous=stable(await insight(f)),ownerCredits=(await api('/me',{token:f.tokens.seller})).credits;
 await Promise.all([removedToggle(f.tokens.buyer,f.properties.main,false),removedToggle(f.tokens.seller,f.properties.main,false),removedToggle(f.tokens.seller,f.properties.main,true)]);
 assert.deepEqual(stable(await insight(f)),continuous,'Removed pause/resume requests cannot change the active package, deadline or counts');assert.equal((await api('/me',{token:f.tokens.seller})).credits,ownerCredits,'Removed pause requests cannot alter credits or trigger a refund');
 f.capacityDecisions=[];
 for(let i=0;i<9;i++){const row=await passFresh(f,f.properties.capacity,`Kapacitási előzmény ${i}`);assert.equal(row.result.feedbackPrompt??null,null);f.capacityDecisions.push(row.s.id);}
 await api('/credits/demo-topup',{token:f.tokens.other,method:'POST',body:{amount:20}});
 f.otherSpend=await createProperty(f.tokens.other,'Külön tízes csomag a határérték előtt');await purchase(f.tokens.other,f.otherSpend,10);
 const lastCredit=await Promise.all(f.otherProperties.map(p=>purchase(f.tokens.other,p,10,randomUUID(),[200,402])));assert.equal(lastCredit.filter(Boolean).length,1);assert.equal((await api('/me',{token:f.tokens.other})).credits,0,'Concurrent package purchases must not spend the final credits twice');
 await api(`/properties/${f.ownProperty.id}`,{token:f.tokens.buyer,method:'DELETE',status:204});assert.deepEqual((await api(`/properties/${f.ownProperty.id}/insights`,{token:f.tokens.buyer})).stats,zeroStats);await purchase(f.tokens.buyer,f.ownProperty,10,randomUUID(),400);
 f.initialSellerCredits=(await api('/me',{token:f.tokens.seller})).credits;f.initialBuyerCredits=(await api('/me',{token:f.tokens.buyer})).credits;
 await save(f);console.log('Seller feedback setup passed: real impressions versus feed fetches, unique people/searches/conversions, ownership gates, package10/20/50 charges, idempotent purchases, single-active and final-credit race.');
}else{
 const f=JSON.parse(await readFile(fixturePath,'utf8'));
 if(mode==='--responses'){
  await removedToggle(f.tokens.seller,f.properties.main,false);
  assert.equal((await insight(f)).activePackage.enabled,true,'An old client cannot suppress the next invitation by trying to pause.');
  const first=await passFresh(f,f.properties.main,'Első meghívott keresés');assertPrompt(first.result.feedbackPrompt,f,f.properties.main);f.firstPrompt=first.result.feedbackPrompt;
  assert.equal((await pending(f.tokens.buyer)).feedbackPrompt.id,f.firstPrompt.id);await answer(f.tokens.other,f.firstPrompt.id,'layout',404);await answer(f.tokens.seller,f.firstPrompt.id,'layout',404);await answer(f.tokens.buyer,f.firstPrompt.id,'unknown',400);
  const concurrent=await Promise.all(Array.from({length:4},()=>answer(f.tokens.buyer,f.firstPrompt.id,reasons[0])));assert.ok(concurrent.every(row=>row.accepted));assert.equal(concurrent.filter(row=>row.alreadyAnswered===false).length,1);
  await answer(f.tokens.buyer,f.firstPrompt.id,'layout',409);assert.equal((await insight(f)).feedback.total,1);assert.equal((await insight(f)).activePackage.receivedCount,1);
  assert.equal((await pending(f.tokens.buyer)).feedbackPrompt,null);assert.equal((await decide(f.tokens.buyer,f.properties.main,first.s,false)).feedbackPrompt??null,null);assert.equal((await pending(f.tokens.buyer)).feedbackPrompt,null,'Decision replay cannot reissue an answered invitation');
  // Even a fresh twenty-pass interval cannot re-invite this person to the same package.
  for(let i=0;i<20;i++){const row=await passFresh(f,f.properties.main,`Már válaszolt személy ${i}`);assert.equal(row.result.feedbackPrompt??null,null);}
  f.responsePrompts=[f.firstPrompt];
  for(let i=1;i<8;i++){
   const p=f.properties[`reason${i}`];let prompt;
   if(i===1){const row=await passFresh(f,p,'Másik csomag, valódi várakozás után');prompt=row.result.feedbackPrompt;assertPrompt(prompt,f,p);}
   else prompt=await afterTwentyPasses(f,p,`Húszas ritmus ${i}`);
   const result=await answer(f.tokens.buyer,prompt.id,reasons[i]);assert.equal(result.accepted,reasons[i]!=='decline');assert.equal(result.alreadyAnswered,false);
   const page=await insight(f,`reason${i}`);assert.equal(page.feedback.total,i===7?0:1);assert.equal(page.activePackage.receivedCount,i===7?0:1);assertAnonymousFeedback(page.feedback);
   f.responsePrompts.push(prompt);
  }
  for(let i=0;i<20;i++){const row=await passFresh(f,f.properties.reason7,`Elutasított kérdőív ${i}`);assert.equal(row.result.feedbackPrompt??null,null,'Declining prevents repeated invitations to the same package');}
  assert.equal((await answer(f.tokens.buyer,f.responsePrompts[7].id,'decline')).accepted,false);assert.equal((await insight(f,'reason7')).feedback.total,0);
  assert.equal((await api('/me',{token:f.tokens.buyer})).credits,f.initialBuyerCredits,'Respondents never pay for feedback');
  await save(f);console.log('Seller feedback response proof passed: all seven paid reasons, explicit non-response excluded, once-per-person campaigns, real twenty-pass cadence, concurrent exactly-once answers and private feedback receipts.');
 }else if(mode==='--capacity'){
  assert.equal((await insight(f,'capacity')).activePackage.receivedCount,9);
  const a=await createSearch(f.tokens.buyer,'Utolsó hely első jelentkező'),b=await createSearch(f.tokens.other,'Utolsó hely második jelentkező');
  await active(f.tokens.buyer,'search',a.id);await active(f.tokens.other,'search',b.id);
  const attempts=await Promise.all([decide(f.tokens.buyer,f.properties.capacity,a),decide(f.tokens.other,f.properties.capacity,b)]);
  const offered=attempts.map((row,i)=>({prompt:row.feedbackPrompt,key:i===0?'buyer':'other'})).filter(row=>row.prompt);assert.equal(offered.length,1,'Only one prompt can reserve the final package slot');
  await answer(f.tokens[offered[0].key],offered[0].prompt.id,'other');const complete=await insight(f,'capacity');assert.equal(complete.feedback.total,10);assert.equal(complete.activePackage.receivedCount,10);assert.equal(complete.activePackage.remaining,0);assert.equal(complete.activePackage.status,'completed');
  await purchase(f.tokens.seller,f.properties.capacity,10,randomUUID(),409);
  // A pending invitation is persisted for the deadline/late-answer proof.
  let prompt;for(let i=0;i<20&&!prompt;i++){const row=await passFresh(f,f.properties.pendingExpiry,`Lejárat előtt nyitott kérdés ${i}`);prompt=row.result.feedbackPrompt;}
  assertPrompt(prompt,f,f.properties.pendingExpiry);f.expiredPrompt=prompt;
  f.beforeRefund=(await api('/me',{token:f.tokens.seller})).credits;await save(f);console.log('Seller feedback capacity proof passed: nine consistent fixture responses plus one concurrently reserved final slot, completed packages block repurchase, pending prompt saved for expiry.');
 }else if(mode==='--expired'){
  await answer(f.tokens.buyer,f.expiredPrompt.id,'layout',410);assert.equal((await pending(f.tokens.buyer)).feedbackPrompt,null);
  const reads=await Promise.all([api('/me',{token:f.tokens.seller}),api('/credits/ledger',{token:f.tokens.seller}),insight(f),insight(f,'pendingExpiry')]);
  assert.equal((await api('/me',{token:f.tokens.seller})).credits,f.beforeRefund+19,'One accepted response refunds9; one unanswered ten-pack refunds10');
  const main=await insight(f),unanswered=await insight(f,'pendingExpiry');assert.equal(main.activePackage,null);assert.equal(main.feedback.total,1);assert.equal(unanswered.activePackage,null);assert.equal(unanswered.feedback.total,0);
  const full=await insight(f,'capacity'),settledFull=full.packages.find(row=>row.id===f.packages.capacity.id);assert.equal(full.activePackage,null);assert.ok(settledFull.refundedAt);assert.equal(settledFull.refundedCredits,0,'A completely delivered campaign must never create a credit refund');
  await removedToggle(f.tokens.seller,f.properties.pendingExpiry,true);
  assert.equal(main.packages.find(row=>row.id===f.packages.main.id).refundedCredits,9);assert.equal(unanswered.packages.find(row=>row.id===f.packages.pendingExpiry.id).refundedCredits,10);
  const notes=await api('/notifications',{token:f.tokens.seller});const refundNotes=notes.items.filter(row=>row.kind==='feedback_refund');assert.equal(refundNotes.length,2);assert.deepEqual(refundNotes.map(row=>row.amount).sort((a,b)=>a-b),[9,10]);
  const replay=await purchase(f.tokens.seller,f.properties.main,10,f.requests.main);assert.equal(replay.charged,0);assert.equal(replay.package.id,f.packages.main.id);
  const fresh=await purchase(f.tokens.seller,f.properties.main,20,randomUUID());assert.equal(fresh.charged,20);assert.notEqual(fresh.package.id,f.packages.main.id);f.newMainPackage=fresh.package;
  assert.equal((await api('/me',{token:f.tokens.seller})).credits,f.beforeRefund-1);
  const expectedMain=await insight(f);assertAnonymousFeedback(expectedMain.feedback);assert.equal(expectedMain.feedback.reasonCounts.find(row=>row.reason==='insufficient_information').count,1);assert.ok(expectedMain.feedback.reasonCounts.every(row=>row.reason!=='decline'));
  const paged=await insight(f,'capacity','?offset=0&limit=3');assert.equal(paged.feedback.items.length,3);assert.equal(paged.feedback.hasMore,true);assertAnonymousFeedback(paged.feedback);
  f.expected={main:stable(expectedMain),unanswered:stable(await insight(f,'pendingExpiry')),capacity:stable(await insight(f,'capacity')),credits:(await api('/me',{token:f.tokens.seller})).credits,notifications:await api('/notifications',{token:f.tokens.seller})};
  await save(f);console.log('Seller feedback expiry proof passed: late responses rejected, exactly-once9+10credit refunds and private notifications, expired request replay free, next package allowed, anonymous paged feedback.');
 }else if(mode==='--preserved'){
  assert.deepEqual(stable(await insight(f)),f.expected.main);assert.deepEqual(stable(await insight(f,'pendingExpiry')),f.expected.unanswered);assert.deepEqual(stable(await insight(f,'capacity')),f.expected.capacity);
  assert.equal((await api('/me',{token:f.tokens.seller})).credits,f.expected.credits);assert.deepEqual(await api('/notifications',{token:f.tokens.seller}),f.expected.notifications);
  assert.equal((await answer(f.tokens.buyer,f.firstPrompt.id,reasons[0])).alreadyAnswered,true);await answer(f.tokens.buyer,f.expiredPrompt.id,'other',410);
  console.log('Seller feedback restart proof passed: impressions/statistics, anonymous answers, original package charges/refunds, notifications, current campaign and answer idempotency survive.');
 }else throw new Error('Expected --setup, --responses, --capacity, --expired or --preserved.');
}
