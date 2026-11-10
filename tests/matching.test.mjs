import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {MATCH_WEIGHTS,prepareSearch,evaluateMatch,valueForMoney,searchSpecificity} from '../dist/matching.js';

const home=(extra={})=>({ownerId:'seller',locationId:'city:Debrecen',city:'Debrecen',type:'Lakás',price:80,area:60,rooms:3,...extra});
const wanted=(extra={})=>({ownerId:'buyer',locationIds:['city:Debrecen'],city:'Debrecen',type:'Lakás',...extra});

test('every exact match receives 100 regardless of price margin or optional amenities',()=>{
  for(const p of [home(),home({price:100}),home({balcony:true,elevator:true}),home({price:60})]){
    const result=evaluateMatch(p,wanted({maxPrice:100}));
    assert.deepEqual({...result,matchDetails:undefined},{eligible:true,isExact:true,score:100,reasons:['Megfelelő elhelyezkedés','A megadott árkereten belül','Megfelelő alapterület és szobaszám'],matchDetails:undefined});
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

test('numeric deviation grows continuously, respects inclusive boundaries and remains below 100 when tiny',()=>{
  const q=wanted({maxPrice:100});
  assert.deepEqual([100,110,120,150,200].map(price=>evaluateMatch(home({price}),q).score),[100,90,80,50,0]);
  assert.equal(evaluateMatch(home({price:100.00001}),q).score,99);
  assert.equal(evaluateMatch(home({rooms:2}),wanted({minRooms:3})).score,67);
  assert.equal(evaluateMatch(home({area:40}),wanted({minArea:50})).score,80);
  assert.equal(evaluateMatch(home({rooms:2.5}),wanted({minRooms:4})).score,63);
});

test('fractions of a million use the same relative price deviation as HUF values',()=>{
  assert.equal(evaluateMatch(home({price:.6}),wanted({maxPrice:.5})).score,80);
  assert.equal(evaluateMatch(home({price:600000}),wanted({maxPrice:500000})).score,80);
  assert.equal(evaluateMatch(home({price:.6}),wanted({maxPrice:0})).score,0);
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
  assert.deepEqual(['Felújítandó','Átlagos','Jó','Új/felújított'].map(condition=>evaluateMatch(home({condition}),q).score),[33,67,100,100]);
  assert.equal(evaluateMatch(home({condition:'Felújított'}),q).score,100);
  assert.equal(evaluateMatch(home(),q).score,0);
  assert.equal(evaluateMatch(home({condition:'Jó'}),wanted({conditions:['Átlagos']})).score,100);
});

test('floor loss uses the nearest allowed floor, supports basement and 11-or-higher and penalizes unknown floors',()=>{
  const q=wanted({floors:[1,5]});
  assert.equal(evaluateMatch(home({floor:4}),q).score,80);
  assert.equal(evaluateMatch(home({floor:3}),q).score,60);
  assert.equal(evaluateMatch(home({floor:-1}),wanted({floors:[0]})).score,80);
  assert.equal(evaluateMatch(home({floor:27}),wanted({floors:[11]})).score,100);
  assert.equal(evaluateMatch(home({floor:null}),q).score,0);
});

test('known category alternatives are OR and missing selected seller details are partial rather than silently exact',()=>{
  const q=wanted({buildings:['Tégla','Panel'],heatingTypes:['Gázkazán','Hőszivattyú'],constructionAges:['10 évnél fiatalabb'],ceilingHeight:'3 m alatti',views:['Kertre néző']});
  const p=home({building:'panel',heatingType:'gázkazán',constructionAge:'10 évnél fiatalabb',ceilingHeight:'3 m alatti',view:'kertre néző'});
  assert.equal(evaluateMatch(p,q).score,100);
  assert.equal(evaluateMatch(home(),q).isExact,false);
  assert.equal(evaluateMatch(home({constructionAge:'10–30 év közötti'}),wanted({constructionAges:['10 évnél fiatalabb']})).score,75);
});

test('houses ignore old floor, balcony and lift restrictions and full room composition remains authoritative',()=>{
  assert.equal(evaluateMatch(home({type:'Ház'}),wanted({type:'Ház',floors:[11],balcony:true,elevator:true})).score,100);
  assert.equal(evaluateMatch(home({rooms:99,wholeRooms:2,halfRooms:1}),wanted({minRooms:3})).isExact,false);
});

test('remaining minimum price, maximum rooms/area and view conditions still participate',()=>{
  assert.equal(evaluateMatch(home({price:40}),wanted({minPrice:50})).score,80);
  assert.equal(evaluateMatch(home({area:90}),wanted({maxArea:60})).score,50);
  assert.equal(evaluateMatch(home({rooms:6}),wanted({maxRooms:3})).score,0);
  assert.equal(evaluateMatch(home({view:'Utcai'}),wanted({views:['Kertre néző']})).score,0);
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
    const p=home(item.property),s=wanted(item.search),result=evaluateMatch(p,s);
    if('eligible' in item)assert.equal(result.eligible,item.eligible,item.name);
    if('score' in item){assert.equal(result.score,item.score,item.name);assert.equal(result.isExact,item.score===100,item.name);}
    if('specificity' in item)assert.equal(searchSpecificity(s),item.specificity,item.name);
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

test('explanations respect bounds, aliases, 11+ floors, unknown values and applicable criteria',()=>{
  let result=evaluateMatch(home({price:80.5,rooms:3.5,area:60}),wanted({minPrice:60,maxPrice:100,minRooms:2.5,maxRooms:4,minArea:50,maxArea:70}));
  assert.equal(result.matchDetails.find(item=>item.key==='rooms').expected,'2,5–4 szoba');
  assert.equal(result.matchDetails.find(item=>item.key==='price').actual,'80,5 M Ft');
  result=evaluateMatch(home({floor:27,condition:'Felújított'}),wanted({floors:[11],conditions:['Jó']}));
  assert.equal(result.matchDetails.find(item=>item.key==='floor').expected,'11. emelet vagy afölötti');
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
