import test from 'node:test';
import assert from 'node:assert/strict';
import {createModel,isCompatible,STORAGE_KEY} from '../dist/model.js';
import {locations, getLocation} from '../dist/locations.js';
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


test('city areas remain compact saved search choices and reload without resetting business data',()=>{
 const storage=store(),m=createModel(storage),before=m.getState();
 const selected=['area:Budapest','area:Debrecen','city:Szeged'];
 const q=m.saveEntity('search',{title:'Nagyvárosok környékén keresek',locationIds:selected,maxPrice:100});
 assert.deepEqual(q.locationIds,selected);assert.equal(q.locations[0].settlementCount,81);assert.equal(q.locations[1].settlementCount,13);
 assert.equal(q.locations.length,3);assert.match(q.locations[0].label,/\(81 település\)$/);
 m.activate('search',q.id);
 const again=createModel(storage),state=again.getState();
 assert.deepEqual(state.searches.find(value=>value.id===q.id).locationIds,selected);
 assert.deepEqual(state.active,{kind:'search',id:q.id});assert.equal(state.credits,before.credits);
 assert.deepEqual(state.ledger,before.ledger);assert.deepEqual(state.decisions,before.decisions);assert.equal(again.matches().length,m.matches().length);
 assert.equal(isCompatible({ownerId:'seller',type:'Lakás',locationId:'district:Budapest:23',price:60,area:60,rooms:3},q),true);
 assert.equal(isCompatible({ownerId:'seller',type:'Lakás',locationId:'city:Szeged',price:60,area:60,rooms:3},q),true);
 assert.equal(isCompatible({ownerId:'seller',type:'Lakás',locationId:'city:Szeged',price:101,area:60,rooms:3},q),false);
});

test('a region is one of at most fifty search selections and cannot be saved as a property',()=>{
 const m=setup(),towns=locations.filter(value=>value.kind==='city').slice(0,50).map(value=>value.id);
 const fifty=['area:Budapest',...towns.slice(0,49)];
 const q=m.saveEntity('search',{title:'Ötven kiválasztott hely',locationIds:fifty});assert.deepEqual(q.locationIds,fifty);
 assert.throws(()=>m.saveEntity('search',{title:'Túl sok hely',locationIds:[...fifty,towns[49]]}),/találati listából/);
 assert.throws(()=>m.saveEntity('property',{title:'Nem pontos hirdetési hely',locationId:'area:Budapest',city:'Budapest',district:'XIII.',price:80,area:60,rooms:3}),/találati listából/);
 assert.equal(getLocation('area:Budapest').settlementCount,81);
});

test('an invalid stored property region never falls back to its central town for matching',()=>{
 const storage=store(),m=createModel(storage);m.activate('search','own-s1');
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));const invalid=raw.properties.find(value=>value.id==='p1');invalid.locationId='area:Budapest';
 storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 const again=createModel(storage);assert.equal(again.feed().some(value=>value.id==='p1'),false);
 assert.equal(isCompatible({ownerId:'seller',type:'Lakás',locationId:'area:Budapest',city:'Budapest',price:60,area:60,rooms:3},{ownerId:'buyer',locationIds:['city:Budapest']}),false);
 assert.equal(isCompatible({ownerId:'seller',type:'Lakás',location:{id:'area:Budapest'},city:'Budapest',price:60,area:60,rooms:3},{ownerId:'buyer',locationIds:['city:Budapest']}),false);
});

