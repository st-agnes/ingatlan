/** Actual anonymous listing and seller-form contracts, scoped to disposable API accounts. */
import assert from 'node:assert/strict';
import {createHash,randomUUID} from 'node:crypto';
import {checkPublicBudgets,verifyPublicBudgets} from './public-budget-smoke.mjs';

const source=(kind,id)=>kind+'-'+createHash('sha256').update(`otthonra:landing-source:v1:${kind}:${id.replaceAll('-','').toLowerCase()}`).digest('hex');
const fields=['hideStreet','hideHouseNumber','isAttic','energyRating','energyRatingScheme','balcony','airConditioning','privateGarden','insulated','solarPanels'];

export async function checkPublicListingRefinements(call,baseProperty){
 const suffix=Date.now()+'-'+randomUUID(),accounts={};
 for(const role of ['buyer','seller']){
  const session=await call('/auth/register',{method:'POST',body:{name:'Publikus '+role,email:`public-${role}-${suffix}@example.test`,password:'PublicListingSmoke2026!',phone:'+36 20 555 0788'}});
  accounts[role]={token:session.accessToken,id:session.user.id,email:session.user.email};
 }
 const buyer=accounts.buyer.token,seller=accounts.seller.token;
 const base={...baseProperty,title:'Minden adattal bemutatott otthon',price:52345678,area:83.5,rooms:3.5,
  description:'Világos szobák és tágas konyha.',floor:10,buildingFloors:15,floorIsUpperRange:false,
  balcony:null,airConditioning:null,privateGarden:null,insulated:null,solarPanels:null,isAttic:null,
  energyRating:'A++',energyRatingScheme:'',street:'OTTHONRA TEST',houseNumber:'82',postalCode:null,
  heatingType:'Gázkazán',images:['https://images.example.test/first.jpg','https://images.example.test/second.jpg']};
 let property=await call('/properties',{token:seller,method:'POST',body:base,status:201});
 assert.equal(property.floor,10);assert.equal(property.buildingFloors,15);
 assert.equal(property.hideStreet,true);assert.equal(property.hideHouseNumber,true);
 for(const key of ['balcony','airConditioning','privateGarden','insulated','solarPanels','isAttic'])assert.equal(property[key],null,key+' must preserve the unspecified state');
 assert.equal(property.heatingType,'Gázkazán / cirkó');
 const propertyKey=source('property',property.id),publicPath='/public/listings/property/'+propertyKey;
 const propertyContext='/listings/property/'+propertyKey+'/context',propertyMap=publicPath+'/map';
 assert.equal(property.publicListingKey,propertyKey);
 await call(propertyContext,{status:401});
 assert.equal((await call(propertyContext,{token:buyer})).unavailableReason,'no_active_profile');
 let detail=await call(publicPath);
 assert.equal(detail.key,propertyKey);assert.equal(detail.sourceKey,propertyKey);assert.equal(detail.kind,'property');
 assert.equal(detail.href,'#listing/property/'+propertyKey);
 assert.equal(detail.listing.title,base.title);assert.deepEqual(detail.listing.images,base.images);
 for(const key of ['address','street','houseNumber'])assert.equal(detail.listing[key],'');
 const noPrivate=(item,ids=[])=>{
  const raw=JSON.stringify(item);
  for(const value of [...ids,accounts.buyer.id,accounts.seller.id,accounts.buyer.email,accounts.seller.email,'+36 20 555 0788'])assert.ok(!raw.includes(value),'Anonymous detail must omit private identities and contacts');
  const visit=value=>{if(Array.isArray(value)){value.forEach(visit);return;}if(!value||typeof value!=='object')return;
   for(const [key,child]of Object.entries(value)){assert.ok(!['ownerId','userId','email','phone','addressDetails','latitude','longitude','geocodingPlaceId','geocodingAddressKey','creationRequestId','creationRequestHash','creationRequestHashVersion'].includes(key),'Anonymous detail exposed '+key);visit(child);}};
  visit(item);
 };
 noPrivate(detail,[property.id]);
 let map=await call(propertyMap);noPrivate(map,[property.id]);assert.equal(map.externalUrl,null);assert.equal(map.available,true);assert.equal(map.locationIds.length,1);
 assert.ok(map.locationIds[0].startsWith('neighborhood:')||map.locationIds[0]==='city:'+base.city,'A hidden home exposes only a containing neighborhood or its municipality');
 assert.ok(property.neighborhoodIds.length?property.neighborhoodIds.includes(map.locationIds[0]):map.locationIds[0]==='city:'+base.city,'A hidden map outline must actually contain the saved property point');
 for(const path of ['/public/listings/property/'+property.id,'/public/listings/search/'+propertyKey,'/public/listings/property/property-'+'0'.repeat(64)])await call(path,{status:404});
 const criteria={title:'Pontos tetőtér- és energiaigény',city:baseProperty.city,locationIds:[baseProperty.locationId],type:'Lakás',
  minPrice:base.price,maxPrice:base.price,minArea:base.area,maxArea:base.area,minRooms:base.rooms,maxRooms:base.rooms,
  balcony:false,elevator:false,atticPreference:'only',minEnergyRating:'B',description:'Tágas, világos otthont keresek.'};
 let search=await call('/searches',{token:buyer,method:'POST',body:criteria,status:201});
 assert.equal(search.publicListingKey,source('search',search.id));
 await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
 const has=async()=> (await call('/feed',{token:buyer})).items.some(item=>item.propertyId===property.id);
 assert.equal(await has(),false,'Unknown attic and unmarked legacy energy cannot satisfy explicit criteria');
 const modern={...base,isAttic:true,energyRating:'A+',energyRatingScheme:'2023',balcony:false,airConditioning:false,privateGarden:false,insulated:false,solarPanels:false,hideStreet:false,hideHouseNumber:false};
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:modern});
 assert.equal(await has(),true);
 let listingContext=await call(propertyContext,{token:buyer});
 assert.equal(listingContext.available,true);assert.equal(listingContext.canDecide,true);assert.equal(listingContext.compatibilityScore,100);assert.equal(listingContext.isExact,true);
 assert.equal(listingContext.active.id,search.id);assert.equal(listingContext.active.maxPrice,criteria.maxPrice);assert.equal(listingContext.likeCost,0);
 assert.equal(listingContext.myDecision,null);assert.equal(listingContext.item.property.publicListingKey,propertyKey);
 assert.equal(listingContext.item.property.addressDetails,null,'The detail context never needs even an owned geocoding payload');
 const ordinary=(await call('/feed',{token:buyer})).items.find(row=>row.propertyId===property.id);
 for(const key of ['compatibilityScore','isExact','matchDetails'])assert.deepEqual(listingContext.item[key],ordinary[key],'Public detail and discovery must use the same '+key);
 map=await call(propertyMap);assert.deepEqual(map.locationIds,[]);assert.match(map.externalUrl,/^https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=/);assert.match(decodeURIComponent(map.externalUrl),/OTTHONRA TEST 82/);
 noPrivate(map,[property.id]);
 const stored=(await call('/me/entities',{token:seller})).properties.find(row=>row.id===property.id);
 for(const key of ['hideStreet','hideHouseNumber','balcony','airConditioning','privateGarden','insulated','solarPanels'])assert.equal(stored[key],false,key+' false must survive actual EF/MySQL persistence');
 assert.equal(stored.isAttic,true);assert.equal(stored.energyRatingScheme,'2023');
 detail=await call(publicPath);assert.equal(detail.listing.street,'OTTHONRA TEST');assert.equal(detail.listing.houseNumber,'82');assert.equal(detail.listing.address,'OTTHONRA TEST 82');noPrivate(detail,[property.id]);
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...modern,hideHouseNumber:true}});
 map=await call(propertyMap);assert.equal(map.externalUrl,null);assert.ok(map.locationIds.length===1);assert.ok(!JSON.stringify(map).includes('OTTHONRA TEST'));
 detail=await call(publicPath);assert.equal(detail.listing.street,'OTTHONRA TEST');assert.equal(detail.listing.houseNumber,'');assert.equal(detail.listing.address,'OTTHONRA TEST');
 search=await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...criteria,atticPreference:'exclude'}});
 assert.equal(await has(),false,'Known attic homes must not satisfy the exclusion');
 const nonAttic={...modern,isAttic:false,hideStreet:true,hideHouseNumber:false};
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:nonAttic});
 assert.equal(property.hideHouseNumber,true,'Hiding the street also hides its number');
 assert.equal(await has(),true,'A hidden street remains eligible through its city/district location');
 assert.deepEqual(property.neighborhoodIds,stored.neighborhoodIds,'Visibility edits must retain indexed neighborhood membership');
 assert.equal(property.addressDetails.latitude,stored.addressDetails.latitude);assert.equal(property.addressDetails.longitude,stored.addressDetails.longitude);
 detail=await call(publicPath);for(const key of ['street','houseNumber','address'])assert.equal(detail.listing[key],'');
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...nonAttic,energyRating:'A++',energyRatingScheme:''}});
 assert.equal(await has(),false,'A legacy-looking good label is not proof of the current energy scheme');
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...nonAttic,balcony:null}});
 search=await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...criteria,atticPreference:'exclude',balcony:true}});
 assert.equal(await has(),false,'Unknown balcony does not satisfy a balcony requirement');
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...nonAttic,balcony:false}});assert.equal(await has(),false);
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...nonAttic,balcony:true}});assert.equal(await has(),true);
 for(const changes of [{energyRating:'AA',energyRatingScheme:'2023'},{energyRating:'A',energyRatingScheme:'unknown'}])await call('/properties',{token:seller,method:'POST',body:{...base,...changes},status:400});
 await call('/searches',{token:buyer,method:'POST',body:{...criteria,minEnergyRating:'AA'},status:400});
 await call('/searches',{token:buyer,method:'POST',body:{...criteria,atticPreference:'unknown'},status:400});
 // A full public search can be copied without inventing any bound or losing an optional criterion.
 const cloneBody={...criteria,title:'Másolható részletes keresés',minPrice:null,maxPrice:75000000,minArea:70,maxArea:null,minRooms:2.5,maxRooms:null,
  conditions:['Jó','Új/felújított'],buildings:['Tégla'],constructionAges:['10 évnél fiatalabb'],views:['Kertre néző'],ceilingHeight:'3 m feletti',
  floors:[0.5,8],heatingTypes:['Gázkazán','Hőszivattyú'],balcony:true,elevator:true,excludeTopFloor:true,airConditioning:true,privateGarden:true,
  atticPreference:'exclude',minEnergyRating:'C',moveIn:'3 hónapon belül',financing:'Saját megtakarítás'};
 const clonedSearch=await call('/searches',{token:buyer,method:'POST',body:cloneBody,status:201});
 const searchKey=source('search',clonedSearch.id),searchPath='/public/listings/search/'+searchKey;
 const searchDetail=await call(searchPath);noPrivate(searchDetail,[clonedSearch.id]);
 for(const key of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms','conditions','buildings','constructionAges','views','ceilingHeight','floors','balcony','elevator','excludeTopFloor','airConditioning','privateGarden','atticPreference','minEnergyRating','moveIn','financing','description'])assert.deepEqual(searchDetail.clonePrefill[key],cloneBody[key],key+' must round-trip into the anonymous search clone');
 assert.deepEqual(searchDetail.clonePrefill.heatingTypes,['Gázkazán / cirkó','Hőszivattyú']);
 assert.deepEqual(searchDetail.clonePrefill.locations.map(row=>row.id),cloneBody.locationIds);
 assert.equal(Object.hasOwn(searchDetail.clonePrefill,'title'),false,'A copied profile receives a new automatic title');
 map=await call(searchPath+'/map');assert.deepEqual(map.locationIds,cloneBody.locationIds);assert.equal(map.externalUrl,null);noPrivate(map,[clonedSearch.id]);
 await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:clonedSearch.id}});
 listingContext=await call('/listings/search/'+searchKey+'/context',{token:buyer});assert.equal(listingContext.available,false);assert.equal(listingContext.unavailableReason,'opposite_profile_required');assert.equal(listingContext.item,null);
 await call('/searches/'+clonedSearch.id,{token:buyer,method:'PUT',body:{...criteria,atticPreference:'exclude',balcony:true}});
 await call('/decisions',{token:buyer,method:'POST',body:{propertyId:property.id,searchRequestId:clonedSearch.id,liked:false}});
 listingContext=await call(propertyContext,{token:buyer});assert.equal(listingContext.myDecision,'passed');assert.equal(listingContext.canDecide,false);assert.equal(listingContext.unavailableReason,'already_passed');
 await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
 const request=randomUUID(),onceBody={...base,title:'Egyszer menthető nullable erkély',price:base.price+1,creationRequestId:request};
 const once=await call('/properties',{token:seller,method:'POST',body:onceBody,status:201});
 const replay=await call('/properties',{token:seller,method:'POST',body:onceBody});assert.equal(replay.id,once.id);assert.equal(replay.balcony,null);
 await call('/properties',{token:seller,method:'POST',body:{...onceBody,balcony:false},status:409});
 // Use disposable extra rows to prove archived public URLs do not remain accessible.
 await call('/properties/'+once.id,{token:seller,method:'DELETE',status:204});
 await call('/public/listings/property/'+source('property',once.id),{status:404});
 await call('/public/listings/property/'+source('property',once.id)+'/map',{status:404});
 await call('/listings/property/'+source('property',once.id)+'/context',{token:buyer,status:404});
 await call('/searches/'+clonedSearch.id,{token:buyer,method:'DELETE',status:204});await call(searchPath,{status:404});
 const budget=await checkPublicBudgets(call,{buyer,seller});
 await checkListingBudgetContexts(call,budget);
 const expected={seller,buyer,propertyId:property.id,searchId:search.id,fields:Object.fromEntries(fields.map(key=>[key,property[key]])),
  search:{atticPreference:search.atticPreference,minEnergyRating:search.minEnergyRating,balcony:search.balcony},publicPath,budget};
 console.log('Public listing API checks passed: visibility persistence, nullable amenities, attic/energy criteria, full anonymous details and cloning, archive 404, and version-two null/false idempotency.');
 return expected;
}

