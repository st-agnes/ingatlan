import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { settlements } from '../dist/locations-data.js';
import { agglomerations } from '../dist/agglomerations-data.js';
import { neighborhoods } from '../dist/neighborhoods-data.js';
import { locations, getLocation, searchLocations, resolveLegacyLocations, matchesLocations, isPropertyLocation, MAX_SEARCH_LOCATIONS, expandLocationSelections, toggleMapLocation } from '../dist/locations.js';

test('map group expansion selects every canonical town without mutating compact choices', () => {
  const compact = ['area:Budapest', 'city:Solymár', 'area:Debrecen'];
  const before = [...compact], expanded = expandLocationSelections(compact);
  const expected = new Set(agglomerations.filter(area => compact.includes(area.id)).flatMap(area => area.settlements.map(city => `city:${city}`)));
  assert.deepEqual(new Set(expanded), expected);
  assert.equal(expanded.length, expected.size, 'Overlapping groups and explicit members are deduplicated');
  assert.deepEqual(compact, before, 'Viewing a group on the map does not change stored search origins');
  assert.deepEqual(expandLocationSelections(expanded), expanded);
  assert.equal(MAX_SEARCH_LOCATIONS, 200);
  assert.ok(agglomerations.every(area => area.settlements.length <= MAX_SEARCH_LOCATIONS));
  assert.equal(agglomerations.find(area => area.id === 'area:Budapest').settlements.length, 81);
});

test('editing a group member materializes the affected group and preserves unrelated selections', () => {
  const group = agglomerations.find(area => area.id === 'area:Budapest');
  const initial = ['area:Budapest', 'city:Solymár', 'area:Debrecen', 'district:Budapest:5'];
  const removed = toggleMapLocation(initial, 'city:Solymár');
  assert.ok(!removed.includes('area:Budapest') && !removed.includes('city:Solymár'));
  assert.ok(removed.includes('area:Debrecen') && removed.includes('district:Budapest:5'));
  assert.deepEqual(new Set(removed.filter(id => getLocation(id).kind === 'city')), new Set(group.settlements.filter(city => city !== 'Solymár').map(city => `city:${city}`)));
  assert.equal(matchesLocations({locationId:'city:Solymár'}, {locationIds:removed}), false);
  assert.equal(matchesLocations({locationId:'city:Budapest'}, {locationIds:removed}), true);
  const restored = toggleMapLocation(removed, 'city:Solymár');
  assert.ok(restored.includes('city:Solymár') && !restored.includes('area:Budapest'), 'An edited group stays a concrete editable list');
  const child = neighborhoods.find(area => area.city === 'Debrecen');
  const narrowed = toggleMapLocation(['area:Debrecen', 'city:Solymár'], child.id);
  assert.ok(narrowed.includes(child.id) && !narrowed.includes('city:Debrecen') && narrowed.includes('city:Solymár'));
  assert.ok(narrowed.includes('city:Hajdúsámson'), 'Choosing a quarter narrows only its city, retaining the neighboring towns');
  assert.deepEqual(initial, ['area:Budapest', 'city:Solymár', 'area:Debrecen', 'district:Budapest:5']);
});

test('duplicate OR choices lose a toggled member, and replacements work at the cap', () => {
  let overlap;
  for (const left of agglomerations) {
    const right = agglomerations.find(area => area.id !== left.id && area.settlements.some(city => left.settlements.includes(city)));
    if (right) { overlap = [left, right, right.settlements.find(city => left.settlements.includes(city))]; break; }
  }
  // Current regional groups are disjoint; duplicate group/member alternatives
  // still exercise the same OR rule. Future overlapping groups use both IDs.
  const [left, right, city] = overlap ?? [agglomerations.find(area => area.id === 'area:Budapest'), agglomerations.find(area => area.id === 'area:Budapest'), 'Solymár'];
  const concrete = toggleMapLocation([left.id, right.id, `city:${city}`], `city:${city}`);
  assert.ok(!expandLocationSelections(concrete).includes(`city:${city}`), 'OR semantics cannot leave the removed town selected through another group');
  const child = neighborhoods.find(area => area.city === 'Debrecen');
  const full = ['city:Debrecen', ...locations.filter(location => location.kind === 'city' && location.city !== 'Debrecen').slice(0, MAX_SEARCH_LOCATIONS - 1).map(location => location.id)];
  const narrowed = toggleMapLocation(full, child.id);
  assert.equal(narrowed.length, MAX_SEARCH_LOCATIONS);
  assert.ok(narrowed.includes(child.id) && !narrowed.includes('city:Debrecen'));
  assert.equal(toggleMapLocation(full, 'city:Zsámbék'), null, 'An unrelated 201st choice cannot bypass the bounded search cap');
  assert.equal(toggleMapLocation(full, 'unknown'), null);
});

