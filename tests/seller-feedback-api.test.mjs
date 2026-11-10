import test,{afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {ApiModel} from '../dist/api.js';
import {FEEDBACK_OPTIONS,FEEDBACK_QUESTION} from '../dist/feedback.js';
const original=globalThis.fetch,originalRuntime=globalThis.OTTHONRA_CONFIG;afterEach(()=>{globalThis.fetch=original;globalThis.OTTHONRA_CONFIG=originalRuntime;});
const propertyId='22222222-2222-4222-8222-222222222222',searchId='33333333-3333-4333-8333-333333333333',requestId='44444444-4444-4444-8444-444444444444';
const pack={id:'package-id',size:10,receivedCount:3,remaining:7,enabled:true,createdAt:'2026-11-10T12:00:00Z',expiresAt:'2026-11-24T12:00:00Z',refundedAt:null,refundedCredits:0,status:'active'};
const prompt={id:'invitation-id',propertyId,sellerFirstName:'Anna',title:'PRIVATE-FULL-OWNER',question:FEEDBACK_QUESTION,options:FEEDBACK_OPTIONS,expiresAt:'2026-11-10T12:15:00Z',email:'PRIVATE-EMAIL',buyerId:'PRIVATE-BUYER'};
const response=(body,status=200)=>({ok:status>=200&&status<300,status,text:async()=>JSON.stringify(body)});
function setup(routes){const calls=[];globalThis.fetch=async(url,options)=>{const target=new URL(url);calls.push({target,...options});const item=routes[target.pathname];assert.ok(item,`Unexpected ${target.pathname}`);return typeof item==='function'?item(options):response(item);};return{api:new ApiModel({baseUrl:'https://api.example.test',token:'test-token'}),calls};}

test('owner insights preserve aggregate counts and package progress but discard respondent identity and decline records',async()=>{
 const {api,calls}=setup({[`/api/properties/${propertyId}/insights`]:{propertyId,stats:{uniqueViewers:8,buyerLikes:3,sellerLikes:6,matchedViewers:2,matchRate:25,buyerEmails:['PRIVATE-EMAIL']},feedback:{total:3,items:[{id:'answer',reason:'layout',label:'PRIVATE-LABEL',createdAt:'2026-11-10T12:00:00Z',buyerId:'PRIVATE-BUYER',email:'PRIVATE-EMAIL'},{id:'skipped',reason:'decline'},{reason:'unknown'}],reasonCounts:[{reason:'layout',count:3},{reason:'decline',count:20}],offset:2,limit:5,hasMore:true},activePackage:{...pack,ownerId:'PRIVATE-OWNER'},packages:[pack],packageSizes:[999],durationDays:999,creditCostPerFeedback:999}});
 const result=await api.getPropertyInsights(propertyId,{offset:2,limit:5});
 assert.deepEqual(result.stats,{uniqueViewers:8,buyerLikes:3,sellerLikes:6,matchedViewers:2,matchRate:25});assert.deepEqual(result.activePackage,pack);
 assert.equal(result.feedback.items.length,1);assert.equal(result.feedback.items[0].label,FEEDBACK_OPTIONS.find(x=>x.value==='layout').label);assert.equal(result.feedback.reasonCounts.length,7);assert.equal(result.feedback.reasonCounts.find(x=>x.reason==='layout').count,3);
 assert.deepEqual(result.packageSizes,[10,20,50]);assert.equal(result.durationDays,14);assert.equal(result.creditCostPerFeedback,1);assert.doesNotMatch(JSON.stringify(result),/PRIVATE-|decline/);
 assert.equal(calls[0].target.searchParams.get('offset'),'2');assert.equal(calls[0].headers.Authorization,'Bearer test-token');
 const before=calls.length;for(const value of ['',null,4])await assert.rejects(api.getPropertyInsights(value),/azonosító/);await assert.rejects(api.getPropertyInsights(propertyId,{limit:0}),/lapozási/);assert.equal(calls.length,before);
});

test('package purchases send one stable request ID and replay-safe response credits without accepting forged sizes or keys',async()=>{
 const {api,calls}=setup({[`/api/properties/${propertyId}/feedback-packages`]:options=>{const body=JSON.parse(options.body);return response({package:pack,charged:calls.length===1?10:0,credits:90});}});
 assert.deepEqual(await api.buyFeedbackPackage(propertyId,10,requestId),{package:pack,charged:10,credits:90});
 assert.equal((await api.buyFeedbackPackage(propertyId,10,requestId)).charged,0);assert.equal(calls[0].method,'POST');assert.deepEqual(JSON.parse(calls[0].body),{size:10,requestId});assert.equal(calls[0].body,calls[1].body);
 for(const size of [0,1,9,11,100])await assert.rejects(api.buyFeedbackPackage(propertyId,size,requestId),/csomagot/);
 for(const key of ['',undefined,'not-a-uuid','00000000-0000-0000-0000-000000000000'])await assert.rejects(api.buyFeedbackPackage(propertyId,10,key),/vásárlási azonosító/);assert.equal(calls.length,2);
});

test('toggle and actual-card impression calls expose only their permitted fields',async()=>{
 const {api,calls}=setup({[`/api/properties/${propertyId}/feedback`]:{package:{...pack,enabled:false}},'/api/impressions':{recorded:true}});
 assert.equal((await api.setFeedbackEnabled(propertyId,false)).package.enabled,false);assert.equal(calls[0].method,'PUT');assert.deepEqual(JSON.parse(calls[0].body),{enabled:false});
 assert.deepEqual(await api.recordImpression(propertyId,searchId),{recorded:true});assert.deepEqual(JSON.parse(calls[1].body),{propertyId,searchRequestId:searchId});
 await assert.rejects(api.setFeedbackEnabled(propertyId,'true'),/beállítás/);await assert.rejects(api.recordImpression(propertyId,''),/azonosító/);assert.equal(calls.length,2);
});

test('pending and decision-returned prompts contain exactly the safe first name and eight one-click options',async()=>{
 const {api}=setup({'/api/feedback/pending':{feedbackPrompt:prompt},'/api/decisions':{charged:0,feedbackPrompt:prompt}});
 const pending=await api.pendingFeedback();assert.equal(pending.title,'Segíts Annának egy visszajelzéssel');assert.equal(pending.question,FEEDBACK_QUESTION);assert.deepEqual(pending.options,FEEDBACK_OPTIONS);assert.doesNotMatch(JSON.stringify(pending),/PRIVATE-|buyerId|email/);
 const result=await api.decide({pair:{propertyId,searchId}},false);assert.deepEqual(result.feedbackPrompt,pending);
 const empty=setup({'/api/feedback/pending':{feedbackPrompt:null}});assert.equal(await empty.api.pendingFeedback(),null);
});

test('answer buttons send exactly one recognized reason and preserve declines and expired-prompt errors',async()=>{
 const {api,calls}=setup({'/api/feedback/invitation-id':options=>response({accepted:JSON.parse(options.body).reason!=='decline',alreadyAnswered:false})});
 for(const option of FEEDBACK_OPTIONS){assert.equal((await api.answerFeedback('invitation-id',option.value)).accepted,option.value!=='decline');assert.deepEqual(JSON.parse(calls.at(-1).body),{reason:option.value});}
 await assert.rejects(api.answerFeedback('invitation-id','not-an-option'),/lehetőséget/);assert.equal(calls.length,8);
 const expired=setup({'/api/feedback/invitation-id':()=>response({message:'A visszajelzési kérés lejárt.'},410)});await assert.rejects(expired.api.answerFeedback('invitation-id','layout'),error=>error.status===410);
});

test('package-refund notifications retain their package key without requiring a decision or exposing private owner data',async()=>{
 const {api}=setup({'/api/notifications':{items:[{id:'notice',kind:'feedback_refund',amount:9,text:'9 kredit visszatérítve.',decisionId:null,feedbackPackageId:pack.id,userId:'PRIVATE-OWNER',createdAt:'2026-11-24T12:00:00Z',readAt:null}]}});
 const page=await api.notifications();assert.equal(page.items[0].decisionId,null);assert.equal(page.items[0].feedbackPackageId,pack.id);assert.equal(page.items[0].amount,9);assert.doesNotMatch(JSON.stringify(page),/PRIVATE-/);
});


test('test scenario capability is explicitly test-only, cached per session and strips private fields',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};
 const capability={available:true,role:'buyer',propertyId,searchId,buyerEmail:'visszajelzes-kereso@otthonra.local',sellerEmail:'visszajelzes-elado@otthonra.local',feedbackReady:true};
 const {api,calls}=setup({'/api/test/feedback-scenario':{...capability,password:'PRIVATE-PASSWORD',accessToken:'PRIVATE-TOKEN'},'/api/test/feedback-scenario/reset':{...capability,token:'PRIVATE-TOKEN'}});
 const first=await api.getFeedbackScenario();assert.deepEqual(first,capability);assert.deepEqual(await api.getFeedbackScenario(),capability);assert.equal(calls.length,1);
 first.buyerEmail='changed';assert.equal((await api.getFeedbackScenario()).buyerEmail,capability.buyerEmail);
 const reset=await api.resetFeedbackScenario();assert.deepEqual(reset,capability);assert.deepEqual(api.active,{kind:'search',id:searchId});
 assert.equal(calls[1].method,'POST');assert.deepEqual(JSON.parse(calls[1].body),{});assert.doesNotMatch(JSON.stringify(reset),/PRIVATE-/);
});

