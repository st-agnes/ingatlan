import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { settlements } from '../dist/locations-data.js';
import { agglomerations } from '../dist/agglomerations-data.js';
import { locations, getLocation, searchLocations, resolveLegacyLocations, matchesLocations } from '../dist/locations.js';

test('complete municipality catalogue and generated browser data agree', async () => {
  const master = JSON.parse(await fs.readFile(new URL('../dist/data/settlements.json', import.meta.url), 'utf8'));
  assert.equal(master.version, 1);
  assert.deepEqual(settlements, master.settlements);
  assert.equal(settlements.length, 3155);
  assert.equal(new Set(settlements).size, settlements.length);
  assert.equal(locations.length, 3155 + 23 + agglomerations.length);
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
