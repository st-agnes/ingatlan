import assert from 'node:assert/strict';
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
const property=await call('/properties',{method:'POST',token:s,status:201,body:{title:'Smoke lakás',city:'Smoketown-'+run,district:'XIII.',type:'Lakás',price:80000000,area:60,rooms:3,floor:2,address:'Private street 12',description:'Világos és csendes.',condition:'Felújított',building:'Tégla',balcony:true,elevator:true,images:[]}});
const search=await call('/searches',{method:'POST',token:b,status:201,body:{title:'Smoke keresés',city:'Smoketown-'+run,districts:['XIII.'],type:'Lakás',minPrice:70000000,maxPrice:90000000,minArea:50,maxArea:80,minRooms:2,maxRooms:4,balcony:true,elevator:true}});
await call('/me/active',{method:'PUT',token:b,body:{kind:'search',id:search.id}});
await call('/me/active',{method:'PUT',token:s,body:{kind:'property',id:property.id}});
await call('/me/active',{method:'PUT',token:o,body:{kind:'property',id:property.id},status:404});
const feed=await call('/feed',{token:b});assert.equal(feed.items.length,1);assert.equal(feed.items[0].property.address,'');assert.ok(!JSON.stringify(feed).includes('9999'));assert.deepEqual(await call('/matches',{token:b}),[]);
const pair={propertyId:property.id,searchRequestId:search.id,liked:true};
await call('/decisions',{method:'POST',token:s,body:pair,status:402});
await call('/credits/demo-topup',{method:'POST',token:s,body:{amount:20}});
const results=await Promise.all([call('/decisions',{method:'POST',token:s,body:pair}),call('/decisions',{method:'POST',token:s,body:pair})]);
assert.equal(results.reduce((sum,v)=>sum+v.charged,0),2);assert.equal((await call('/me',{token:s})).credits,18);assert.deepEqual(await call('/matches',{token:b}),[]);
assert.equal((await call('/feed',{token:s})).items.length,0);const matchDecision=await call('/decisions',{method:'POST',token:b,body:pair});assert.ok(matchDecision.matchId);assert.equal(matchDecision.charged,0);
const matches=await call('/matches',{token:b});assert.equal(matches.length,1);assert.equal(matches[0].contact.email,seller.user.email);assert.equal(matches[0].property.address,'Private street 12');
const matchId=matches[0].id;await call(`/matches/${matchId}/messages`,{method:'POST',token:o,body:{text:'Should fail'},status:404});
const message=await call(`/matches/${matchId}/messages`,{method:'POST',token:b,body:{text:'Szia! Mikor nézhetem meg?'},status:201});assert.equal(message.senderId,buyer.user.id);
assert.equal((await call('/matches',{token:s}))[0].messages.length,1);
const retry=await call('/decisions',{method:'POST',token:s,body:pair});assert.equal(retry.charged,0);assert.equal(retry.matchId,matchId);
await call('/decisions',{method:'POST',token:b,body:{...pair,liked:false},status:409});
assert.equal((await call('/credits/ledger',{token:s})).filter(x=>x.amount<0).length,1);
await call(`/properties/${property.id}`,{method:'DELETE',token:o,status:404});
await call('/me',{status:401});
console.log('API smoke passed: privacy, authorization, compatibility, concurrent single billing, match, messaging.');
