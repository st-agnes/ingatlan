import test, {afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {ApiModel} from '../dist/api.js';
import {createModel,STORAGE_KEY} from '../dist/model.js';
import {locations,getLocation,registerLocations,searchLocations,searchStreets,resolveStreetLocation,matchesLocations,isPropertyLocation} from '../dist/locations.js';
import {evaluateMatch,prepareSearch,searchSpecificity} from '../dist/matching.js';
import {streetDemoData} from '../dist/street-demo-data.js';

const street=(digit,extras={})=>({id:'street:'+digit.repeat(24),label:'Budapest XI. kerület, Tesztelő utca',city:'Budapest',district:'XI.',kind:'street',streetName:'Tesztelő utca',postalCodes:['1111'],...extras});
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch;});
const storage=()=>{const values=new Map();return {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};};
const response=body=>({ok:true,status:200,text:async()=>JSON.stringify(body)});
const api=()=>new ApiModel({baseUrl:'https://example.test',token:'token'});
const property={id:'property',ownerId:'seller',title:'Teszt otthon',locationId:'district:Budapest:11',type:'Lakás',price:60000000,area:60,rooms:3};
const profile={id:'viewer',name:'Nagy Anna',credits:24,activeKind:'search',activeEntityId:'search'};
function accountRoutes(entities,extra={}){
  const routes={'/api/me':profile,'/api/me/entities':entities,'/api/credits/ledger':[],...extra};
  globalThis.fetch=async url=>{const path=new URL(url).pathname;assert.ok(path in routes,path);return response(routes[path]);};
}

test('street metadata is registered explicitly, validates its shape and never becomes an exact property location',()=>{
  const selected=street('1');
  assert.equal(getLocation(selected.id),null);
  for(const invalid of [street('2',{city:'Nemváros'}),street('2',{district:'XXIV.'}),street('2',{postalCodes:['111']}),street('2',{streetName:'Bad\nname'}),street('2',{id:'street:bad'})]){
    assert.deepEqual(registerLocations([invalid]),[]);
    assert.equal(getLocation(invalid.id),null);
  }
  assert.deepEqual(registerLocations([selected]).map(item=>item.id),[selected.id]);
  assert.equal(isPropertyLocation(getLocation(selected.id)),false);
  assert.equal(locations.some(item=>item.kind==='street'),false,'the initial browser catalogue stays metadata-only');
  assert.equal(searchLocations('Tesztelő utca Budapest')[0].id,selected.id);
  assert.equal(searchLocations('Tesztelő utca',8,{kind:'property'}).some(item=>item.kind==='street'),false);
  assert.equal(searchStreets('tesztel','district:Budapest:11')[0].id,selected.id);
  assert.equal(searchStreets('tesztel','city:Budapest')[0].id,selected.id);
  assert.deepEqual(searchStreets('tesztel','district:Budapest:13'),[]);
  assert.deepEqual(registerLocations([{...selected,streetName:'Changed identity'}]),[]);
  assert.equal(getLocation(selected.id).streetName,selected.streetName);
});

test('unknown source wards remain available city-wide and cannot be assigned to a specific property ward',()=>{
  const unknownWard=registerLocations([street('0',{district:null,streetName:'Ismeretlen kerület fixture utca',label:'Budapest, Ismeretlen kerület fixture utca',postalCodes:['1007']})])[0];
  const city=getLocation('city:Budapest'),district=getLocation('district:Budapest:11');
  assert.equal(searchStreets('Ismeretlen kerület',city.id,8,[unknownWard])[0].id,unknownWard.id);
  assert.deepEqual(searchStreets('Ismeretlen kerület',district.id,8,[unknownWard]),[]);
  assert.equal(resolveStreetLocation(unknownWard.streetName,city,'1007',[unknownWard]).id,unknownWard.id);
  assert.equal(resolveStreetLocation(unknownWard.streetName,district,'1007',[unknownWard]),null);
  assert.equal(matchesLocations({locationId:district.id,streetId:unknownWard.id,hideStreet:false},{locationIds:[unknownWard.id]}),true,'matching still honors trusted legacy associations');
});