test('scenario controls remain unavailable in production or on a test API without seeded fixtures',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'production'};
 const prod=setup({});assert.deepEqual(await prod.api.getFeedbackScenario(),{available:false});await assert.rejects(prod.api.resetFeedbackScenario(),/tesztkörnyezet/);assert.equal(prod.calls.length,0);
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};
 const absent=setup({'/api/test/feedback-scenario':()=>response({message:'Not found'},404)});
 assert.deepEqual(await absent.api.getFeedbackScenario(),{available:false});assert.deepEqual(await absent.api.getFeedbackScenario(),{available:false});assert.equal(absent.calls.length,1);
 const ordinary=setup({'/api/test/feedback-scenario':{available:false}});assert.deepEqual(await ordinary.api.getFeedbackScenario(),{available:false});
});

test('scenario authentication and server failures stay retryable instead of becoming a false capability',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};
 const expired=setup({'/api/test/feedback-scenario':()=>response({message:'Expired'},401)});await assert.rejects(expired.api.getFeedbackScenario(),error=>error.status===401);
 const unavailable=setup({'/api/test/feedback-scenario':()=>response({message:'Unavailable'},503)});await assert.rejects(unavailable.api.getFeedbackScenario(),error=>error.status===503);assert.equal(unavailable.api.feedbackScenarioCapability,undefined);
});
