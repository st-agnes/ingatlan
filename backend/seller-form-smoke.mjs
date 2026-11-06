/** Seller form contracts against the actual disposable MySQL API, including restart persistence. */
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile, chmod} from 'node:fs/promises';
import {resolve, dirname} from 'node:path';
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
if(origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback API.');
const fixturePath=resolve('.local/seller-form-upgrade-fixture.json');
async function call(path,{token,method='GET',body,status=200}={}){
  const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  assert.equal(response.status,status,`${method} ${path}: HTTP ${response.status}`);
  if(response.status===204||status>=400){await response.text();return null;}
  return response.json();
}
async function verify(fixture){
  const seller=await call('/me/entities',{token:fixture.seller});
  const property=seller.properties.find(x=>x.id===fixture.propertyId),house=seller.properties.find(x=>x.id===fixture.houseId);
  assert.ok(property);assert.ok(house);
  assert.equal(property.rooms,3.5);assert.equal(property.wholeRooms,2);assert.equal(property.halfRooms,3);
  assert.equal(property.heatingType,'Hőszivattyú');assert.equal(property.secondaryHeatingType,'Kandalló');
  assert.deepEqual(property.parkingTypes,['Garázs','Udvari beálló']);
  assert.equal(house.lotArea,480);assert.equal(house.floor,null);assert.equal(house.balcony,false);assert.equal(house.elevator,false);
  const buyer=await call('/me/entities',{token:fixture.buyer});
  const search=buyer.searchRequests.find(x=>x.id===fixture.searchId);
  assert.ok(search);assert.deepEqual(search.heatingTypes,['Nincs fűtés','Hőszivattyú']);
  assert.deepEqual(search.floors,[]);assert.equal(search.balcony,false);assert.equal(search.elevator,false);
  await call('/me/active',{token:fixture.buyer,method:'PUT',body:{kind:'search',id:search.id}});
  const feed=await call('/feed',{token:fixture.buyer});
  assert.ok(feed.items.some(x=>x.propertyId===fixture.houseId),'A house with cleared irrelevant constraints must match');
}
if(process.argv[3]==='--verify'){
  await verify(JSON.parse(await readFile(fixturePath,'utf8')));
  console.log('Seller-form restart preservation passed: explicit room composition, heating, parking, required house plot and clean house criteria survive.');
}else{
  const suffix=Date.now()+'-'+Math.random().toString(16).slice(2);
  const account=async name=>(await call('/auth/register',{method:'POST',body:{name:'Seller form '+name,email:`seller-form-${name}-${suffix}@example.test`,password:'SellerFormSmoke2026!'}})).accessToken;
  const buyer=await account('buyer'),seller=await account('seller');
  const base={title:'Eladói mezők API-próba',city:'Budapest',district:'XIII.',locationId:'district:Budapest:13',type:'Lakás',price:75000000,area:72,rooms:3.5,wholeRooms:2,halfRooms:3,images:[],balcony:false,elevator:false};
  const complete={...base,heatingType:'Hőszivattyú',secondaryHeatingType:'Kandalló',parkingTypes:['Garázs','Udvari beálló','Garázs']};
  let property=await call('/properties',{token:seller,method:'POST',body:complete,status:201});
  assert.deepEqual(property.parkingTypes,['Garázs','Udvari beálló']);
  assert.equal(property.wholeRooms,2);assert.equal(property.halfRooms,3);assert.equal(property.rooms,3.5);
  const noCounts={...complete};delete noCounts.wholeRooms;delete noCounts.halfRooms;
  property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...noCounts,title:'Szobabontást megőrző régi kliens'}});
  assert.equal(property.wholeRooms,2);assert.equal(property.halfRooms,3,'A legacy client with unchanged total must not collapse the composition');
  const olderParkingClient={...noCounts,parkingType:property.parkingType};delete olderParkingClient.parkingTypes;
  property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:olderParkingClient});
  assert.deepEqual(property.parkingTypes,['Garázs','Udvari beálló'],'Legacy compatibility strings must not overwrite the authoritative list');
  const cleared=await call('/properties/'+property.id,{token:seller,method:'PUT',body:{...complete,heatingType:'',secondaryHeatingType:'',parkingTypes:[]}});
  assert.equal(cleared.heatingType,'');assert.equal(cleared.secondaryHeatingType,'');assert.deepEqual(cleared.parkingTypes,[]);assert.equal(cleared.parkingType,'');
  property=await call('/properties/'+property.id,{token:seller,method:'PUT',body:complete});
  const legacyBody={...base,rooms:2.5,parkingType:'Mélygarázs'};delete legacyBody.wholeRooms;delete legacyBody.halfRooms;
  const legacy=await call('/properties',{token:seller,method:'POST',body:legacyBody,status:201});
  assert.equal(legacy.wholeRooms,2);assert.equal(legacy.halfRooms,1);assert.deepEqual(legacy.parkingTypes,['Mélygarázs']);
  const precise=await call('/properties',{token:seller,method:'POST',body:{...legacyBody,rooms:2.25},status:201});
  assert.equal(precise.rooms,2.25);assert.equal(precise.wholeRooms,null);assert.equal(precise.halfRooms,null,'Old arbitrary decimals must never be silently rounded');
  for(const change of [{price:-1},{area:-1},{wholeRooms:-1},{halfRooms:-1},{wholeRooms:1.5},{halfRooms:1.5},{rooms:-1},{rooms:9},{wholeRooms:0,halfRooms:0,rooms:0},{wholeRooms:1001},{heatingType:'Ismeretlen'},{secondaryHeatingType:'Ismeretlen'},{parkingTypes:['Ismeretlen']},{parkingTypes:[null]},{parkingTypes:['']}]){
    await call('/properties',{token:seller,method:'POST',body:{...complete,...change},status:400});
  }
  const houseBase={...complete,type:'Ház',floor:2,balcony:true,elevator:true};
  for(const lotArea of [undefined,null,0,-1])await call('/properties',{token:seller,method:'POST',body:{...houseBase,lotArea},status:400});
  const house=await call('/properties',{token:seller,method:'POST',body:{...houseBase,lotArea:480},status:201});
  assert.equal(house.floor,null);assert.equal(house.balcony,false);assert.equal(house.elevator,false);
  const apartment=await call('/properties',{token:seller,method:'POST',body:{...complete,lotArea:480,floor:-1},status:201});
  assert.equal(apartment.lotArea,null);assert.equal(apartment.floor,-1,'Basement is a valid categorical floor');
  const searchBase={title:'Közös fűtéslista API-próba',city:'Budapest',locationIds:['district:Budapest:13'],type:'Lakás',minPrice:null,maxPrice:90000000,minArea:40,maxArea:null,minRooms:3.5,maxRooms:3.5,balcony:false,elevator:false,heatingTypes:['Nincs fűtés','Hőszivattyú','Hőszivattyú']};
  let search=await call('/searches',{token:buyer,method:'POST',body:searchBase,status:201});
  assert.deepEqual(search.heatingTypes,['Nincs fűtés','Hőszivattyú']);
  const secondaryOnly=await call('/properties',{token:seller,method:'POST',body:{...complete,heatingType:'Gázkazán',secondaryHeatingType:'Hőszivattyú'},status:201});
  const noHeating=await call('/properties',{token:seller,method:'POST',body:{...complete,heatingType:'Nincs fűtés'},status:201});
  const unknown=await call('/properties',{token:seller,method:'POST',body:{...complete,heatingType:''},status:201});
  await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
  let feed=await call('/feed',{token:buyer});
  for(const included of [property,noHeating])assert.ok(feed.items.some(x=>x.propertyId===included.id));
  for(const excluded of [secondaryOnly,unknown]){
    assert.ok(!feed.items.some(x=>x.propertyId===excluded.id),'The primary heating selection must be enforced; unknown is not explicitly no heating');
    await call('/decisions',{token:buyer,method:'POST',body:{propertyId:excluded.id,searchRequestId:search.id,liked:true},status:400});
  }
  await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...searchBase,heatingTypes:[]}});
  feed=await call('/feed',{token:buyer});
  assert.ok(feed.items.some(x=>x.propertyId===unknown.id),'Empty heating filter must include unknown heating');
  for(const heatingTypes of [['Ismeretlen'],[null],['']])await call('/searches',{token:buyer,method:'POST',body:{...searchBase,heatingTypes},status:400});
  search=await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...searchBase,type:'Ház',floors:[3],balcony:true,elevator:true}});
  assert.deepEqual(search.floors,[]);assert.equal(search.balcony,false);assert.equal(search.elevator,false);
  const fixture={seller,buyer,propertyId:property.id,houseId:house.id,searchId:search.id};
  await verify(fixture);
  await mkdir(dirname(fixturePath),{recursive:true});await writeFile(fixturePath,JSON.stringify(fixture),{mode:0o600});await chmod(fixturePath,0o600);
  console.log('Seller-form API integration passed: room composition and legacy compatibility, shared heating/primary-only matching, multi parking, invalid values, required house plot and hidden criteria clearing.');
}
