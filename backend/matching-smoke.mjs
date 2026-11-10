/** New ranking and approximate-match consent through the real disposable API/MySQL. */
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {assertNoContactData} from './smoke-privacy.mjs';

const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000');
if (process.env.CI !== 'true' || origin.protocol !== 'http:'
    || !['localhost','127.0.0.1','[::1]'].includes(origin.hostname)
    || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) {
  throw new Error('Run matching smoke only against a disposable loopback CI API.');
}
const suffix = randomUUID();
const privatePhone = '+36 30 555 8801';
const feedTimes = [];
async function api(path, {token, method='GET', body, status=200}={}) {
  const started = performance.now();
  const response = await fetch(new URL('/api'+path, origin), {
    method, redirect:'error', signal:AbortSignal.timeout(20000),
    headers:{...(token ? {Authorization:`Bearer ${token}`} : {}), ...(body === undefined ? {} : {'Content-Type':'application/json'})},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})
  });
  assert.equal(response.status, status, `${method} ${path}: expected HTTP ${status}, got ${response.status}`);
  if (path.startsWith('/feed')) feedTimes.push(performance.now()-started);
  return response.status === 204 ? null : response.json();
}
async function register(name) {
  const session = await api('/auth/register', {method:'POST', body:{
    name:`Matching ${name}`, email:`matching-${name.toLowerCase()}-${suffix}@example.test`,
    password:'MatchingFixturePassword2026!', phone:privatePhone
  }});
  return {...session.user, token:session.accessToken};
}
const buyer = await register('Buyer'), seller = await register('Seller'), secondBuyer = await register('SecondBuyer');
await api('/credits/demo-topup', {token:seller.token, method:'POST', body:{amount:100}});

// This town has no baseline demo fixture; all recommendation candidates below
// are created by this test, without editing the database or mocking API replies.
const town = 'Abádszalók';
const propertyBase = {
  title:'Matching property fixture', city:town, district:'', locationId:`city:${town}`,
  type:'Lakás', price:80_000_000, area:80, rooms:3, floor:2,
  condition:'Jó', building:'Tégla', address:'Private matching street 42',
  description:'Kitalált integrációs tesztadat.', balcony:false, elevator:false, images:[]
};
const searchBase = {
  title:'Matching search fixture', city:town, districts:[], locationIds:[`city:${town}`],
  type:'Lakás', minPrice:null, maxPrice:100_000_000, minArea:60, maxArea:null,
  minRooms:3, maxRooms:null, balcony:false, elevator:false
};
const property = (name, changes={}, owner=seller) => api('/properties', {
  token:owner.token, method:'POST', status:201, body:{...propertyBase, title:name, ...changes}
});
const search = (name, changes={}, owner=buyer) => api('/searches', {
  token:owner.token, method:'POST', status:201, body:{...searchBase, title:name, ...changes}
});
const activate = (owner, kind, id) => api('/me/active', {token:owner.token, method:'PUT', body:{kind,id}});
const feed = (owner, approximate=false) => api('/feed'+(approximate ? '?includeApproximate=true' : ''), {token:owner.token});
const decide = (owner, home, request, liked, allowApproximate=false, status=200) => api('/decisions', {
  token:owner.token, method:'POST', status,
  body:{propertyId:home.id, searchRequestId:request.id, liked, allowApproximate}
});
const score = item => item.compatibilityScore;
const propertyId = item => item.propertyId;
const searchId = item => item.searchRequestId;
const primary = await search('Primary exact and approximate search');
await activate(buyer,'search',primary.id);
const poor = await property('Exact ordinary value', {price:96_000_000,area:60,condition:'Átlagos'});
const good = await property('Exact better value', {price:75_000_000,area:80});
const liked = await property('Exact already interested seller', {price:99_000_000,area:61});
const close = await property('Small numeric deviations', {price:102_000_000,area:59,rooms:2.5});
const far = await property('Larger numeric deviations', {price:140_000_000,area:40,rooms:1});
const areaOnly = await property('Only a small area deviation', {price:80_000_000,area:58});
const wrongTown = await property('Wrong town must never be suggested', {city:'Poroszló',locationId:'city:Poroszló'});
const wrongType = await property('Wrong type must never be suggested', {type:'Ház',lotArea:500,floor:null});
const archived = await property('Archived property must never be suggested', {archived:true});
const own = await property('Own property must never be suggested', {}, buyer);

// Fifty is a response page size, not a limit on the pool of exact matches.
const fillers=[];
for(let index=0;index<52;index++) fillers.push(await property(`Exact pagination fixture ${index+1}`, {
  price:98_000_000+index*1000, area:60
}));
const exactIds = new Set([poor,good,liked,...fillers].map(item=>item.id));
const nearIds = new Set([close,far,areaOnly].map(item=>item.id));
const excludedIds = new Set([wrongTown,wrongType,archived,own].map(item=>item.id));
await activate(seller,'property',liked.id);
assert.equal((await decide(seller,liked,primary,true)).charged,2);
// A low-scoring partial like must not outrank a better unliked partial for a buyer.
await activate(seller,'property',far.id);
const farGate = await feed(seller);
assert.equal(farGate.items.length,0);assert.equal(farGate.requiresApproximateConsent,true);
assert.equal((await decide(seller,far,primary,true,true)).charged,2);

