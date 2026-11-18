import test, {afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {neighborhoods} from '../dist/neighborhoods-data.js';
import {neighborhoodDemoPoints} from '../dist/neighborhood-demo-points.js';
import {locations, getLocation} from '../dist/locations.js';
import {evaluateMatch, prepareSearch, searchSpecificity} from '../dist/matching.js';
import {createModel, STORAGE_KEY, demoLanding} from '../dist/model.js';
import {ApiModel} from '../dist/api.js';

const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch;});
const storage=()=>{const values=new Map();return {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};};
const quarter=neighborhoods.find(value=>value.city==='Debrecen');
const wrongQuarter=neighborhoods.find(value=>value.city===quarter.city&&value.id!==quarter.id);
const home={id:'property',ownerId:'seller',locationId:'city:Debrecen',type:'Lakás',price:60,area:60,rooms:3,neighborhoodIds:[quarter.id]};
const search={id:'search',ownerId:'buyer',locationIds:[quarter.id],type:'Lakás'};
const address={street:'Fiktív teszt utca',houseNumber:'42/A',postalCode:'4026'};
const details={...address,latitude:47.5,longitude:21.6,geocodedAt:'2026-11-16T12:00:00Z',provider:'Google',quality:'ROOFTOP',geocodingStatus:'succeeded'};
const api=()=>new ApiModel({baseUrl:'https://api.example.test',token:'test-token'});
const response=value=>({ok:true,status:200,text:async()=>JSON.stringify(value)});

test('verified neighborhood membership is a hard gate before exact and partial scoring',()=>{
  assert.equal(evaluateMatch(home,search).score,100);
  assert.equal(evaluateMatch({...home,price:100},{...search,maxPrice:60}).eligible,true);
  for(const property of [{...home,neighborhoodIds:[]},{...home,neighborhoodIds:[wrongQuarter.id]},{...home,neighborhoodIds:undefined,neighborhood:quarter.name}]){
    assert.deepEqual(evaluateMatch(property,{...search,maxPrice:1}),{eligible:false,isExact:false,score:0,reasons:[],matchDetails:[]});
  }
  assert.equal(evaluateMatch({...home,locationId:'city:Szeged'},search).score,100,'polygon membership may cross the source municipality boundary');
  assert.equal(evaluateMatch(home,{...search,locationIds:[wrongQuarter.id,'city:Debrecen']}).score,100);
  assert.equal(evaluateMatch({...home,locationId:'city:Solymár',neighborhoodIds:[]},{...search,locationIds:[quarter.id,'area:Budapest']}).score,100);
  assert.equal(evaluateMatch(home,{...search,locationIds:[quarter.id,'neighborhood:unknown']}).eligible,false);
  assert.equal(evaluateMatch({...home,locationId:quarter.id},search).eligible,false);
  assert.ok(searchSpecificity(search)>searchSpecificity({...search,locationIds:['city:Debrecen']}));
  assert.ok(prepareSearch(search).neighborhoodIds.has(quarter.id));
});

test('neighborhood choices preserve canonical IDs, validate the fifty-choice cap, and cannot become property locations',()=>{
  const model=createModel(storage());
  const selected=[quarter.id,'city:Solymár','area:Budapest'];
  const saved=model.saveEntity('search',{title:'Több lehetséges környék',locationIds:selected});
  assert.deepEqual(saved.locationIds,selected);
  assert.equal(saved.locations[0].label,`${quarter.name} (${quarter.city})`);
  assert.throws(()=>model.saveEntity('search',{title:'Ismeretlen környék',locationIds:[quarter.id,'neighborhood:unknown']}),/találati listából/);
  assert.throws(()=>model.saveEntity('search',{title:'Túl sok környék',locationIds:neighborhoods.slice(0,51).map(value=>value.id)}),/találati listából/);
  assert.throws(()=>model.saveEntity('property',{title:'Nem pontos helyszín',locationId:quarter.id,price:60,area:60,rooms:3,...address}),/találati listából/);
  assert.equal(locations.filter(value=>value.kind==='neighborhood').length,4308);
  assert.equal(getLocation(quarter.id).id,quarter.id);
});

