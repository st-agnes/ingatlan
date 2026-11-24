/** Buyer-only budgets and seller-visible caps through the actual disposable MySQL API. */
import assert from 'node:assert/strict';
import {createHash,randomUUID} from 'node:crypto';

const source=(kind,id)=>kind+'-'+createHash('sha256').update(`otthonra:landing-source:v1:${kind}:${id.replaceAll('-','').toLowerCase()}`).digest('hex');
const privateBudgets=[80_000_000,90_000_000,120_000_000];
function publicBudget(value){
 if(Array.isArray(value)){value.forEach(publicBudget);return;}
 if(value&&typeof value==='object'){
  for(const [key,child]of Object.entries(value)){
   assert.ok(!['publicMaxPrice','privateMaxPrice','actualMaxPrice','trueMaxPrice'].includes(key),'A foreign response exposed owner budget metadata: '+key);
   publicBudget(child);
  }
  return;
 }
 if(typeof value==='number')assert.ok(!privateBudgets.includes(value),'A foreign response exposed the buyer-only budget');
 if(typeof value==='string')assert.doesNotMatch(value,/(?:\b(?:80|90|120)(?:[,.]0+)?\s*M\s*Ft\b|\b(?:80|90|120)[\s\u00a0]000[\s\u00a0]000\b|\b(?:80000000|90000000|120000000)\b)/u,'A foreign explanation exposed the buyer-only budget');
}

