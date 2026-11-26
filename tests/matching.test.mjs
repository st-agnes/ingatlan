import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {MATCH_WEIGHTS,prepareSearch,evaluateMatch,valueForMoney,searchSpecificity} from '../dist/matching.js';
import {locations,MAX_SEARCH_LOCATIONS} from '../dist/locations.js';

const home=(extra={})=>({ownerId:'seller',locationId:'city:Debrecen',city:'Debrecen',type:'Lakás',price:80,area:60,rooms:3,...extra});
const wanted=(extra={})=>({ownerId:'buyer',locationIds:['city:Debrecen'],city:'Debrecen',type:'Lakás',...extra});

test('every exact match receives 100 regardless of price margin or optional amenities',()=>{
  for(const p of [home(),home({price:100}),home({balcony:true,elevator:true}),home({price:60})]){
    const result=evaluateMatch(p,wanted({maxPrice:100}));
    assert.deepEqual({...result,matchDetails:undefined},{eligible:true,isExact:true,score:100,distanceSquared:0,locationDistanceKm:0,reasons:['Megfelelő elhelyezkedés','A megadott árkereten belül','Megfelelő alapterület és szobaszám'],matchDetails:undefined});
    assert.ok(result.matchDetails.every(detail=>detail.matches));
  }
  assert.equal(evaluateMatch(home({type:'Ház'}),wanted({type:'Ház'})).score,100);
});

test('location, type, self ownership and archive state remain hard exclusions',()=>{
  for(const p of [home({locationId:'city:Szeged'}),home({locationId:'city:missing'}),home({locationId:'area:Debrecen'}),home({type:'Ház'}),home({ownerId:'buyer'}),home({archived:true})])
    assert.equal(evaluateMatch(p,wanted()).eligible,false);
  assert.equal(evaluateMatch(home(),wanted({type:'Bármilyen'})).eligible,false);
  assert.equal(evaluateMatch(home(),wanted({archived:true})).eligible,false);
});

test('canonical areas, selected alternatives and Budapest districts retain their hard location semantics',()=>{
  assert.equal(evaluateMatch(home({locationId:'city:Hajdúsámson'}),wanted({locationIds:['area:Debrecen']})).score,100);
  assert.equal(evaluateMatch(home({locationId:'city:Szeged'}),wanted({locationIds:['city:Szeged','city:Debrecen']})).score,100);
  const buda=home({locationId:'district:Budapest:2',city:'Budapest',district:'II.'});
  assert.equal(evaluateMatch(buda,wanted({locationIds:['city:Budapest']})).score,100);
  assert.equal(evaluateMatch(buda,wanted({locationIds:['district:Budapest:13']})).eligible,false);
});

test('expanded surroundings keep every selected town matchable up to the shared location limit',()=>{
 const selected=locations.filter(location=>location.kind==='city').slice(0,MAX_SEARCH_LOCATIONS+1);
 const request=wanted({locationIds:selected.slice(0,MAX_SEARCH_LOCATIONS).map(location=>location.id)});
 const prepared=prepareSearch(request),last=selected[MAX_SEARCH_LOCATIONS-1];
 assert.equal(prepared.cities.size,MAX_SEARCH_LOCATIONS);
 assert.equal(evaluateMatch(home({locationId:last.id,city:last.city}),prepared).score,100);
 assert.equal(prepareSearch({...request,locationIds:selected.map(location=>location.id)}).cities.size,0,'Over-limit stored choices remain invalid rather than becoming a partial selection');
});

test('numeric deviation grows continuously, respects inclusive boundaries and remains below 100 when tiny',()=>{
  const q=wanted({maxPrice:100});
  assert.deepEqual([100,110,120,150,200].map(price=>evaluateMatch(home({price}),q).score),[100,90,80,58,33]);
  assert.equal(evaluateMatch(home({price:100.00001}),q).score,99);
  assert.equal(evaluateMatch(home({rooms:2}),wanted({minRooms:3})).score,70);
  assert.equal(evaluateMatch(home({area:40}),wanted({minArea:50})).score,82);
  assert.equal(evaluateMatch(home({rooms:2.5}),wanted({minRooms:4})).score,67);
});