test('street selections are exact hard gates with town, district, neighborhood and area OR semantics',()=>{
  const selected=registerLocations([street('3')])[0];
  const home={ownerId:'seller',locationId:'district:Budapest:11',streetId:selected.id,hideStreet:false,type:'Lakás',price:60,area:60,rooms:3};
  const query={ownerId:'buyer',type:'Lakás',locationIds:[selected.id]};
  assert.equal(prepareSearch(query).streetIds.has(selected.id),true);
  for(const check of [matchesLocations,(p,q)=>evaluateMatch(p,q).eligible]){
    assert.equal(check(home,query),true);
    assert.equal(check({...home,streetId:null},query),false);
    assert.equal(check({...home,streetId:'street:'+'4'.repeat(24)},query),false);
    assert.equal(check({...home,locationId:'city:Szeged'},query),false);
    assert.equal(check({...home,locationId:'district:Budapest:13'},query),false);
    assert.equal(check({...home,locationId:'city:Budapest'},query),true,'legacy trusted IDs can have no ward');
    assert.equal(check({...home,streetId:null},{...query,locationIds:[selected.id,'city:Budapest']}),true);
    assert.equal(check({...home,locationId:'city:Solymár',streetId:null},{...query,locationIds:[selected.id,'area:Budapest']}),true);
    const quarter=locations.find(location=>location.kind==='neighborhood');
    assert.equal(check({...home,streetId:null,neighborhoodIds:[quarter.id]},{...query,locationIds:[selected.id,quarter.id]}),true);
    assert.equal(check(home,{...query,locationIds:[selected.id,'street:'+'f'.repeat(24)]}),false);
  }
  assert.ok(searchSpecificity(query)>searchSpecificity({...query,locationIds:['city:Budapest']}));
  assert.equal(evaluateMatch(home,query).score,100);
});

test('direct location matching enforces the raw 50-selection cap even for duplicate IDs',()=>{
  const home={locationId:'city:Debrecen'};
  assert.equal(matchesLocations(home,{locationIds:Array(50).fill(home.locationId)}),true);
  assert.equal(matchesLocations(home,{locationIds:Array(51).fill(home.locationId)}),false);
});

test('nearby distances cannot relax street-only searches while mixed choices retain area-based proximity',()=>{
  const selected=registerLocations([street('e',{id:'street:1234567890abcdef01234567',streetName:'Közelség fixture utca',label:'Budapest XI. kerület, Közelség fixture utca'})])[0];
  const home={ownerId:'seller',locationId:'district:Budapest:11',streetId:null,hideStreet:false,type:'Lakás',price:60,area:60,rooms:3};
  const query={ownerId:'buyer',type:'Lakás',locationIds:[selected.id]};
  for(const distance of [0,.01,1,20]){
    assert.equal(evaluateMatch(home,query,{locationDistanceKm:distance}).eligible,false);
    assert.equal(evaluateMatch({...home,streetId:selected.id},query,{locationDistanceKm:distance}).score,100);
  }
  assert.equal(evaluateMatch({...home,streetId:selected.id,hideStreet:true},query,{locationDistanceKm:0}).eligible,false);
  const mixed={...query,locationIds:[selected.id,'city:Szeged']};
  const nearby=evaluateMatch(home,mixed,{locationDistanceKm:1});
  assert.equal(nearby.eligible,true);assert.equal(nearby.isExact,false);assert.equal(nearby.score,94);
  assert.equal(evaluateMatch({...home,hideStreet:true},mixed,{locationDistanceKm:1}).score,94);
});

test('API suggestion methods use bounded scoped endpoints and register only valid public metadata',async()=>{
  const selected=street('5');const calls=[];
  globalThis.fetch=async url=>{const parsed=new URL(url);calls.push(parsed);return response({items:parsed.pathname.endsWith('/streets')?[selected,street('6',{city:'Szeged',district:null})]:[{id:'city:Budapest'},selected]});};
  const model=api();
  assert.deepEqual((await model.findLocations('Tesztelő',12)).map(item=>item.id),['city:Budapest',selected.id]);
  assert.equal(calls[0].searchParams.get('kind'),'search');
  assert.equal(calls[0].searchParams.get('limit'),'12');
  assert.equal((await model.findLocations('Budapest',8,{kind:'property'})).some(item=>item.kind==='street'),false);
  assert.deepEqual((await model.findStreets('Tesztelő','district:Budapest:11',7)).map(item=>item.id),[selected.id]);
  assert.equal(calls.at(-1).pathname,'/api/streets');assert.equal(calls.at(-1).searchParams.get('locationId'),'district:Budapest:11');
  const before=calls.length;
  assert.deepEqual(await model.findStreets('Tesztelő',selected.id),[]);
  assert.deepEqual(await model.findLocations('',8),[]);
  await assert.rejects(model.findLocations('Budapest',8,{kind:'invalid'}));
  assert.equal(calls.length,before);
});

