/** Actual MySQL/API coverage for account visibility, contextual reports and incoming likes. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,chmod} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000'),mode=process.argv[3];
if(origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback API.');
const fixturePath=resolve('.local/interaction-fixture.json');
async function api(path,{token,method='GET',body,status=200}={}){
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.ok((Array.isArray(status)?status:[status]).includes(response.status),`${method} ${path}: HTTP ${response.status}`);
 const text=await response.text();return response.status>=400||!text?null:JSON.parse(text);
}
async function save(f){await mkdir(dirname(fixturePath),{recursive:true});await writeFile(fixturePath,JSON.stringify(f),{mode:0o600});await chmod(fixturePath,0o600);}
const active=(token,kind,id)=>api('/me/active',{token,method:'PUT',body:{kind,id}});
const decision=(token,p,s,liked=true,status=200)=>api('/decisions',{token,method:'POST',body:{propertyId:p.id,searchRequestId:s.id,liked},status});
function privatePage(page){for(const row of page.items){assert.equal(row.property.address,'');for(const entity of [row.property,row.searchRequest])for(const field of ['phone','email','contact','passwordHash'])assert.equal(Object.hasOwn(entity,field),false);assert.equal(row.likedYou,true);assert.ok(!Number.isNaN(Date.parse(row.likedAt)));}}
async function verify(f){
 for(const key of ['a1','b2']){const page=await api('/incoming-likes',{token:f.tokens[key]});privatePage(page);assert.deepEqual(page,f.incoming[key],'Incoming likes changed after a restart');}
 for(const key of Object.keys(f.tokens)){const profile=await api('/me',{token:f.tokens[key]});assert.equal(profile.credits,f.balances[key]);assert.deepEqual(await api('/credits/ledger',{token:f.tokens[key]}),f.ledgers[key]);}
 const rows=await api('/me/entities',{token:f.tokens.b2});assert.equal(rows.reportedEntities.length,5);assert.ok(rows.reportedEntities.every(row=>!Object.hasOwn(row,'createdAt')));
}
if(mode==='--verify'){
 await verify(JSON.parse(await readFile(fixturePath,'utf8')));console.log('Interaction restart preservation passed: incoming statuses/privacy, contextual report summaries, balances and ledger unchanged.');
}else if(mode==='--legacy-upgrade'){
 const f=JSON.parse(await readFile(fixturePath,'utf8')),legacy=f.legacy.report;
 const duplicate=await api('/reports',{token:f.tokens.b2,method:'POST',body:{entityKind:legacy.entityKind,entityId:legacy.entityId,reason:legacy.reason}});
 assert.equal(duplicate.id,legacy.id);assert.equal(duplicate.alreadyReported,true);assert.equal(Object.hasOwn(duplicate,'createdAt'),false);
 f.legacy.newReports=[];
 for(const [entityKind,entityId,reason] of [[legacy.entityKind,legacy.entityId,'misleading_content'],['search',f.entities.b1.s.id,'suspected_agent']]){
  const receipt=await api('/reports',{token:f.tokens.b2,method:'POST',body:{entityKind,entityId,reason},status:201});assert.equal(receipt.alreadyReported,false);
  f.legacy.newReports.push({id:receipt.id,reporterId:f.ids.b2,reportedUserId:f.ids.b1,entityKind,entityId,reason});
 }
 await save(f);console.log('Legacy report upgrade API passed: original report retained, independent reason and same-owner search report accepted.');
}else{
 const suffix=Date.now()+'-'+Math.random().toString(16).slice(2),tokens={},ids={};
 for(const [key,accountType] of [['a1','agent'],['a2','agent'],['b1','private'],['b2','private']]){
  const session=await api('/auth/register',{method:'POST',body:{name:'Interaction '+key,email:`interaction-${key}-${suffix}@example.test`,password:'InteractionSmoke2026!',phone:'+36 30 555 0888',accountType}});tokens[key]=session.accessToken;ids[key]=session.user.id;
 }
 const property={title:'Interakciós API-próba',locationId:'city:Őriszentpéter',city:'Őriszentpéter',district:'',type:'Lakás',price:55000000,area:77,rooms:3.5,wholeRooms:2,halfRooms:3,floor:2,address:'Private test street 10',images:[],balcony:false,elevator:false};
 const search={title:'Interakciós keresés',locationIds:['city:Őriszentpéter'],city:'Őriszentpéter',type:'Lakás',maxPrice:70000000,minArea:60,maxArea:100,minRooms:3,maxRooms:4,balcony:false,elevator:false};
 const entities={};for(const key of Object.keys(tokens))entities[key]={p:await api('/properties',{token:tokens[key],method:'POST',body:{...property,title:property.title+' '+key},status:201}),s:await api('/searches',{token:tokens[key],method:'POST',body:{...search,title:search.title+' '+key},status:201})};
 const empty=await api('/incoming-likes',{token:tokens.b2});assert.equal(empty.active,null);assert.deepEqual(empty.items,[]);assert.equal(empty.total,0);
 await api('/incoming-likes',{status:401});
 for(const query of ['offset=-1','offset=1000001','limit=0','limit=101'])await api('/incoming-likes?'+query,{token:tokens.b2,status:400});
 await active(tokens.a1,'search',entities.a1.s.id);await active(tokens.a2,'property',entities.a2.p.id);await active(tokens.b1,'property',entities.b1.p.id);await active(tokens.b2,'search',entities.b2.s.id);
 for(const key of ['a1','a2']){const feed=await api('/feed',{token:tokens[key]});const counterpart=row=>key==='a1'?row.property:row.searchRequest;assert.ok(feed.items.length>=2);assert.ok(feed.items.every(row=>counterpart(row).ownerAccountType==='private'));assert.equal(feed.items.some(row=>(key==='a1'?row.propertyId:row.searchRequestId)===(key==='a1'?entities.a2.p.id:entities.a1.s.id)),false);}
 const privateFeed=await api('/feed',{token:tokens.b2});assert.ok(privateFeed.items.some(row=>row.property.ownerAccountType==='agent'));assert.ok(privateFeed.items.some(row=>row.property.ownerAccountType==='private'));
 for(const liked of [true,false]){await decision(tokens.a1,entities.a2.p,entities.a1.s,liked,400);await decision(tokens.a2,entities.a2.p,entities.a1.s,liked,400);}
 for(const key of ['a1','a2']){assert.equal((await api('/me/entities',{token:tokens[key]})).decisions.length,0);assert.deepEqual(await api('/credits/ledger',{token:tokens[key]}),[]);}
 for(const key of ['a1','a2','b1'])await api('/credits/demo-topup',{token:tokens[key],method:'POST',body:{amount:20}});
 await decision(tokens.b1,entities.b1.p,entities.a1.s);await decision(tokens.b1,entities.b1.p,entities.b2.s);await decision(tokens.a2,entities.a2.p,entities.b2.s);
 const beforeAgentView=await api('/me',{token:tokens.a1}),beforeLedger=await api('/credits/ledger',{token:tokens.a1});
 const incomingA=await api('/incoming-likes',{token:tokens.a1});privatePage(incomingA);assert.equal(incomingA.total,1);assert.equal(incomingA.items[0].propertyId,entities.b1.p.id);assert.equal(incomingA.items[0].myDecision,null);assert.equal(incomingA.items[0].compatible,true);assert.equal(incomingA.items[0].isExact,true);assert.equal(incomingA.items[0].compatibilityScore,100);assert.equal(incomingA.likeCost,1);
 assert.equal((await api('/me',{token:tokens.a1})).credits,beforeAgentView.credits);assert.deepEqual(await api('/credits/ledger',{token:tokens.a1}),beforeLedger,'Viewing incoming likes is free');
 const matchA=await decision(tokens.a1,entities.b1.p,entities.a1.s);assert.equal(matchA.charged,1);assert.ok(matchA.matchId);
 const matchedA=await api('/incoming-likes',{token:tokens.a1});assert.equal(matchedA.items[0].myDecision,'liked');assert.equal(matchedA.items[0].matchId,matchA.matchId);privatePage(matchedA);
 await decision(tokens.b2,entities.a2.p,entities.b2.s,false);const matchB=await decision(tokens.b2,entities.b1.p,entities.b2.s);assert.equal(matchB.charged,0);assert.ok(matchB.matchId);
 const extra=await api('/properties',{token:tokens.b1,method:'POST',body:{...property,title:'Később nem illeszkedő ajánlat'},status:201});await active(tokens.b1,'property',extra.id);await decision(tokens.b1,extra,entities.b2.s);
 const pages=[];for(let offset=0;offset<3;offset++)pages.push(await api(`/incoming-likes?offset=${offset}&limit=1`,{token:tokens.b2}));assert.equal(new Set(pages.flatMap(page=>page.items.map(row=>row.propertyId))).size,3);assert.equal(pages[0].hasMore,true);assert.equal(pages[2].hasMore,false);
 let incomingB=await api('/incoming-likes',{token:tokens.b2});assert.equal(incomingB.items.find(row=>row.propertyId===entities.a2.p.id).myDecision,'passed');assert.equal(incomingB.items.find(row=>row.propertyId===entities.b1.p.id).matchId,matchB.matchId);
 await api('/searches/'+entities.b2.s.id,{token:tokens.b2,method:'PUT',body:{...search,maxPrice:10000000}});
 incomingB=await api('/incoming-likes',{token:tokens.b2});assert.equal(incomingB.total,3);
 assert.ok(incomingB.items.every(row=>row.compatible===true&&row.isExact===false&&row.compatibilityScore>=0&&row.compatibilityScore<100),
  'Over-budget incoming likes remain location/type eligible but must be marked as partial matches');
 assert.equal(incomingB.items.find(row=>row.propertyId===extra.id).myDecision,null);
 await decision(tokens.b2,extra,entities.b2.s,true,400);
 await api('/searches/'+entities.b2.s.id,{token:tokens.b2,method:'PUT',body:search});await api('/properties/'+extra.id,{token:tokens.b1,method:'DELETE',status:204});assert.equal((await api('/incoming-likes',{token:tokens.b2})).total,2);
 const secondSearch=await api('/searches',{token:tokens.a1,method:'POST',body:{...search,title:'Másik aktív keresés'},status:201});await active(tokens.a1,'search',secondSearch.id);assert.equal((await api('/incoming-likes',{token:tokens.a1})).total,0);await active(tokens.a1,'search',entities.a1.s.id);assert.equal((await api('/incoming-likes',{token:tokens.a1})).total,1);
 await decision(tokens.b2,entities.a1.p,entities.b2.s);await active(tokens.a1,'property',entities.a1.p.id);const sellerIncoming=await api('/incoming-likes',{token:tokens.a1});assert.equal(sellerIncoming.total,1);assert.equal(sellerIncoming.items[0].searchRequestId,entities.b2.s.id);assert.equal(sellerIncoming.likeCost,2);privatePage(sellerIncoming);
 const sellerResponse=await decision(tokens.a1,entities.a1.p,entities.b2.s);assert.equal(sellerResponse.charged,2);assert.ok(sellerResponse.matchId);
 const scoped=await api('/incoming-likes?entityId='+entities.a2.p.id,{token:tokens.b2});assert.equal(scoped.active.id,entities.b2.s.id);assert.equal(scoped.total,3);
 const reportStart=new Date().toISOString(),reports=[];
 const report=async(key,owner,kind,id,reason,status=201)=>{const receipt=await api('/reports',{token:tokens[key],method:'POST',body:{entityKind:kind,entityId:id,reason},status});if(status<400){assert.equal(Object.hasOwn(receipt,'createdAt'),false);assert.equal(receipt.reason,reason);if(!receipt.alreadyReported)reports.push({id:receipt.id,reporterId:ids[key],reportedUserId:ids[owner],entityKind:kind,entityId:id,reason});}return receipt;};
 const anchor=await report('b2','b1','property',entities.b1.p.id,'suspected_agent');const misleading=await report('b2','b1','property',entities.b1.p.id,'misleading_content');assert.notEqual(anchor.id,misleading.id);assert.equal((await report('b2','b1','property',entities.b1.p.id,'misleading_content',200)).id,misleading.id);
 assert.notEqual((await report('b2','b1','search',entities.b1.s.id,'suspected_agent')).id,anchor.id);
 await report('b2','a2','property',entities.a2.p.id,'misleading_content');await report('b2','a2','search',entities.a2.s.id,'other_violation');await report('a1','a2','property',entities.a2.p.id,'other_violation');
 for(const [owner,kind,id,reason] of [['a2','property',entities.a2.p.id,'suspected_agent'],['b2','property',entities.b2.p.id,'other_violation'],['b1','property',entities.b1.p.id,'unknown'],['b1','property',entities.b1.p.id,'']])await report('b2',owner,kind,id,reason,400);
 const legacyDefault=await api('/reports',{token:tokens.b2,method:'POST',body:{entityKind:'property',entityId:entities.b1.p.id}});assert.equal(legacyDefault.id,anchor.id);assert.equal(legacyDefault.alreadyReported,true);
 const reportEnd=new Date().toISOString(),f={tokens,ids,entities,reports,reportStart,reportEnd,incoming:{},balances:{},ledgers:{}};
 for(const key of ['a1','b2'])f.incoming[key]=await api('/incoming-likes',{token:tokens[key]});
 for(const key of Object.keys(tokens)){f.balances[key]=(await api('/me',{token:tokens[key]})).credits;f.ledgers[key]=await api('/credits/ledger',{token:tokens[key]});}
 await verify(f);await save(f);console.log('Interaction API integration passed: agent exclusion on both sides, server decision enforcement, universal reason-aware reports, incoming privacy/statuses/paging/activation, free viewing and normal reciprocal billing.');
}
