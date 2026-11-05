import test from 'node:test';
import assert from 'node:assert/strict';
import {createModel,isCompatible,STORAGE_KEY} from '../dist/model.js';
const store=()=>{const values=new Map();return{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)}};
const setup=()=>createModel(store(),()=>new Date('2026-10-31T12:00:00Z').toISOString());

test('feed respects every explicit search limit and excludes own or previously judged properties',()=>{
 const m=setup(),s=m.getState(),q=s.searches.find(q=>q.id===s.active.id);
 assert.equal(m.feed()[0].id,'p1');
 for(const p of m.feed())assert.equal(isCompatible(p,q),true);
 assert.equal(m.feed().some(p=>p.id.startsWith('incompatible')||p.ownerId==='me'),false);
 const first=m.feed()[0];m.decide(first,false);assert.equal(m.feed().some(p=>p.id===first.id),false);
 assert.throws(()=>m.decide(first,true),/már döntöttél/);
});
test('buyer like is free; contacts appear only after a reciprocal like',()=>{
 const m=setup();const card=m.feed()[0];assert.equal('email'in card,false);assert.equal('phone'in card,false);
 const before=m.getState().credits;const result=m.decide(card,true);
 assert.equal(result.charged,0);assert.equal(m.getState().credits,before);
 assert.ok(result.match.partner.email);assert.equal(m.matches().length,4);
 const noReciprocal=m.feed().find(p=>!p.likedYou);assert.equal(m.decide(noReciprocal,true).match,null);
});
test('seller is charged exactly once for a compatible like and passing is free',()=>{
 const m=setup();m.activate('property','own-p1');const first=m.feed()[0];assert.ok(first);
 const before=m.getState().credits;assert.equal(m.decide(first,true).charged,2);assert.equal(m.getState().credits,before-2);
 assert.throws(()=>m.decide(first,true),/már döntöttél/);assert.equal(m.getState().credits,before-2);
 const next=m.feed()[0];m.decide(next,false);assert.equal(m.getState().credits,before-2);
 assert.equal(m.getState().ledger.filter(l=>l.type==='seller_like').length,1);
});
test('insufficient balance leaves decisions and ledger untouched',()=>{
 const storage=store();const m=createModel(storage);m.activate('property','own-p1');m.buyDemoCredits(1);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.credits=1;storage.setItem(STORAGE_KEY,JSON.stringify(raw));const reloaded=createModel(storage);
 const before=reloaded.getState();assert.throws(()=>reloaded.decide(reloaded.feed()[0],true),/elegendő/);assert.deepEqual(reloaded.getState(),before);
});
test('judgements persist across reloads, returned objects cannot mutate state',()=>{
 const storage=store();const m=createModel(storage);const first=m.feed()[0];m.decide(first,false);
 const again=createModel(storage);assert.equal(again.feed().some(p=>p.id===first.id),false);
 const state=again.getState();state.credits=999;state.searches[0].title='Tampered';assert.notEqual(again.getState().credits,999);assert.notEqual(again.getState().searches[0].title,'Tampered');
});
test('both profile types can be created, validated, activated, and archived without losing matches',()=>{
 const m=setup();assert.throws(()=>m.saveEntity('search',{title:'Bad',locationIds:['district:Budapest:11'],minPrice:80,maxPrice:50}),/minimum/);
 const q=m.saveEntity('search',{title:'Új keresésem',locationIds:['district:Budapest:11'],minPrice:55,maxPrice:80,minArea:50,maxArea:70,minRooms:2,maxRooms:3});m.activate('search',q.id);assert.ok(m.feed().length);
 m.deleteEntity('search',q.id);assert.notEqual(m.getState().active.id,q.id);assert.equal(m.matches().length,3);
 assert.throws(()=>m.activate('search',q.id),/aktiválható/);
 assert.throws(()=>m.activate('property','p1'),/aktiválható/);
});
test('messages require a reciprocal match and accept literal text safely',()=>{
 const m=setup();assert.throws(()=>m.sendMessage('fake','hello'),/kölcsönös/);assert.throws(()=>m.sendMessage('m1','  '),/1–4000/);
 m.sendMessage('m1','<script>alert(1)</script>');assert.equal(m.matches().find(m=>m.id==='m1').messages.at(-1).text,'<script>alert(1)</script>');
});
test('compatibility handles required balcony/elevator and exact district/type/size/budget',()=>{
 const p={ownerId:'a',city:'Budapest',district:'XI.',type:'Lakás',price:60,area:60,rooms:2,balcony:false,elevator:true};
 const s={ownerId:'b',city:'Budapest',districts:['XI.'],type:'Lakás',minPrice:55,maxPrice:70,minArea:50,maxArea:75,minRooms:2,maxRooms:3};
 assert.ok(isCompatible(p,s));assert.equal(isCompatible(p,{...s,balcony:true}),false);assert.equal(isCompatible(p,{...s,districts:['XIII.']}),false);assert.equal(isCompatible(p,{...s,minRooms:3}),false);assert.equal(isCompatible(p,{...s,maxPrice:59}),false);assert.equal(isCompatible(p,{...s,type:'Ház'}),false);
});
test('storage failure does not commit mutation',()=>{const m=createModel({getItem:()=>null,setItem:()=>{throw new Error('quota')}});assert.throws(()=>m.buyDemoCredits(20),/tárhely/);assert.equal(m.getState().credits,24)});