test('explicit room composition survives save, reload and old-client total-only edits without changing weighted search matching',()=>{
 const storage=store(),m=createModel(storage);
 const p=m.saveEntity('property',{title:'Fél szobás otthon',locationId:'city:Debrecen',type:'Lakás',price:60,area:70,wholeRooms:2,halfRooms:3});
 assert.deepEqual([p.wholeRooms,p.halfRooms,p.rooms],[2,3,3.5]);
 const again=createModel(storage),loaded=again.getState().properties.find(item=>item.id===p.id);
 assert.deepEqual([loaded.wholeRooms,loaded.halfRooms,loaded.rooms],[2,3,3.5]);
 const unchanged=again.saveEntity('property',{rooms:3.5,title:'Csak a név módosul'},p.id);
 assert.deepEqual([unchanged.wholeRooms,unchanged.halfRooms],[2,3]);
 const changed=again.saveEntity('property',{rooms:4},p.id);assert.deepEqual([changed.wholeRooms,changed.halfRooms,changed.rooms],[4,0,4]);
 const countEdit=again.saveEntity('property',{wholeRooms:1,halfRooms:3},p.id);assert.deepEqual([countEdit.wholeRooms,countEdit.halfRooms,countEdit.rooms],[1,3,2.5]);
 const halfOnly=again.saveEntity('property',{halfRooms:1},p.id);assert.deepEqual([halfOnly.wholeRooms,halfOnly.halfRooms,halfOnly.rooms],[0,1,0.5],'a missing count counterpart means zero rather than the old stored count');
 const search={ownerId:'other',locationIds:['city:Debrecen'],minRooms:3.5,maxRooms:3.5};
 assert.equal(isCompatible(p,search),true);assert.equal(isCompatible({...p,rooms:100},search),true,'explicit composition is authoritative for compatibility');
 assert.equal(isCompatible(p,{...search,minRooms:4,maxRooms:null}),false);
});

test('old room and house data load unchanged without rewriting storage or unrelated account data',()=>{
 const storage=store(),m=createModel(storage);m.buyDemoCredits(1);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY)),old=raw.properties.find(item=>item.id==='own-p1');
 Object.assign(old,{type:'Ház',lotArea:null,floor:3,balcony:true,elevator:true,rooms:3.2});delete old.wholeRooms;delete old.halfRooms;
 storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 const again=createModel(storage),before=again.getState(),loaded=before.properties.find(item=>item.id===old.id);
 assert.deepEqual([loaded.rooms,loaded.wholeRooms,loaded.halfRooms,loaded.floor,loaded.balcony,loaded.elevator],[3.2,null,null,3,true,true]);
 assert.equal(storage.getItem(STORAGE_KEY),JSON.stringify(raw));
 assert.throws(()=>again.saveEntity('property',{title:'Új név változatlan telekkel'},old.id),/telekméret/);
 const updated=again.saveEntity('property',{lotArea:750},old.id);
 assert.deepEqual([updated.rooms,updated.wholeRooms,updated.halfRooms,updated.floor,updated.balcony,updated.elevator],[3.2,null,null,null,false,false]);
 const after=again.getState();assert.equal(after.credits,before.credits);assert.deepEqual(after.ledger,before.ledger);assert.deepEqual(after.decisions,before.decisions);assert.equal(again.matches().length,m.matches().length);
});

test('house saves require positive plot area and clear hidden property and search controls',()=>{
 const m=setup(),base={title:'Ház a város szélén',locationId:'city:Solymár',type:'Ház',price:90,area:120,wholeRooms:4,halfRooms:1};
 for(const lotArea of [undefined,null,'',0,-1,'hibás',true,10000001])assert.throws(()=>m.saveEntity('property',{...base,lotArea}),/telekméret/);
 const house=m.saveEntity('property',{...base,lotArea:500,floor:'invalid',balcony:true,elevator:true});
 assert.deepEqual([house.floor,house.balcony,house.elevator],[null,false,false]);
 const q=m.saveEntity('search',{title:'Családi házat keresünk',locationIds:['city:Solymár'],type:'Ház',floors:[3],balcony:true,elevator:true});
 assert.deepEqual([q.floors,q.balcony,q.elevator],[[],false,false]);
 assert.equal(isCompatible(house,{...q,ownerId:'other',floors:[3],balcony:true,elevator:true}),true,'hidden constraints from old house searches do not block matching');
});