test('demo saves require an exact address and never trust supplied coordinates or neighborhood membership',()=>{
  const model=createModel(storage());
  const input={title:'Új fiktív otthon',locationId:'city:Debrecen',price:60,area:60,rooms:3};
  assert.throws(()=>model.saveEntity('property',input),/utcáját és házszámát/);
  const saved=model.saveEntity('property',{...input,...address,neighborhood:quarter.name,neighborhoodIds:[quarter.id],latitude:1,longitude:2,addressDetails:details});
  assert.deepEqual(saved.neighborhoodIds,[]);
  assert.equal(saved.neighborhood,'');
  assert.equal(saved.addressDetails.street,address.street);
  assert.equal(saved.addressDetails.latitude,null);
  assert.equal(saved.addressDetails.longitude,null);
  assert.equal(saved.addressDetails.geocodingStatus,'demo-unverified');
  assert.equal('latitude' in saved,false);
  for(const invalid of [{street:'x'.repeat(181)},{street:'Teszt\nutca'},{houseNumber:'nincs'},{houseNumber:'1'.repeat(33)},{postalCode:'12345'}]){
    assert.throws(()=>model.saveEntity('property',{...input,...address,...invalid}),/érvényes utcát/);
  }
});

test('every fictional demo seed uses its explicit synthetic point and all known overlapping memberships',()=>{
  const store=storage(),model=createModel(store);
  model.buyDemoCredits(1);
  const raw=JSON.parse(store.getItem(STORAGE_KEY));
  const addresses=new Set();
  for(const property of raw.properties){
    const detail=property.addressDetails;
    assert.ok(detail.streetId?getLocation(detail.streetId)?.streetName===detail.street:detail.street.includes('Fiktív'));
    assert.match(detail.houseNumber,/^99999\//);
    assert.match(detail.postalCode,/^\d{4}$/);
    assert.equal(detail.provider,'synthetic-demo');
    assert.equal(detail.geocodingStatus,'demo-synthetic');
    const point=neighborhoodDemoPoints.find(value=>value.latitude===detail.latitude&&value.longitude===detail.longitude);
    assert.ok(point?.synthetic);
    assert.deepEqual(property.neighborhoodIds,point.membershipIds);
    assert.ok(property.neighborhoodIds.every(id=>getLocation(id)?.kind==='neighborhood'));
    addresses.add([property.city,detail.street,detail.houseNumber].join('|'));
  }
  assert.equal(addresses.size,raw.properties.length);
  const own=model.getState().properties[0];
  const unchanged=model.saveEntity('property',{title:'Új név azonos címen'},own.id);
  assert.deepEqual(unchanged.addressDetails,own.addressDetails);
  assert.deepEqual(unchanged.neighborhoodIds,own.neighborhoodIds);
  assert.equal(unchanged.neighborhood,own.neighborhood);
  const changed=model.saveEntity('property',{street:'Másik fiktív utca'},own.id);
  assert.deepEqual(changed.neighborhoodIds,[]);
  assert.equal(changed.neighborhood,'');
  assert.equal(changed.addressDetails.latitude,null);
});

test('demo neighborhood discovery works in both roles and keeps exact addresses private in cards, incoming likes and history',()=>{
  const store=storage(),seed=createModel(store);
  seed.buyDemoCredits(1);
  const raw=JSON.parse(store.getItem(STORAGE_KEY));
  const ownSearch=raw.searches.find(value=>value.id==='own-s1');
  ownSearch.locationIds=[quarter.id];ownSearch.type='Lakás';ownSearch.minPrice=null;ownSearch.maxPrice=null;ownSearch.minArea=null;ownSearch.maxArea=null;ownSearch.minRooms=null;ownSearch.maxRooms=null;
  for(const property of raw.properties){property.neighborhoodIds=[];property.addressDetails={...details};}
  Object.assign(raw.properties.find(value=>value.id==='p1'),home,{id:'p1',ownerId:'u1'});
  raw.properties.find(value=>value.id==='p2').neighborhoodIds=[wrongQuarter.id];
  store.setItem(STORAGE_KEY,JSON.stringify(raw));
  const model=createModel(store);
  assert.deepEqual(model.feed().map(value=>value.id),['p1']);
  const publicCards=[...model.feed(),...model.incomingLikes().items,...model.getState().decisions.map(value=>value.property),...model.matches().map(value=>value.property)].filter(Boolean);
  for(const card of publicCards){
    assert.equal('addressDetails' in card,false);
    assert.equal('street' in card,false);
    assert.equal('latitude' in card,false);
    assert.equal(card.address,'');
  }
  const owner=raw.properties.find(value=>value.id==='own-p1');
  Object.assign(owner,home,{id:'own-p1',ownerId:'me',addressDetails:{...details}});
  const otherSearch=raw.searches.find(value=>value.id==='s1');
  Object.assign(otherSearch,search,{id:'s1',ownerId:'u1'});
  raw.active={kind:'property',id:'own-p1'};
  store.setItem(STORAGE_KEY,JSON.stringify(raw));
  const seller=createModel(store);
  assert.ok(seller.feed().some(value=>value.id==='s1'));
  assert.equal(seller.getState().properties.find(value=>value.id==='own-p1').addressDetails.street,address.street);
  assert.doesNotMatch(JSON.stringify(demoLanding()),/addressDetails|latitude|longitude|houseNumber|postalCode/);
});

test('API sends address inputs only and accepts server-owned membership and private address details',async()=>{
  let body;
  globalThis.fetch=async(url,options)=>{body=JSON.parse(options.body);return response({...home,...body,addressDetails:details,neighborhoodIds:[quarter.id]});};
  const model=api();
  await assert.rejects(model.saveEntity('property',{...home,title:'Cím nélkül'}),/utcáját és házszámát/);
  for(const invalid of [{street:'x'.repeat(181)},{street:'Teszt\nutca'},{houseNumber:'nincs'},{houseNumber:'1'.repeat(33)},{postalCode:'12345'}]){
    await assert.rejects(model.saveEntity('property',{...home,title:'Hibás cím',...address,...invalid}),/érvényes utcát/);
  }
  const saved=await model.saveEntity('property',{...home,title:'Pontos cím',...address,address:'Korábban mentett magáncím',latitude:1,longitude:2,addressDetails:{...details,provider:'forged'},neighborhoodIds:[wrongQuarter.id]});
  assert.deepEqual([body.street,body.houseNumber,body.postalCode],[address.street,address.houseNumber,address.postalCode]);
  assert.equal(body.address,'Korábban mentett magáncím');
  for(const key of ['latitude','longitude','addressDetails','provider','neighborhoodIds'])assert.equal(key in body,false,key);
  assert.deepEqual(saved.addressDetails,details);
  assert.deepEqual(saved.neighborhoodIds,[quarter.id]);
  assert.equal('latitude' in saved,false);
});

test('malformed server location selections cannot revive a legacy city or become valid neighborhood choices',async()=>{
  for(const locationIds of [quarter.id,{id:quarter.id},neighborhoods.slice(0,51).map(value=>value.id)]){
    globalThis.fetch=async(url)=>response(new URL(url).pathname==='/api/me'?{id:'buyer'}:new URL(url).pathname==='/api/credits/ledger'?[]:{properties:[],searchRequests:[{...search,city:'Debrecen',locationIds}]});
    const saved=(await api().getState()).searches[0];
    assert.deepEqual(saved.locationIds,locationIds);
    assert.equal(evaluateMatch(home,saved).eligible,false);
  }
});

test('API cards and saved history strip foreign private fields while own properties retain address details',async()=>{
  const privateProperty={...home,title:'Otthon',address:'PRIVATE-ADDRESS',...address,addressDetails:details,latitude:details.latitude,longitude:details.longitude};
  const candidate={property:privateProperty,searchRequest:search,propertyId:home.id,searchRequestId:search.id,compatible:true};
  globalThis.fetch=async(url)=>{
    switch(new URL(url).pathname){
      case '/api/me':return response({id:'buyer',name:'Nagy Anna',credits:10});
      case '/api/me/entities':return response({properties:[{...privateProperty,id:'own',ownerId:'buyer'}],searchRequests:[search],decisions:[candidate],active:{kind:'search',id:'search'}});
      case '/api/credits/ledger':return response([]);
      case '/api/feed':return response({items:[candidate]});
      case '/api/incoming-likes':return response({active:{kind:'search',id:'search'},items:[candidate]});
      case '/api/matches':return response([{id:'match',property:privateProperty,searchRequest:search,partner:{id:'seller',email:'allowed@example.test'}}]);
      default:throw new Error('Unexpected request');
    }
  };
  const model=api(),state=await model.getState();
  assert.deepEqual(state.properties[0].addressDetails,details);
  const cards=[...(await model.feed()),...(await model.incomingLikes()).items,...state.decisions.map(value=>value.property),...(await model.matches()).map(value=>value.property)];
  for(const card of cards){
    assert.equal('addressDetails' in card,false);assert.equal('street' in card,false);assert.equal('houseNumber' in card,false);
    assert.equal('latitude' in card,false);assert.equal('longitude' in card,false);assert.equal(card.address,'');
    assert.deepEqual(card.neighborhoodIds,[quarter.id]);
  }
});