test('several towns and Budapest districts form an OR filter, with Budapest city covering every district',()=>{
 const property={ownerId:'seller',type:'Lakás',price:60,area:60,rooms:2};
 const search={ownerId:'buyer',type:'Lakás',locationIds:['city:Debrecen','city:Hajdúszoboszló','city:Hajdúsámson']};
 for(const city of ['Debrecen','Hajdúszoboszló','Hajdúsámson'])assert.ok(isCompatible({...property,locationId:`city:${city}`},search));
 assert.equal(isCompatible({...property,locationId:'city:Szeged'},search),false);
 const mixed={...search,locationIds:['district:Budapest:5','district:Budapest:9','city:Solymár','city:Pilisvörösvár']};
 for(const id of mixed.locationIds)assert.ok(isCompatible({...property,locationId:id},mixed));
 assert.equal(isCompatible({...property,locationId:'district:Budapest:11'},mixed),false);
 assert.ok(isCompatible({...property,locationId:'district:Budapest:11'},{...mixed,locationIds:['city:Budapest']}));
 assert.equal(isCompatible({...property,locationId:'city:Budapest'},{...mixed,locationIds:['district:Budapest:5']}),false);
});

test('unselected or unknown locations are rejected and canonical selections override stale legacy fields',()=>{
 const m=setup();const data={title:'Új keresés',maxPrice:80};
 for(const locationIds of [[],['city:Nemlétező'],['city:Debrecen','city:Nemlétező']])assert.throws(()=>m.saveEntity('search',{...data,locationIds}),/találati listából/);
 assert.throws(()=>m.saveEntity('search',data),/találati listából/);
 assert.throws(()=>m.saveEntity('property',{title:'Ismeretlen ház',locationId:'city:Nemlétező',price:50,area:70,rooms:3}),/találati listából/);
 const q=m.saveEntity('search',{...data,locationIds:['city:Debrecen','city:Solymár'],city:'Szeged'});
 assert.deepEqual(q.locations.map(location=>location.city),['Debrecen','Solymár']);assert.equal(q.city,'Debrecen');
 const p=m.saveEntity('property',{title:'Debreceni lakás',locationId:'city:Debrecen',city:'Budapest',district:'XI.',price:60,area:60,rooms:2});
 assert.equal(p.city,'Debrecen');assert.equal(p.district,'');
});

test('blank optional limits remain null after saving and reloading, with no artificial upper bound or invalid score',()=>{
 const storage=store();const m=createModel(storage);
 const q=m.saveEntity('search',{title:'Korlátok nélküli keresés',locationIds:['city:Budapest'],minPrice:'',maxPrice:200,minArea:1,maxArea:'',minRooms:1,maxRooms:null});
 m.activate('search',q.id);
 const again=createModel(storage);const saved=again.getState().searches.find(search=>search.id===q.id);
 assert.deepEqual([saved.minPrice,saved.maxArea,saved.maxRooms],[null,null,null]);
 assert.ok(again.feed().length);assert.ok(again.feed().every(card=>Number.isFinite(card.score)));
 assert.ok(isCompatible({ownerId:'seller',locationId:'district:Budapest:5',type:'Lakás',price:0.01,area:2000001,rooms:1000001},saved));
});

test('legacy v3 records migrate in memory without losing decisions, matches, credits or IDs',()=>{
 const storage=store();const initial=createModel(storage);const first=initial.feed()[0];initial.decide(first,false);
 const old=JSON.parse(storage.getItem(STORAGE_KEY));
 for(const property of old.properties){delete property.locationId;delete property.location;delete property.lotArea;}
 for(const search of old.searches){delete search.locationIds;delete search.locations;}
 storage.setItem(STORAGE_KEY,JSON.stringify(old));
 const migrated=createModel(storage);const state=migrated.getState();
 assert.equal(state.properties[0].id,'own-p1');assert.equal(state.properties[0].locationId,'district:Budapest:11');
 assert.deepEqual(state.searches[0].locationIds,['district:Budapest:13','district:Budapest:11','district:Budapest:2']);
 assert.equal(migrated.feed().some(card=>card.id===first.id),false);assert.equal(migrated.matches().length,3);assert.equal(state.credits,24);
 assert.equal(storage.getItem(STORAGE_KEY),JSON.stringify(old),'migration does not overwrite a saved store until a successful edit');
});

