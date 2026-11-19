/** Actual MySQL/API onboarding creation retries. Only runs against disposable CI. */
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {mkdir,writeFile,chmod,readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {withTestAddress} from './smoke-address.mjs';

const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
if(process.env.CI!=='true'||origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback CI API.');
const fixturePath=resolve('.local/onboarding-fixture.json');
function noCreationMetadata(value){
 if(Array.isArray(value)){value.forEach(noCreationMetadata);return;}
 if(!value||typeof value!=='object')return;
 for(const [key,item] of Object.entries(value)){assert.ok(!/^creationRequest/i.test(key),`Response leaked ${key}`);noCreationMetadata(item);}
}
async function api(path,{token,method='GET',body,status=200}={}){
 body=withTestAddress(path,method,body);
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.ok((Array.isArray(status)?status:[status]).includes(response.status),`${method} ${path}: HTTP ${response.status}`);
 const raw=await response.text();const data=raw?JSON.parse(raw):null;
 if(response.ok)noCreationMetadata(data);
 return {status:response.status,data};
}
async function entities(token){return (await api('/me/entities',{token})).data;}
if(process.argv.includes('--verify')){
 const fixture=JSON.parse(await readFile(fixturePath,'utf8'));
 for(const owner of fixture.owners){
  const owned=await entities(owner.token);
  for(const [kind,field] of [['property','properties'],['search','searchRequests']])assert.deepEqual(owned[field].map(row=>row.id).sort(),fixture.rows.filter(row=>row.ownerId===owner.id&&row.kind===kind&&!row.archived).map(row=>row.id).sort());
 }
 console.log('Onboarding retries preserve their exact owned entities after API restart.');
 process.exit(0);
}
const suffix=randomUUID(),owners=[];
for(let index=0;index<2;index++){
 const session=(await api('/auth/register',{method:'POST',body:{name:`Onboarding ${index}`,email:`onboarding-${index}-${suffix}@example.test`,password:'OnboardingIntegration2026!',phone:'+36 30 555 0181',accountType:'private'}})).data;
 assert.ok(session.accessToken,'Registration must immediately return the current authenticated session');
 owners.push({id:session.user.id,token:session.accessToken});
 assert.equal((await entities(session.accessToken)).properties.length,0);assert.equal((await entities(session.accessToken)).searchRequests.length,0);
}
const creationRequestId=randomUUID(),rows=[];
const property={title:'Saját szerkeszthető otthon',locationId:'city:Debrecen',city:'Debrecen',district:'',type:'Lakás',price:50000000,area:60,wholeRooms:2,halfRooms:1,rooms:2.5,images:[],balcony:false,elevator:false,description:'PRIVATE-ONBOARDING-DESCRIPTION',street:'OTTHONRA TEST',houseNumber:'1',postalCode:null};
const search={title:'Saját szerkeszthető keresés',locationIds:['city:Debrecen'],city:'Debrecen',type:'Lakás',minPrice:null,maxPrice:55000000,minArea:54,maxArea:66,minRooms:null,maxRooms:2.5,balcony:false,elevator:false,description:'PRIVATE-ONBOARDING-DESCRIPTION'};
for(const [kind,path,body,field] of [['property','/properties',property,'properties'],['search','/searches',search,'searchRequests']]){
 const token=owners[0].token,keyed={...body,creationRequestId};
 await api(path,{method:'POST',body:keyed,status:401});
 const concurrent=await Promise.all(Array.from({length:8},()=>api(path,{token,method:'POST',body:keyed,status:[200,201]})));
 assert.equal(concurrent.filter(result=>result.status===201).length,1,'One concurrent request must perform creation');
 const ids=new Set(concurrent.map(result=>result.data.id));assert.equal(ids.size,1,'Concurrent retry must return one entity ID');
 const id=concurrent[0].data.id;rows.push({kind,id,ownerId:owners[0].id,creationRequestId,archived:true});
 assert.equal((await entities(token))[field].length,1,'Concurrent retry must create exactly one owned row');
 assert.equal((await api(path,{token,method:'POST',body:keyed})).data.id,id);
 await api(path,{token,method:'POST',body:{...keyed,title:'A different draft must not overwrite the first one'},status:409});
 await api(path,{token,method:'POST',body:{...body,creationRequestId:'00000000-0000-0000-0000-000000000000'},status:400});
 assert.equal((await entities(token))[field].length,1,'Rejected requests must leave the owned count unchanged');
 await api(`${path}/${id}`,{token:owners[1].token,method:'DELETE',status:404});
 await api(`${path}/${id}`,{token,method:'DELETE',status:204});
 const archived=(await api(path,{token,method:'POST',body:keyed})).data;assert.equal(archived.id,id);assert.equal(archived.archived,true,'A retry must preserve the original archive state');
 assert.equal((await entities(token))[field].length,0,'Replaying an archived receipt must not recreate an active entity');
 const other=(await api(path,{token:owners[1].token,method:'POST',body:keyed,status:201})).data;assert.notEqual(other.id,id,'The creation key must be scoped to its owner');rows.push({kind,id:other.id,ownerId:owners[1].id,creationRequestId,archived:false});
 for(const legacyBody of [body,body,{...body,creationRequestId:null},{...body,creationRequestId:null}]){
  const fresh=(await api(path,{token,method:'POST',body:legacyBody,status:201})).data;
  assert.ok(!rows.some(row=>row.id===fresh.id),'Old clients without a key must still create independent entities');rows.push({kind,id:fresh.id,ownerId:owners[0].id,creationRequestId:null,archived:false});
 }
 assert.equal((await entities(token))[field].length,4);assert.equal((await entities(owners[1].token))[field].length,1);
}
const landing=(await api('/public/landing')).data;
const serialized=JSON.stringify(landing);assert.ok(!serialized.includes(creationRequestId));assert.ok(!serialized.includes('PRIVATE-ONBOARDING-DESCRIPTION'));assert.ok(!serialized.includes('OTTHONRA TEST'));
for(const row of rows)assert.ok(!serialized.includes(row.id),'Anonymous teasers must not reveal source entity IDs');
await mkdir(resolve('.local'),{recursive:true});await writeFile(fixturePath,JSON.stringify({owners,rows}),{mode:0o600});await chmod(fixturePath,0o600);
console.log('Onboarding MySQL API: concurrent/repeated creation, archived replay, conflict rejection, empty key, owner/kind scoping, old clients, immediate registration and DTO privacy passed.');
