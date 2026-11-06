import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {settlements} from '../dist/locations-data.js';
import {agglomerations} from '../dist/agglomerations-data.js';
import {getLocation, isPropertyLocation, searchLocations, resolveLegacyLocations, matchesLocations} from '../dist/locations.js';

const officialCounts = {
  Budapest:81, Győr:78, Miskolc:41, Pécs:49, Eger:19, Szombathely:63, Zalaegerszeg:67,
  Békéscsaba:11, Debrecen:13, Kaposvár:30, Kecskemét:13, Nyíregyháza:11, Salgótarján:12,
  Sopron:15, Szeged:16, Szekszárd:10, Székesfehérvár:43, Szolnok:13, Tatabánya:11,
  Veszprém:27, Dunaújváros:9, Nagykanizsa:27, Baja:3, Esztergom:2
};

test('all 24 official city areas use the same validated membership in JSON and the browser module',async()=>{
  const master=JSON.parse(await readFile(new URL('../dist/data/agglomerations.json',import.meta.url),'utf8'));
  assert.equal(master.schemaVersion,1);
  assert.deepEqual(agglomerations,master.areas);
  assert.deepEqual(agglomerations.map(area=>area.city).sort(),Object.keys(officialCounts).sort());
  const known=new Set(settlements),ids=new Set();
  for(const area of agglomerations){
    assert.equal(area.id,`area:${area.city}`);assert.equal(ids.has(area.id),false);ids.add(area.id);
    assert.equal(area.settlements.length,officialCounts[area.city],`${area.city}: published settlement count`);
    assert.equal(new Set(area.settlements).size,area.settlements.length);
    assert.ok(area.settlements.includes(area.city),'Central city must be counted once');
    for(const member of area.settlements)assert.ok(known.has(member),`${area.city}: unknown municipality ${member}`);
    const location=getLocation(area.id);assert.equal(location.kind,'area');assert.equal(location.district,null);
    assert.equal(location.settlementCount,area.settlements.length);
    assert.equal(location.label,`${area.city} és környéke (${area.settlements.length} település)`);
  }
});

test('ordinary city queries visibly offer the counted area next to the exact city',()=>{
  for(const city of ['Budapest','Debrecen','Győr','Pécs','Székesfehérvár']){
    const found=searchLocations(city,12);
    assert.equal(found[0].id,`city:${city}`);
    assert.equal(found[1].id,`area:${city}`,'Budapest districts must not crowd the area out of the picker');
    assert.ok(found[1].settlementCount>1);
  }
  for(const query of ['debrecen es kornyeke','DEBRECEN KÖRNYÉKE','Debrecen agglomeráció'])assert.equal(searchLocations(query)[0].id,'area:Debrecen');
  assert.equal(searchLocations('DEBRECN')[0].id,'city:Debrecen');
  assert.equal(searchLocations('DEBRECN')[1].id,'area:Debrecen');
  assert.deepEqual(searchLocations('81'),[],'A settlement count is display metadata, not a location name');
  assert.equal(searchLocations(getLocation('area:Debrecen').label)[0].id,'area:Debrecen');
  assert.equal(getLocation('area:budapest'),null);
  assert.throws(()=>searchLocations('Debrecen',8,{kind:'invalid'}),/helyszínválasztó/);
});

test('seller suggestions and canonical legacy town resolution never admit a search area',()=>{
  const suggestions=searchLocations('Budapest',50,{kind:'property'});
  assert.equal(suggestions[0].id,'city:Budapest');assert.ok(suggestions.some(value=>value.kind==='district'));
  assert.ok(suggestions.every(isPropertyLocation));
  assert.deepEqual(searchLocations('Debrecen és környéke',8,{kind:'property'}),[]);
  assert.equal(isPropertyLocation(getLocation('area:Debrecen')),false);
  assert.equal(isPropertyLocation(null),false);
  assert.deepEqual(resolveLegacyLocations({city:getLocation('area:Debrecen').label}),[]);
  assert.deepEqual(resolveLegacyLocations({city:'Debrecen'}).map(value=>value.id),['city:Debrecen']);
});

test('each city group matches its central city and every member, while an outside town fails',()=>{
  for(const area of agglomerations){
    const wanted={locationIds:[area.id]};
    for(const member of area.settlements)assert.equal(matchesLocations({locationId:`city:${member}`},wanted),true,`${area.city}: ${member}`);
    const outside=settlements.find(city=>!area.settlements.includes(city));
    assert.equal(matchesLocations({locationId:`city:${outside}`},wanted),false,`${area.city}: outside ${outside}`);
  }
});

test('Budapest contributes one settlement to the count while all 23 districts match',()=>{
  const area=agglomerations.find(value=>value.city==='Budapest');
  assert.equal(area.settlements.filter(value=>value==='Budapest').length,1);
  assert.equal(getLocation(area.id).settlementCount,81);
  for(let number=1;number<=23;number++)assert.equal(matchesLocations({locationId:`district:Budapest:${number}`},{locationIds:[area.id]}),true);
  assert.equal(matchesLocations({city:'Budapest',district:'XIII.'},{locationIds:[area.id]}),true);
});

test('areas mix with other towns and districts using OR without broadening an exact town choice',()=>{
  const area=agglomerations.find(value=>value.city==='Debrecen');
  const member=area.settlements.find(value=>value!==area.city);
  assert.equal(matchesLocations({locationId:`city:${member}`},{locationIds:[area.id,'district:Budapest:5','city:Szeged']}),true);
  assert.equal(matchesLocations({locationId:'district:Budapest:5'},{locationIds:[area.id,'district:Budapest:5','city:Szeged']}),true);
  assert.equal(matchesLocations({locationId:'city:Szeged'},{locationIds:[area.id,'district:Budapest:5','city:Szeged']}),true);
  assert.equal(matchesLocations({locationId:'district:Budapest:9'},{locationIds:[area.id,'district:Budapest:5','city:Szeged']}),false);
  assert.equal(matchesLocations({locationId:`city:${member}`},{locationIds:['city:Debrecen']}),false);
});

test('unknown groups and group-valued property locations cannot silently become wildcards or central cities',()=>{
  const wanted={locationIds:['area:Debrecen']};
  assert.equal(matchesLocations({locationId:'area:Debrecen',city:'Debrecen'},wanted),false);
  assert.equal(matchesLocations({location:{id:'area:Debrecen'},city:'Debrecen'},wanted),false);
  assert.equal(matchesLocations({locationId:'city:Debrecen'},{locationIds:['area:Unknown','city:Debrecen']}),false);
  assert.equal(matchesLocations({locationId:'city:Debrecen'},{locationIds:['area:Unknown'],city:'Debrecen'}),false);
});