export async function checkPublicBudgets(call,{buyer,seller}){
 // This small municipality has no seeded fixture or other smoke scenario.
 // Reuse the public-listing accounts instead of increasing the auth burst.
 const town='Szuhafő',locationIds=['city:'+town];
 const propertyBody={title:'Külön árkeretek ingatlanpróbája',city:town,locationId:locationIds[0],type:'Lakás',
  price:75_000_000,area:83.5,rooms:3.5,street:'OTTHONRA TEST',houseNumber:'84',postalCode:null,
  description:'Kitalált, kizárólag integrációs tesztelésre használt ingatlan.',balcony:false,elevator:false,images:[]};
 const primary=await call('/properties',{token:seller,method:'POST',body:propertyBody,status:201});
 const higher=await call('/properties',{token:seller,method:'POST',body:{...propertyBody,title:'Második árkeretpróba',price:85_000_000,houseNumber:'86'},status:201});
 const searchBody={title:'Alkupozíciót védő keresés',city:town,locationIds,type:'Lakás',minPrice:null,
  maxPrice:80_000_000,publicMaxPrice:70_000_000,minArea:70,maxArea:null,minRooms:2.5,maxRooms:null,balcony:false,elevator:false};
 const creationRequestId=randomUUID(),createBody={...searchBody,creationRequestId};
 let search=await call('/searches',{token:buyer,method:'POST',body:createBody,status:201});
 assert.equal(search.maxPrice,80_000_000);assert.equal(search.publicMaxPrice,70_000_000);
 const replay=await call('/searches',{token:buyer,method:'POST',body:createBody});assert.equal(replay.id,search.id);
 await call('/searches',{token:buyer,method:'POST',body:{...createBody,publicMaxPrice:71_000_000},status:409});
 for(const changes of [{publicMaxPrice:0},{publicMaxPrice:-1},{publicMaxPrice:81_000_000},{minPrice:71_000_000}])
  await call('/searches',{token:buyer,method:'POST',body:{...searchBody,...changes},status:400});
 const visible=await call('/searches',{token:buyer,method:'POST',body:{...searchBody,title:'Azonos publikus keret',maxPrice:70_000_000,publicMaxPrice:null},status:201});
 assert.equal(visible.maxPrice,70_000_000);assert.equal(visible.publicMaxPrice,null,'An omitted public cap retains the legacy same-budget fallback');
 const exact=await call('/searches',{token:buyer,method:'POST',body:{...searchBody,title:'Eladói szemszögből teljes egyezés',maxPrice:120_000_000,publicMaxPrice:75_000_000},status:201});
 const searchPath='/public/listings/search/'+source('search',search.id);
 const detail=await call(searchPath);publicBudget(detail);
 assert.equal(detail.listing.maxPrice,70_000_000);assert.equal(detail.clonePrefill.maxPrice,70_000_000);
 assert.equal(detail.prefill.maxPrice,70_000_000,'The anonymous onboarding seed uses only the public maximum');
 const activate=(token,kind,id)=>call('/me/active',{token,method:'PUT',body:{kind,id}});
 const feed=(token,approximate=false)=>call('/feed'+(approximate?'?includeApproximate=true':''),{token});
 const decide=(token,property,request,liked,allowApproximate=false,status=200)=>call('/decisions',{token,method:'POST',
  body:{propertyId:property.id,searchRequestId:request.id,liked,allowApproximate},status});
 await activate(buyer,'search',search.id);
 let buyerFeed=await feed(buyer);
 assert.equal(buyerFeed.stage,'exact');
 const buyerCard=buyerFeed.items.find(row=>row.propertyId===primary.id);assert.ok(buyerCard);
 assert.equal(buyerCard.compatibilityScore,100);assert.equal(buyerCard.isExact,true);
 assert.equal(buyerFeed.items.some(row=>row.propertyId===higher.id),false,'The real maximum remains the buyer recommendation bound');
 await call('/impressions',{token:buyer,method:'POST',body:{propertyId:primary.id,searchRequestId:search.id}});
 await activate(seller,'property',primary.id);
 let sellerFeed=await feed(seller,true);publicBudget(sellerFeed);
 assert.equal(sellerFeed.stage,'exact');assert.deepEqual(sellerFeed.items.map(row=>row.searchRequestId),[exact.id]);
 assert.equal(sellerFeed.items[0].compatibilityScore,100);assert.equal(sellerFeed.items[0].searchRequest.maxPrice,75_000_000);
 assert.equal(sellerFeed.hasApproximate,true,'A buyer-only larger budget cannot turn a public over-budget search into an exact seller match');
 await decide(seller,primary,search,true,true,400);
 assert.equal((await decide(buyer,primary,search,true)).charged,0,'The buyer may like its own true-budget exact match without approximate consent');
 const incoming=await call('/incoming-likes',{token:seller});publicBudget(incoming);
 const interest=incoming.items.find(row=>row.searchRequestId===search.id);assert.ok(interest);
 assert.equal(interest.isExact,false);assert.ok(interest.compatibilityScore<100);
 assert.equal(interest.searchRequest.maxPrice,70_000_000);
 const price=interest.matchDetails.find(row=>row.key==='price');assert.equal(price.matches,false);assert.match(price.expected,/70\s*M Ft/);
 const notifications=await call('/notifications',{token:seller});
 const notice=notifications.items.find(row=>row.kind==='incoming_like'&&row.target?.searchRequestId===search.id);assert.ok(notice);
 const context=await call('/notifications/'+notice.id+'/context',{token:seller});publicBudget(context);
 assert.equal(context.available,true);assert.equal(context.item.compatibilityScore,interest.compatibilityScore);
 assert.equal(context.item.searchRequest.maxPrice,70_000_000);
 await decide(seller,primary,exact,false);
 const consent=await feed(seller);assert.equal(consent.items.length,0);assert.equal(consent.requiresApproximateConsent,true);
 sellerFeed=await feed(seller,true);publicBudget(sellerFeed);
 const protectedRow=sellerFeed.items.find(row=>row.searchRequestId===search.id),samePublic=sellerFeed.items.find(row=>row.searchRequestId===visible.id);
 assert.ok(protectedRow&&samePublic);assert.ok(protectedRow.compatibilityScore<100);
 assert.equal(protectedRow.compatibilityScore,samePublic.compatibilityScore,'Seller percentages use the same public limit regardless of hidden capacity');
 assert.equal(protectedRow.searchSpecificity,samePublic.searchSpecificity,'Seller specificity cannot reveal a different hidden maximum');
 const before=(await call('/me',{token:seller})).credits;
 await decide(seller,primary,search,true,false,400);assert.equal((await call('/me',{token:seller})).credits,before);
 await call('/credits/demo-topup',{token:seller,method:'POST',body:{amount:20}});
 const match=await decide(seller,primary,search,true,true);assert.equal(match.charged,2);assert.ok(match.matchId);
 assert.equal((await decide(seller,primary,search,true,true)).charged,0,'Retry remains exactly-once even with asymmetric budget matching');
 const sellerMatch=(await call('/matches',{token:seller})).find(row=>row.id===match.matchId);assert.ok(sellerMatch);publicBudget(sellerMatch.searchRequest);
 assert.equal(sellerMatch.searchRequest.maxPrice,70_000_000,'A mutual match does not disclose a private negotiation ceiling');
 const history=(await call('/me/entities',{token:seller})).decisions.find(row=>row.searchRequestId===search.id);assert.ok(history);publicBudget(history.search);
 assert.equal(history.search.maxPrice,70_000_000);
 await activate(seller,'property',higher.id);
 const beforePrivateEdit=(await feed(seller,true)).items.find(row=>row.searchRequestId===search.id);assert.ok(beforePrivateEdit);publicBudget(beforePrivateEdit);
 assert.equal(beforePrivateEdit.isExact,false);
 search=await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...searchBody,maxPrice:90_000_000}});
 assert.equal(search.maxPrice,90_000_000);assert.equal(search.publicMaxPrice,70_000_000);
 buyerFeed=await feed(buyer);const nowExact=buyerFeed.items.find(row=>row.propertyId===higher.id);assert.ok(nowExact);assert.equal(nowExact.compatibilityScore,100);
 const afterPrivateEdit=(await feed(seller,true)).items.find(row=>row.searchRequestId===search.id);assert.ok(afterPrivateEdit);publicBudget(afterPrivateEdit);
 for(const key of ['compatibilityScore','isExact','searchSpecificity','matchDetails'])assert.deepEqual(afterPrivateEdit[key],beforePrivateEdit[key],'Changing the private maximum cannot change seller-visible '+key);
 assert.equal((await call(searchPath)).clonePrefill.maxPrice,70_000_000);
 const owned=(await call('/searches',{token:buyer})).find(row=>row.id===search.id);assert.equal(owned.maxPrice,90_000_000);assert.equal(owned.publicMaxPrice,70_000_000);
 console.log('Public budget API checks passed: asymmetric exact/partial ranking, public-only seller specificity and consent, protected incoming/history/match/notification details, public cloning, immutable creation receipts and unchanged seller results after a private-budget edit.');
 return {buyer,seller,searchId:search.id,propertyId:higher.id,matchId:match.matchId,searchPath,maxPrice:90_000_000,publicMaxPrice:70_000_000};
}

