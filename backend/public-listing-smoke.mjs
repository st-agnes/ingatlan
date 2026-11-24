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
 for(const path of ['/public/listings/property/'+property.id,'/public/listings/search/'+propertyKey,'/public/listings/property/property-'+'0'.repeat(64)])await call(path,{status:404});
 const criteria={title:'Pontos tetőtér- és energiaigény',city:baseProperty.city,locationIds:[baseProperty.locationId],type:'Lakás',
  minPrice:base.price,maxPrice:base.price,minArea:base.area,maxArea:base.area,minRooms:base.rooms,maxRooms:base.rooms,
  balcony:false,elevator:false,atticPreference:'only',minEnergyRating:'B',description:'Tágas, világos otthont keresek.'};
 let search=await call('/searches',{token:buyer,method:'POST',body:criteria,status:201});
 await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
 const has=async()=> (await call('/feed',{token:buyer})).items.some(item=>item.propertyId===property.id);
 assert.equal(await has(),false,'Unknown attic and unmarked legacy energy cannot satisfy explicit criteria');
 const modern={...base,isAttic:true,energyRating:'A+',energyRatingScheme:'2023',balcony:false,airConditioning:false,privateGarden:false,insulated:false,solarPanels:false,hideStreet:false,hideHouseNumber:false};
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:modern});
 assert.equal(await has(),true);
 const stored=(await call('/me/entities',{token:seller})).properties.find(row=>row.id===property.id);
 for(const key of ['hideStreet','hideHouseNumber','balcony','airConditioning','privateGarden','insulated','solarPanels'])assert.equal(stored[key],false,key+' false must survive actual EF/MySQL persistence');
 assert.equal(stored.isAttic,true);assert.equal(stored.energyRatingScheme,'2023');
 detail=await call(publicPath);assert.equal(detail.listing.street,'OTTHONRA TEST');assert.equal(detail.listing.houseNumber,'82');assert.equal(detail.listing.address,'OTTHONRA TEST 82');noPrivate(detail,[property.id]);
 property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...modern,hideHouseNumber:true}});
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
  floors:[0.5,9],heatingTypes:['Gázkazán','Hőszivattyú'],balcony:true,elevator:true,excludeTopFloor:true,airConditioning:true,privateGarden:true,
  atticPreference:'exclude',minEnergyRating:'C',moveIn:'3 hónapon belül',financing:'Saját megtakarítás'};
 const clonedSearch=await call('/searches',{token:buyer,method:'POST',body:cloneBody,status:201});
 const searchKey=source('search',clonedSearch.id),searchPath='/public/listings/search/'+searchKey;
 const searchDetail=await call(searchPath);noPrivate(searchDetail,[clonedSearch.id]);
 for(const key of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms','conditions','buildings','constructionAges','views','ceilingHeight','floors','balcony','elevator','excludeTopFloor','airConditioning','privateGarden','atticPreference','minEnergyRating','moveIn','financing','description'])assert.deepEqual(searchDetail.clonePrefill[key],cloneBody[key],key+' must round-trip into the anonymous search clone');
 assert.deepEqual(searchDetail.clonePrefill.heatingTypes,['Gázkazán / cirkó','Hőszivattyú']);
 assert.deepEqual(searchDetail.clonePrefill.locations.map(row=>row.id),cloneBody.locationIds);
 assert.equal(Object.hasOwn(searchDetail.clonePrefill,'title'),false,'A copied profile receives a new automatic title');
 const request=randomUUID(),onceBody={...base,title:'Egyszer menthető nullable erkély',price:base.price+1,creationRequestId:request};
 const once=await call('/properties',{token:seller,method:'POST',body:onceBody,status:201});
 const replay=await call('/properties',{token:seller,method:'POST',body:onceBody});assert.equal(replay.id,once.id);assert.equal(replay.balcony,null);
 await call('/properties',{token:seller,method:'POST',body:{...onceBody,balcony:false},status:409});
 // Use disposable extra rows to prove archived public URLs do not remain accessible.
 await call('/properties/'+once.id,{token:seller,method:'DELETE',status:204});
 await call('/public/listings/property/'+source('property',once.id),{status:404});
 await call('/searches/'+clonedSearch.id,{token:buyer,method:'DELETE',status:204});await call(searchPath,{status:404});
 const budget=await checkPublicBudgets(call,{buyer,seller});
 const expected={seller,buyer,propertyId:property.id,searchId:search.id,fields:Object.fromEntries(fields.map(key=>[key,property[key]])),
  search:{atticPreference:search.atticPreference,minEnergyRating:search.minEnergyRating,balcony:search.balcony},publicPath,budget};
 console.log('Public listing API checks passed: visibility persistence, nullable amenities, attic/energy criteria, full anonymous details and cloning, archive 404, and version-two null/false idempotency.');
 return expected;
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