test('fractions of a million use the same relative price deviation as HUF values',()=>{
  assert.equal(evaluateMatch(home({price:.6}),wanted({maxPrice:.5})).score,80);
  assert.equal(evaluateMatch(home({price:600000}),wanted({maxPrice:500000})).score,80);
  assert.equal(evaluateMatch(home({price:.6}),wanted({maxPrice:0})).score,33);
  assert.equal(searchSpecificity(wanted({minPrice:.4,maxPrice:.5})),searchSpecificity(wanted({minPrice:400000,maxPrice:500000})));
});

test('importance weights and weighted losses preserve the requested priority order',()=>{
  const order=['maxPrice','minRooms','minArea','condition','floor','elevator','balcony','building','heatingType','constructionAge','ceilingHeight'];
  for(let i=1;i<order.length;i++)assert.ok(MATCH_WEIGHTS[order[i-1]]>MATCH_WEIGHTS[order[i]]);
  const q=wanted({maxPrice:100,minRooms:4,minArea:80});
  const price=evaluateMatch(home({price:150,rooms:4,area:80}),q);
  const rooms=evaluateMatch(home({price:100,rooms:2,area:80}),q);
  const area=evaluateMatch(home({price:100,rooms:4,area:40}),q);
  assert.ok(price.score<rooms.score&&rooms.score<area.score);
});

test('condition is an ordered minimum and better conditions remain exact',()=>{
  const q=wanted({conditions:['Jó','Új/felújított']});
  assert.deepEqual(['Felújítandó','Átlagos','Jó','Új/felújított'].map(condition=>evaluateMatch(home({condition}),q).score),[67,82,100,100]);
  assert.equal(evaluateMatch(home({condition:'Felújított'}),q).score,100);
  assert.equal(evaluateMatch(home(),q).score,55);
  assert.equal(evaluateMatch(home({condition:'Jó'}),wanted({conditions:['Átlagos']})).score,100);
});

test('floor loss uses the nearest allowed floor, supports basement and 8-or-higher and penalizes unknown floors',()=>{
  const q=wanted({floors:[1,5]});
  assert.equal(evaluateMatch(home({floor:4}),q).score,90);
  assert.equal(evaluateMatch(home({floor:3}),q).score,82);
  assert.equal(evaluateMatch(home({floor:-1}),wanted({floors:[0]})).score,90);
  assert.equal(evaluateMatch(home({floor:27}),wanted({floors:[11]})).score,100);
  assert.equal(evaluateMatch(home({floor:null}),q).score,61);
});

test('known category alternatives are OR and missing selected seller details are partial rather than silently exact',()=>{
  const q=wanted({buildings:['Tégla','Panel'],heatingTypes:['Gázkazán','Hőszivattyú'],constructionAges:['10 évnél fiatalabb'],ceilingHeight:'3 m alatti',views:['Kertre néző']});
  const p=home({building:'panel',heatingType:'gázkazán',constructionAge:'10 évnél fiatalabb',ceilingHeight:'3 m alatti',view:'kertre néző'});
  assert.equal(evaluateMatch(p,q).score,100);
  assert.equal(evaluateMatch(home(),q).isExact,false);
  assert.equal(evaluateMatch(home({constructionAge:'10–30 év közötti'}),wanted({constructionAges:['10 évnél fiatalabb']})).score,97);
});

test('houses ignore old floor, balcony and lift restrictions and full room composition remains authoritative',()=>{
  assert.equal(evaluateMatch(home({type:'Ház'}),wanted({type:'Ház',floors:[11],balcony:true,elevator:true})).score,100);
  assert.equal(evaluateMatch(home({rooms:99,wholeRooms:2,halfRooms:1}),wanted({minRooms:3})).isExact,false);
});

test('remaining minimum price, maximum rooms/area and view conditions still participate',()=>{
  assert.equal(evaluateMatch(home({price:40}),wanted({minPrice:50})).score,94);
  assert.equal(evaluateMatch(home({area:90}),wanted({maxArea:60})).score,82);
  assert.equal(evaluateMatch(home({rooms:6}),wanted({maxRooms:3})).score,67);
  assert.equal(evaluateMatch(home({view:'Utcai'}),wanted({views:['Kertre néző']})).score,90);
});