test('complete municipality catalogue and generated browser data agree', async () => {
  const master = JSON.parse(await fs.readFile(new URL('../dist/data/settlements.json', import.meta.url), 'utf8'));
  assert.equal(master.version, 1);
  assert.deepEqual(settlements, master.settlements);
  assert.equal(settlements.length, 3155);
  assert.equal(new Set(settlements).size, settlements.length);
  assert.equal(locations.length, 3155 + 23 + agglomerations.length + neighborhoods.length);
  assert.equal(new Set(locations.map(location => location.id)).size, locations.length);
  assert.ok(settlements.every(name => name.trim() === name && !/\d|[()]/.test(name)));
  for (const city of ['Budapest', 'Debrecen', 'Hajdúszoboszló', 'Hajdúsámson', 'Solymár', 'Pilisvörösvár', 'Őr', 'Zsámbék']) {
    assert.equal(getLocation('city:' + city)?.city, city);
  }
  for (let number = 1; number <= 23; number++) {
    const district = getLocation('district:Budapest:' + number);
    assert.equal(district.city, 'Budapest');
    assert.match(district.label, /^Budapest [IVX]+\. kerület$/);
    assert.ok(district.district.endsWith('.'));
  }
});

test('the complete neighborhood catalog is searchable by name, city and aliases, and only selectable for searches', () => {
  assert.equal(neighborhoods.length, 4308);
  for (const value of neighborhoods) {
    const location=getLocation(value.id);
    assert.equal(location.kind,'neighborhood');
    assert.equal(location.label,`${value.name} (${value.city})`);
    assert.equal(isPropertyLocation(location),false);
    assert.deepEqual(resolveLegacyLocations({city:location.label}),[]);
  }
  const unique=neighborhoods.find(value=>neighborhoods.filter(other=>other.name===value.name).length===1);
  assert.ok(searchLocations(`${unique.city} ${unique.name}`,50).some(value=>value.id===unique.id));
  assert.ok(searchLocations(unique.label,50).some(value=>value.id===unique.id));
  assert.ok(searchLocations(unique.name,50).some(value=>value.id===unique.id));
  assert.ok(searchLocations(unique.name,50,{kind:'property'}).every(isPropertyLocation));
  const aliased=neighborhoods.find(value=>value.aliases?.some(alias=>alias!==value.name));
  if(aliased)assert.ok(searchLocations(`${aliased.aliases.find(alias=>alias!==aliased.name)} ${aliased.city}`,50).some(value=>value.id===aliased.id));
});

test('neighborhood matching requires explicit membership and combines with town and area alternatives', () => {
  const quarter=neighborhoods.find(value=>value.city==='Debrecen');
  const other=neighborhoods.find(value=>value.city===quarter.city&&value.id!==quarter.id);
  const property={locationId:'city:'+quarter.city,neighborhoodIds:[quarter.id]};
  assert.equal(matchesLocations(property,{locationIds:[quarter.id]}),true);
  assert.equal(matchesLocations({...property,neighborhoodIds:[]},{locationIds:[quarter.id]}),false);
  assert.equal(matchesLocations(property,{locationIds:[other.id]}),false);
  assert.equal(matchesLocations(property,{locationIds:[other.id,'city:'+quarter.city]}),true);
  assert.equal(matchesLocations({locationId:'city:Solymár'},{locationIds:[quarter.id,'area:Budapest']}),true);
  // Polygon membership may cross its source municipality boundary.
  assert.equal(matchesLocations({...property,locationId:'city:Szeged'},{locationIds:[quarter.id]}),true);
  assert.equal(matchesLocations({locationId:'city:Szeged'},{locationIds:[quarter.id]}),false);
  assert.equal(matchesLocations({locationId:quarter.id,neighborhoodIds:[quarter.id]},{locationIds:['city:'+quarter.city]}),false);
  assert.equal(matchesLocations(property,{locationIds:[quarter.id,'neighborhood:missing']}),false);
});

test('autocomplete handles accents, case, prefixes and Budapest district notation', () => {
  assert.equal(searchLocations('hajdusam')[0].id, 'city:Hajdúsámson');
  assert.equal(searchLocations('PILISVOR')[0].id, 'city:Pilisvörösvár');
  assert.equal(searchLocations('őr')[0].id, 'city:Őr');
  for (const text of ['Budapest 5', 'Budapest V.', 'Budapest V. kerület', '5. kerület', 'Bp 5']) {
    assert.equal(searchLocations(text)[0]?.id, 'district:Budapest:5', text);
  }
  assert.equal(searchLocations('Budapest 23')[0].id, 'district:Budapest:23');
  assert.equal(searchLocations('Budapest')[0].id, 'city:Budapest');
  assert.equal(searchLocations('Debrecn')[0].id, 'city:Debrecen');
  assert.equal(searchLocations('', 8).length, 0);
  assert.equal(searchLocations('Budapest', 2).length, 2);
  assert.equal(searchLocations('Budapest', 0).length, 0);
  assert.deepEqual(searchLocations('Budapest 24'), []);
  assert.deepEqual(searchLocations('Nincsilyenhelység'), []);
  assert.equal(getLocation('city:Debrecn'), null);
  assert.equal(getLocation('city:debrecen'), null);
});