test('heating and parking data persist while new invalid options or negative measurements leave state untouched',()=>{
 const storage=store(),m=createModel(storage),base={title:'Kényelmes lakás',locationId:'city:Debrecen',type:'Lakás',price:60,area:70,wholeRooms:2,halfRooms:1,heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',parkingTypes:['Garázs','Udvari beálló','Garázs']};
 const p=m.saveEntity('property',base),again=createModel(storage),loaded=again.getState().properties.find(item=>item.id===p.id);
 assert.deepEqual([loaded.heatingType,loaded.secondaryHeatingType,loaded.parkingTypes],['Hőszivattyú','Klíma',['Garázs','Udvari beálló']]);
 const oldClient=again.saveEntity('property',{parkingType:loaded.parkingType},p.id);assert.deepEqual(oldClient.parkingTypes,loaded.parkingTypes);
 const changed=again.saveEntity('property',{parkingType:'Utcai parkolás'},p.id);assert.deepEqual(changed.parkingTypes,['Utcai parkolás']);
 const before=again.getState();
 for(const changes of [{price:-1},{area:-1},{wholeRooms:-1},{halfRooms:-1},{rooms:-1,wholeRooms:null,halfRooms:null},{heatingType:'Új kitalált fűtés'},{secondaryHeatingType:'Más'},{parkingTypes:['Más']}])assert.throws(()=>again.saveEntity('property',{...base,...changes}));
 for(const key of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])assert.throws(()=>again.saveEntity('search',{title:'Hibás keresés',locationIds:['city:Debrecen'],[key]:-1}));
 assert.deepEqual(again.getState(),before);
 const q=again.saveEntity('search',{title:'Fűtésre szűrt keresés',locationIds:['city:Debrecen'],heatingTypes:['Hőszivattyú','Klíma','Hőszivattyú']});
 assert.deepEqual(q.heatingTypes,['Hőszivattyú','Klíma']);
 assert.equal(isCompatible(loaded,{...q,ownerId:'other'}),true);
 assert.equal(isCompatible({...loaded,heatingType:'Nincs fűtés'},{...q,ownerId:'other'}),false);
});

test('legacy account declarations migrate in memory without resetting business data and owner labels cannot be forged',()=>{
 const storage=store(),m=createModel(storage);m.buyDemoCredits(1);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));for(const user of raw.users)delete user.accountType;
 raw.properties.find(p=>p.id==='p1').ownerAccountType='agent';
 storage.setItem(STORAGE_KEY,JSON.stringify(raw));const oldSaved=storage.getItem(STORAGE_KEY),again=createModel(storage),state=again.getState();
 assert.equal(state.user.accountType,'private');assert.equal(state.likeCost,0);assert.deepEqual(state.reportedOwnerIds,[]);
 assert.equal(again.feed().find(p=>p.id==='p1').ownerAccountType,'private');
 assert.equal(storage.getItem(STORAGE_KEY),oldSaved,'reading must not rewrite old saved records');
 assert.equal(state.credits,raw.credits);assert.deepEqual(state.ledger,raw.ledger);assert.equal(state.decisions.length,raw.decisions.filter(d=>d.actorKind==='search'&&d.actorId==='own-s1').length);
 assert.equal(again.matches().length,m.matches().length);
 const saved=again.saveEntity('property',{title:'Magánszemély hirdetése',locationId:'city:Debrecen',price:60,area:60,rooms:2,ownerAccountType:'agent'});
 assert.equal(saved.ownerAccountType,'private');assert.equal(again.getState().properties.find(p=>p.id===saved.id).ownerAccountType,'private');
});

test('agent search likes cost one credit once, passes are free and insufficient balance commits nothing',()=>{
 const storage=store(),m=createModel(storage);m.buyDemoCredits(1);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.users.find(user=>user.id==='me').accountType='agent';raw.credits=0;
 storage.setItem(STORAGE_KEY,JSON.stringify(raw));let again=createModel(storage),first=again.feed()[0],before=again.getState();
 assert.equal(before.likeCost,1);assert.throws(()=>again.decide(first,true),/1 kredit/);assert.deepEqual(again.getState(),before);
 assert.equal(again.decide(first,false).charged,0);assert.equal(again.getState().credits,0);
 again.buyDemoCredits(1);const next=again.feed()[0],balance=again.getState().credits,result=again.decide(next,true);
 assert.equal(result.charged,1);assert.equal(again.getState().credits,balance-1);
 const entry=again.getState().ledger[0];assert.equal(entry.amount,-1);assert.equal(entry.type,'agent_search_like');assert.match(entry.description,/Közvetítői keresés/);
 const after=again.getState();assert.throws(()=>again.decide(next,true),/már döntöttél/);assert.deepEqual(again.getState(),after);
 again=createModel(storage);assert.equal(again.getState().credits,0);assert.equal(again.getState().user.accountType,'agent');
 again.activate('property','own-p1');assert.equal(again.getState().likeCost,2);again.buyDemoCredits(2);assert.equal(again.decide(again.feed()[0],true).charged,2);
});