test('value ordering is primarily living size per price, with bounded quality and house plot contributions',()=>{
  const p=home({area:100,price:100,rooms:4});
  assert.ok(valueForMoney({...p,price:80})>valueForMoney(p));
  assert.ok(valueForMoney({...p,area:150})>valueForMoney(p));
  assert.ok(valueForMoney({...p,condition:'Új/felújított',insulated:true})>valueForMoney(p));
  const house={...p,type:'Ház'};
  assert.ok(valueForMoney({...house,lotArea:500})>valueForMoney(house));
  assert.equal(valueForMoney({...house,lotArea:500}),valueForMoney({...house,lotArea:50000}));
  assert.ok(valueForMoney({...house,area:200,rooms:8})>valueForMoney({...house,lotArea:50000}));
  assert.equal(valueForMoney({...p,price:0}),0);
});

test('specificity rewards more restrictions, narrower ranges and fewer locations or categories',()=>{
  const broad=wanted(),narrow=wanted({minPrice:70,maxPrice:90,minRooms:2,maxRooms:3,minArea:50,maxArea:70,conditions:['Jó'],buildings:['Tégla'],heatingTypes:['Hőszivattyú'],constructionAges:['10 évnél fiatalabb'],views:['Kertre néző'],ceilingHeight:'3 m alatti',floors:[1],balcony:true,elevator:true});
  assert.ok(searchSpecificity(narrow)>searchSpecificity(broad));
  assert.ok(searchSpecificity(wanted({minPrice:90,maxPrice:100}))>searchSpecificity(wanted({minPrice:10,maxPrice:100})));
  assert.ok(searchSpecificity(wanted({buildings:['Tégla']}))>searchSpecificity(wanted({buildings:['Tégla','Panel']})));
  assert.ok(searchSpecificity(wanted())>searchSpecificity(wanted({locationIds:['city:Debrecen','city:Szeged','city:Pécs']})));
  assert.equal(searchSpecificity(wanted({type:'Ház'})),searchSpecificity(wanted({type:'Ház',floors:[1],balcony:true,elevator:true})));
});

test('prepared filters can be reused across large candidate lists without mutating entities or reparsing edited source arrays',()=>{
  const q=wanted({maxPrice:100,buildings:['Tégla']}),prepared=prepareSearch(q),p=home({building:'Tégla'}),original=structuredClone(p);
  q.maxPrice=1;q.buildings.push('Panel');q.locationIds.push('city:Szeged');
  for(let i=0;i<10000;i++)assert.equal(evaluateMatch(p,prepared).score,100);
  assert.deepEqual(p,original);assert.equal(evaluateMatch(home({locationId:'city:Szeged'}),prepared).eligible,false);
});

test('the browser and .NET matching engines use the same fixed cross-language score fixtures',()=>{
  const cases=JSON.parse(readFileSync(new URL('../backend/fixtures/matching-ranking-cases.json',import.meta.url),'utf8'));
  for(const item of cases){
    const p=home(item.property),s=wanted(item.search),result=evaluateMatch(p,s,{perspective:item.perspective??'buyer',locationDistanceKm:item.locationDistanceKm??null});
    if('eligible' in item)assert.equal(result.eligible,item.eligible,item.name);
    if('score' in item){assert.equal(result.score,item.score,item.name);assert.equal(result.isExact,item.score===100,item.name);}
    if('specificity' in item)assert.equal(searchSpecificity(s,{perspective:item.perspective??'buyer',locationDistanceKm:item.locationDistanceKm??null}),item.specificity,item.name);
    if('valueForMoney' in item)assert.ok(Math.abs(valueForMoney(p)-item.valueForMoney)<1e-8,item.name);
    if('matchDetails' in item)assert.deepEqual(result.matchDetails,item.matchDetails,item.name);
  }
});

