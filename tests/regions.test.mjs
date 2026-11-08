import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {regions} from '../dist/regions-data.js';
import {settlements} from '../dist/locations-data.js';
import {agglomerations} from '../dist/agglomerations-data.js';

const catalog = JSON.parse(await readFile(new URL('../backend/Otthonra.Api/Data/regions.json', import.meta.url), 'utf8'));
const byTown = new Map(catalog.regions.flatMap(region => region.settlements.map(town => [town, region.id])));
const expectedIds = ['HU110','HU120','HU211','HU212','HU213','HU221','HU222','HU223','HU231','HU232','HU233',
  'HU311','HU312','HU313','HU321','HU322','HU323','HU331','HU332','HU333'];

test('backend county membership and immutable browser choices agree on all 20 official regions', () => {
  assert.equal(catalog.schemaVersion, 1);
  assert.deepEqual(regions, catalog.regions.map(({id,label}) => ({id,label})));
  assert.deepEqual(regions.map(region => region.id).sort(), expectedIds);
  assert.equal(new Set(regions.map(region => region.id)).size, 20);
  assert.equal(new Set(regions.map(region => region.label)).size, 20);
  assert.ok(Object.isFrozen(regions) && regions.every(Object.isFrozen));
  assert.deepEqual(regions[0], {id:'HU110',label:'Budapest'});
  assert.ok(regions.slice(1).every(region => region.label.endsWith(' vármegye')));
});

test('every one of the 3155 canonical municipalities belongs to exactly one county or Budapest', () => {
  const towns = catalog.regions.flatMap(region => region.settlements);
  assert.equal(towns.length, 3155);
  assert.equal(new Set(towns).size, towns.length, 'duplicate membership would broaden regional previews');
  assert.deepEqual([...towns].sort(), [...settlements].sort(), 'there are no missing or invented municipalities');
  for (const region of catalog.regions) {
    assert.ok(region.settlements.length > 0);
    assert.equal(new Set(region.settlements).size, region.settlements.length);
  }
  assert.deepEqual(catalog.regions.find(region => region.id === 'HU110').settlements, ['Budapest']);
});

test('known towns and surrounding areas keep their real county boundaries', () => {
  for (const [town, expected] of Object.entries({Budapest:'HU110',Solymár:'HU120',Pilisvörösvár:'HU120',
    Debrecen:'HU321',Hajdúszoboszló:'HU321',Hajdúsámson:'HU321',Őriszentpéter:'HU222',Szeged:'HU333'})) {
    assert.equal(byTown.get(town), expected, town);
  }
  const budapestArea = agglomerations.find(area => area.id === 'area:Budapest');
  assert.deepEqual([...new Set(budapestArea.settlements.map(town => byTown.get(town)))].sort(), ['HU110','HU120']);
  for (const area of agglomerations) {
    assert.ok(area.settlements.every(town => byTown.has(town)), `${area.city}: every area member needs county membership`);
  }
});

test('offline catalogue retains the official source, pinned workbook fingerprint and attribution', () => {
  assert.equal(catalog.source.url, 'https://www.ksh.hu/docs/osztalyozasok/teruleti_szamjel/teruleti_szamjelrendszer_struktura_elemei_2026.xlsx');
  assert.equal(catalog.source.sha256, '36927d2798ea709f8239d806c9a84881524395f3d6f11dfdd756cc662776e1a5');
  assert.equal(catalog.source.retrievedOn, '2026-11-06');
  assert.equal(catalog.source.license, 'CC BY 4.0');
  assert.equal(catalog.source.licenseUrl, 'https://www.ksh.hu/copyright');
  assert.match(catalog.source.title, /KSH/);
  assert.match(catalog.processing, /NUTS 2016/);
  assert.ok(!/"(?:latitude|longitude|lat|lon|ip)"/.test(JSON.stringify(catalog)), 'regional membership contains no geolocation observations');
});