test('owner declarations are available consistently in property and search feeds, decisions and matches',()=>{
 const m=setup();assert.equal(m.getState().user.accountType,'private');
 assert.equal(m.feed().find(p=>p.id==='p2').ownerAccountType,'agent');
 const privateCard=m.feed().find(p=>p.id==='p1');assert.equal(privateCard.ownerAccountType,'private');assert.equal('email' in privateCard,false);assert.equal('phone' in privateCard,false);
 m.decide(privateCard,false);const history=m.getState().decisions.find(d=>d.propertyId==='p1');assert.equal(history.property.ownerAccountType,'private');assert.equal(history.search.ownerAccountType,'private');
 const match=m.matches().find(match=>match.id==='m1');assert.equal(match.partner.accountType,'agent');assert.equal(match.property.ownerAccountType,'agent');assert.equal(match.search.ownerAccountType,'private');
 m.activate('property','own-p1');assert.equal(m.feed().find(s=>s.id==='s2').ownerAccountType,'agent');
 const before=m.getState().user;m.updateProfile({accountType:'agent'});assert.equal(m.getState().user.accountType,before.accountType,'profile updates cannot turn a declaration into a billing switch');
});

test('reports retain private UTC timestamps while deduplicating per source entity and selected reason',()=>{
 const storage=store(),at='2026-11-07T09:10:11.000Z',m=createModel(storage,()=>at),before=m.getState(),matches=m.matches();
 const first=m.reportAccount('property','p1','suspected_agent');assert.equal(first.reported,true);assert.equal(first.alreadyReported,false);assert.equal(first.reportedOwnerId,'u1');assert.equal('createdAt' in first,false);
 assert.deepEqual(m.getState().reportedOwnerIds,['u1']);assert.equal('reports' in m.getState(),false);
 const repeat=m.reportAccount('property','p1');assert.equal(repeat.id,first.id);assert.equal(repeat.alreadyReported,true);
 const otherEntity=m.reportAccount('search','s1','suspected_agent');assert.notEqual(otherEntity.id,first.id);assert.equal(otherEntity.alreadyReported,false);
 const otherReason=m.reportAccount('property','p1','misleading_content');assert.notEqual(otherReason.id,first.id);assert.equal(otherReason.alreadyReported,false);
 const stored=JSON.parse(storage.getItem(STORAGE_KEY));assert.equal(stored.reports.length,3);assert.deepEqual(stored.reports[0],{id:first.id,reporterId:'me',reportedUserId:'u1',entityKind:'property',entityId:'p1',reason:'suspected_agent',createdAt:at});
 assert.deepEqual(m.getState().reportedEntities,[{entityKind:'property',entityId:'p1',reason:'suspected_agent'},{entityKind:'search',entityId:'s1',reason:'suspected_agent'},{entityKind:'property',entityId:'p1',reason:'misleading_content'}]);
 const after=m.getState();for(const field of ['credits','ledger','decisions','properties','searches','active','user'])assert.deepEqual(after[field],before[field]);assert.deepEqual(m.matches(),matches);
 const again=createModel(storage,()=>new Date().toISOString());assert.deepEqual(again.getState().reportedOwnerIds,['u1']);assert.equal(again.reportAccount('property','p1').alreadyReported,true);assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).reports[0].createdAt,at);
});

