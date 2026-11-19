/** Account-wide activity notifications against an explicitly disposable CI API. */
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {mkdir,writeFile,readFile,chmod} from 'node:fs/promises';
import {resolve} from 'node:path';
import {withTestAddress} from './smoke-address.mjs';

const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
if(process.env.CI!=='true'||origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback CI API.');
const fixturePath=resolve('.local/activity-notifications-fixture.json');
const mode=process.argv[3]||'--create';
const guid=value=>{assert.match(value,/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i);return value;};
async function save(value){await mkdir(resolve('.local'),{recursive:true});await writeFile(fixturePath,JSON.stringify(value),{mode:0o600});await chmod(fixturePath,0o600);}
async function api(path,{token,method='GET',body,status=200}={}){
 body=withTestAddress(path,method,body);
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.ok((Array.isArray(status)?status:[status]).includes(response.status),`${method} ${path}: HTTP ${response.status}`);
 const raw=await response.text();return raw?JSON.parse(raw):null;
}
const active=(owner,kind,id)=>api('/me/active',{token:owner.token,method:'PUT',body:{kind,id}});
const page=(owner,offset=0)=>api(`/notifications?offset=${offset}&limit=50`,{token:owner.token});
const context=(owner,id,status=200)=>api(`/notifications/${id}/context`,{token:owner.token,status});
const mark=(owner,id,status=200)=>api(`/notifications/${id}/read`,{token:owner.token,method:'PUT',status});
const profile=owner=>api('/me',{token:owner.token});
const decide=(owner,property,search,liked=true)=>api('/decisions',{token:owner.token,method:'POST',body:{propertyId:property.id,searchRequestId:search.id,liked}});
const hasTarget=(item,kind,id)=>item.target?.entityKind===kind&&item.target?.entityId===id;
async function onlyNotice(owner,kind,predicate=()=>true){const rows=(await page(owner)).items.filter(item=>item.kind===kind&&predicate(item));assert.equal(rows.length,1,`Expected exactly one ${kind} event`);return rows[0];}
function noContact(value,f){const raw=JSON.stringify(value);for(const item of f.owners)for(const secret of [item.email,item.phone])assert.ok(!raw.includes(secret),'Unmatched notification/context leaked a contact');assert.doesNotMatch(raw,/addressDetails|geocodingPlaceId|latitude|longitude|"password/i);}
function sourceSummary(items){return items.map(item=>({kind:item.kind,amount:item.amount,target:item.target??null,text:item.text,readAt:item.readAt??null})).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));}
async function checkpoint(f){f.snapshots={};for(const owner of f.owners){const notices=await page(owner);const me=await profile(owner);assert.equal(me.unreadNotificationCount,notices.unreadCount);f.snapshots[owner.id]={credits:me.credits,total:notices.total,unreadCount:notices.unreadCount,items:sourceSummary(notices.items)};}await save(f);}

if(mode==='--verify'||mode==='--verify-upgrade'){
 const f=JSON.parse(await readFile(fixturePath,'utf8'));
 for(const owner of f.owners){
  const notices=await page(owner),me=await profile(owner),before=f.snapshots[owner.id];
  assert.equal(me.credits,before.credits,'Notification migration/restart must not change credits');
  assert.equal(me.unreadNotificationCount,notices.unreadCount);
  assert.equal(notices.total,before.total,'Notification catch-up cannot duplicate source events');
  // Legacy refunds retain their exact first-read timestamp even when generic activities are backfilled.
  if(owner.id===f.sender.id){const legacy=notices.items.find(item=>item.id===f.legacyRefund.id);assert.ok(legacy);assert.equal(legacy.kind,'like_refund');assert.equal(legacy.readAt,f.legacyRefund.readAt);assert.equal(legacy.decisionId,f.legacyRefund.decisionId);}
  if(mode==='--verify')assert.deepEqual(sourceSummary(notices.items),before.items,'Same-source startup must preserve the complete activity/read snapshot');
 }
 if(mode==='--verify-upgrade')f.deletedNoticeId=(await onlyNotice(f.recipient,'incoming_like',item=>hasTarget(item,'search',f.searchC.id))).id;
 const gone=await context(f.recipient,f.deletedNoticeId);assert.equal(gone.available,false);assert.equal(gone.canActivate,false);assert.equal(gone.item??null,null);
 if(mode==='--verify-upgrade')await checkpoint(f);
 console.log(`Activity notifications ${mode.slice(2)}: owner activity count, credit balances, first-read refund state, unavailable deleted context and restart/backfill deduplication passed.`);
 process.exit(0);
}
if(mode==='--feedback'){
 const f=JSON.parse(await readFile(fixturePath,'utf8'));
 // The store helper sets only this disposable buyer's sampling counter to19.
 await active(f.sender,'search',f.senderSearch.id);
 const passed=await decide(f.sender,f.feedbackProperty,f.senderSearch,false);assert.ok(passed.feedbackPrompt?.id,'The prepared rejection must issue a feedback request');
 const promptId=guid(passed.feedbackPrompt.id);
 const before=(await page(f.recipient)).items.filter(item=>item.kind==='feedback_received').length;
 const answers=await Promise.all(Array.from({length:6},()=>api(`/feedback/${promptId}`,{token:f.sender.token,method:'POST',body:{reason:'layout'}})));
 assert.equal(answers.filter(item=>item.alreadyAnswered===false).length,1);assert.ok(answers.every(item=>item.accepted));
 const received=await onlyNotice(f.recipient,'feedback_received',item=>hasTarget(item,'property',f.feedbackProperty.id));assert.equal(received.readAt,null);assert.equal((await page(f.recipient)).items.filter(item=>item.kind==='feedback_received').length,before+1);
 const target=await context(f.recipient,received.id);assert.equal(target.available,true);assert.equal(target.target.page,'insights');assert.equal(target.target.entityId,f.feedbackProperty.id);assert.equal(target.item??null,null);
 await context(f.outsider,received.id,404);
 // Backdating the unanswered paid like causes the existing, real refund path to run.
 const refunded=await onlyNotice(f.sender,'like_refund',item=>item.decisionId===f.deletedDecisionId);assert.equal(refunded.amount,2);
 const marked=await mark(f.sender,refunded.id);assert.ok(marked.readAt);f.legacyRefund={id:marked.id,readAt:marked.readAt,decisionId:marked.decisionId};
 await checkpoint(f);
 console.log('Activity notification feedback: concurrent paid response creates one seller event with anonymous context; legacy paid-like refund remains independently readable.');
 process.exit(0);
}
assert.equal(mode,'--create');
const suffix=randomUUID(),owners=[];
for(const [name,phone]of [['Recipient Ági','+36 30 555 9011'],['Sender Péter','+36 30 555 9022'],['Outsider Anna','+36 30 555 9033']]){
 const email=`activity-${owners.length}-${suffix}@example.test`;
 const session=await api('/auth/register',{method:'POST',body:{name,email,phone,password:'NotificationIntegration2026!',accountType:'private'}});
 owners.push({id:guid(session.user.id),token:session.accessToken,email,phone});
}
const [recipient,sender,outsider]=owners;
const criteria={locationIds:['city:Debrecen'],city:'Debrecen',type:'Lakás',minPrice:null,maxPrice:90000000,minArea:20,maxArea:null,minRooms:1,maxRooms:null,balcony:false,elevator:false};
const listing={locationId:'city:Debrecen',city:'Debrecen',type:'Lakás',price:50000000,area:60,rooms:2,wholeRooms:2,halfRooms:0,balcony:false,elevator:false,images:[],street:'OTTHONRA TEST',houseNumber:'1',postalCode:null};
const createSearch=(owner,title)=>api('/searches',{token:owner.token,method:'POST',body:{...criteria,title},status:201});
const createProperty=(owner,title)=>api('/properties',{token:owner.token,method:'POST',body:{...listing,title},status:201});
const searchA=await createSearch(recipient,'Éppen aktív keresés'),searchB=await createSearch(recipient,'Másik, nem aktív keresés'),searchC=await createSearch(recipient,'Később törölt keresés');
const senderSearch=await createSearch(sender,'Visszajelzést adó kereső');
const p1=await createProperty(sender,'Az első beérkező ajánlat'),p2=await createProperty(sender,'Ajánlat később törölt profilra'),feedbackProperty=await createProperty(recipient,'Visszajelzést váró ingatlan');
await api('/credits/demo-topup',{token:sender.token,method:'POST',body:{amount:20}});await active(recipient,'search',searchA.id);await active(sender,'property',p1.id);
const creditsBefore=(await profile(sender)).credits;
const likes=await Promise.all(Array.from({length:8},()=>decide(sender,p1,searchB)));
assert.equal(likes.filter(item=>item.charged===2).length,1);assert.equal((await profile(sender)).credits,creditsBefore-2);
let liked=await onlyNotice(recipient,'incoming_like',item=>hasTarget(item,'search',searchB.id));assert.equal(liked.readAt,null);assert.equal(liked.target.page,'incoming');
assert.equal((await api('/me/entities',{token:recipient.token})).active.id,searchA.id,'Receiving a notification must not change the selected profile');
await api('/notifications',{status:401});await context(outsider,liked.id,404);await mark(outsider,liked.id,404);
let resolved=await context(recipient,liked.id);assert.equal(resolved.available,true);assert.equal(resolved.canActivate,true);assert.equal(resolved.item.propertyId,p1.id);assert.equal(resolved.item.searchRequestId,searchB.id);assert.equal(resolved.item.matchId??null,null);
noContact(resolved,{owners});assert.equal((await api('/me/entities',{token:recipient.token})).active.id,searchA.id,'Viewing a context must not activate it implicitly');
assert.equal((await onlyNotice(recipient,'incoming_like')).readAt,null,'Listing/fetching notifications alone never marks them read');
const reads=await Promise.all(Array.from({length:8},()=>mark(recipient,liked.id)));assert.ok(reads[0].readAt);assert.ok(reads.every(item=>item.readAt===reads[0].readAt));assert.ok(reads.every(item=>Number.isInteger(item.unreadCount)));assert.equal((await mark(recipient,liked.id)).readAt,reads[0].readAt);
await active(recipient,'search',searchB.id);const mutual=await decide(recipient,p1,searchB);assert.ok(mutual.matchId);const matchId=guid(mutual.matchId);
const matchesR=await onlyNotice(recipient,'match_created',item=>item.target?.matchId===matchId),matchesS=await onlyNotice(sender,'match_created',item=>item.target?.matchId===matchId);assert.notEqual(matchesR.id,matchesS.id);
assert.ok(hasTarget(matchesR,'search',searchB.id));assert.ok(hasTarget(matchesS,'property',p1.id));
await api(`/matches/${matchId}/messages`,{token:outsider.token,method:'POST',body:{text:'Unauthorized message'},status:404});
const sent=await api(`/matches/${matchId}/messages`,{token:sender.token,method:'POST',body:{text:'Érdeklődés a másik saját profilhoz.'},status:201});
const message=await onlyNotice(recipient,'message_received',item=>item.target?.matchId===matchId);assert.ok(hasTarget(message,'search',searchB.id));assert.equal((await page(sender)).items.filter(item=>item.kind==='message_received').length,0);
await active(recipient,'search',searchA.id);resolved=await context(recipient,message.id);assert.equal(resolved.available,true);assert.equal(resolved.target.matchId,matchId);assert.equal(resolved.target.page,'messages');
await active(sender,'property',p2.id);await decide(sender,p2,searchC);const deletedNotice=await onlyNotice(recipient,'incoming_like',item=>hasTarget(item,'search',searchC.id));
await api(`/searches/${searchC.id}`,{token:recipient.token,method:'DELETE',status:204});assert.ok(!(await api('/me/entities',{token:recipient.token})).searchRequests.some(item=>item.id===searchC.id));
resolved=await context(recipient,deletedNotice.id);assert.equal(resolved.available,false);assert.equal(resolved.canActivate,false);assert.equal(resolved.item??null,null);await mark(recipient,deletedNotice.id);
const credit=await onlyNotice(sender,'credit_added');assert.equal(credit.amount,20);assert.equal(credit.target.page,'credits');
await api('/credits/demo-topup',{token:recipient.token,method:'POST',body:{amount:20}});
const campaign=await api(`/properties/${feedbackProperty.id}/feedback-packages`,{token:recipient.token,method:'POST',body:{size:10,requestId:randomUUID()}});assert.ok(campaign.package?.id);
const f={owners,recipient,sender,outsider,searchA,searchB,searchC,senderSearch,p1,p2,feedbackProperty,matchId,messageId:sent.id,deletedNoticeId:deletedNotice.id,deletedDecisionId:null,packageId:guid(campaign.package.id),readNotice:{id:liked.id,readAt:reads[0].readAt}};
await save(f);
console.log('Account activity MySQL API: inactive profile likes, concurrent idempotent event/billing, owner privacy, exact context, independent first-read states, both match recipients, new message and deleted-subject history passed.');