test('API search DTO metadata hydrates street IDs before reading and malformed unknown choices fail closed',async()=>{
  const selected=street('7');const search={id:'search',ownerId:'viewer',title:'Utcában keresünk',locationIds:[selected.id],locations:[selected],city:'Budapest'};
  assert.equal(getLocation(selected.id),null);
  accountRoutes({properties:[],searchRequests:[search]});
  const state=await api().getState();
  assert.equal(state.searches[0].locations[0].kind,'street');
  assert.deepEqual(state.searches[0].locationIds,[selected.id]);
  assert.equal(evaluateMatch({...property,price:60,streetId:selected.id,hideStreet:false},state.searches[0]).eligible,true);
  const invalid='street:'+'8'.repeat(24);
  accountRoutes({properties:[],searchRequests:[{...search,locationIds:[invalid],locations:[street('8',{postalCodes:['bad']})]}]});
  const broken=(await api().getState()).searches[0];
  assert.deepEqual(broken.locationIds,[invalid]);assert.deepEqual(broken.locations,[]);
  assert.equal(evaluateMatch({...property,price:60},broken).eligible,false);
});

test('over fifty raw location IDs stay invalid before duplicate removal in API and demo reads and saves',async()=>{
  const chosen=streetDemoData.find(street=>street.streetName==='Pozsonyi út'),invalid=Array(51).fill(chosen.id);
  const query={id:'search',ownerId:'viewer',title:'Érvénytelen ismételt helyszínek',city:'Budapest',locationIds:invalid,locations:[chosen]};
  accountRoutes({properties:[],searchRequests:[query]});
  const remoteModel=api(),remote=(await remoteModel.getState()).searches[0];
  assert.deepEqual(remote.locationIds,invalid);assert.deepEqual(remote.locations,[]);
  assert.equal(evaluateMatch({...property,price:60,streetId:chosen.id},remote).eligible,false);
  await assert.rejects(remoteModel.saveEntity('search',remote),/találati listából/);

  const values=storage();createModel(values).buyDemoCredits(1);
  const raw=JSON.parse(values.getItem(STORAGE_KEY));
  Object.assign(raw.searches.find(search=>search.id==='own-s1'),query,{id:'own-s1',ownerId:'me'});
  values.setItem(STORAGE_KEY,JSON.stringify(raw));
  const localModel=createModel(values),local=localModel.getState().searches.find(search=>search.id==='own-s1');
  assert.deepEqual(local.locationIds,invalid);assert.deepEqual(local.locations,[]);assert.deepEqual(localModel.feed(),[]);
  assert.throws(()=>localModel.saveEntity('search',local,local.id),/találati listából/);
});

test('API property inputs carry selected street IDs but never authoritative coordinates or memberships',async()=>{
  const selected=registerLocations([street('9')])[0];let body;
  globalThis.fetch=async(url,options)=>{body=JSON.parse(options.body);return response({...property,...body,addressDetails:{streetId:selected.id,street:body.street,houseNumber:body.houseNumber,postalCode:body.postalCode}});};
  const saved=await api().saveEntity('property',{title:'Saját lakás',locationId:'district:Budapest:11',streetId:selected.id,street:selected.streetName,houseNumber:'12',postalCode:'1111',price:60,area:60,rooms:3,latitude:47,longitude:19,neighborhoodIds:['forged']});
  assert.equal(body.streetId,selected.id);assert.equal(saved.addressDetails.streetId,selected.id);
  for(const key of ['latitude','longitude','addressDetails','neighborhoodIds'])assert.equal(key in body,false,key);
  assert.equal('streetId' in saved,false);
});