test('reporting rejects invalid sources and a disguised-agent reason for declared agents atomically',()=>{
 const m=setup(),before=m.getState();
 for(const [kind,id] of [['user','u1'],['property','unknown'],['property','own-p1'],['property','p2'],['search','s2']])assert.throws(()=>m.reportAccount(kind,id));
 assert.deepEqual(m.getState(),before);
 const storage=store(),initial=createModel(storage);initial.buyDemoCredits(1);const raw=JSON.parse(storage.getItem(STORAGE_KEY));
 raw.properties.find(p=>p.id==='p1').archived=true;raw.reports=[{id:'other-report',reporterId:'u3',reportedUserId:'u1',reason:'suspected_agent',createdAt:'2026-11-07T00:00:00Z'}];
 storage.setItem(STORAGE_KEY,JSON.stringify(raw));const again=createModel(storage);assert.deepEqual(again.getState().reportedOwnerIds,[],'other reporters are private');
 assert.throws(()=>again.reportAccount('property','p1'),/nem érhető/);assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).reports.length,1);
});

test('agents cannot discover or decide about another agent on either side even with forged entity labels',()=>{
 const storage=store(),initial=createModel(storage);initial.buyDemoCredits(1);const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.users.find(user=>user.id==='me').accountType='agent';
 raw.properties.find(item=>item.id==='p2').ownerAccountType='private';raw.searches.find(item=>item.id==='s2').ownerAccountType='private';storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 const m=createModel(storage);assert.ok(m.feed().length);assert.ok(m.feed().every(item=>item.ownerAccountType==='private'));
 const before=m.getState();for(const liked of [true,false])assert.throws(()=>m.decide({pair:{propertyId:'p2',searchId:'own-s1'}},liked),/nem érhető/);assert.deepEqual(m.getState(),before);
 m.activate('property','own-p1');assert.ok(m.feed().length);assert.ok(m.feed().every(item=>item.ownerAccountType==='private'));for(const liked of [true,false])assert.throws(()=>m.decide({pair:{propertyId:'own-p1',searchId:'s2'}},liked),/nem érhető/);
 assert.equal(m.matches().some(match=>match.partner.accountType==='agent'),true,'Historical conversations remain available');
});

test('general report reasons apply to declared agents and legacy reports migrate without rewriting stored data',()=>{
 const storage=store(),m=createModel(storage),first=m.reportAccount('property','p2','misleading_content');assert.equal(first.alreadyReported,false);assert.equal(m.reportAccount('property','p2','misleading_content').alreadyReported,true);
 assert.equal(m.reportAccount('search','s2','other_violation').alreadyReported,false);const before=m.getState();
 for(const reason of ['',false,'unknown','suspected_agent'])assert.throws(()=>m.reportAccount('property','p2',reason));assert.deepEqual(m.getState(),before);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.reports.push({id:'legacy',reporterId:'me',reportedUserId:'u1',entityKind:'property',entityId:'p1',createdAt:'2026-11-01T00:00:00Z'});storage.setItem(STORAGE_KEY,JSON.stringify(raw));const original=storage.getItem(STORAGE_KEY),again=createModel(storage);
 assert.equal(storage.getItem(STORAGE_KEY),original,'Reading does not rewrite older report rows');assert.ok(again.getState().reportedEntities.some(item=>item.entityId==='p1'&&item.reason==='suspected_agent'));
 assert.equal(again.reportAccount('property','p1').id,'legacy');assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).reports.find(report=>report.id==='legacy').createdAt,'2026-11-01T00:00:00Z');
});

