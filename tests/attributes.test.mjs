import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CONDITION_OPTIONS,BUILDING_OPTIONS,CONSTRUCTION_AGE_OPTIONS,VIEW_OPTIONS,CEILING_HEIGHT_OPTIONS,FLOOR_OPTIONS,HEATING_OPTIONS,PARKING_OPTIONS,
  normalizeCondition,normalizeBuilding,normalizePropertyAttributes,normalizePropertyRooms,roomLabel,normalizeSearchAttributes,attributesCompatible
} from '../dist/attributes.js';

const property = {condition:'Jó',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m alatti',floor:3};
const search = {conditions:['Jó','Átlagos'],buildings:['Panel','Tégla'],constructionAges:['10–30 év közötti','31–40 év közötti'],views:['Kertre néző','Panorámás'],ceilingHeight:'3 m alatti',floors:[0,3]};

test('attribute choices cover every requested category and the floor buckets include basement and ground level',()=>{
  assert.deepEqual(CONDITION_OPTIONS,['Felújítandó','Átlagos','Jó','Új/felújított']);
  assert.equal(BUILDING_OPTIONS.length,12);assert.equal(CONSTRUCTION_AGE_OPTIONS.length,5);
  assert.equal(VIEW_OPTIONS.length,4);assert.equal(CEILING_HEIGHT_OPTIONS.length,2);
  assert.deepEqual(FLOOR_OPTIONS.map(option=>option.value),[-1,0,0.5,1,2,3,4,5,6,7,8,9]);
  assert.equal(FLOOR_OPTIONS.at(-1).label,'9 vagy afölötti');
});

test('legacy known condition labels normalize while unknown old text is retained on reads',()=>{
  for(const value of ['Felújított','Újszerű','Új építésű',' új/felújított '])assert.equal(normalizeCondition(value),'Új/felújított');
  assert.equal(normalizeCondition('Jó állapotú'),'Jó');assert.equal(normalizeBuilding(' tégla '),'Tégla');
  assert.equal(normalizeCondition('Régi egyedi állapot'),'Régi egyedi állapot');
  assert.equal(normalizeBuilding('Régi egyedi falazat'),'Régi egyedi falazat');
  assert.equal(attributesCompatible({condition:'Régi egyedi állapot'},{conditions:['Jó']}),false);
  assert.equal(attributesCompatible({condition:'Felújított'},{conditions:['Új/felújított']}),true);
});

test('each selected category uses OR while different categories all have to match',()=>{
  assert.equal(attributesCompatible(property,search),true);
  for(const [field,value] of [['condition','Felújítandó'],['building','Fa'],['constructionAge','Több mint 50 éves'],['view','Utcai'],['ceilingHeight','3 m feletti'],['floor',1]]) {
    assert.equal(attributesCompatible({...property,[field]:value},search),false,field);
  }
  assert.equal(attributesCompatible({...property,condition:'Átlagos',building:'Panel',view:'Panorámás'},search),true);
});

test('unselected filters accept old incomplete property data, but selected ones require known values',()=>{
  assert.equal(attributesCompatible({},{}),true);
  assert.equal(attributesCompatible({},{conditions:[],buildings:[],constructionAges:[],views:[],ceilingHeight:'',floors:[]}),true);
  for(const [field,value] of [['conditions',['Jó']],['buildings',['Tégla']],['constructionAges',['10 évnél fiatalabb']],['views',['Utcai']],['ceilingHeight','3 m alatti'],['floors',[0]]]) {
    assert.equal(attributesCompatible({}, {[field]:value}),false,field);
  }
});

test('floor buckets preserve zero, reject unknown floors and include every floor above nine',()=>{
  for(const floor of [9,10,11,12,20,200])assert.equal(attributesCompatible({floor},{floors:[11]}),true);
  for(const floor of [null,undefined,-2,0,8])assert.equal(attributesCompatible({floor},{floors:[11]}),false);
  assert.equal(attributesCompatible({floor:0},{floors:[0]}),true);
  assert.equal(attributesCompatible({floor:-1},{floors:[-1]}),true);
  assert.equal(attributesCompatible({floor:null},{floors:[0]}),false);
});

test('normalizers deduplicate selections, canonicalize aliases, preserve unrelated fields and never mutate inputs',()=>{
  const input={id:'same-id',conditions:['Jó állapotú','Jó','Felújított'],buildings:['panel','Panel'],constructionAges:['10 évnél fiatalabb'],views:['Udvari','Udvari'],floors:['0',0,'11']};
  const before=structuredClone(input),result=normalizeSearchAttributes(input,{strict:true});
  assert.deepEqual(input,before);assert.equal(result.id,'same-id');
  assert.deepEqual(result.conditions,['Jó','Új/felújított']);assert.deepEqual(result.buildings,['Panel']);
  assert.deepEqual(result.views,['Udvari']);assert.deepEqual(result.floors,[0,9]);
  assert.equal(normalizeSearchAttributes({condition:'Bármilyen'}).conditions.length,0);
});

test('optional booleans distinguish unknown from explicit no and text fields retain their meaning',()=>{
  const blank=normalizePropertyAttributes({title:'Kept'});
  assert.equal(blank.title,'Kept');assert.equal(blank.floor,null);assert.equal(blank.condition,'');assert.equal(blank.building,'');
  assert.deepEqual([blank.insulated,blank.airConditioning,blank.solarPanels],[null,null,null]);
  const value=normalizePropertyAttributes({insulated:'false',airConditioning:'true',solarPanels:false,heatingType:' Hőszivattyú ',energyRating:'BB',parkingTypes:['Garázs'],floor:0},{strict:true});
  assert.deepEqual([value.insulated,value.airConditioning,value.solarPanels],[false,true,false]);
  assert.equal(value.heatingType,'Hőszivattyú');assert.equal(value.energyRating,'BB');assert.equal(value.floor,0);
  assert.equal(normalizePropertyAttributes({floor:' '},{strict:true}).floor,null);
});

test('strict writes reject unknown options, malformed arrays, invalid floors and oversized or contact-bearing extras',()=>{
  for(const value of [{condition:'Ismeretlen'},{building:'Titkos falazat'},{view:'Bármerre'},{constructionAge:'2000'},{ceilingHeight:'3 méter'},{floor:1.5},{floor:201},{insulated:'maybe'},{heatingType:'x'.repeat(81)},{energyRating:'x'.repeat(21)},{parkingType:'x'.repeat(81)},{heatingType:'anna@example.hu'}]) {
    assert.throws(()=>normalizePropertyAttributes(value,{strict:true}),undefined,JSON.stringify(value));
  }
  for(const value of [{conditions:'Jó'},{buildings:['Ismeretlen']},{constructionAges:['Új']},{views:['A házra']},{ceilingHeight:'magas'},{floors:[null]},{floors:[12]},{floors:[' ']}]) {
    assert.throws(()=>normalizeSearchAttributes(value,{strict:true}),undefined,JSON.stringify(value));
  }
  const previous={condition:'Régi egyedi állapot',building:'Régi egyedi falazat'};
  assert.equal(normalizePropertyAttributes(previous,{strict:true,previous}).condition,previous.condition);
  assert.throws(()=>normalizePropertyAttributes({...previous,condition:'Más ismeretlen'},{strict:true,previous}),/Érvénytelen/);
});


test('strict malformed selections cannot silently clear filters or reinterpret booleans as floors',()=>{
  for(const field of ['conditions','buildings','constructionAges','views']) {
    for(const element of ['',null,undefined,'   ']) {
      assert.throws(()=>normalizeSearchAttributes({[field]:[element]},{strict:true}),/Érvénytelen/,`${field}: blank element`);
    }
  }
  assert.throws(()=>normalizeSearchAttributes({conditions:['Jó','']},{strict:true}),/Érvénytelen/,'a valid choice must not hide a malformed element');
  for(const floor of [false,true]) {
    assert.throws(()=>normalizePropertyAttributes({floor},{strict:true}),/emelet|magasföldszint/);
    assert.throws(()=>normalizeSearchAttributes({floors:[floor]},{strict:true}),/Érvénytelen/);
    assert.throws(()=>normalizeSearchAttributes({floors:[0,floor]},{strict:true}),/Érvénytelen/);
    assert.equal(normalizePropertyAttributes({floor}).floor,null,'a malformed stored boolean is not ground or first floor');
  }
  assert.deepEqual(normalizeSearchAttributes({conditions:[],buildings:null,constructionAges:[],views:[],floors:[]},{strict:true}).conditions,[],'an explicitly empty category remains a valid clear operation');
  assert.deepEqual(normalizeSearchAttributes({floors:['0','1']},{strict:true}).floors,[0,1],'numeric form values still represent valid floors');
});


test('new lower basement values are rejected while unchanged legacy floors remain editable',()=>{
  assert.throws(()=>normalizePropertyAttributes({floor:-2},{strict:true}),/emelet|magasföldszint/);
  assert.throws(()=>normalizePropertyAttributes({floor:-5},{strict:true}),/emelet|magasföldszint/);
  assert.equal(normalizePropertyAttributes({floor:-2}).floor,-2,'reading old rows does not rewrite their stored floor');
  assert.equal(normalizePropertyAttributes({floor:'-2'},{strict:true,previous:{floor:-2}}).floor,-2,'an unrelated local edit can retain its exact old floor');
  assert.throws(()=>normalizePropertyAttributes({floor:-3},{strict:true,previous:{floor:-2}}),/emelet|magasföldszint/);
  assert.equal(normalizePropertyAttributes({floor:-2},{strict:true,allowLegacyUnknown:true}).floor,-2,'API updates can relay the old floor for authoritative server comparison');
  assert.equal(normalizePropertyAttributes({floor:-1},{strict:true}).floor,-1);
  assert.equal(normalizePropertyAttributes({floor:12},{strict:true}).floor,12);
});

test('explicit whole and half room counts preserve their composition and weighted total',()=>{
 const input={wholeRooms:'2',halfRooms:'3',rooms:'3.5',title:'Megmarad'};
 const value=normalizePropertyRooms(input,{strict:true});
 assert.deepEqual([value.wholeRooms,value.halfRooms,value.rooms],[2,3,3.5]);
 assert.equal(roomLabel(value),'2 egész + 3 fél szoba');
 assert.equal(roomLabel({wholeRooms:0,halfRooms:2}),'2 fél szoba');
 assert.equal(roomLabel({wholeRooms:3,halfRooms:0}),'3 szoba');
 assert.equal(input.wholeRooms,'2');
 assert.deepEqual([normalizePropertyRooms({halfRooms:1},{strict:true}).wholeRooms,normalizePropertyRooms({halfRooms:1},{strict:true}).rooms],[0,0.5]);
 for(const invalid of [{wholeRooms:-1,halfRooms:2},{wholeRooms:1.5},{halfRooms:true},{wholeRooms:0,halfRooms:0},{halfRooms:1001},{wholeRooms:1000,halfRooms:1},{wholeRooms:2,halfRooms:3,rooms:4},{wholeRooms:2,rooms:-1}])assert.throws(()=>normalizePropertyRooms(invalid,{strict:true}),undefined,JSON.stringify(invalid));
 assert.equal(normalizePropertyRooms({wholeRooms:2,halfRooms:3,rooms:0},{strict:true}).rooms,3.5);
});

test('legacy room totals derive only exact half steps and retain an existing explicit composition',()=>{
 for(const [rooms,whole,half] of [[3,3,0],[2.5,2,1],[0.5,0,1]])assert.deepEqual(Object.values(normalizePropertyRooms({rooms})),[rooms,whole,half]);
 const arbitrary=normalizePropertyRooms({rooms:3.2});
 assert.deepEqual([arbitrary.rooms,arbitrary.wholeRooms,arbitrary.halfRooms],[3.2,null,null]);
 assert.equal(roomLabel(arbitrary),'3,2 szoba');
 const previous={rooms:3.5,wholeRooms:2,halfRooms:3};
 const retained=normalizePropertyRooms({rooms:3.5},{strict:true,previous});
 assert.deepEqual([retained.wholeRooms,retained.halfRooms],[2,3]);
 assert.deepEqual([normalizePropertyRooms({rooms:4},{strict:true,previous}).wholeRooms,normalizePropertyRooms({rooms:4},{strict:true,previous}).halfRooms],[4,0]);
});

test('heating selections share canonical options and filter primary heating without confusing unknown with none',()=>{
 assert.equal(HEATING_OPTIONS.length,13);assert.ok(HEATING_OPTIONS.includes('Nincs fűtés'));
 const value=normalizePropertyAttributes({heatingType:'hőszivattyú',secondaryHeatingType:'klíma'},{strict:true});
 assert.equal(value.heatingType,'Hőszivattyú');assert.equal(value.secondaryHeatingType,'Klíma');
 const old={heatingType:'Hőszivattyú és padlófűtés'};
 assert.equal(normalizePropertyAttributes(old).heatingType,old.heatingType);
 assert.equal(normalizePropertyAttributes(old,{strict:true,previous:old}).heatingType,old.heatingType);
 assert.throws(()=>normalizePropertyAttributes(old,{strict:true}),/Érvénytelen/);
 assert.throws(()=>normalizePropertyAttributes({secondaryHeatingType:'Régi egyedi'},{strict:true,allowLegacyUnknown:true}),/Érvénytelen/);
 assert.deepEqual(normalizeSearchAttributes({heatingTypes:['klíma','Klíma','Hőszivattyú']},{strict:true}).heatingTypes,['Klíma','Hőszivattyú']);
 assert.equal(attributesCompatible(value,{heatingTypes:['Hőszivattyú','Nincs fűtés']}),true);
 assert.equal(attributesCompatible(value,{heatingTypes:['Klíma']}),false,'supplementary heating does not satisfy a primary-heating filter');
 assert.equal(attributesCompatible({},{heatingTypes:['Nincs fűtés']}),false);
 assert.equal(attributesCompatible({heatingType:'Nincs fűtés'},{heatingTypes:['Nincs fűtés']}),true);
 for(const heatingTypes of ['Klíma',[''],[null],['Ismeretlen']])assert.throws(()=>normalizeSearchAttributes({heatingTypes},{strict:true}));
});

test('multiple parking choices deduplicate, clear explicitly and preserve a legacy description as one choice',()=>{
 assert.equal(PARKING_OPTIONS.length,7);
 const value=normalizePropertyAttributes({parkingTypes:['Garázs','Utcai parkolás','Garázs']},{strict:true});
 assert.deepEqual(value.parkingTypes,['Garázs','Utcai parkolás']);assert.equal(value.parkingType,'Garázs, Utcai parkolás');
 assert.deepEqual(normalizePropertyAttributes({parkingType:value.parkingType},{strict:true,previous:value}).parkingTypes,value.parkingTypes,'old clients retain a known existing multi-selection');
 assert.deepEqual(normalizePropertyAttributes({parkingType:'Garázs',parkingTypes:[]},{strict:true}).parkingTypes,[]);
 const old={parkingType:'Saját garázs, kapubeállóval'};
 const read=normalizePropertyAttributes(old);assert.deepEqual(read.parkingTypes,[old.parkingType]);
 assert.deepEqual(normalizePropertyAttributes({...read},{strict:true,previous:read}).parkingTypes,[old.parkingType]);
 assert.throws(()=>normalizePropertyAttributes(old,{strict:true}),/Érvénytelen/);
 for(const parkingTypes of ['Garázs',[''],[null],['Ismeretlen'],Array(21).fill('Garázs')])assert.throws(()=>normalizePropertyAttributes({parkingTypes},{strict:true}));
});

test('house saves clear irrelevant floor constraints while old rows remain readable',()=>{
 const property={type:'Ház',floor:3,balcony:true,elevator:true};
 assert.equal(normalizePropertyAttributes(property).floor,3);
 assert.equal(normalizePropertyAttributes({...property,floor:'invalid'},{strict:true}).floor,null);
 const search={type:'Ház',floors:[3],balcony:true,elevator:true};
 assert.deepEqual(normalizeSearchAttributes(search).floors,[3]);
 const saved=normalizeSearchAttributes(search,{strict:true});
 assert.deepEqual([saved.floors,saved.balcony,saved.elevator],[[],false,false]);
 assert.equal(attributesCompatible({type:'Ház',floor:null},search),true);
});

test('building height is optional, bounded and consistent with a known property floor',()=>{
 const p=normalizePropertyAttributes({type:'Lakás',floor:'0',buildingFloors:'0',privateGarden:false,sharedGarden:'true'},{strict:true});
 assert.equal(p.floor,0);assert.equal(p.buildingFloors,0);assert.equal(p.privateGarden,false);assert.equal(p.sharedGarden,null);
 for(const buildingFloors of [true,-1,1.5,201,'invalid'])assert.throws(()=>normalizePropertyAttributes({type:'Lakás',buildingFloors},{strict:true}),/épület/);
 assert.throws(()=>normalizePropertyAttributes({type:'Lakás',floor:3,buildingFloors:2},{strict:true}),/magasabb/);
 assert.equal(normalizePropertyAttributes({type:'Lakás',floor:3},{strict:true}).buildingFloors,null);
 assert.equal(normalizePropertyAttributes({type:'Lakás',floor:-1,buildingFloors:0},{strict:true}).buildingFloors,0);
 assert.equal(normalizePropertyAttributes({type:'Ház',floor:8,buildingFloors:3,privateGarden:true,sharedGarden:true},{strict:true}).buildingFloors,null);
});

test('search amenities retain a private garden and ignore the retired shared garden option',()=>{
 const empty=normalizeSearchAttributes({type:'Lakás'});
 for(const key of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden','sharedGarden'])assert.equal(empty[key],false,key);
 const p=normalizePropertyAttributes({type:'Lakás',privateGarden:true,sharedGarden:false});
 assert.equal(attributesCompatible(p,{type:'Lakás',privateGarden:true}),true);
 assert.equal(attributesCompatible(p,{type:'Lakás',sharedGarden:true}),true);
 assert.equal(normalizeSearchAttributes({type:'Lakás',sharedGarden:true},{strict:true}).sharedGarden,false);
 assert.equal(normalizePropertyAttributes({type:'Lakás',sharedGarden:true},{strict:true}).sharedGarden,null);
 assert.equal(attributesCompatible({type:'Lakás'},{type:'Lakás',privateGarden:true}),false);
 for(const type of ['Ház','Telek','Iroda']){
  const property=normalizePropertyAttributes({type,privateGarden:true,sharedGarden:false});
  assert.deepEqual([property.privateGarden,property.sharedGarden],[null,null]);
  const search=normalizeSearchAttributes({type,privateGarden:true,sharedGarden:true,airConditioning:true,excludeTopFloor:true,excludeGroundFloorAndBelow:true});
  assert.deepEqual([search.privateGarden,search.sharedGarden],[false,false]);assert.equal(search.airConditioning,true);
  if(type==='Ház')assert.deepEqual([search.excludeTopFloor,search.excludeGroundFloorAndBelow],[false,false]);
 }
});

test('exact attribute compatibility requires known non-top and above-ground facts when requested',()=>{
 const search={type:'Lakás',excludeTopFloor:true,excludeGroundFloorAndBelow:true,airConditioning:true};
 assert.equal(attributesCompatible({type:'Lakás',floor:2,buildingFloors:3,airConditioning:true},search),true);
 for(const p of [{floor:3,buildingFloors:3},{floor:0,buildingFloors:3},{floor:-1,buildingFloors:3},{floor:2},{buildingFloors:3}])assert.equal(attributesCompatible({type:'Lakás',airConditioning:true,...p},search),false,JSON.stringify(p));
 assert.equal(attributesCompatible({type:'Lakás',floor:2,buildingFloors:3,airConditioning:null},search),false);
});


test('raised ground and grouped upper floors preserve exact legacy values and top-floor uncertainty',()=>{
 const raised=normalizePropertyAttributes({type:'Lakás',floor:'0.5',buildingFloors:'0'},{strict:true});
 assert.equal(raised.floor,0.5);assert.equal(raised.floorIsUpperRange,false);
 assert.equal(attributesCompatible(raised,{type:'Lakás',floors:[0.5],excludeGroundFloorAndBelow:true}),true);
 assert.equal(attributesCompatible(raised,{type:'Lakás',excludeTopFloor:true}),false);
 assert.equal(attributesCompatible({...raised,buildingFloors:1},{type:'Lakás',excludeTopFloor:true}),true);
 const range=normalizePropertyAttributes({type:'Lakás',floor:9,floorIsUpperRange:true,buildingFloors:12},{strict:true});
 assert.equal(attributesCompatible(range,{type:'Lakás',floors:[9]}),true);
 assert.equal(attributesCompatible(range,{type:'Lakás',excludeTopFloor:true}),false);
 assert.equal(normalizePropertyAttributes({floor:12,buildingFloors:12},{strict:true}).floor,12);
 assert.equal(normalizePropertyAttributes({floor:12},{strict:true}).floorIsUpperRange,false);
 assert.throws(()=>normalizePropertyAttributes({floor:8,floorIsUpperRange:true},{strict:true}),/9 vagy/);
 assert.throws(()=>normalizePropertyAttributes({floor:1.5},{strict:true}),/emelet/);
 assert.deepEqual(normalizeSearchAttributes({floors:[9,10,11,0.5]},{strict:true}).floors,[9,0.5]);
 assert.equal(normalizePropertyAttributes({type:'Ház',floor:9,floorIsUpperRange:true},{strict:true}).floorIsUpperRange,false);
});
