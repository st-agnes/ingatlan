/** Real account-type, billing and reporting integration. Disposable loopback API only. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,chmod} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
if(origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback API.');
const fixturePath=resolve('.local/broker-upgrade-fixture.json');
async function call(path,{token,method='GET',body,status=200}={}){
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.ok((Array.isArray(status)?status:[status]).includes(response.status),`${method} ${path}: HTTP ${response.status}`);
 const text=await response.text();if(response.status>=400||!text)return null;
 return JSON.parse(text);
}
const activate=(token,kind,id)=>call('/me/active',{token,method:'PUT',body:{kind,id}});
const entities=token=>call('/me/entities',{token});
const pair=(property,search,liked=true)=>({propertyId:property.id,searchRequestId:search.id,liked});
async function verify(f){
 const [agent,seller,privateUser,agentEntities,privateEntities]=await Promise.all([call('/me',{token:f.agent}),call('/me',{token:f.seller}),call('/me',{token:f.privateUser}),entities(f.agent),entities(f.privateUser)]);
 assert.equal(agent.accountType,'agent');assert.equal(seller.accountType,'private');assert.equal(privateUser.accountType,'private');assert.equal(agent.credits,18);assert.equal(seller.credits,18);assert.equal(privateUser.credits,0);
 assert.ok(agentEntities.properties.some(p=>p.id===f.agentPropertyId&&p.ownerAccountType==='agent'));
 assert.ok(agentEntities.searchRequests.some(s=>s.id===f.agentSearchId&&s.ownerAccountType==='agent'));
 assert.ok(agentEntities.decisions.some(d=>d.actorKind==='search'&&d.property.ownerAccountType==='private'&&d.search.ownerAccountType==='agent'));
 const ledger=await call('/credits/ledger',{token:f.agent});assert.equal(ledger.filter(x=>x.amount===-1).length,20);assert.equal(ledger.filter(x=>x.amount===-2).length,1);assert.equal(ledger.filter(x=>x.amount<0).length,21);
 assert.deepEqual(privateEntities.reportedOwnerIds,[f.sellerId]);assert.deepEqual(agentEntities.reportedOwnerIds,[f.privateUserId]);
 const matches=await call('/matches',{token:f.agent});
 const match=matches.find(x=>x.id===f.matchId);assert.ok(match);assert.equal(match.property.ownerAccountType,'private');assert.equal(match.searchRequest.ownerAccountType,'agent');assert.equal(match.contact.id,f.sellerId);
 const receipt=await call('/reports',{token:f.privateUser,method:'POST',body:{entityKind:'search',entityId:f.sellerSearchId}});
 assert.equal(receipt.id,f.reports[0].id);assert.equal(receipt.alreadyReported,true);assert.equal(Object.hasOwn(receipt,'createdAt'),false);
 assert.equal((await entities(f.privateUser)).decisions.filter(d=>d.liked).length,2,'Private search likes survive without a debit');
}
if(process.argv[3]==='--verify'){
 await verify(JSON.parse(await readFile(fixturePath,'utf8')));
 console.log('Broker restart preservation passed: account types, owner badges, one-time credit ledger, matching and reporter-private deduplication survive.');
}else{
 const suffix=Date.now()+'-'+Math.random().toString(16).slice(2),password='BrokerSmoke2026!';
 const register=async(name,accountType)=>call('/auth/register',{method:'POST',body:{name:'Broker '+name,email:`broker-${name}-${suffix}@example.test`,password,...(accountType===undefined?{}:{accountType})}});
 // Assert invalid registration statuses explicitly without relying on an exception.
 for(const accountType of ['unknown',''])await call('/auth/register',{method:'POST',status:400,body:{name:'Invalid type',email:`broker-invalid-${accountType||'empty'}-${suffix}@example.test`,password,accountType}});
 const a=await register('agent','agent'),s=await register('seller','private'),b=await register('private');
 const agent=a.accessToken,seller=s.accessToken,privateUser=b.accessToken;
 assert.equal(a.user.accountType,'agent');assert.equal(s.user.accountType,'private');assert.equal(b.user.accountType,'private');
 const logged=await call('/auth/login',{method:'POST',body:{email:a.user.email,password}});assert.equal(logged.user.accountType,'agent');
 const flip=await call('/me',{token:agent,method:'PUT',body:{name:a.user.name,email:a.user.email,phone:'',accountType:'private'}});assert.equal(flip.accountType,'agent','Profile writes must not turn paid agent searches into free private searches');
 const propertyBody={title:'Közvetítői elszámolás API-próba',locationId:'city:Debrecen',city:'Debrecen',district:'',type:'Lakás',price:40000000,area:80,rooms:3,wholeRooms:3,halfRooms:0,balcony:false,elevator:false,images:[]};
 const searchBody={title:'Közvetítői keresés API-próba',locationIds:['city:Debrecen'],city:'Debrecen',type:'Lakás',minPrice:null,maxPrice:60000000,minArea:70,maxArea:null,minRooms:3,maxRooms:null,balcony:false,elevator:false};
 const property=await call('/properties',{token:seller,method:'POST',body:{...propertyBody,ownerAccountType:'agent'},status:201});assert.equal(property.ownerAccountType,'private');
 const agentProperty=await call('/properties',{token:agent,method:'POST',body:{...propertyBody,ownerAccountType:'private'},status:201});assert.equal(agentProperty.ownerAccountType,'agent');
 const otherProperty=await call('/properties',{token:privateUser,method:'POST',body:propertyBody,status:201});
 const search=await call('/searches',{token:agent,method:'POST',body:{...searchBody,ownerAccountType:'private'},status:201});assert.equal(search.ownerAccountType,'agent');
 const sellerSearch=await call('/searches',{token:seller,method:'POST',body:searchBody,status:201});
 const privateSearch=await call('/searches',{token:privateUser,method:'POST',body:searchBody,status:201});
 await activate(agent,'search',search.id);await activate(seller,'property',property.id);await activate(privateUser,'search',privateSearch.id);
 const feed=await call('/feed',{token:agent});assert.equal(feed.likeCost,1);assert.equal(feed.sellerLikeCost,2);
 const card=feed.items.find(x=>x.propertyId===property.id);assert.ok(card);assert.equal(card.property.ownerAccountType,'private');assert.equal(card.searchRequest.ownerAccountType,'agent');assert.equal(card.property.address,'');assert.equal(Object.hasOwn(card.property,'email'),false);
 const sellerFeed=await call('/feed',{token:seller});assert.equal(sellerFeed.likeCost,2);assert.equal(sellerFeed.items.find(x=>x.searchRequestId===search.id).searchRequest.ownerAccountType,'agent');
 await call('/decisions',{token:agent,method:'POST',body:pair(property,search),status:402});assert.equal((await entities(agent)).decisions.length,0);assert.equal((await call('/credits/ledger',{token:agent})).length,0);
 const pass=await call('/decisions',{token:agent,method:'POST',body:pair(otherProperty,search,false)});assert.equal(pass.charged,0);assert.equal(pass.credits,0);
 assert.equal((await call('/feed',{token:privateUser})).likeCost,0);
 for(const p of [property,agentProperty]){const free=await call('/decisions',{token:privateUser,method:'POST',body:pair(p,privateSearch)});assert.equal(free.charged,0);assert.equal(free.credits,0);}
 assert.equal((await call('/credits/ledger',{token:privateUser})).filter(x=>x.amount<0).length,0);
 await call('/credits/demo-topup',{token:seller,method:'POST',body:{amount:20}});
 const sellerLike=await call('/decisions',{token:seller,method:'POST',body:pair(property,search)});assert.equal(sellerLike.charged,2);
 await call('/credits/demo-topup',{token:agent,method:'POST',body:{amount:20}});
 const likes=await Promise.all([call('/decisions',{token:agent,method:'POST',body:pair(property,search)}),call('/decisions',{token:agent,method:'POST',body:pair(property,search)})]);
 assert.equal(likes.reduce((sum,x)=>sum+x.charged,0),1);const matchId=likes.find(x=>x.matchId)?.matchId;assert.ok(matchId);assert.equal((await call('/me',{token:agent})).credits,19);
 const additional=[];for(let index=0;index<20;index++)additional.push(await call('/properties',{token:seller,method:'POST',body:{...propertyBody,title:`Közvetítői kreditpróba ${index}`},status:201}));
 for(const p of additional.slice(0,18))assert.equal((await call('/decisions',{token:agent,method:'POST',body:pair(p,search)})).charged,1);
 assert.equal((await call('/me',{token:agent})).credits,1);
 const lastResults=await Promise.all(additional.slice(18).map(p=>call('/decisions',{token:agent,method:'POST',body:pair(p,search),status:[200,402]})));
 assert.equal(lastResults.filter(Boolean).length,1,'One remaining credit permits exactly one of two simultaneous different likes');assert.equal((await call('/me',{token:agent})).credits,0);
 const replay=await call('/decisions',{token:agent,method:'POST',body:pair(property,search)});assert.equal(replay.charged,0);assert.equal(replay.matchId,matchId);
 const before=(await entities(agent)).decisions.length,loser=additional[18+lastResults.findIndex(x=>!x)];await call('/decisions',{token:agent,method:'POST',body:pair(loser,search),status:402});assert.equal((await entities(agent)).decisions.length,before);
 await activate(agent,'property',agentProperty.id);assert.equal((await call('/feed',{token:agent})).likeCost,2);
 await call('/credits/demo-topup',{token:agent,method:'POST',body:{amount:20}});
 const agentSellerLikes=await Promise.all([call('/decisions',{token:agent,method:'POST',body:pair(agentProperty,privateSearch)}),call('/decisions',{token:agent,method:'POST',body:pair(agentProperty,privateSearch)})]);assert.equal(agentSellerLikes.reduce((sum,x)=>sum+x.charged,0),2,'An agent seller pays two, not an extra search fee');
 // Reciprocal reports lock the same two user rows in a consistent order.
 const reportStart=new Date().toISOString();
 const [reportOne,reportTwo]=await Promise.all([
  call('/reports',{token:privateUser,method:'POST',body:{entityKind:'property',entityId:property.id,reportedUserId:a.user.id},status:201}),
  call('/reports',{token:seller,method:'POST',body:{entityKind:'property',entityId:otherProperty.id},status:201})
 ]);
 assert.equal(reportOne.reportedOwnerId,s.user.id,'The reported owner must be derived from the source entity');
 const dup=await call('/reports',{token:privateUser,method:'POST',body:{entityKind:'search',entityId:sellerSearch.id}});assert.equal(dup.id,reportOne.id);assert.equal(dup.alreadyReported,true);
 const concurrentReports=await Promise.all([0,1].map(()=>call('/reports',{token:agent,method:'POST',body:{entityKind:'search',entityId:privateSearch.id},status:[200,201]})));
 assert.equal(concurrentReports.filter(x=>!x.alreadyReported).length,1);assert.equal(new Set(concurrentReports.map(x=>x.id)).size,1);
 const reportThree=concurrentReports.find(x=>!x.alreadyReported),reportEnd=new Date().toISOString();
 for(const receipt of [reportOne,reportTwo,dup,...concurrentReports]){assert.equal(receipt.reported,true);assert.equal(Object.hasOwn(receipt,'createdAt'),false);}
 await call('/reports',{method:'POST',body:{entityKind:'property',entityId:property.id},status:401});
 for(const body of [{entityKind:'user',entityId:property.id},{entityKind:'property',entityId:otherProperty.id},{entityKind:'property',entityId:agentProperty.id}])await call('/reports',{token:privateUser,method:'POST',body,status:400});
 await call('/reports',{token:privateUser,method:'POST',body:{entityKind:'property',entityId:'00000000-0000-0000-0000-000000000001'},status:404});
 const archived=await call('/properties',{token:seller,method:'POST',body:propertyBody,status:201});await call('/properties/'+archived.id,{token:seller,method:'DELETE',status:204});await call('/reports',{token:privateUser,method:'POST',body:{entityKind:'property',entityId:archived.id},status:404});
 const reports=[{id:reportOne.id,reporterId:b.user.id,reportedUserId:s.user.id,entityKind:'property',entityId:property.id},{id:reportTwo.id,reporterId:s.user.id,reportedUserId:b.user.id,entityKind:'property',entityId:otherProperty.id},{id:reportThree.id,reporterId:a.user.id,reportedUserId:b.user.id,entityKind:'search',entityId:privateSearch.id}];
 const fixture={agent,seller,privateUser,sellerId:s.user.id,privateUserId:b.user.id,agentPropertyId:agentProperty.id,agentSearchId:search.id,sellerSearchId:sellerSearch.id,matchId,reportStart,reportEnd,reports};
 await verify(fixture);await mkdir(dirname(fixturePath),{recursive:true});await writeFile(fixturePath,JSON.stringify(fixture),{mode:0o600});await chmod(fixturePath,0o600);
 console.log('Broker API integration passed: strict registration, server owner badges, 1-credit agent search, 2-credit seller, free private search, concurrent one-time billing/last-credit race, mutual contact privacy, authenticated duplicate/reciprocal reports and private receipts.');
}