test('partial explanations contain concrete requested and actual values plus met criteria',()=>{
  const p=home({price:95,rooms:3,area:60,condition:'Átlagos',floor:2,building:'Tégla',heatingType:'Gázkazán'});
  const s=wanted({maxPrice:80,minRooms:4,minArea:50,conditions:['Jó','Új/felújított'],floors:[1,5],elevator:true,buildings:['Tégla'],heatingTypes:['Gázkazán']});
  const result=evaluateMatch(p,s),details=Object.fromEntries(result.matchDetails.map(item=>[item.key,item]));
  assert.equal(result.isExact,false);
  assert.deepEqual(details.rooms,{key:'rooms',label:'Szobaszám',expected:'legalább 4 szoba',actual:'3 szoba',matches:false});
  assert.deepEqual(details.price,{key:'price',label:'Ár',expected:'legfeljebb 80 M Ft',actual:'95 M Ft',matches:false});
  assert.deepEqual(details.area,{key:'area',label:'Alapterület',expected:'legalább 50 m²',actual:'60 m²',matches:true});
  assert.equal(details.condition.expected,'Jó vagy jobb');assert.equal(details.condition.actual,'Átlagos');assert.equal(details.condition.matches,false);
  assert.equal(details.floor.expected,'1. emelet vagy 5. emelet');assert.equal(details.floor.actual,'2. emelet');assert.equal(details.floor.matches,false);
  assert.equal(details.elevator.expected,'Van lift');assert.equal(details.elevator.actual,'Nincs lift');
  for(const key of ['location','type','area','building','heatingType'])assert.equal(details[key].matches,true,key);
});

test('explanations respect bounds, aliases, 8+ floors, unknown values and applicable criteria',()=>{
  let result=evaluateMatch(home({price:80.5,rooms:3.5,area:60}),wanted({minPrice:60,maxPrice:100,minRooms:2.5,maxRooms:4,minArea:50,maxArea:70}));
  assert.equal(result.matchDetails.find(item=>item.key==='rooms').expected,'2,5–4 szoba');
  assert.equal(result.matchDetails.find(item=>item.key==='price').actual,'80,5 M Ft');
  result=evaluateMatch(home({floor:27,condition:'Felújított'}),wanted({floors:[11],conditions:['Jó']}));
  assert.equal(result.matchDetails.find(item=>item.key==='floor').expected,'8. emelet vagy afölötti');
  assert.equal(result.matchDetails.find(item=>item.key==='floor').actual,'27. emelet');
  assert.ok(result.matchDetails.every(item=>item.matches));
  result=evaluateMatch(home(),wanted({buildings:['Panel','Tégla'],heatingTypes:['Nincs fűtés']}));
  assert.equal(result.matchDetails.find(item=>item.key==='building').expected,'Tégla vagy Panel');
  assert.equal(result.matchDetails.find(item=>item.key==='building').actual,'Nincs megadva');
  assert.equal(result.matchDetails.find(item=>item.key==='heatingType').matches,false);
  result=evaluateMatch(home({type:'Ház'}),wanted({type:'Ház',floors:[11],balcony:true,elevator:true}));
  assert.deepEqual(result.matchDetails.map(item=>item.key),['location','type']);
  assert.deepEqual(evaluateMatch(home({type:'Ház'}),wanted()).matchDetails,[]);
});

test('lean ranking omits presentation details while snapshots retain the original location labels',()=>{
  const s=wanted({maxPrice:100}),prepared=prepareSearch(s);
  s.locationIds.push('city:Szeged');
  const result=evaluateMatch(home(),prepared);
  assert.equal(result.matchDetails.find(item=>item.key==='location').expected,'Debrecen');
  const lean=evaluateMatch(home({price:120}),prepared,{includeReasons:false});
  assert.equal(lean.score,80);assert.deepEqual(lean.matchDetails,[]);assert.deepEqual(lean.reasons,[]);
});

test('top-floor and ground exclusions require known facts and share one floor penalty budget',()=>{
 const q=wanted({maxPrice:100,excludeTopFloor:true,excludeGroundFloorAndBelow:true});
 assert.equal(evaluateMatch(home({floor:2,buildingFloors:3}),q).score,100);
 for(const p of [{floor:3,buildingFloors:3},{floor:0,buildingFloors:3},{floor:-1,buildingFloors:3},{floor:2},{buildingFloors:3}]){
  const result=evaluateMatch(home(p),q);assert.equal(result.eligible,true);assert.equal(result.isExact,false);assert.equal(result.score,61,JSON.stringify(p));
 }
 const all=wanted({maxPrice:100,floors:[2],excludeTopFloor:true,excludeGroundFloorAndBelow:true});
 assert.equal(evaluateMatch(home({floor:0,buildingFloors:0}),all).score,61,'three failed floor predicates share one floor-distance term');
 assert.equal(evaluateMatch(home({floor:12,buildingFloors:13}),wanted({floors:[11],excludeTopFloor:true,excludeGroundFloorAndBelow:true})).score,100);
 assert.equal(evaluateMatch(home({floor:-1,buildingFloors:0}),wanted({excludeTopFloor:true})).score,100);
 assert.equal(evaluateMatch(home({floor:201,buildingFloors:200}),wanted({excludeTopFloor:true})).matchDetails.find(x=>x.key==='excludeTopFloor').actual,'Nincs megadva');
});

