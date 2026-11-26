/** Included by the disposable loopback attribute/API smoke, never run in a deployment. */
import assert from 'node:assert/strict';
import {descriptionContactMessage} from '../dist/contact-policy.js';
import {evaluateMatch} from '../dist/matching.js';
import {checkPublicListingRefinements,verifyPublicListingRefinements} from './public-listing-smoke.mjs';

export async function checkFormRefinements({call, buyer, seller, baseProperty}) {
  const safeDescription='Világos, 2020-ban felújított, harminchat négyzetméteres otthon, két egész szobával.';
  const propertyBody={...baseProperty,title:'Új emeletválasztások próbája',price:41123456,area:77.5,rooms:2.5,description:safeDescription};
  const createProperty=change=>call('/properties',{token:seller,method:'POST',body:{...propertyBody,...change},status:201});
  const raised=await createProperty({floor:0.5,buildingFloors:0});
  const ground=await createProperty({floor:0,buildingFloors:0});
  const upper=await createProperty({floor:9,floorIsUpperRange:true,buildingFloors:12});
  const exact=await createProperty({floor:12,floorIsUpperRange:false,buildingFloors:12});
  assert.equal(raised.floor,0.5);assert.equal(raised.floorIsUpperRange,false);
  assert.equal(upper.floor,9);assert.equal(upper.floorIsUpperRange,true);
  assert.equal(exact.floor,12);assert.equal(exact.floorIsUpperRange,false);
  const searchBody={title:'Új emeletfeltételek próbája',city:baseProperty.city,locationIds:[baseProperty.locationId],type:'Lakás',
    minPrice:propertyBody.price,maxPrice:propertyBody.price,minArea:propertyBody.area,maxArea:propertyBody.area,minRooms:2.5,maxRooms:2.5,
    balcony:false,elevator:false,description:safeDescription};
  const searchAndFeed=async change=>{
    const search=await call('/searches',{token:buyer,method:'POST',body:{...searchBody,...change},status:201});
    await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
    return {search,feed:await call('/feed',{token:buyer})};
  };
  const ids=feed=>feed.items.map(item=>item.propertyId).sort();
  const raisedSearch=await searchAndFeed({floors:[0.5]});
  assert.deepEqual(ids(raisedSearch.feed),[raised.id]);
  const upperSearch=await searchAndFeed({floors:[9]});
  assert.deepEqual(ids(upperSearch.feed),[upper.id,exact.id].sort());
  const legacySearch=await searchAndFeed({floors:[11]});
  assert.deepEqual(legacySearch.search.floors,[8]);
  assert.deepEqual(ids(legacySearch.feed),[upper.id,exact.id].sort());
  const upperWithoutTop=await searchAndFeed({floors:[9],excludeTopFloor:true});
  assert.equal(upperWithoutTop.feed.items.length,0,'Neither a known top floor nor an unknown 9+ floor can be a perfect not-top-floor match');
  const raisedWithoutTop=await searchAndFeed({floors:[0.5],excludeTopFloor:true});
  assert.equal(raisedWithoutTop.feed.items.length,0,'A raised ground floor is the top in a ground-only building');
  const aboveGround=await searchAndFeed({excludeGroundFloorAndBelow:true});
  assert.ok(ids(aboveGround.feed).includes(raised.id),'Raised ground is above ground for the exclusion');
  assert.ok(!ids(aboveGround.feed).includes(ground.id));
  for(const floor of [0.25,1.5])await call('/properties',{token:seller,method:'POST',body:{...propertyBody,floor,buildingFloors:12},status:400});
  await call('/properties',{token:seller,method:'POST',body:{...propertyBody,floor:8,floorIsUpperRange:true,buildingFloors:12},status:400});
  await call('/searches',{token:buyer,method:'POST',body:{...searchBody,floors:[0.25]},status:400});

  // Use a different non-house type and a substantial price gap from the
  // earlier apartment fixtures. Their one-forint differences can otherwise
  // round away in MySQL's relative numeric-loss arithmetic.
  const alternativeType='Iroda',alternativePrice=propertyBody.price+5_000_000;
  const eighth=await createProperty({type:alternativeType,price:alternativePrice,floor:8,buildingFloors:9,isAttic:false});
  const third=await createProperty({type:alternativeType,price:alternativePrice,floor:3,buildingFloors:9,isAttic:false});
  const attic=await createProperty({type:alternativeType,price:alternativePrice,floor:7,buildingFloors:7,isAttic:true});
  const alternative={type:alternativeType,minPrice:alternativePrice,maxPrice:alternativePrice};
  const alternativePropertyIds=new Set([eighth.id,third.id,attic.id]);
  const alternativeItems=feed=>feed.items.filter(item=>alternativePropertyIds.has(item.propertyId));
  const alternativeIds=feed=>alternativeItems(feed).map(item=>item.propertyId).sort();
  const eighthSearch=await searchAndFeed({...alternative,floors:[8]});
  assert.deepEqual(alternativeIds(eighthSearch.feed),[eighth.id],'Only the eighth-floor cohort property satisfies the upper search bucket');
  const legacyEighthSearch=await searchAndFeed({...alternative,floors:[11]});
  assert.deepEqual(legacyEighthSearch.search.floors,[8]);
  assert.deepEqual(alternativeIds(legacyEighthSearch.feed),[eighth.id],'A stored legacy upper bucket also includes the eighth floor');
  const atticOrFloor=await searchAndFeed({...alternative,floors:[3],atticPreference:'only'});
  assert.deepEqual(alternativeIds(atticOrFloor.feed),[third.id,attic.id].sort(),'The third floor OR an attic is an exact match; the eighth floor is partial');
  for(const item of alternativeItems(atticOrFloor.feed)){
    const detail=item.matchDetails.find(value=>value.key==='floor');
    assert.equal(detail.expected,'3. emelet vagy Tetőtéri ingatlan');assert.equal(detail.matches,true);
    assert.ok(!item.matchDetails.some(value=>value.key==='atticPreference'),'An OR alternative cannot appear as an independent failed criterion');
  }
  await call('/me/active',{token:seller,method:'PUT',body:{kind:'property',id:attic.id}});
  const sellerAlternatives=await call('/feed',{token:seller});
  assert.ok(sellerAlternatives.items.some(item=>item.searchRequestId===atticOrFloor.search.id&&item.compatibilityScore===100),'The same OR choice works in the seller query');
  // Approximate consent does not skip unseen exact matches. Pass only this
  // search's two known exact candidates before requesting its partial stage.
  for(const property of [third,attic])await call('/decisions',{token:buyer,method:'POST',body:{propertyId:property.id,searchRequestId:atticOrFloor.search.id,liked:false}});
  const partial=await call('/feed?includeApproximate=true',{token:buyer});
  assert.equal(partial.stage,'approximate','Partial floor scoring is checked only after the known exact matches have been handled');
  const eighthCard=alternativeItems(partial).find(item=>item.propertyId===eighth.id);assert.ok(eighthCard,'The isolated eighth-floor candidate must be selected for the partial page');
  assert.equal(eighthCard.compatibilityScore,61,'The OR alternatives share one floor penalty');
  assert.equal(eighthCard.compatibilityScore,evaluateMatch(eighthCard.property,eighthCard.searchRequest).score,'MySQL and browser share the floor/attic distance');
  const notTop=await searchAndFeed({...alternative,floors:[3],atticPreference:'only',excludeTopFloor:true});
  assert.deepEqual(alternativeIds(notTop.feed),[third.id],'The top-floor exclusion still applies to an attic alternative');
  const withLift=await searchAndFeed({...alternative,floors:[3],atticPreference:'only',elevator:true});
  assert.deepEqual(alternativeIds(withLift.feed),[],'The elevator requirement still applies to both alternatives');

  const forbidden=[
    'Telefonon elérsz: +36 20 123 4567.',
    'Elérsz: nulla hat húsz egy kettő három négy öt hat hét.',
    'Írj ide: peter kukac pelda pont hu.'
  ];
  for(const description of forbidden){
    const error={status:400,message:descriptionContactMessage};
    await call('/properties',{token:seller,method:'POST',body:{...propertyBody,floor:0,description},...error});
    await call('/searches',{token:buyer,method:'POST',body:{...searchBody,description},...error});
    await call('/properties/'+raised.id,{token:seller,method:'PUT',body:{...propertyBody,floor:0.5,buildingFloors:0,description},...error});
    await call('/searches/'+raisedSearch.search.id,{token:buyer,method:'PUT',body:{...searchBody,floors:[0.5],description},...error});
  }
  const owner=await call('/me/entities',{token:seller});
  assert.equal(owner.properties.find(item=>item.id===raised.id).description,safeDescription,'Rejected descriptions cannot overwrite a saved property');
  const seeker=await call('/me/entities',{token:buyer});
  assert.equal(seeker.searchRequests.find(item=>item.id===raisedSearch.search.id).description,safeDescription,'Rejected descriptions cannot overwrite a saved search');
  console.log('Form refinement API checks passed: raised/upper floor semantics, legacy floor buckets, numeric precision and contact-free descriptions.');
  const publicListings=await checkPublicListingRefinements(call,baseProperty);
  return {publicListings,properties:[raised,ground,upper,exact,eighth,third,attic].map(({id,floor,floorIsUpperRange,buildingFloors})=>({id,floor,floorIsUpperRange,buildingFloors})),
    search:{id:raisedSearch.search.id,floors:[0.5]},description:safeDescription};
}

export async function verifyFormRefinementPersistence(refinements,seller,buyer,call) {
  if(!refinements)return;
  for(const expected of refinements.properties){
    const property=seller.properties.find(item=>item.id===expected.id);assert.ok(property);
    for(const field of ['floor','floorIsUpperRange','buildingFloors'])assert.equal(property[field],expected[field],field+' must survive a MySQL restart');
    assert.equal(property.description,refinements.description);
  }
  const search=buyer.searchRequests.find(item=>item.id===refinements.search.id);assert.ok(search);
  assert.deepEqual(search.floors,refinements.search.floors);assert.equal(search.description,refinements.description);
  await verifyPublicListingRefinements(refinements.publicListings,call);
}
