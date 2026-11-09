import assert from 'node:assert/strict';
import {chmod, mkdir, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {assertNoContactData} from './smoke-privacy.mjs';
const base = (process.argv[2] || 'http://localhost:5080').replace(/\/$/, '') + '/api';
const run = Date.now() + '-' + Math.random().toString(16).slice(2);
async function call(path, {token,method='GET',body,status=200}={}) {
  const response=await fetch(base+path,{signal:AbortSignal.timeout(10000),method,headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const raw=await response.text();let value;try{value=JSON.parse(raw)}catch{value=raw}
  assert.equal(response.status,status,`${method} ${path}: ${JSON.stringify(value)}`);return value;
}
async function account(name){return await call('/auth/register',{method:'POST',body:{name,email:`${name}-${run}@example.test`,password:'SmokePassword2026!',phone:'+36 30 555 9999'}})}
const buyer=await account('Buyer'),seller=await account('Seller'),outsider=await account('Outsider');
const b=buyer.accessToken,s=seller.accessToken,o=outsider.accessToken;
const suggestions=await call('/locations?q=Debr');
assert.ok((Array.isArray(suggestions)?suggestions:suggestions.items).some(item=>item.id==='city:Debrecen'));
const propertyBody={title:'Smoke lakás',locationId:'district:Budapest:13',city:'Budapest',district:'XIII.',type:'Lakás',price:80000000,area:60,rooms:3,floor:2,address:'Private street 12',description:'Világos és csendes.',condition:'Felújított',building:'Tégla',balcony:true,elevator:true,images:[]};
const searchBody={title:'Smoke keresés',city:'Budapest',districts:['XIII.'],locationIds:['district:Budapest:13'],type:'Lakás',minPrice:null,maxPrice:90000000,minArea:50,maxArea:null,minRooms:2,maxRooms:null,balcony:true,elevator:true};
const property=await call('/properties',{method:'POST',token:s,status:201,body:propertyBody});
const search=await call('/searches',{method:'POST',token:b,status:201,body:searchBody});
assert.equal(property.locationId,'district:Budapest:13');
assert.deepEqual(search.locationIds,searchBody.locationIds);
assert.equal(search.locations.length,1);
assert.equal(search.minPrice,null);assert.equal(search.maxArea,null);assert.equal(search.maxRooms,null);
await call('/properties',{method:'POST',token:s,body:{...propertyBody,locationId:'city:Debrceen'},status:400});
await call('/searches',{method:'POST',token:b,body:{...searchBody,locationIds:[]},status:400});
await call('/searches',{method:'POST',token:b,body:{...searchBody,locationIds:['city:Debrceen']},status:400});
await call('/me/active',{method:'PUT',token:b,body:{kind:'search',id:search.id}});
await call('/me/active',{method:'PUT',token:s,body:{kind:'property',id:property.id}});
await call('/me/active',{method:'PUT',token:o,body:{kind:'property',id:property.id},status:404});
const feed=await call('/feed',{token:b});
const card=feed.items.find(item=>item.propertyId===property.id);
assert.ok(card);assert.equal(card.property.address,'');
assertNoContactData(card,[buyer.user.phone,seller.user.phone,buyer.user.email,seller.user.email,propertyBody.address]);
assert.deepEqual(await call('/matches',{token:b}),[]);
const pair={propertyId:property.id,searchRequestId:search.id,liked:true};
await call('/decisions',{method:'POST',token:s,body:pair,status:402});
await call('/credits/demo-topup',{method:'POST',token:s,body:{amount:20}});
const results=await Promise.all([call('/decisions',{method:'POST',token:s,body:pair}),call('/decisions',{method:'POST',token:s,body:pair})]);
assert.equal(results.reduce((sum,v)=>sum+v.charged,0),2);assert.equal((await call('/me',{token:s})).credits,18);assert.deepEqual(await call('/matches',{token:b}),[]);
assert.equal((await call('/feed',{token:s})).items.some(item=>item.searchRequestId===search.id),false);const matchDecision=await call('/decisions',{method:'POST',token:b,body:pair});assert.ok(matchDecision.matchId);assert.equal(matchDecision.charged,0);
const matches=await call('/matches',{token:b});assert.equal(matches.length,1);assert.equal(matches[0].contact.email,seller.user.email);assert.equal(matches[0].contact.phone,seller.user.phone);assert.equal(matches[0].property.address,'Private street 12');
const matchId=matches[0].id;await call(`/matches/${matchId}/messages`,{method:'POST',token:o,body:{text:'Should fail'},status:404});
const message=await call(`/matches/${matchId}/messages`,{method:'POST',token:b,body:{text:'Szia! Mikor nézhetem meg?'},status:201});assert.equal(message.senderId,buyer.user.id);
assert.equal((await call('/matches',{token:s}))[0].messages.length,1);
const retry=await call('/decisions',{method:'POST',token:s,body:pair});assert.equal(retry.charged,0);assert.equal(retry.matchId,matchId);
await call('/decisions',{method:'POST',token:b,body:{...pair,liked:false},status:409});
assert.equal((await call('/credits/ledger',{token:s})).filter(x=>x.amount<0).length,1);
await call(`/properties/${property.id}`,{method:'DELETE',token:o,status:404});
await call('/me',{status:401});

// The location selection is OR across towns, while other filters still apply.
const townSearch=await call('/searches',{method:'POST',token:b,status:201,body:{...searchBody,city:'Debrecen',districts:[],locationIds:['city:Debrecen','city:Hajdúszoboszló','city:Hajdúsámson']}});
assert.equal(townSearch.locations.length,3);
await call('/me/active',{method:'PUT',token:b,body:{kind:'search',id:townSearch.id}});
const townProperties=[];
for(const city of ['Debrecen','Hajdúszoboszló','Hajdúsámson','Szeged'])townProperties.push(await call('/properties',{method:'POST',token:s,status:201,body:{...propertyBody,locationId:'city:'+city,city,district:''}}));
const townFeed=await call('/feed',{token:b});
for(const item of townProperties)assert.equal(townFeed.items.some(card=>card.propertyId===item.id),item.city!=='Szeged');
const mixedIds=['district:Budapest:5','district:Budapest:9','city:Solymár','city:Pilisvörösvár'];
const mixed=await call('/searches',{method:'POST',token:b,status:201,body:{...searchBody,city:'Budapest',locationIds:mixedIds,balcony:false,elevator:false}});
assert.deepEqual(mixed.locationIds,mixedIds);
const mixedProperties=[];
for(const [locationId,city,district] of [['district:Budapest:5','Budapest','V.'],['district:Budapest:9','Budapest','IX.'],['city:Solymár','Solymár',''],['city:Pilisvörösvár','Pilisvörösvár',''],['district:Budapest:13','Budapest','XIII.']]) {
 mixedProperties.push(await call('/properties',{method:'POST',token:s,status:201,body:{...propertyBody,locationId,city,district,area:250,rooms:12,price:5000000}}));
}
await call('/me/active',{method:'PUT',token:b,body:{kind:'search',id:mixed.id}});
const mixedFeed=await call('/feed',{token:b});
for(const item of mixedProperties)assert.equal(mixedFeed.items.some(card=>card.propertyId===item.id),mixedIds.includes(item.locationId));
assert.equal(mixedFeed.items.some(card=>card.propertyId===property.id),false);
const reloaded=(await call('/me/entities',{token:b})).searchRequests.find(item=>item.id===mixed.id);
assert.equal(reloaded.minPrice,null);assert.equal(reloaded.maxArea,null);assert.equal(reloaded.maxRooms,null);assert.deepEqual(reloaded.locationIds,mixedIds);

const house=await call('/properties',{method:'POST',token:s,status:201,body:{...propertyBody,type:'Ház',lotArea:1280}});
assert.equal(house.lotArea,1280);
await call('/properties',{method:'POST',token:s,body:{...propertyBody,type:'Ház',lotArea:-1},status:400});
await call('/properties',{method:'POST',token:s,body:{...propertyBody,type:'Ház',lotArea:0},status:400});
const apartment=await call(`/properties/${house.id}`,{method:'PUT',token:s,body:{...propertyBody,lotArea:1280}});
assert.equal(apartment.lotArea,null);
if(process.env.OTTHONRA_UPGRADE_FIXTURE){
 const fixturePath=resolve(process.env.OTTHONRA_UPGRADE_FIXTURE);
 const [buyerEntities,sellerEntities,buyerProfile,sellerProfile,sellerLedger]=await Promise.all([call('/me/entities',{token:b}),call('/me/entities',{token:s}),call('/me',{token:b}),call('/me',{token:s}),call('/credits/ledger',{token:s})]);
 await mkdir(dirname(fixturePath),{recursive:true});
 await writeFile(fixturePath,JSON.stringify({buyerToken:b,sellerToken:s,buyerId:buyer.user.id,sellerId:seller.user.id,propertyId:property.id,searchId:search.id,matchId,expectedBuyerCredits:buyerProfile.credits,expectedCredits:sellerProfile.credits,sellerLedger,messageId:message.id,messageText:message.text,messageCount:1,propertyIds:sellerEntities.properties.map(item=>item.id).sort(),searchIds:buyerEntities.searchRequests.map(item=>item.id).sort()}),{mode:0o600});
 await chmod(fixturePath,0o600);
}
console.log('API smoke passed: privacy, authorization, compatibility, concurrent single billing, match, messaging, canonical multi-location OR, optional bounds, and house plot area.');