test('air conditioning and private garden requests retain weighted losses while shared garden input is retired',()=>{
 for(const [key,score] of [['airConditioning',82],['privateGarden',82]]){
  const q=wanted({maxPrice:100,[key]:true});
  assert.equal(evaluateMatch(home({[key]:true}),q).score,100,key);
  assert.equal(evaluateMatch(home({[key]:false}),q).score,score,key);
  assert.equal(evaluateMatch(home({[key]:null}),q).score,score,key);
 }
 assert.equal(evaluateMatch(home({privateGarden:true,sharedGarden:false}),wanted({sharedGarden:true})).score,100);
 for(const value of [true,false,null]){
  assert.equal(evaluateMatch(home({sharedGarden:value}),wanted({sharedGarden:true})).score,100);
  assert.equal(searchSpecificity(wanted({sharedGarden:value})),searchSpecificity(wanted()));
  assert.equal(valueForMoney(home({sharedGarden:value})),valueForMoney(home()));
 }
 assert.equal(evaluateMatch(home({type:'Ház',airConditioning:true}),wanted({type:'Ház',airConditioning:true,privateGarden:true,sharedGarden:true,excludeTopFloor:true,excludeGroundFloorAndBelow:true})).score,100);
 assert.equal(evaluateMatch(home({type:'Ház'}),wanted({type:'Ház',airConditioning:true})).score,82,'aircon also applies to houses');
});

test('new match explanations expose requested and actual facts while lean scans stay presentation free',()=>{
 const p=home({floor:2,buildingFloors:3,airConditioning:false,privateGarden:true,sharedGarden:null});
 const q=wanted({excludeTopFloor:true,excludeGroundFloorAndBelow:true,airConditioning:true,privateGarden:true,sharedGarden:true});
 const details=Object.fromEntries(evaluateMatch(p,q).matchDetails.map(x=>[x.key,x]));
 assert.deepEqual(details.excludeTopFloor,{key:'excludeTopFloor',label:'Legfelső emelet',expected:'Nem legfelső emelet',actual:'Nem legfelső emelet',matches:true});
 assert.equal(details.excludeGroundFloorAndBelow.actual,'2. emelet');assert.equal(details.excludeGroundFloorAndBelow.matches,true);
 assert.equal(details.airConditioning.actual,'Nincs légkondi');assert.equal(details.airConditioning.matches,false);
 assert.equal(details.privateGarden.actual,'Van saját kert');assert.equal('sharedGarden' in details,false);
 assert.deepEqual(evaluateMatch(p,q,{includeReasons:false}).matchDetails,[]);
 assert.ok(searchSpecificity(q)>searchSpecificity(wanted()));
 assert.equal(searchSpecificity(wanted({type:'Ház',privateGarden:true,sharedGarden:true,excludeTopFloor:true,excludeGroundFloorAndBelow:true})),searchSpecificity(wanted({type:'Ház'})));
 assert.ok(valueForMoney(home({privateGarden:true}))>valueForMoney(home()));
 assert.equal(valueForMoney(home({type:'Ház',privateGarden:true})),valueForMoney(home({type:'Ház'})));
});