test('foreign API properties lose street IDs and private metadata in feeds, incoming likes, history and matches',async()=>{
  const selected=street('a');
  const privateProperty={...property,streetId:selected.id,streetMetadata:selected,addressDetails:{streetId:selected.id,street:'Private street',latitude:47,longitude:19}};
  const search={id:'search',ownerId:'viewer',title:'Keresés',locationIds:['city:Budapest']};
  const pair={property:privateProperty,searchRequest:search,propertyId:'property',searchRequestId:'search'};
  accountRoutes({properties:[],searchRequests:[search],decisions:[{...pair,id:'decision',actorId:'search'}]}, {
    '/api/feed':{items:[pair]},'/api/incoming-likes':{active:{kind:'search',id:'search'},items:[pair]},'/api/matches':[{id:'match',...pair,contact:{id:'seller',name:'Teszt Elek'},messages:[]}]
  });
  const model=api();const state=await model.getState();
  const values=[state.decisions[0].property,(await model.feed())[0],(await model.incomingLikes()).items[0],(await model.matches())[0].property];
  for(const value of values)for(const key of ['streetId','streetMetadata','street','addressDetails','latitude','longitude'])assert.equal(key in value,false,key);
  assert.equal(getLocation(selected.id),null,'foreign property data never registers a private street association');
});

test('demo loads the full street catalogue only after a search picker requests it',async()=>{
  let loads=0;const selected=street('b');
  const model=createModel(storage(),()=> '2026-11-18T12:00:00Z',{streetLoader:async()=>{loads++;return [selected];}});
  assert.equal(loads,0);assert.equal(getLocation(selected.id),null);
  assert.equal((await model.findLocations('Budapest',8,{kind:'property'})).length,8);assert.equal(loads,0);
  assert.deepEqual(await model.findLocations(''),[]);assert.equal(loads,0);
  assert.equal((await model.findLocations('Tesztelő utca'))[0].id,selected.id);assert.equal(loads,1);
  assert.equal((await model.findStreets('Tesztelő','city:Budapest'))[0].id,selected.id);assert.equal(loads,1);
});

test('demo street binding derives only an exact known source choice, derives its ward and clears stale addresses',()=>{
  const values=storage();const selected=street('c',{streetName:'Egyedi fixture utca',label:'Budapest XI. kerület, Egyedi fixture utca'});
  const model=createModel(values,()=> '2026-11-18T12:00:00Z',{streetCatalog:[selected]});
  const input={title:'Új saját lakás',locationId:'city:Budapest',street:selected.streetName,houseNumber:'12',postalCode:'1111',price:60,area:60,rooms:3};
  const saved=model.saveEntity('property',input);
  assert.equal(saved.addressDetails.streetId,selected.id);assert.equal(saved.locationId,'district:Budapest:11');assert.equal('streetId' in saved,false);
  const raw=JSON.parse(values.getItem(STORAGE_KEY));assert.equal(raw.properties.find(item=>item.id===saved.id).streetId,selected.id);
  const changed=model.saveEntity('property',{...input,streetId:selected.id,street:'Másik utca'},saved.id);
  assert.equal(changed.addressDetails.streetId,null);
  const moved=model.saveEntity('property',{...input,locationId:'city:Szeged',streetId:selected.id},saved.id);
  assert.equal(moved.addressDetails.streetId,null);
  const wrongPostal=model.saveEntity('property',{...input,postalCode:'9999',streetId:selected.id},saved.id);
  assert.equal(wrongPostal.addressDetails.streetId,null);
  assert.equal(createModel(values).getState().properties.find(item=>item.id===saved.id).addressDetails.streetId,null);
});

test('demo keeps private street associations for matching and strips them from every foreign property view',()=>{
  const values=storage(),selected=street('d',{district:'XIII.',label:'Budapest XIII. kerület, Privát fixture utca',streetName:'Privát fixture utca',postalCodes:['1133']});
  createModel(values,()=> '2026-11-18T12:00:00Z',{streetCatalog:[selected]}).buyDemoCredits(1);
  const raw=JSON.parse(values.getItem(STORAGE_KEY));
  for(const home of raw.properties.filter(item=>['p1','matched-p1'].includes(item.id))){
    home.streetId=selected.id;home.streetMetadata=selected;home.hideStreet=false;
    home.addressDetails={...home.addressDetails,street:selected.streetName,postalCode:'1133',streetId:selected.id};
  }
  const ownSearch=raw.searches.find(item=>item.id==='own-s1');ownSearch.locationIds=[selected.id];ownSearch.locations=[selected];
  values.setItem(STORAGE_KEY,JSON.stringify(raw));
  const model=createModel(values);assert.ok(model.feed().some(item=>item.id==='p1'));
  const publicProperties=[...model.feed(),...model.incomingLikes().items,...model.getState().decisions.map(item=>item.property),...model.matches().map(item=>item.property)].filter(Boolean);
  for(const home of publicProperties)for(const key of ['streetId','streetMetadata','streetLocation','addressDetails'])assert.equal(key in home,false,key);
  const query=model.getState().searches.find(item=>item.id==='own-s1');
  assert.equal(query.locations[0].id,selected.id,'published search choices remain public metadata');
});