async function checkListingBudgetContexts(call,budget){
 const {buyer,seller,propertyId,searchId,matchId}=budget;
 const propertyPath='/listings/property/'+source('property',propertyId)+'/context',searchPath='/listings/search/'+source('search',searchId)+'/context';
 const buyerContext=await call(propertyPath,{token:buyer}),sellerContext=await call(searchPath,{token:seller});
 assert.equal(buyerContext.compatibilityScore,100);assert.equal(buyerContext.isExact,true);assert.equal(buyerContext.active.maxPrice,90_000_000);
 assert.equal(sellerContext.compatible,true);assert.equal(sellerContext.isExact,false);assert.ok(sellerContext.compatibilityScore<100);assert.equal(sellerContext.requiresApproximateConsent,true);
 assert.equal(sellerContext.item.searchRequest.maxPrice,70_000_000);assert.equal(Object.hasOwn(sellerContext.item.searchRequest,'publicMaxPrice'),false);
 const foreign=JSON.stringify(sellerContext);assert.ok(!foreign.includes('90000000'));assert.ok(!foreign.includes('80000000'));
 for(const context of [buyerContext,sellerContext]){
  const visit=value=>{if(!value||typeof value!=='object')return;for(const [key,child]of Object.entries(value)){assert.ok(!['latitude','longitude','provider','phone','email','geocodingPlaceId','geocodingAddressKey','streetId'].includes(key),'Detail context leaked '+key);visit(child);}};
  visit(context);
 }
 const matched=(await call('/matches',{token:seller})).find(row=>row.id===matchId);assert.ok(matched);
 await call('/me/active',{token:seller,method:'PUT',body:{kind:'property',id:matched.property.id}});
 const prior=await call(searchPath,{token:seller});assert.equal(prior.myDecision,'liked');assert.equal(prior.matchId,matchId);assert.equal(prior.canDecide,false);assert.equal(prior.item.likedYou,true);
 await call('/me/active',{token:seller,method:'PUT',body:{kind:'property',id:propertyId}});
 const ownSearch=(await call('/me/entities',{token:buyer})).searchRequests.find(row=>row.id===searchId);assert.ok(ownSearch);
 const exact=await call('/searches',{token:buyer,method:'POST',body:{title:'Teljes egyezés védi a részleges döntést',city:ownSearch.city,locationIds:ownSearch.locationIds,type:ownSearch.type,maxPrice:100_000_000,publicMaxPrice:85_000_000,balcony:false,elevator:false},status:201});
 const blocked=await call(searchPath,{token:seller});assert.equal(blocked.hasUnseenExact,true);assert.equal(blocked.canDecide,false);assert.equal(blocked.unavailableReason,'exact_matches_remaining');
 await call('/decisions',{token:seller,method:'POST',body:{propertyId,searchRequestId:searchId,liked:false,allowApproximate:true},status:400});
 await call('/searches/'+exact.id,{token:buyer,method:'DELETE',status:204});
 const selfSearch=await call('/searches',{token:seller,method:'POST',body:{title:'Saját profil nem lehet partner',city:ownSearch.city,locationIds:ownSearch.locationIds,type:ownSearch.type,balcony:false,elevator:false},status:201});
 await call('/me/active',{token:seller,method:'PUT',body:{kind:'search',id:selfSearch.id}});
 const self=await call(propertyPath,{token:seller});assert.equal(self.available,false);assert.equal(self.unavailableReason,'own_listing');assert.equal(self.item,null);
 await call('/searches/'+selfSearch.id,{token:seller,method:'DELETE',status:204});
 await call('/me/active',{token:seller,method:'PUT',body:{kind:'property',id:propertyId}});
 const streets=(await call('/locations?q='+encodeURIComponent('Budapest Nádor')+'&kind=search&limit=25')).items.filter(row=>row.kind==='street');assert.ok(streets.length);
 const streetSearch=await call('/searches',{token:buyer,method:'POST',body:{title:'Utca térképi adatvédelme',city:streets[0].city,locationIds:[streets[0].id],type:'Lakás',balcony:false,elevator:false},status:201});
 const mapPath='/public/listings/search/'+source('search',streetSearch.id)+'/map';
 const onlyStreet=await call(mapPath);assert.equal(onlyStreet.available,false);assert.deepEqual(onlyStreet.locationIds,[]);assert.equal(onlyStreet.externalUrl,null);assert.ok(!JSON.stringify(onlyStreet).includes(streets[0].id));
 await call('/searches/'+streetSearch.id,{token:buyer,method:'PUT',body:{title:streetSearch.title,city:streetSearch.city,locationIds:[streets[0].id,'city:Debrecen'],type:'Lakás',balcony:false,elevator:false}});
 assert.deepEqual((await call(mapPath)).locationIds,['city:Debrecen']);
 await call('/searches/'+streetSearch.id,{token:buyer,method:'DELETE',status:204});
 console.log('Shared listing context checks passed: current owned activation, exact/partial scorer parity, asymmetric private budgets, prior pass/like/match states, and coordinate-free map descriptors.');
}

export async function verifyPublicListingRefinements(fixture,call){
 if(!fixture)return;
 const seller=await call('/me/entities',{token:fixture.seller}),buyer=await call('/me/entities',{token:fixture.buyer});
 const property=seller.properties.find(row=>row.id===fixture.propertyId),search=buyer.searchRequests.find(row=>row.id===fixture.searchId);assert.ok(property&&search);
 for(const [key,value]of Object.entries(fixture.fields))assert.deepEqual(property[key],value,key+' must survive the actual restart');
 for(const [key,value]of Object.entries(fixture.search))assert.deepEqual(search[key],value,key+' search criterion must survive the actual restart');
 const detail=await call(fixture.publicPath);assert.equal(detail.listing.address,'');assert.equal(detail.listing.balcony,true);assert.equal(detail.listing.isAttic,false);assert.equal(detail.listing.energyRatingScheme,'2023');
 await verifyPublicBudgets(fixture.budget,call);
 console.log('Public listing restart preservation passed: address switches, nullable amenities, attic and energy criteria, and stable anonymous URLs.');
}