const exact = await feed(buyer);
assert.equal(exact.stage,'exact');assert.equal(exact.items.length,50);
assert.equal(exact.requiresApproximateConsent,false);
assert.equal(propertyId(exact.items[0]),liked.id,'An existing seller like comes before value among equal percentages');
assert.equal(propertyId(exact.items[1]),good.id,'Price and living area must reward the better-value property');
for(const item of exact.items){
  assert.equal(score(item),100);assert.equal(item.isExact,true);assert.ok(exactIds.has(propertyId(item)));
  assert.equal(item.property.address,'');assertNoContactData(item,[privatePhone,buyer.email,seller.email,propertyBase.address]);
}
const notLiked = exact.items.filter(item=>!item.likedYou);
for(let index=1;index<notLiked.length;index++) assert.ok(notLiked[index-1].valueForMoney>=notLiked[index].valueForMoney);
assert.deepEqual((await feed(buyer,true)).items.map(propertyId),exact.items.map(propertyId),
  'Opting in cannot skip unseen exact matches');
const beforeForbidden = (await api('/me',{token:buyer.token})).credits;
await decide(buyer,close,primary,true,true,400);
await decide(buyer,wrongTown,primary,true,true,400);
await decide(buyer,wrongType,primary,true,true,400);
assert.equal((await api('/me',{token:buyer.token})).credits,beforeForbidden);
for(const item of exact.items) await decide(buyer,{id:item.propertyId},primary,false);
const remaining = await feed(buyer,true);
assert.equal(remaining.stage,'exact');assert.equal(remaining.items.length,5);
assert.ok(remaining.items.every(item=>item.isExact&&score(item)===100&&exactIds.has(propertyId(item))));
for(const item of remaining.items) await decide(buyer,{id:item.propertyId},primary,false);

const consent = await feed(buyer);
assert.equal(consent.items.length,0);assert.equal(consent.hasApproximate,true);
assert.equal(consent.requiresApproximateConsent,true);
const approximate = await feed(buyer,true);
assert.equal(approximate.stage,'approximate');assert.equal(approximate.requiresApproximateConsent,false);
assert.equal(approximate.items.length,3);
assert.deepEqual(new Set(approximate.items.map(propertyId)),nearIds);
for(const item of approximate.items){
  assert.equal(item.isExact,false);assert.ok(score(item)>=0&&score(item)<100);
  assert.equal(excludedIds.has(propertyId(item)),false);assert.equal(item.property.address,'');
}
const closeItem=approximate.items.find(item=>propertyId(item)===close.id);
const farItem=approximate.items.find(item=>propertyId(item)===far.id);
assert.ok(score(closeItem)>score(farItem),'Greater bound deviations must lose more percentage points');
assert.equal(farItem.likedYou,true);
assert.ok(approximate.items.indexOf(closeItem)<approximate.items.indexOf(farItem),
  'Buyer percentage takes precedence over a lower-scoring existing like');
await decide(buyer,wrongTown,primary,true,true,400);
await decide(buyer,wrongType,primary,true,true,400);
await decide(buyer,close,primary,true,false,400);
assert.equal((await decide(buyer,close,primary,true,true)).charged,0);
assert.equal((await decide(buyer,close,primary,true,true)).charged,0);

// Near matches still use the ordinary two-sided matching and exactly-once billing.
await activate(seller,'property',close.id);
assert.equal((await feed(seller)).requiresApproximateConsent,true);
const beforeSeller = (await api('/me',{token:seller.token})).credits;
await decide(seller,close,primary,true,false,400);
assert.equal((await api('/me',{token:seller.token})).credits,beforeSeller);
const replies = await Promise.all([decide(seller,close,primary,true,true),decide(seller,close,primary,true,true)]);
assert.equal(replies.reduce((sum,item)=>sum+item.charged,0),2);
assert.ok(replies.every(item=>item.matchId&&item.matchId===replies[0].matchId));
assert.equal((await api('/me',{token:seller.token})).credits,beforeSeller-2);
const matches = await api('/matches',{token:buyer.token});
const matched = matches.find(item=>item.id===replies[0].matchId);
assert.ok(matched);assert.equal(matched.contact.email,seller.email);assert.equal(matched.contact.phone,privatePhone);
assert.equal(matched.property.address,propertyBase.address);
await api(`/matches/${matched.id}/messages`,{token:secondBuyer.token,method:'POST',body:{text:'Forbidden outsider message'},status:404});