test('incoming likes include only the active entity, expose no contacts, and retain handled and incompatible statuses',()=>{
 const storage=store(),initial=createModel(storage);initial.buyDemoCredits(1);const raw=JSON.parse(storage.getItem(STORAGE_KEY));
 raw.properties.find(item=>item.id==='p1').address='Private exact street 42';
 for(const decision of raw.decisions)if(decision.actorKind==='property')decision.createdAt=decision.propertyId==='p1'?'2026-11-07T00:00:00Z':'2026-11-01T00:00:00Z';
 raw.decisions.push({id:'newest-incoming',actorKind:'property',actorId:'p3',propertyId:'p3',searchId:'own-s1',liked:true,createdAt:'2026-11-08T00:00:00Z'});
 raw.decisions.push({id:'own-pass',actorKind:'search',actorId:'own-s1',propertyId:'p3',searchId:'own-s1',liked:false,createdAt:'2026-11-08T00:00:01Z'});
 raw.decisions.push({id:'different-active',actorKind:'property',actorId:'p4',propertyId:'p4',searchId:'own-s2',liked:true,createdAt:'2026-11-09T00:00:00Z'});
 raw.searches.find(item=>item.id==='own-s1').maxPrice=70;storage.setItem(STORAGE_KEY,JSON.stringify(raw));const m=createModel(storage),before=storage.getItem(STORAGE_KEY),page=m.incomingLikes({limit:2});
 assert.deepEqual(page.active,{kind:'search',id:'own-s1'});assert.equal(page.total,5);assert.equal(page.offset,0);assert.equal(page.limit,2);assert.equal(page.hasMore,true);assert.equal(page.likeCost,0);assert.equal(page.items[0].id,'p3');assert.equal(page.items[0].myDecision,'passed');assert.equal(page.items[0].compatible,false);
 assert.equal(page.items[1].id,'p1');assert.equal(page.items[1].address,'');assert.equal(page.items[1].myDecision,null);assert.equal(page.items[1].likedYou,true);assert.deepEqual(page.items[1].pair,{propertyId:'p1',searchId:'own-s1'});
 for(const item of page.items){assert.equal('phone' in item,false);assert.equal('email' in item,false);assert.equal('partner' in item,false);assert.equal('contact' in item,false);}
 const rest=m.incomingLikes({offset:2,limit:100});assert.equal(rest.hasMore,false);assert.equal(rest.items.length,3);assert.ok(rest.items.every(item=>item.myDecision==='liked'&&item.matchId));assert.equal(storage.getItem(STORAGE_KEY),before,'Viewing incoming likes is free and read-only');
 m.activate('property','own-p1');const seller=m.incomingLikes();assert.deepEqual(seller.active,{kind:'property',id:'own-p1'});assert.equal(seller.items.length,1);assert.equal(seller.items[0].id,'s1');assert.equal(seller.items[0].kind,'search');assert.equal(seller.likeCost,2);
 for(const options of [{offset:-1},{limit:101},{offset:1.5}])assert.throws(()=>m.incomingLikes(options),/lapozási/);
});

test('incoming pagination is stable, excludes invalid counterparties and isolates all agent interactions',()=>{
 const storage=store(),initial=createModel(storage);initial.buyDemoCredits(1);const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.users.find(user=>user.id==='me').accountType='agent';
 raw.decisions=raw.decisions.filter(decision=>decision.id!=='seed-prelike');
 for(const [index,id] of ['p1','p2','p3','p4'].entries())raw.decisions.push({id:'same-time-'+index,actorKind:'property',actorId:id,propertyId:id,searchId:'own-s1',liked:true,createdAt:'2026-11-09T12:00:00Z'});
 raw.properties.find(item=>item.id==='p4').archived=true;storage.setItem(STORAGE_KEY,JSON.stringify(raw));const m=createModel(storage);const first=m.incomingLikes({limit:1}),next=m.incomingLikes({offset:1,limit:1});assert.equal(first.items[0].id,'p3');assert.equal(next.items[0].id,'p1');assert.ok(m.incomingLikes().items.every(item=>item.ownerAccountType==='private'));assert.equal(first.likeCost,1);
 const noActive=JSON.parse(storage.getItem(STORAGE_KEY));noActive.active={kind:'search',id:null};storage.setItem(STORAGE_KEY,JSON.stringify(noActive));assert.deepEqual(createModel(storage).incomingLikes(),{active:null,items:[],total:0,offset:0,limit:50,hasMore:false,likeCost:0});
});