test('legacy fields resolve to canonical choices and malformed locations never become wildcards', () => {
  assert.deepEqual(resolveLegacyLocations({ city: 'hajdusamson' }).map(location => location.id), ['city:Hajdúsámson']);
  assert.deepEqual(resolveLegacyLocations({ city: 'Budapest', districts: ['5', 'IX.', 'V.'] }).map(location => location.id), ['district:Budapest:5', 'district:Budapest:9']);
  assert.equal(resolveLegacyLocations({ city: 'Budapest', district: 'XI.' })[0].id, 'district:Budapest:11');
  assert.equal(resolveLegacyLocations({ city: 'Budapest V. kerület' })[0].id, 'district:Budapest:5');
  assert.equal(resolveLegacyLocations({ city: 'Budapest', districts: [] })[0].id, 'city:Budapest');
  assert.deepEqual(resolveLegacyLocations({ city: 'Budapest', districts: ['XXIV.'] }), []);
  assert.deepEqual(resolveLegacyLocations({ city: 'Debrecn' }), []);
});

test('legacy municipality identity preserves accents before an unambiguous folded fallback', () => {
  const cases = [
    ['Komló', 'city:Komló'], ['komló', 'city:Komló'], ['KOMLÓ', 'city:Komló'], [' Komló ', 'city:Komló'], ['Komlo\u0301', 'city:Komló'],
    ['Kömlő', 'city:Kömlő'], ['kömlő', 'city:Kömlő'], ['KÖMLŐ', 'city:Kömlő'], ['Ko\u0308mlo\u030b', 'city:Kömlő']
  ];
  for (const [city, id] of cases) {
    assert.deepEqual(resolveLegacyLocations({city}).map(location => location.id), [id], city);
    assert.equal(matchesLocations({city}, {locationIds:[id]}), true, city);
    const other = id === 'city:Komló' ? 'city:Kömlő' : 'city:Komló';
    assert.equal(matchesLocations({city}, {locationIds:[other]}), false, city);
  }
  for (const city of ['Komlo', 'komlo', 'KOMLO']) {
    assert.deepEqual(resolveLegacyLocations({city}), [], city);
    assert.equal(matchesLocations({city}, {locationIds:['city:Komló', 'city:Kömlő']}), false, city);
  }
  assert.deepEqual(resolveLegacyLocations({city:'hajdusamson'}).map(location => location.id), ['city:Hajdúsámson']);
  for (const city of ['Budapest V.', 'budapest v. kerulet', 'BUDAPEST 5'])
    assert.deepEqual(resolveLegacyLocations({city}).map(location => location.id), ['district:Budapest:5'], city);
});

test('selected towns and Budapest districts match with OR semantics', () => {
  const search = { locationIds: ['district:Budapest:5', 'district:Budapest:9', 'city:Solymár', 'city:Pilisvörösvár'] };
  for (const id of search.locationIds) assert.equal(matchesLocations({ locationId: id }, search), true, id);
  for (const id of ['district:Budapest:11', 'city:Budapest', 'city:Debrecen', 'city:Piliscsaba']) {
    assert.equal(matchesLocations({ locationId: id }, search), false, id);
  }
  const provincial = { locationIds: ['city:Debrecen', 'city:Hajdúszoboszló', 'city:Hajdúsámson'] };
  assert.equal(matchesLocations({ locationId: 'city:Hajdúsámson' }, provincial), true);
  assert.equal(matchesLocations({ locationId: 'city:Hajdúhadház' }, provincial), false);
  assert.equal(matchesLocations({ city: 'Budapest', district: 'XIII.' }, { locationIds: ['city:Budapest'] }), true);
  assert.equal(matchesLocations({ locationId: 'district:Budapest:23' }, { city: 'Budapest' }), true);
  assert.equal(matchesLocations({ city: 'Budapest', district: 'IX.' }, { city: 'Budapest', districts: ['V.'] }), false);
});

test('invalid or absent locations cannot broaden compatibility', () => {
  const home = { locationId: 'city:Debrecen' };
  assert.equal(matchesLocations(home, { locationIds: [] }), false);
  assert.equal(matchesLocations(home, {}), false);
  assert.equal(matchesLocations(home, { locationIds: ['city:Debrecen', 'city:Invalid'] }), false);
  assert.equal(matchesLocations({ locationId: 'city:Invalid', city: 'Debrecen' }, { city: 'Debrecen' }), false);
  assert.equal(matchesLocations({ city: 'Budapest', district: 'XXIV.' }, { city: 'Budapest' }), false);
  assert.equal(matchesLocations({ city: 'Debrecen' }, { city: 'Invalid' }), false);
});