test('raised-ground ordering and upper ranges distinguish known levels from unknown top floors',()=>{
 assert.equal(valueForMoney(home({floor:1.5})),valueForMoney(home()),'An invalid fractional floor cannot earn a known-low-floor bonus');
 const raised=home({floor:0.5,buildingFloors:0});
 assert.equal(evaluateMatch(raised,wanted({floors:[0.5],excludeGroundFloorAndBelow:true})).score,100);
 assert.equal(evaluateMatch(raised,wanted({floors:[0]})).score,95);
 assert.equal(evaluateMatch(raised,wanted({excludeTopFloor:true})).score,61);
 assert.equal(evaluateMatch({...raised,buildingFloors:1},wanted({excludeTopFloor:true})).score,100);
 const range=home({floor:9,floorIsUpperRange:true,buildingFloors:12});
 assert.equal(evaluateMatch(range,wanted({floors:[9]})).score,100);
 assert.equal(evaluateMatch(range,wanted({floors:[11]})).score,100);
 assert.equal(evaluateMatch(range,wanted({excludeTopFloor:true})).score,61);
 const detail=evaluateMatch(range,wanted({floors:[8]})).matchDetails.find(x=>x.key==='floor');
 assert.equal(detail.actual,'9. emelet vagy afölötti');assert.equal(detail.expected,'8. emelet vagy afölötti');assert.equal(detail.matches,true);
 assert.equal(evaluateMatch(home({floor:12,buildingFloors:13}),wanted({floors:[9],excludeTopFloor:true})).score,100);
});

test('certificate minimum applies its ordered deviation only to a known current scheme',()=>{
 const q=wanted({minEnergyRating:'A'});
 const high=evaluateMatch(home({energyRating:'A+',energyRatingScheme:'2023'}),q);
 const near=evaluateMatch(home({energyRating:'B',energyRatingScheme:'2023'}),q);
 const far=evaluateMatch(home({energyRating:'I',energyRatingScheme:'2023'}),q);
 assert.equal(high.score,100);assert.equal(near.score,98);assert.equal(far.score,86);
 assert.equal(evaluateMatch(home({energyRating:'A+'}),q).score,82);
 const detail=near.matchDetails.find(item=>item.key==='minEnergyRating');assert.equal(detail.label,'Minimum energetikai besorolás');assert.equal(detail.expected,'A vagy jobb');assert.equal(detail.actual,'B');assert.equal(detail.matches,false);
 assert.ok(searchSpecificity(wanted({minEnergyRating:'A'}))>=searchSpecificity(wanted({minEnergyRating:'C'})));
 assert.ok(searchSpecificity(wanted({minEnergyRating:'A+++'}))>searchSpecificity(wanted()));
});

test('attic facts share the existing floor penalty budget and explicit false differs from missing',()=>{
 const q=wanted({floors:[2],atticPreference:'exclude'}),p=home({floor:2,isAttic:false});
 assert.equal(evaluateMatch(p,q).score,100);assert.equal(evaluateMatch({...p,isAttic:true},q).score,61);
 assert.equal(evaluateMatch({...p,isAttic:null},q).score,61);
 const single=evaluateMatch({...p,floor:7},wanted({floors:[2]})),combined=evaluateMatch({...p,floor:7,isAttic:true},q);
 assert.equal(single.score,combined.score,'Adding another failed floor fact does not spend another independent penalty budget');
 assert.equal(combined.matchDetails.find(item=>item.key==='atticPreference').expected,'Nem tetőtéri ingatlan');
 assert.equal(evaluateMatch(home({type:'Ház',isAttic:true}),wanted({type:'Ház',atticPreference:'exclude'})).score,100);
});

test('selected floors and attic are OR alternatives in scores and displayed requirements',()=>{
 const request=wanted({floors:[3],atticPreference:'only'});
 for(const property of [home({floor:3,isAttic:false}),home({floor:3}),home({floor:7,isAttic:true}),home({isAttic:true})]){
  const result=evaluateMatch(property,request);
  assert.equal(result.score,100);assert.equal(result.isExact,true);
  const floor=result.matchDetails.find(item=>item.key==='floor');
  assert.equal(floor.expected,'3. emelet vagy Tetőtéri ingatlan');assert.equal(floor.matches,true);
  assert.equal(result.matchDetails.some(item=>item.key==='atticPreference'),false,'The attic alternative cannot appear as an independent unmet requirement');
 }
 const near=evaluateMatch(home({floor:2,isAttic:false}),request),far=evaluateMatch(home({floor:10,isAttic:false}),request);
 assert.equal(near.score,90);assert.equal(far.score,61,'An unmet attic alternative bounds the combined floor loss at one');
 assert.equal(evaluateMatch(home({floor:7,buildingFloors:7,isAttic:true}),{...request,excludeTopFloor:true}).score,61);
 assert.equal(evaluateMatch(home({floor:0,isAttic:true}),{...request,excludeGroundFloorAndBelow:true}).score,61);
 assert.equal(evaluateMatch(home({floor:3,isAttic:true}),{...request,atticPreference:'exclude'}).score,61);
});