const REFUND_START='2026-11-01T12:00:00.000Z';
const REFUND_DEADLINE='2026-11-15T12:00:00.000Z';
function refundFixture({agent=false}={}) {
 const storage=store();let clock=REFUND_START;
 let m=createModel(storage,()=>clock);
 m.buyDemoCredits(1);
 if(agent){const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.users.find(user=>user.id==='me').accountType='agent';storage.setItem(STORAGE_KEY,JSON.stringify(raw));m=createModel(storage,()=>clock);}
 else m.activate('property','own-p1');
 const item=m.feed().find(item=>!item.likedYou);
 assert.ok(item,'A compatible unanswered candidate is available');
 const balance=m.getState().credits,result=m.decide(item,true);
 assert.equal(result.charged,agent?1:2);assert.equal(result.match,null);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));
 const decision=raw.decisions.find(d=>d.propertyId===item.pair.propertyId&&d.searchId===item.pair.searchId&&d.actorKind===(agent?'search':'property'));
 return {storage,m,item,decision,balance,setClock:value=>{clock=value;},reload:()=>createModel(storage,()=>clock)};
}

test('paid unanswered likes refund exactly at fourteen days once, persisting a private notification and ledger reference',()=>{
 const t=refundFixture();t.setClock('2026-11-15T11:59:59.999Z');
 assert.equal(t.m.getState().credits,t.balance-2);assert.equal(t.m.notifications().total,0);
 t.setClock(REFUND_DEADLINE);const refunded=t.m.getState();
 assert.equal(refunded.credits,t.balance);assert.equal(refunded.unreadNotificationCount,1);
 const entry=refunded.ledger.find(entry=>entry.type==='like_refund');assert.equal(entry.amount,2);assert.equal(entry.refundedDecisionId,t.decision.id);
 const page=t.m.notifications();assert.equal(page.total,1);assert.equal(page.unreadCount,1);assert.equal(page.hasMore,false);
 assert.deepEqual(Object.keys(page.items[0]).sort(),['amount','createdAt','decisionId','id','kind','readAt','text']);
 assert.equal(page.items[0].kind,'like_refund');assert.equal(page.items[0].amount,2);assert.match(page.items[0].text,/14 napon/);assert.equal(page.items[0].readAt,null);
 assert.equal(t.m.getState().decisions.find(d=>d.id===t.decision.id).refundedAt,REFUND_DEADLINE);
 const again=t.reload();for(let i=0;i<3;i++){assert.equal(again.getState().credits,t.balance);assert.equal(again.notifications().total,1);}
 assert.equal(again.getState().ledger.filter(entry=>entry.type==='like_refund').length,1);
});

test('any opposite decision at or before the deadline blocks a refund, including pre-existing passes',()=>{
 for(const liked of [false,true])for(const createdAt of ['2026-10-31T12:00:00.000Z',REFUND_DEADLINE]){
  const t=refundFixture(),raw=JSON.parse(t.storage.getItem(STORAGE_KEY));
  raw.decisions.push({id:'opposite',actorKind:'search',actorId:t.item.pair.searchId,...t.item.pair,liked,charged:0,createdAt});
  t.storage.setItem(STORAGE_KEY,JSON.stringify(raw));t.setClock('2026-11-20T12:00:00.000Z');
  const m=t.reload();assert.equal(m.getState().credits,t.balance-2);assert.equal(m.notifications().total,0);
 }
});

test('a reaction after fourteen days keeps the due refund and a later mutual match remains usable',()=>{
 const t=refundFixture(),raw=JSON.parse(t.storage.getItem(STORAGE_KEY));
 raw.decisions.push({id:'late',actorKind:'search',actorId:t.item.pair.searchId,...t.item.pair,liked:true,charged:0,createdAt:'2026-11-15T12:00:00.001Z'});
 raw.matches.push({id:'late-match',...t.item.pair,createdAt:'2026-11-15T12:00:00.001Z',unread:0,messages:[]});
 t.storage.setItem(STORAGE_KEY,JSON.stringify(raw));t.setClock('2026-11-16T12:00:00.000Z');
 const m=t.reload();assert.equal(m.getState().credits,t.balance);assert.equal(m.notifications().total,1);assert.ok(m.matches().find(item=>item.id==='late-match').partner.email);
});

