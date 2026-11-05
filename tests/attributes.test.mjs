import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CONDITION_OPTIONS,BUILDING_OPTIONS,CONSTRUCTION_AGE_OPTIONS,VIEW_OPTIONS,CEILING_HEIGHT_OPTIONS,FLOOR_OPTIONS,
  normalizeCondition,normalizeBuilding,normalizePropertyAttributes,normalizeSearchAttributes,attributesCompatible
} from '../dist/attributes.js';

const property = {condition:'Jó',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m alatti',floor:3};
const search = {conditions:['Jó','Átlagos'],buildings:['Panel','Tégla'],constructionAges:['10–30 év közötti','31–40 év közötti'],views:['Kertre néző','Panorámás'],ceilingHeight:'3 m alatti',floors:[0,3]};

test('attribute choices cover every requested category and the floor buckets include basement and ground level',()=>{
  assert.deepEqual(CONDITION_OPTIONS,['Felújítandó','Átlagos','Jó','Új/felújított']);
  assert.equal(BUILDING_OPTIONS.length,12);assert.equal(CONSTRUCTION_AGE_OPTIONS.length,5);
  assert.equal(VIEW_OPTIONS.length,4);assert.equal(CEILING_HEIGHT_OPTIONS.length,2);
  assert.deepEqual(FLOOR_OPTIONS.map(option=>option.value),[-1,0,1,2,3,4,5,6,7,8,9,10,11]);
  assert.equal(FLOOR_OPTIONS.at(-1).label,'11 vagy afölötti');
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

test('floor buckets preserve zero, reject unknown floors and include every floor above eleven',()=>{
  for(const floor of [11,12,20,200])assert.equal(attributesCompatible({floor},{floors:[11]}),true);
  for(const floor of [null,undefined,-2,0,10])assert.equal(attributesCompatible({floor},{floors:[11]}),false);
  assert.equal(attributesCompatible({floor:0},{floors:[0]}),true);
  assert.equal(attributesCompatible({floor:-1},{floors:[-1]}),true);
  assert.equal(attributesCompatible({floor:null},{floors:[0]}),false);
});

test('normalizers deduplicate selections, canonicalize aliases, preserve unrelated fields and never mutate inputs',()=>{
  const input={id:'same-id',conditions:['Jó állapotú','Jó','Felújított'],buildings:['panel','Panel'],constructionAges:['10 évnél fiatalabb'],views:['Udvari','Udvari'],floors:['0',0,'11']};
  const before=structuredClone(input),result=normalizeSearchAttributes(input,{strict:true});
  assert.deepEqual(input,before);assert.equal(result.id,'same-id');
  assert.deepEqual(result.conditions,['Jó','Új/felújított']);assert.deepEqual(result.buildings,['Panel']);
  assert.deepEqual(result.views,['Udvari']);assert.deepEqual(result.floors,[0,11]);
  assert.equal(normalizeSearchAttributes({condition:'Bármilyen'}).conditions.length,0);
});

test('optional booleans distinguish unknown from explicit no and text fields retain their meaning',()=>{
  const blank=normalizePropertyAttributes({title:'Kept'});
  assert.equal(blank.title,'Kept');assert.equal(blank.floor,null);assert.equal(blank.condition,'');assert.equal(blank.building,'');
  assert.deepEqual([blank.insulated,blank.airConditioning,blank.solarPanels],[null,null,null]);
  const value=normalizePropertyAttributes({insulated:'false',airConditioning:'true',solarPanels:false,heatingType:' hőszivattyú és padlófűtés ',energyRating:'BB',parkingType:'saját garázs',floor:0},{strict:true});
  assert.deepEqual([value.insulated,value.airConditioning,value.solarPanels],[false,true,false]);
  assert.equal(value.heatingType,'hőszivattyú és padlófűtés');assert.equal(value.energyRating,'BB');assert.equal(value.floor,0);
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
    assert.throws(()=>normalizePropertyAttributes({floor},{strict:true}),/egész szám/);
    assert.throws(()=>normalizeSearchAttributes({floors:[floor]},{strict:true}),/Érvénytelen/);
    assert.throws(()=>normalizeSearchAttributes({floors:[0,floor]},{strict:true}),/Érvénytelen/);
    assert.equal(normalizePropertyAttributes({floor}).floor,null,'a malformed stored boolean is not ground or first floor');
  }
  assert.deepEqual(normalizeSearchAttributes({conditions:[],buildings:null,constructionAges:[],views:[],floors:[]},{strict:true}).conditions,[],'an explicitly empty category remains a valid clear operation');
  assert.deepEqual(normalizeSearchAttributes({floors:['0','1']},{strict:true}).floors,[0,1],'numeric form values still represent valid floors');
});


test('new lower basement values are rejected while unchanged legacy floors remain editable',()=>{
  assert.throws(()=>normalizePropertyAttributes({floor:-2},{strict:true}),/egész szám/);
  assert.throws(()=>normalizePropertyAttributes({floor:-5},{strict:true}),/egész szám/);
  assert.equal(normalizePropertyAttributes({floor:-2}).floor,-2,'reading old rows does not rewrite their stored floor');
  assert.equal(normalizePropertyAttributes({floor:'-2'},{strict:true,previous:{floor:-2}}).floor,-2,'an unrelated local edit can retain its exact old floor');
  assert.throws(()=>normalizePropertyAttributes({floor:-3},{strict:true,previous:{floor:-2}}),/egész szám/);
  assert.equal(normalizePropertyAttributes({floor:-2},{strict:true,allowLegacyUnknown:true}).floor,-2,'API updates can relay the old floor for authoritative server comparison');
  assert.equal(normalizePropertyAttributes({floor:-1},{strict:true}).floor,-1);
  assert.equal(normalizePropertyAttributes({floor:12},{strict:true}).floor,12);
});