export async function verifyPublicBudgets(fixture,call){
 if(!fixture)return;
 const owner=(await call('/me/entities',{token:fixture.buyer})).searchRequests.find(row=>row.id===fixture.searchId);assert.ok(owner);
 assert.equal(owner.maxPrice,fixture.maxPrice);assert.equal(owner.publicMaxPrice,fixture.publicMaxPrice);
 const detail=await call(fixture.searchPath);publicBudget(detail);assert.equal(detail.listing.maxPrice,fixture.publicMaxPrice);assert.equal(detail.clonePrefill.maxPrice,fixture.publicMaxPrice);
 const matches=await call('/matches',{token:fixture.seller});const match=matches.find(row=>row.id===fixture.matchId);assert.ok(match);publicBudget(match.searchRequest);assert.equal(match.searchRequest.maxPrice,fixture.publicMaxPrice);
 const buyerFeed=await call('/feed',{token:fixture.buyer});const buyerRow=buyerFeed.items.find(row=>row.propertyId===fixture.propertyId);assert.ok(buyerRow);assert.equal(buyerRow.compatibilityScore,100);
 const sellerFeed=await call('/feed?includeApproximate=true',{token:fixture.seller});publicBudget(sellerFeed);
 const sellerRow=sellerFeed.items.find(row=>row.searchRequestId===fixture.searchId);assert.ok(sellerRow);assert.ok(sellerRow.compatibilityScore<100);assert.equal(sellerRow.searchRequest.maxPrice,fixture.publicMaxPrice);
 console.log('Public budget restart preservation passed: the owner retains the private cap, foreign/public responses retain only the public cap, and both recommendation perspectives remain distinct.');
}