// Seller order: existing likes, percentage, then search specialization.
const rankingHome = await property('Seller specialization ranking property', {
  price:80_000_000,area:80,rooms:4,condition:'Jó',building:'Tégla',
  constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m alatti',
  heatingType:'Gázkazán',floor:2,balcony:true,elevator:true
});
const newlyExact = await feed(buyer,true);
assert.equal(newlyExact.stage,'exact');
assert.deepEqual(newlyExact.items.map(propertyId),[rankingHome.id],
  'A new exact listing must restore the exact stage after earlier approximate consent');
await decide(buyer,far,primary,true,true,400);
const broad = await search('Broad seller ranking search', {
  maxPrice:150_000_000,minArea:40,minRooms:1,
  locationIds:[`city:${town}`,'city:Tiszafüred','city:Karcag']
},secondBuyer);
const specific = await search('Specialized seller ranking search', {
  maxPrice:90_000_000,minArea:75,maxArea:90,minRooms:4,maxRooms:4.5,
  conditions:['Jó'],buildings:['Tégla'],constructionAges:['10–30 év közötti'],
  views:['Kertre néző'],ceilingHeight:'3 m alatti',floors:[2],heatingTypes:['Gázkazán'],balcony:true,elevator:true
},secondBuyer);
const partialSearch = await search('Already interested partial seller ranking search', {
  maxPrice:79_000_000,minArea:80,minRooms:4
},secondBuyer);
await activate(secondBuyer,'search',partialSearch.id);
assert.equal((await feed(secondBuyer)).requiresApproximateConsent,true);
assert.equal((await decide(secondBuyer,rankingHome,partialSearch,true,true)).charged,0);
await activate(buyer,'search',primary.id);
assert.equal((await decide(buyer,rankingHome,primary,true)).charged,0);
await activate(seller,'property',rankingHome.id);
const ranked = await feed(seller,true);
assert.equal(ranked.stage,'exact');assert.equal(ranked.items.length,3);
assert.ok(ranked.items.every(item=>item.isExact&&score(item)===100));
assert.equal(searchId(ranked.items[0]),primary.id,'A liked exact search comes first');
assert.equal(searchId(ranked.items[1]),specific.id);
assert.equal(searchId(ranked.items[2]),broad.id);
assert.ok(ranked.items[1].searchSpecificity>ranked.items[2].searchSpecificity);
assert.ok(ranked.items.every(item=>Number.isInteger(item.searchSpecificity)&&item.searchSpecificity>=0&&item.searchSpecificity<=100));
await decide(seller,rankingHome,partialSearch,true,true,400);
for(const item of ranked.items) await decide(seller,rankingHome,{id:item.searchRequestId},false);
assert.equal((await feed(seller)).requiresApproximateConsent,true);
const sellerNear = await feed(seller,true);
assert.equal(sellerNear.items.length,1);assert.equal(searchId(sellerNear.items[0]),partialSearch.id);
assert.equal(sellerNear.items[0].likedYou,true);assert.ok(score(sellerNear.items[0])<100);
const sellerNearLike = await decide(seller,rankingHome,partialSearch,true,true);
assert.equal(sellerNearLike.charged,2);assert.ok(sellerNearLike.matchId);
assert.equal((await decide(seller,rankingHome,partialSearch,true,true)).charged,0);
assert.equal((await feed(seller,true)).items.length,0);

// The compact reverse-location index must follow edits atomically, retain a
// search only once when both its city and its area match, and preserve links
// across an ordinary title-only update. This type has no baseline fixtures.
const mappingHome = await property('Location-index holiday property', {
  type:'Nyaraló',city:'Solymár',locationId:'city:Solymár'
});
const mappingBody = {...searchBase,type:'Nyaraló',title:'Location-index holiday search'};
const mappingSearch = await search(mappingBody.title,mappingBody,secondBuyer);
await activate(seller,'property',mappingHome.id);
assert.deepEqual((await feed(seller,true)).items,[],'A search outside the property location must not enter the reverse index result');
async function editMapping(locationIds,title=mappingBody.title){
  await api('/searches/'+mappingSearch.id,{token:secondBuyer.token,method:'PUT',body:{...mappingBody,locationIds,title}});
}
async function oneMappedSearch(){
  const page=await feed(seller,true);
  assert.equal(page.items.length,1,'Overlapping selected locations must not duplicate a search');
  assert.equal(searchId(page.items[0]),mappingSearch.id);assert.equal(score(page.items[0]),100);
}
await editMapping(['area:Budapest','city:Solymár']);
await oneMappedSearch();
await editMapping([`city:${town}`]);
assert.deepEqual((await feed(seller,true)).items,[],'Editing locations must remove the previous reverse-index links');
const mappedLocations=['city:Solymár','city:Tiszafüred'];
await editMapping(mappedLocations);
await oneMappedSearch();
await editMapping(mappedLocations,'Location-index title edited without changing places');
await oneMappedSearch();
console.log(`Matching API smoke passed: exact 100% and >50-candidate exhaustion, value/specialization ordering, hard location/type filters, explicit partial consent, graded deviations, privacy, mutual matches, exactly-once billing and indexed location edits/overlaps. ${feedTimes.length} real feed reads; maximum observed ${Math.round(Math.max(...feedTimes))} ms.`);
