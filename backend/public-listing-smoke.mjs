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
 await checkListingProfileOptions(call,budget);
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
 assert.equal(sellerContext.compatible,true);assert.equal(sellerContext.isExact,false);assert.ok(sellerContext.compatibilityScore<100);assert.equal(sellerContext.requiresApproximateConsent,false);assert.equal(sellerContext.canDecide,true);
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
 const exact=await call('/searches',{token:buyer,method:'POST',body:{title:'Felfedezésben előbb teljes egyezés',city:ownSearch.city,locationIds:ownSearch.locationIds,type:ownSearch.type,maxPrice:100_000_000,publicMaxPrice:85_000_000,balcony:false,elevator:false},status:201});
 const direct=await call(searchPath,{token:seller});assert.equal(direct.hasUnseenExact,false);assert.equal(direct.canDecide,true);assert.equal(direct.requiresApproximateConsent,false);assert.equal(direct.unavailableReason,null);
 // Discovery keeps the exact-first gate, whereas a detail action names and
 // validates the actual opposite listing and may decide an eligible partial.
 await call('/decisions',{token:seller,method:'POST',body:{propertyId,searchRequestId:searchId,liked:false,allowApproximate:true},status:400});
 const partial=await call('/searches',{token:buyer,method:'POST',body:{title:'Közvetlen részleges adatlapdöntés',city:ownSearch.city,locationIds:ownSearch.locationIds,type:ownSearch.type,maxPrice:90_000_000,publicMaxPrice:70_000_000,balcony:false,elevator:false},status:201});
 const partialKey=source('search',partial.id),partialPath='/listings/search/'+partialKey+'/context';
 const partialContext=await call(partialPath,{token:seller});assert.equal(partialContext.isExact,false);assert.equal(partialContext.canDecide,true);
 const wrongType=await call('/searches',{token:buyer,method:'POST',body:{title:'Eltérő típus nem engedélyezhető',city:ownSearch.city,locationIds:ownSearch.locationIds,type:'Ház',maxPrice:90_000_000,balcony:false,elevator:false},status:201});
 const wrongTypeContext=await call('/listings/search/'+source('search',wrongType.id)+'/context',{token:seller});assert.equal(wrongTypeContext.canDecide,false);assert.equal(wrongTypeContext.compatible,false);
 await call('/decisions',{token:seller,method:'POST',body:{propertyId,searchRequestId:wrongType.id,liked:true,listingKey:source('search',wrongType.id)},status:400});
 await call('/searches/'+wrongType.id,{token:buyer,method:'DELETE',status:204});
 const beforeDirect=(await call('/me',{token:seller})).credits,beforeDirectLedger=await call('/credits/ledger',{token:seller});
 const partialDecision={propertyId,searchRequestId:partial.id,liked:true};
 await call('/decisions',{token:seller,method:'POST',body:{...partialDecision,allowApproximate:true},status:400});
 for(const listingKey of ['',source('property',propertyId),source('search',exact.id),'search-'+'0'.repeat(64)])
  await call('/decisions',{token:seller,method:'POST',body:{...partialDecision,listingKey},status:400});
 await call('/decisions',{token:seller,method:'POST',body:{...partialDecision,propertyId:matched.property.id,listingKey:partialKey},status:403});
 assert.equal((await call('/me',{token:seller})).credits,beforeDirect);assert.deepEqual(await call('/credits/ledger',{token:seller}),beforeDirectLedger,'Invalid detail keys and active pairs never debit credits');
 const accepted=await call('/decisions',{token:seller,method:'POST',body:{...partialDecision,listingKey:partialKey}});assert.equal(accepted.charged,2);assert.equal(accepted.matchId,null);
 const retry=await call('/decisions',{token:seller,method:'POST',body:{...partialDecision,listingKey:partialKey}});assert.equal(retry.charged,0);assert.equal((await call('/me',{token:seller})).credits,beforeDirect-2);
 await call('/decisions',{token:seller,method:'POST',body:{...partialDecision,liked:false,listingKey:partialKey},status:409});
 const decided=await call(partialPath,{token:seller});assert.equal(decided.myDecision,'liked');assert.equal(decided.canDecide,false);
 const buyerPartial=await call('/searches',{token:buyer,method:'POST',body:{title:'Közvetlen részleges elutasítás',city:ownSearch.city,locationIds:ownSearch.locationIds,type:ownSearch.type,maxPrice:60_000_000,balcony:false,elevator:false},status:201});
 await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:buyerPartial.id}});
 const buyerPartialContext=await call(propertyPath,{token:buyer});assert.equal(buyerPartialContext.isExact,false);assert.equal(buyerPartialContext.canDecide,true);
 await call('/decisions',{token:buyer,method:'POST',body:{propertyId,searchRequestId:buyerPartial.id,liked:false},status:400});
 const rejected=await call('/decisions',{token:buyer,method:'POST',body:{propertyId,searchRequestId:buyerPartial.id,liked:false,listingKey:source('property',propertyId)}});assert.equal(rejected.charged,0);
 const passed=await call(propertyPath,{token:buyer});assert.equal(passed.myDecision,'passed');assert.equal(passed.canDecide,false);
 await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:searchId}});
 for(const row of [partial,buyerPartial])await call('/searches/'+row.id,{token:buyer,method:'DELETE',status:204});
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
 console.log('Shared listing context checks passed: validated direct partial decisions despite remaining exact discoveries, unchanged feed consent, active-pair enforcement, idempotent charges, asymmetric private budgets, prior pass/like/match states, and coordinate-free map descriptors.');
}