test('agent search refunds the charged one credit; free, passed, foreign and legacy uncharged decisions never create money',()=>{
 const t=refundFixture({agent:true});t.setClock(REFUND_DEADLINE);
 assert.equal(t.m.getState().credits,t.balance);assert.equal(t.m.notifications().items[0].amount,1);
 const storage=store();let clock=REFUND_START;const m=createModel(storage,()=>clock);m.decide(m.feed().find(item=>!item.likedYou),true);
 m.activate('property','own-p1');m.decide(m.feed()[0],false);clock='2026-12-01T12:00:00.000Z';
 assert.equal(m.getState().credits,24);assert.equal(m.notifications().total,0,'Free, pass and foreign seeded likes do not refund');
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.decisions.push({id:'legacy-uncharged',actorKind:'property',actorId:'own-p1',propertyId:'own-p1',searchId:'s3',liked:true,createdAt:REFUND_START});storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 assert.equal(createModel(storage,()=>clock).getState().credits,24);
});

test('notification reads are owner-scoped and idempotent, with bounded pagination and stable saved timestamps',()=>{
 const t=refundFixture();t.setClock(REFUND_DEADLINE);const item=t.m.notifications().items[0];
 assert.equal(t.m.getState().unreadNotificationCount,1);const marked=t.m.markNotificationRead(item.id);assert.equal(marked.readAt,REFUND_DEADLINE);
 t.setClock('2026-11-16T12:00:00.000Z');assert.deepEqual(t.m.markNotificationRead(item.id),marked);assert.equal(t.m.getState().unreadNotificationCount,0);
 assert.equal(t.reload().notifications().unreadCount,0);assert.equal(t.m.notifications({offset:1,limit:1}).items.length,0);
 for(const options of [{offset:-1},{limit:101}])assert.throws(()=>t.m.notifications(options),/lapozási/);
 assert.throws(()=>t.m.markNotificationRead('missing'),/nem található/);
 const raw=JSON.parse(t.storage.getItem(STORAGE_KEY));raw.notifications.push({...item,id:'foreign-notification',userId:'u1'});t.storage.setItem(STORAGE_KEY,JSON.stringify(raw));
 const again=t.reload();assert.equal(again.notifications().total,1);assert.throws(()=>again.markNotificationRead('foreign-notification'),/nem található/);
});

test('refund storage failure commits neither balance, decision marker, ledger nor notification',()=>{
 const t=refundFixture();t.setClock(REFUND_DEADLINE);const before=t.storage.getItem(STORAGE_KEY);
 const m=createModel({getItem:key=>t.storage.getItem(key),setItem:()=>{throw new Error('quota');}},()=>REFUND_DEADLINE);
 assert.throws(()=>m.getState(),/tárhely/);assert.equal(t.storage.getItem(STORAGE_KEY),before);
 assert.equal(t.reload().getState().credits,t.balance);assert.equal(t.reload().notifications().total,1);
});

test('no-longer-current reports apply to both account types and keep existing contextual deduplication',()=>{
 const storage=store(),m=createModel(storage,()=>REFUND_START);
 for(const id of ['p1','p2']){
  const receipt=m.reportAccount('property',id,'no_longer_current');assert.equal(receipt.alreadyReported,false);assert.equal(m.reportAccount('property',id,'no_longer_current').id,receipt.id);
 }
 assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).reports.every(report=>report.reason==='no_longer_current'&&report.createdAt===REFUND_START),true);
 assert.equal(m.getState().reportedEntities.length,2);
});

test('legacy paid decisions with no valid recorded timestamp cannot produce a synthetic refund',()=>{
 for(const createdAt of [null,'',undefined,'invalid']){
  const t=refundFixture(),raw=JSON.parse(t.storage.getItem(STORAGE_KEY));raw.decisions.find(item=>item.id===t.decision.id).createdAt=createdAt;t.storage.setItem(STORAGE_KEY,JSON.stringify(raw));t.setClock(REFUND_DEADLINE);
  const m=t.reload();assert.equal(m.getState().credits,t.balance-2);assert.equal(m.notifications().total,0);
 }
});