test('house plot area survives save and reload and is cleared when changing to an apartment',()=>{
 const storage=store();const m=createModel(storage);
 const p=m.saveEntity('property',{title:'Családi ház Solymáron',locationId:'city:Solymár',type:'Ház',price:95,area:110,rooms:4,lotArea:'750.5'});
 assert.equal(p.location.city,'Solymár');assert.equal(p.lotArea,750.5);
 const again=createModel(storage);assert.equal(again.getState().properties.find(property=>property.id===p.id).lotArea,750.5);
 assert.throws(()=>again.saveEntity('property',{...p,lotArea:0},p.id),/telekméret/);
 assert.throws(()=>again.saveEntity('property',{...p,lotArea:'hibás'},p.id),/telekméret/);
 const changed=again.saveEntity('property',{...p,type:'Lakás'},p.id);assert.equal(changed.lotArea,null);
});

test('new optional property data and multiselect filters persist without turning unknown details into defaults',()=>{
 const storage=store(),m=createModel(storage);
 const p=m.saveEntity('property',{title:'Részletes tesztlakás',locationId:'district:Budapest:13',type:'Lakás',price:78,area:68,rooms:3,condition:'Jó',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m feletti',floor:0,heatingType:'Hőszivattyú',insulated:false,energyRating:'A+',airConditioning:true,solarPanels:null,parkingType:'Garázs'});
 const q=m.saveEntity('search',{title:'Részletes keresési igény',locationIds:['district:Budapest:13'],conditions:['Jó','Átlagos'],buildings:['Panel','Tégla'],constructionAges:['10–30 év közötti'],views:['Kertre néző','Panorámás'],ceilingHeight:'3 m feletti',floors:[0,11]});
 const again=createModel(storage),saved=again.getState().properties.find(item=>item.id===p.id),savedSearch=again.getState().searches.find(item=>item.id===q.id);
 for(const field of ['condition','building','constructionAge','view','ceilingHeight','floor','heatingType','insulated','energyRating','airConditioning','solarPanels','parkingType'])assert.deepEqual(saved[field],p[field],field);
 assert.deepEqual(savedSearch.conditions,['Jó','Átlagos']);assert.deepEqual(savedSearch.floors,[0,11]);
 const blank=again.saveEntity('property',{title:'Opcionális mezők nélkül',locationId:'city:Debrecen',type:'Lakás',price:40,area:50,rooms:2});
 assert.deepEqual([blank.condition,blank.building,blank.floor,blank.insulated,blank.airConditioning,blank.solarPanels],['','',null,null,null,null]);
 const cleared=again.saveEntity('property',{...p,condition:'',building:'',constructionAge:'',view:'',ceilingHeight:'',floor:'',insulated:'',airConditioning:'',solarPanels:''},p.id);
 assert.deepEqual([cleared.floor,cleared.insulated,cleared.airConditioning,cleared.solarPanels],[null,null,null,null]);
});

test('new attributes constrain actual demo feeds, using OR within lists and rejecting missing seller data',()=>{
 const m=setup();
 const all=m.feed();assert.ok(all.length);
 const base=m.getState().searches.find(item=>item.id==='own-s1');
 m.saveEntity('search',{...base,conditions:['Új/felújított'],buildings:['Tégla','Panel'],floors:[3]},base.id);
 assert.ok(m.feed().length);assert.ok(m.feed().every(item=>item.condition==='Új/felújított'&&item.floor===3));
 m.saveEntity('search',{...base,views:['Panorámás']},base.id);assert.equal(m.feed().length,0);
 m.saveEntity('search',{...base,views:[],conditions:[],buildings:[],floors:[]},base.id);assert.equal(m.feed().length,all.length);
});

test('legacy custom condition and wall text survive reads and unrelated edits while new unknown labels fail',()=>{
 const storage=store(),m=createModel(storage);m.buyDemoCredits(20);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY)),own=raw.properties.find(item=>item.id==='own-p1');
 own.condition='Régi egyedi állapot';own.building='Régi egyedi falazat';
 storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 const again=createModel(storage),before=again.getState(),existing=before.properties.find(item=>item.id===own.id);
 assert.equal(existing.condition,own.condition);assert.equal(existing.building,own.building);
 again.saveEntity('property',{...existing,title:'Csak a név változott'},existing.id);
 assert.equal(again.getState().properties.find(item=>item.id===own.id).condition,own.condition);
 assert.equal(again.getState().credits,before.credits);assert.deepEqual(again.matches(),m.matches());
 assert.throws(()=>again.saveEntity('property',{...existing,condition:'Más ismeretlen'},existing.id),/Érvénytelen/);
 assert.throws(()=>again.saveEntity('search',{title:'Hibás új szűrő',locationIds:['city:Budapest'],floors:[12]}),/Érvénytelen/);
});