test('seller scores, explanations and specificity depend only on the public budget while buyers use their true cap',()=>{
 const property=home({price:75});
 const request=wanted({minPrice:20,maxPrice:80,publicMaxPrice:70});
 assert.equal(evaluateMatch(property,request).score,100);
 const seller=evaluateMatch(property,request,{perspective:'seller'});
 assert.equal(seller.isExact,false);assert.ok(seller.score<100);
 assert.equal(seller.matchDetails.find(x=>x.key==='price').expected,'20–70 M Ft');
 for(const privateCap of [80,100,150]){
  const changed={...request,maxPrice:privateCap};
  assert.deepEqual(evaluateMatch(property,changed,{perspective:'seller'}),seller);
  assert.equal(searchSpecificity(changed,{perspective:'seller'}),searchSpecificity(request,{perspective:'seller'}));
 }
 const prepared=prepareSearch(request,{perspective:'seller'});request.maxPrice=1000;request.publicMaxPrice=1000;
 assert.deepEqual(evaluateMatch(property,prepared),seller,'A compiled seller search snapshots only its public cap');
 for(const legacyPublic of [undefined,null,''])assert.equal(evaluateMatch(property,wanted({maxPrice:80,publicMaxPrice:legacyPublic}),{perspective:'seller'}).score,100);
});

test('severe size shortfalls retain their distance when additional fulfilled criteria are specified',()=>{
 const property=home({area:50,condition:'Jó',building:'Tégla',floor:2,balcony:true,elevator:true});
 const onlyArea=evaluateMatch(property,wanted({minArea:250}));
 const detailed=evaluateMatch(property,wanted({minArea:250,maxArea:300,maxPrice:100,minRooms:1,conditions:['Jó'],buildings:['Tégla'],floors:[2],balcony:true,elevator:true}));
 assert.equal(onlyArea.score,45);assert.ok(Math.abs(onlyArea.distanceSquared-.64)<1e-12);
 assert.equal(detailed.score,onlyArea.score);assert.equal(detailed.distanceSquared,onlyArea.distanceSquared);
 assert.ok(detailed.matchDetails.filter(item=>item.key!=='area').every(item=>item.matches));
});

test('large numeric overruns do not flatten into the same capped penalty',()=>{
 const request=wanted({maxPrice:100});
 const twice=evaluateMatch(home({price:200}),request),fourTimes=evaluateMatch(home({price:400}),request);
 assert.equal(twice.score,33);assert.equal(fourTimes.score,4);assert.ok(fourTimes.distanceSquared>twice.distanceSquared);
 assert.equal(evaluateMatch(home({area:250}),wanted({maxArea:50})).score,20);
});

test('only valid nearby distances soften nonstreet locations and their penalty increases with distance',()=>{
 const property=home({locationId:'city:Szeged',city:'Szeged'}),request=wanted();
 const near=evaluateMatch(property,request,{locationDistanceKm:1}),far=evaluateMatch(property,request,{locationDistanceKm:20});
 assert.equal(near.eligible,true);assert.equal(near.isExact,false);assert.equal(near.score,94);assert.equal(far.score,29);
 assert.ok(near.distanceSquared<far.distanceSquared);
 assert.equal(near.matchDetails.find(detail=>detail.key==='location').matches,false);
 assert.match(near.matchDetails.find(detail=>detail.key==='location').expected,/Debrecen/);
 assert.equal(evaluateMatch(property,request,{locationDistanceKm:0}).score,99);
 for(const distance of [-1,NaN,Infinity])assert.equal(evaluateMatch(property,request,{locationDistanceKm:distance}).eligible,false);
 assert.equal(evaluateMatch({...property,locationId:'city:missing'},request,{locationDistanceKm:1}).eligible,false);
});