async function checkListingProfileOptions(call,budget){
 const {buyer,seller,propertyId,searchId}=budget,propertyKey=source('property',propertyId),searchKey=source('search',searchId);
 const buyerPath='/listings/property/'+propertyKey+'/profiles',sellerPath='/listings/search/'+searchKey+'/profiles';
 await call(buyerPath,{status:401});
 for(const suffix of ['?offset=-1','?offset=1000001','?limit=0','?limit=51'])await call(buyerPath+suffix,{token:buyer,status:400});
 await call('/listings/property/property-'+'0'.repeat(64)+'/profiles',{token:buyer,status:404});
 const own=await call(buyerPath,{token:seller});assert.equal(own.unavailableReason,'own_listing');assert.equal(own.total,0);assert.deepEqual(own.items,[]);
 const current=await call('/me/entities',{token:buyer}),wanted=current.searchRequests.find(row=>row.id===searchId);assert.ok(wanted);
 const created=[];
 const snapshot=async token=>{
  const entities=await call('/me/entities',{token}),ledger=await call('/credits/ledger',{token});
  return {active:entities.active,decisions:entities.decisions,ledger};
 };
 const privateFree=value=>{
  const visit=item=>{if(!item||typeof item!=='object')return;for(const [key,child]of Object.entries(item)){assert.ok(!['ownerId','userId','street','houseNumber','address','addressDetails','latitude','longitude','email','phone','provider','geocodingPlaceId','geocodingAddressKey','creationRequestId','creationRequestHash'].includes(key),'Profile picker leaked '+key);visit(child);}};
  visit(value);
 };
 try{
  // A page genuinely spans more than fifty live owned rows. Search creation
  // needs no geocoder and reuses this suite's accounts rather than auth bursts.
  for(let index=0;index<51;index++)created.push(await call('/searches',{token:buyer,method:'POST',status:201,body:{
   title:'Profilválasztó próba '+String(index).padStart(2,'0'),city:index===0?'Debrecen':wanted.city,
   locationIds:index===0?['city:Debrecen']:wanted.locationIds,type:index===1?'Ház':wanted.type,
   maxPrice:90_000_000,publicMaxPrice:70_000_000,balcony:false,elevator:false}}));
  const archived=created.at(-1);await call('/searches/'+archived.id,{token:buyer,method:'DELETE',status:204});archived.archived=true;
  const before=await snapshot(buyer),owned=(await call('/me/entities',{token:buyer})).searchRequests.filter(row=>!row.archived);
  const first=await call(buyerPath,{token:buyer});assert.equal(first.kind,'search');assert.equal(first.offset,0);assert.equal(first.limit,50);
  assert.equal(first.items.length,50);assert.equal(first.total,owned.length);assert.equal(first.hasMore,true);
  assert.equal(first.items[0].profile.id,searchId);assert.equal(first.items[0].isActive,true);assert.equal(first.items[0].score,100);
  assert.equal(first.items[0].profile.maxPrice,90_000_000,'A buyer may see its own actual maximum');
  const all=[...first.items];let offset=first.items.length;
  while(offset<first.total){const page=await call(buyerPath+'?offset='+offset+'&limit=50',{token:buyer});assert.equal(page.total,first.total);assert.equal(page.offset,offset);all.push(...page.items);offset+=page.items.length;assert.ok(page.items.length>0);assert.equal(page.hasMore,offset<first.total);}
  assert.equal(new Set(all.map(item=>item.profile.id)).size,first.total,'Stable pages never repeat or omit an owned choice');
  assert.deepEqual(all.map(item=>item.profile.id).sort(),owned.map(item=>item.id).sort());
  assert.ok(all.every(item=>item.profile.kind==='search'&&item.profile.id!==archived.id));
  const wrongType=all.find(item=>item.profile.id===created[1].id);assert.ok(wrongType);assert.equal(wrongType.compatible,false);assert.equal(wrongType.score,0);
  const outside=all.find(item=>item.profile.id===created[0].id);assert.ok(outside);assert.equal(outside.compatible,true);assert.ok(outside.score<100,'Batched geography evaluates an outside-town owned search without inventing a perfect match');
  privateFree(first);assert.deepEqual(await snapshot(buyer),before,'Listing choices never activate, debit, decide or mutate the ledger');
  const empty=await call(buyerPath+'?offset='+first.total,{token:buyer});assert.deepEqual(empty.items,[]);assert.equal(empty.hasMore,false);
  const prior=await call('/listings/property/'+propertyKey+'/context',{token:buyer});assert.equal(prior.active.id,searchId);assert.equal(prior.compatibilityScore,first.items[0].score);
  // Seller scores must use the counterpart's public cap. The displayed own
  // property summary never carries that counterpart's private maximum.
  const sellerBefore=await snapshot(seller),properties=await call(sellerPath,{token:seller});assert.equal(properties.kind,'property');
  const high=properties.items.find(item=>item.profile.id===propertyId);assert.ok(high);assert.equal(high.isActive,true);assert.equal(high.compatible,true);assert.equal(high.isExact,false);assert.ok(high.score<100);
  privateFree(properties);assert.ok(!JSON.stringify(properties).includes('90000000'));assert.ok(!JSON.stringify(properties).includes('80000000'));
  assert.deepEqual(await snapshot(seller),sellerBefore);
  const sellerContext=await call('/listings/search/'+searchKey+'/context',{token:seller});assert.equal(high.score,sellerContext.compatibilityScore);
  await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:created[1].id}});
  const alternate=await call('/listings/property/'+propertyKey+'/context',{token:buyer});assert.equal(alternate.active.id,created[1].id);assert.equal(alternate.compatible,false);
  const selected=await call(buyerPath,{token:buyer});assert.equal(selected.items[0].profile.id,created[1].id);assert.equal(selected.items[0].isActive,true);assert.equal(selected.items[0].score,0);
  const archiveKey=source('search',archived.id);await call('/listings/search/'+archiveKey+'/profiles',{token:seller,status:404});
 }finally{
  await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:searchId}});
  for(const row of created)if(!row.archived)await call('/searches/'+row.id,{token:buyer,method:'DELETE',status:204});
 }
 console.log('Listing profile picker API checks passed: owned opposite kinds, paginated 50+ choices, exact/partial/public-budget scores, read-only state, activation refresh and coordinate/contact privacy.');
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
