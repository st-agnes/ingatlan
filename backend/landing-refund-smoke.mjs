/** Real API integration. Loopback disposable CI only; the companion SQL fixture ages known decisions. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,chmod} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';

const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
const mode=process.argv[3]||'--setup';
if(process.env.CI!=='true'||origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback CI API.');
const fixturePath=resolve('.local/landing-refund-fixture.json');
async function api(path,{token,method='GET',body,status=200}={}){
 // The web proxy deliberately forwards only /api; internal jobs target the API directly.
 const internal=path.startsWith('/internal/');
 const response=await fetch(new URL(internal?path:'/api'+path,internal?'http://127.0.0.1:5080':origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.ok((Array.isArray(status)?status:[status]).includes(response.status),`${method} ${path}: HTTP ${response.status}`);
 const text=await response.text();return response.status>=400||!text?null:JSON.parse(text);
}
async function save(f){await mkdir(dirname(fixturePath),{recursive:true});await writeFile(fixturePath,JSON.stringify(f),{mode:0o600});await chmod(fixturePath,0o600);}
const active=(token,kind,id)=>api('/me/active',{token,method:'PUT',body:{kind,id}});
const decision=(token,p,s,liked=true)=>api('/decisions',{token,method:'POST',body:{propertyId:p.id,searchRequestId:s.id,liked}});
const byId=rows=>[...rows].sort((a,b)=>a.id.localeCompare(b.id));
function noPrivateFields(value){
 if(Array.isArray(value)){value.forEach(noPrivateFields);return;}
 if(!value||typeof value!=='object')return;
 for(const [key,item] of Object.entries(value)){
  assert.ok(!['ownerId','userId','name','email','phone','contact','address','description','passwordHash','images','image','imageUrl','propertyId','searchRequestId','searchId'].includes(key),`Public teaser leaked ${key}`);
  noPrivateFields(item);
 }
}
async function publicLanding(f){
 const national=await api('/public/landing');assert.equal(national.scope,'national');assert.equal(national.region,null);
 assert.equal(national.regions.length,20);assert.equal(new Set(national.regions.map(r=>r.id)).size,20);
 assert.ok(national.searches.length>0&&national.searches.length<=8);assert.ok(national.properties.length>0&&national.properties.length<=4);
 for(const page of [national,await api('/public/landing?region=HU222'),await api('/public/landing?region=HU321')]){
  noPrivateFields(page);const raw=JSON.stringify(page);assert.ok(!raw.includes(f.secret),'Public landing exposed submitted free text');
  for(const id of [...Object.values(f.ids),...Object.values(f.properties).map(p=>p.id),f.search.id,f.agentSearch.id])assert.ok(!raw.includes(id),'Public landing exposed source/owner IDs');
 }
 const vas=await api('/public/landing?region=HU222');assert.equal(vas.scope,'region');assert.equal(vas.region.id,'HU222');
 assert.ok(vas.properties.length>0);assert.ok(vas.properties.every(p=>p.location==='Őriszentpéter'),'County selection must filter properties before limiting');
 const hajdu=await api('/public/landing?region=HU321');assert.equal(hajdu.region.id,'HU321');assert.ok(hajdu.searches.some(s=>s.locations.includes('Debrecen')),'A multi-location search must belong to every matching county');
 await api('/public/landing?region=unknown',{status:400});
}

if(mode==='--setup'){
 const suffix=Date.now()+'-'+Math.random().toString(16).slice(2),secret='PRIVATE-CONTENT-'+suffix.replace(/[0-9]/g,d=>String.fromCharCode(97+Number(d))),tokens={},ids={};
 for(const [key,accountType] of [['seller','private'],['buyer','private'],['agent','agent']]){
  const session=await api('/auth/register',{method:'POST',body:{name:secret+' '+key,email:`refund-${key}-${suffix}@example.test`,password:'RefundIntegration2026!',phone:'+36 30 555 0777',accountType}});tokens[key]=session.accessToken;ids[key]=session.user.id;
 }
 for(const key of ['seller','agent'])await api('/credits/demo-topup',{token:tokens[key],method:'POST',body:{amount:20}});
 const property={title:secret,description:secret,locationId:'city:Őriszentpéter',city:'Őriszentpéter',district:'',type:'Lakás',price:55000000,area:77,rooms:3,wholeRooms:3,halfRooms:0,floor:2,address:secret+' street 10',images:[],balcony:false,elevator:false};
 const criteria={title:secret,description:secret,locationIds:['city:Őriszentpéter','city:Debrecen'],city:'Őriszentpéter',type:'Lakás',maxPrice:70000000,minArea:60,maxArea:100,minRooms:2,maxRooms:4,balcony:false,elevator:false};
 const search=await api('/searches',{token:tokens.buyer,method:'POST',body:criteria,status:201});
 const agentSearch=await api('/searches',{token:tokens.agent,method:'POST',body:criteria,status:201});
 await active(tokens.buyer,'search',search.id);await active(tokens.agent,'search',agentSearch.id);
 const properties={},cases={};
 for(const name of ['due','timelyPass','timelyLike','latePass','lateLike','young','freePass','agentDue','privateFree']){
  const p=await api('/properties',{token:tokens.seller,method:'POST',body:property,status:201});properties[name]=p;
  if(name==='agentDue'){assert.equal((await decision(tokens.agent,p,agentSearch)).charged,1);cases[name]={actor:'agent',kind:'search',propertyId:p.id,searchId:agentSearch.id,expected:1};}
  else if(name==='privateFree'){assert.equal((await decision(tokens.buyer,p,search)).charged,0);cases[name]={actor:'buyer',kind:'search',propertyId:p.id,searchId:search.id,expected:0};}
  else{
   await active(tokens.seller,'property',p.id);assert.equal((await decision(tokens.seller,p,search,name!=='freePass')).charged,name==='freePass'?0:2);
   cases[name]={actor:'seller',kind:'property',propertyId:p.id,searchId:search.id,expected:['due','latePass','lateLike'].includes(name)?2:0};
   if(['timelyPass','timelyLike','latePass','lateLike'].includes(name))await decision(tokens.buyer,p,search,name.endsWith('Like'));
  }
 }
 const reports=[];
 for(const [entityKind,entityId] of [['property',properties.due.id],['search',agentSearch.id]]){
  const receipt=await api('/reports',{token:tokens.buyer,method:'POST',body:{entityKind,entityId,reason:'no_longer_current'},status:201});
  assert.equal(receipt.reason,'no_longer_current');assert.equal(Object.hasOwn(receipt,'createdAt'),false);
  const repeat=await api('/reports',{token:tokens.buyer,method:'POST',body:{entityKind,entityId,reason:'no_longer_current'}});assert.equal(repeat.id,receipt.id);assert.equal(repeat.alreadyReported,true);reports.push({id:receipt.id,entityKind,entityId});
 }
 const f={tokens,ids,properties,search,agentSearch,cases,reports,secret,balances:{}};
 for(const key of Object.keys(tokens)){
  const entities=await api('/me/entities',{token:tokens[key]});
  for(const c of Object.values(cases).filter(c=>c.actor===key)){
   const row=entities.decisions.find(d=>d.propertyId===c.propertyId&&d.searchId===c.searchId&&d.actorKind===c.kind);assert.ok(row);c.decisionId=row.id;
  }
  f.balances[key]=(await api('/me',{token:tokens[key]})).credits;
  assert.equal((await api('/notifications',{token:tokens[key]})).total,0);
 }
 await api('/notifications',{status:401});
 await api('/internal/refunds/run',{token:tokens.seller,method:'POST',status:[401,403,404]});
 await publicLanding(f);await save(f);
 console.log('Landing/refund setup passed: anonymous privacy and counties, new report reason for both roles, real paid/free/replied decision cases.');
}else{
 const f=JSON.parse(await readFile(fixturePath,'utf8'));
 if(mode==='--verify'){
  // Simultaneous catch-up paths exercise the same durable refunds independently.
  await Promise.all(Array.from({length:12},(_,i)=>api(i%3===0?'/me':i%3===1?'/credits/ledger':'/notifications',{token:f.tokens[i%2===0?'seller':'agent']})));
  for(const [key,expectedRefund,count] of [['seller',6,3],['agent',1,1],['buyer',0,0]]){
   const token=f.tokens[key],profile=await api('/me',{token});assert.equal(profile.credits,f.balances[key]+expectedRefund);assert.equal(profile.unreadNotificationCount,count);
   const notifications=await api('/notifications',{token});assert.equal(notifications.total,count);assert.equal(notifications.unreadCount,count);assert.equal(notifications.items.length,count);
   const expectedCases=Object.values(f.cases).filter(c=>c.actor===key&&c.expected>0);
   assert.deepEqual(notifications.items.map(n=>n.decisionId).sort(),expectedCases.map(c=>c.decisionId).sort());
   for(const n of notifications.items){assert.equal(n.kind,'like_refund');assert.equal(n.amount,expectedCases.find(c=>c.decisionId===n.decisionId).expected);assert.ok(n.text.includes('14'));assert.equal(n.readAt,null);assert.ok(!Object.hasOwn(n,'userId'));}
   const ledger=await api('/credits/ledger',{token}),refunds=ledger.filter(e=>e.refundedDecisionId);
   assert.equal(refunds.length,count);assert.equal(refunds.reduce((sum,e)=>sum+e.amount,0),expectedRefund);
   const entities=await api('/me/entities',{token});for(const c of Object.values(f.cases).filter(c=>c.actor===key)){const d=entities.decisions.find(d=>d.id===c.decisionId);assert.equal(Boolean(d.refundedAt),c.expected>0);}
   for(const query of ['offset=-1','limit=0','limit=101'])await api('/notifications?'+query,{token,status:400});
  }
  const first=(await api('/notifications',{token:f.tokens.seller})).items[0];
  await api('/notifications/'+first.id+'/read',{token:f.tokens.buyer,method:'PUT',status:404});
  const read=await api('/notifications/'+first.id+'/read',{token:f.tokens.seller,method:'PUT'});assert.ok(read.readAt);
  assert.equal((await api('/notifications/'+first.id+'/read',{token:f.tokens.seller,method:'PUT'})).readAt,read.readAt);
  assert.equal((await api('/me',{token:f.tokens.seller})).unreadNotificationCount,2);
  const pages=await Promise.all([0,1,2].map(offset=>api('/notifications?offset='+offset+'&limit=1',{token:f.tokens.seller})));
  assert.equal(new Set(pages.flatMap(p=>p.items.map(n=>n.id))).size,3);assert.equal(pages[0].hasMore,true);assert.equal(pages[2].hasMore,false);
  // A late reply can still match the original like without reclaiming the refund.
  const late=await decision(f.tokens.buyer,f.properties.due,f.search);assert.ok(late.matchId);assert.equal(late.charged,0);
  await active(f.tokens.seller,'property',f.properties.due.id);
  const repeat=await decision(f.tokens.seller,f.properties.due,f.search);assert.equal(repeat.charged,0);assert.equal(repeat.credits,f.balances.seller+6);
  f.final={};for(const key of Object.keys(f.tokens))f.final[key]={credits:(await api('/me',{token:f.tokens[key]})).credits,notifications:await api('/notifications',{token:f.tokens[key]}),ledger:byId(await api('/credits/ledger',{token:f.tokens[key]}))};
  await save(f);console.log('Refund API verification passed: exact2/1credits, both timely replies excluded, late replies refunded, free/young decisions excluded, concurrent exactly-once catch-up, private notifications, read state, paging and late match.');
 }else if(mode==='--preserved'){
  for(const key of Object.keys(f.tokens)){
   assert.equal((await api('/me',{token:f.tokens[key]})).credits,f.final[key].credits);
   assert.deepEqual(await api('/notifications',{token:f.tokens[key]}),f.final[key].notifications);
   assert.deepEqual(byId(await api('/credits/ledger',{token:f.tokens[key]})),f.final[key].ledger);
  }
  console.log('Refund restart preservation passed: balances, unique credits, original notifications/read timestamps and charge ledger remain unchanged.');
 }else throw new Error('Unknown landing/refund smoke phase.');
}