test('unchanged owned demo associations survive a reload before the public catalogue is loaded',()=>{
  const values=storage();createModel(values).buyDemoCredits(1);
  const raw=JSON.parse(values.getItem(STORAGE_KEY)),home=raw.properties.find(item=>item.id==='own-p1');
  const id='street:'+'e'.repeat(24);home.streetId=id;home.addressDetails.streetId=id;home.addressDetails.street='Még be nem töltött fixture utca';
  values.setItem(STORAGE_KEY,JSON.stringify(raw));
  const model=createModel(values);assert.equal(getLocation(id),null);
  const own=model.getState().properties.find(item=>item.id==='own-p1');assert.equal(own.addressDetails.streetId,id);
  const edited=model.saveEntity('property',{title:'Új cím változatlan utcával'},own.id);
  assert.equal(edited.addressDetails.streetId,id);
  const changed=model.saveEntity('property',{title:'Megváltoztatott cím',street:'Új ismeretlen utca'},own.id);
  assert.equal(changed.addressDetails.streetId,null);
  assert.equal(evaluateMatch({...property,price:60,streetId:id},{ownerId:'buyer',locationIds:[id],city:'Budapest'}).eligible,false);
});

test('fictional demo seeds bind real catalogue streets while retaining synthetic addresses and stable IDs',()=>{
  const values=storage(),model=createModel(values);model.buyDemoCredits(1);
  const raw=JSON.parse(values.getItem(STORAGE_KEY));
  const supported=raw.properties.filter(home=>['II.','XI.','XIII.'].includes(home.district));
  assert.ok(supported.length>=10);assert.ok(raw.properties.some(home=>home.id==='own-p1'));
  for(const home of supported){
    const source=streetDemoData.find(street=>street.id===home.addressDetails.streetId);
    assert.ok(source);assert.equal(source.district,home.district);assert.equal(source.streetName,home.addressDetails.street);
    assert.equal(home.streetId,source.id);assert.ok(source.postalCodes.includes(home.addressDetails.postalCode));
    assert.match(home.addressDetails.houseNumber,/^99999\//);assert.equal(home.addressDetails.provider,'synthetic-demo');
  }
  const choice=streetDemoData.find(street=>street.streetName==='Pozsonyi út');
  for(const home of supported)home.hideStreet=false;values.setItem(STORAGE_KEY,JSON.stringify(raw));
  const visibleModel=createModel(values);
  const search=visibleModel.saveEntity('search',{title:'Pozsonyi úton keresünk',locationIds:[choice.id],type:'Lakás'});
  visibleModel.activate('search',search.id);assert.ok(visibleModel.feed().some(home=>home.id==='p1'));
  for(const home of visibleModel.feed())assert.equal('streetId' in home,false);
});


test('hidden street choices cannot discover a property but broad location alternatives still can',()=>{
 const selected=registerLocations([street('f',{streetName:'Elrejtett fixture utca',label:'Budapest XI. kerület, Elrejtett fixture utca'})])[0];
 const home={ownerId:'seller',locationId:'district:Budapest:11',streetId:selected.id,type:'Lakás',price:60,area:60,rooms:3};
 for(const check of [matchesLocations,(p,q)=>evaluateMatch(p,q).eligible]){
  const query={ownerId:'buyer',type:'Lakás',locationIds:[selected.id]};
  assert.equal(check(home,query),false,'Legacy missing visibility settings remain private');
  assert.equal(check({...home,hideStreet:true},query),false);
  assert.equal(check({...home,hideStreet:false,hideHouseNumber:true},query),true);
  assert.equal(check({...home,hideStreet:true},{...query,locationIds:[selected.id,'city:Budapest']}),true);
 }
});
