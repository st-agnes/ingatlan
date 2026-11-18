import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync} from 'node:zlib';
import {collectCountryCandidates, loadCountrySource, mergeCurrentOsmSources} from '../scripts/neighborhoods/country.mjs';
import {validateGeometry} from '../scripts/neighborhoods/build.mjs';

const digest = value => createHash('sha256').update(value).digest('hex');
const pbfSha256 = 'a'.repeat(64);
const timestamp = '2026-11-12T21:20:00Z';
const canonical = ['Budapest', 'Esztergom', 'Dorog'];
const square = {type: 'Polygon', coordinates: [[[19, 47], [19.1, 47], [19.1, 47.1], [19, 47.1], [19, 47]]]};
const collection = features => ({type: 'FeatureCollection', features});

function source(id = 101, name = 'Várnegyed', tags = {}) {
  return {osmType: 'relation', osmId: id, tags: {name, place: 'quarter', ...tags},
    objectVersion: 2, objectTimestamp: timestamp, changeset: 1234,
    members: [{type: 'way', ref: 12, role: 'outer'}],
    url: `https://www.openstreetmap.org/relation/${id}`, pbfSha256, osmTimestamp: timestamp,
    geometrySha256: digest(JSON.stringify(square)), license: 'ODbL-1.0',
    attribution: '© OpenStreetMap contributors'};
}

function polygon(id = 101, name = 'Várnegyed', municipality = 'Esztergom', tags = {}) {
  const ident = `osm:relation:${id}`;
  return {type: 'Feature', id: ident, bbox: [19, 47, 19.1, 47.1],
    properties: {id: ident, name, sourceName: name, municipality, municipalityId: `city:${municipality}`,
      municipalityOsmId: 'osm:relation:100', municipalityEvidence: 'source_full_containment',
      coveringMunicipalityOsmIds: ['osm:relation:100'], hierarchyMunicipalityOsmIds: [],
      boundaryKind: 'neighbourhood', classificationReason: 'place_quarter', adminLevel: tags.admin_level ?? null,
      reviewStatus: 'unreviewed', usableForAddressAssignment: false, sourceIsOfficial: false,
      sourceIsHardBoundary: false, source: source(id, name, tags)}, geometry: structuredClone(square)};
}

function point(id = 201, name = 'Pontos városrész') {
  const raw = source(id, name);
  raw.osmType = 'node';
  raw.url = `https://www.openstreetmap.org/node/${id}`;
  delete raw.members;
  delete raw.geometrySha256;
  return {type: 'Feature', id: `osm:node:${id}`, properties: {name, place: 'quarter', municipality: 'Dorog',
    municipalityId: 'city:Dorog', municipalityOsmId: 'osm:relation:102',
    municipalityEvidence: 'source_full_containment', coveringMunicipalityOsmIds: ['osm:relation:102'],
    hierarchyMunicipalityOsmIds: [], hasSourcePolygon: false, source: raw},
  geometry: {type: 'Point', coordinates: [19.03, 47.03]}};
}

function snapshot(features = [polygon()], nodes = [], rejected = []) {
  const document = collection(features), namedNodes = collection(nodes);
  const sha256 = digest(JSON.stringify(document));
  const nodeSha256 = digest(JSON.stringify(namedNodes));
  return {manifest: {version: 1, license: 'ODbL-1.0', generatedAt: '2026-11-13T00:00:00Z',
    input: {file: 'hungary-latest.osm.pbf', bytes: 12345, sha256: pbfSha256,
      header: {osmosis_replication_timestamp: timestamp}},
    counts: {polygons: features.length, namedNodes: nodes.length,
      sourcePolygonCandidates: features.length + rejected.length, rejectedPolygonCandidates: rejected.length}},
  document, namedNodes, audit: {rejectedCandidates: rejected, assemblyFailures: []},
  path: 'data/neighborhoods/sources/country-osm/polygons.geojson', sha256, rawSha256: sha256,
  nodePath: 'data/neighborhoods/sources/country-osm/named-nodes.geojson', nodeSha256, nodeRawSha256: nodeSha256,
  manifestPath: 'data/neighborhoods/sources/country-osm/manifest.json'};
}

const collect = value => collectCountryCandidates(value, canonical, validateGeometry);

test('country polygons preserve exact geometry, actual source IDs and snapshot provenance', () => {
  const input = snapshot();
  const original = structuredClone(input);
  const result = collect(input);
  assert.equal(result.features.length, 1);
  assert.deepEqual(input, original, 'collection must not mutate source geometry or metadata');
  const feature = result.features[0];
  assert.equal(feature.id, 'osm:relation:101');
  assert.equal(feature.properties.municipality, 'Esztergom');
  assert.deepEqual(feature.geometry, square);
  assert.equal(feature.properties.source.pbfSha256, pbfSha256);
  assert.equal(feature.properties.source.sha256, input.sha256);
  assert.equal(feature.properties.source.osmTimestamp, timestamp);
  assert.deepEqual(feature.properties.source.members, original.document.features[0].properties.source.members);
  assert.equal(feature.properties.source.license, 'ODbL-1.0');
  assert.equal(feature.properties.usableForAddressAssignment, false);
  assert.equal(feature.properties.sourceIsOfficial, false);
});

test('administrative country classifications distinguish Budapest districts from quarter candidates', () => {
  const district = polygon(102, 'I. kerület', 'Budapest', {place: 'suburb', boundary: 'administrative', admin_level: '9'});
  district.properties.boundaryKind = 'administrative_subdivision';
  const quarter = polygon(103, 'Belváros', 'Esztergom', {place: undefined, boundary: 'administrative', admin_level: '10'});
  quarter.properties.boundaryKind = 'administrative_subdivision';
  const result = collect(snapshot([district, quarter]));
  assert.equal(result.features.find(feature => feature.id === district.id).properties.boundaryKind, 'district');
  assert.equal(result.features.find(feature => feature.id === quarter.id).properties.boundaryKind, 'neighbourhood');
  assert.equal(result.districtRecords, 1);
  assert.equal(result.neighbourhoodRecords, 1);
});

test('source points remain an excluded inventory and incomplete source polygons stay audited', () => {
  const rejected = {id: 'osm:relation:999', name: 'Hiányos határ',
    reason: 'no_valid_assembled_source_polygon', source: source(999, 'Hiányos határ')};
  const input = snapshot([polygon()], [point()], [rejected]);
  const original = structuredClone(input);
  const result = collect(input);
  assert.equal(result.features.length, 1);
  assert.equal(result.features.some(feature => feature.geometry.type === 'Point'), false);
  const namedPoint = result.excluded.find(item => item.id === 'osm:node:201');
  assert.equal(namedPoint.reason, 'not_polygon');
  assert.equal(namedPoint.geometryType, 'Point');
  assert.ok(result.excluded.some(item => item.id === rejected.id));
  assert.equal(result.candidateRecords, 3);
  assert.equal(result.candidateRecords, result.features.length + result.excluded.length);
  assert.deepEqual(input, original);
});

test('unresolved/unknown municipalities, unsupported association evidence and malformed geometry never enter the catalogue', () => {
  const unresolved = polygon(101);
  unresolved.properties.municipality = null;
  unresolved.properties.municipalityId = null;
  unresolved.properties.municipalityEvidence = 'no_full_containment';
  const unknown = polygon(102, 'Ismeretlen', 'Invented city');
  const intersection = polygon(103, 'Átfedés');
  intersection.properties.municipalityEvidence = 'intersection_only';
  const open = polygon(104, 'Nyitott');
  open.geometry.coordinates[0].pop();
  const result = collect(snapshot([unresolved, unknown, intersection, open]));
  assert.equal(result.features.length, 0);
  assert.equal(result.excluded.length, 4);
  assert.equal(result.excluded.find(item => item.id === unresolved.id).reason, 'country_unresolved_municipality');
  assert.equal(result.excluded.find(item => item.id === unknown.id).reason, 'unknown_municipality');
  assert.equal(result.excluded.find(item => item.id === open.id).reason, 'open_ring');
});

test('a country feature needs matching real OSM identity, source tags and the pinned input PBF', () => {
  const missingTags = polygon(101);
  delete missingTags.properties.source.tags;
  const mismatchedId = polygon(102);
  mismatchedId.properties.source.osmId = 123;
  const wrongPbf = polygon(103);
  wrongPbf.properties.source.pbfSha256 = '0'.repeat(64);
  const residential = polygon(104, 'Önkényes lakótelep');
  residential.properties.source.tags = {name: 'Önkényes lakótelep', landuse: 'residential'};
  assert.throws(() => collect(snapshot([mismatchedId])), /identity mismatch/);
  assert.throws(() => collect(snapshot([wrongPbf])), /identity mismatch/);
  const result = collect(snapshot([missingTags, residential]));
  assert.equal(result.features.length, 0);
  assert.equal(result.excluded.length, 2);
});

function cohort(features, excluded = [], queryResults = []) {
  return {features, excluded, sourceRecords: features.length + excluded.length,
    candidateRecords: features.length + excluded.length,
    neighbourhoodRecords: features.length + excluded.length, districtRecords: 0,
    sourceSnapshots: 1, queryResults};
}

test('the freshest actual OSM object wins across country/city sources and country wins timestamp ties', () => {
  const country = collect(snapshot());
  const cityFeature = structuredClone(country.features[0]);
  cityFeature.properties.source.sha256 = 'b'.repeat(64);
  cityFeature.properties.source.osmTimestamp = '2026-11-11T00:00:00Z';
  cityFeature.geometry.coordinates[0] = cityFeature.geometry.coordinates[0].map(([x, y]) => [x + 0.01, y]);
  const original = structuredClone(cityFeature);
  const oldExclusion = {id: 'osm:way:555', reason: 'audited_municipality_mismatch',
    source: {provider: 'openstreetmap', sha256: 'c'.repeat(64)}};
  const queryResults = [{city: 'Dorog', status: 'failed', error: 'http_429'}];
  let merged = mergeCurrentOsmSources(cohort([cityFeature], [oldExclusion], queryResults), country);
  assert.equal(merged.features.length, 1);
  assert.deepEqual(merged.features[0].geometry, square);
  assert.ok(merged.excluded.some(item => item.id === oldExclusion.id && item.reason === oldExclusion.reason));
  assert.deepEqual(merged.queryResults, queryResults);
  assert.equal(merged.candidateRecords, merged.features.length + merged.excluded.length);
  assert.deepEqual(cityFeature, original);
  cityFeature.properties.source.osmTimestamp = '2026-11-13T00:00:00Z';
  merged = mergeCurrentOsmSources(cohort([cityFeature]), country);
  assert.deepEqual(merged.features[0].geometry, cityFeature.geometry);
  cityFeature.properties.source.osmTimestamp = timestamp;
  merged = mergeCurrentOsmSources(cohort([cityFeature]), country);
  assert.deepEqual(merged.features[0].geometry, square);
});

test('PBF replication time overrides contradictory feature dates and retrieval/generation times never establish freshness', () => {
  const input = snapshot();
  input.manifest.generatedAt = '2029-01-01T00:00:00Z';
  input.manifest.input.acquisition = {retrievedAt: '2028-01-01T00:00:00Z'};
  input.document.features[0].properties.source.osmTimestamp = '2027-01-01T00:00:00Z';
  input.document.features[0].properties.source.retrievedAt = '2030-01-01T00:00:00Z';
  const country = collect(input);
  assert.equal(country.features[0].properties.source.osmTimestamp, timestamp);
  const cityFeature = structuredClone(country.features[0]);
  cityFeature.properties.source.osmTimestamp = '2026-11-13T00:00:00Z';
  cityFeature.geometry.coordinates[0] = cityFeature.geometry.coordinates[0].map(([x, y]) => [x + 0.01, y]);
  assert.deepEqual(mergeCurrentOsmSources(cohort([cityFeature]), country).features[0].geometry, cityFeature.geometry);
  delete input.manifest.input.header.osmosis_replication_timestamp;
  delete input.document.features[0].properties.source.osmTimestamp;
  assert.equal(collect(input).features[0].properties.source.osmTimestamp, null,
    'retrievedAt and generatedAt must not substitute for a missing OSM snapshot timestamp');
});

test('old per-city audit exclusions cannot remove a fresh same-ID country feature', () => {
  const country = collect(snapshot());
  const obsoleteAudit = {id: 'osm:relation:101', name: 'Várnegyed', municipality: 'Dorog',
    boundaryKind: 'neighbourhood', reason: 'audited_municipality_mismatch',
    source: {provider: 'openstreetmap', sha256: 'b'.repeat(64)}};
  const merged = mergeCurrentOsmSources(cohort([], [obsoleteAudit]), country);
  assert.equal(merged.features.length, 1);
  assert.equal(merged.features[0].properties.municipality, 'Esztergom');
  assert.ok(merged.excluded.includes(obsoleteAudit));
  assert.equal(merged.candidateRecords, 2);
});

async function writeSource(root) {
  const directory = join(root, 'data/neighborhoods/sources/country-osm');
  await mkdir(directory, {recursive: true});
  const input = snapshot();
  const documents = {'polygons.geojson': input.document, 'named-nodes.geojson': input.namedNodes,
    'municipalities.geojson': collection([]), 'audit.json': input.audit};
  const manifest = {...input.manifest, outputs: []};
  for (const [file, document] of Object.entries(documents)) {
    const bytes = Buffer.from(JSON.stringify(document));
    await writeFile(join(directory, file), bytes);
    manifest.outputs.push({file, bytes: bytes.length, sha256: digest(bytes)});
  }
  await writeFile(join(directory, 'manifest.json'), JSON.stringify(manifest));
  return {directory, manifest};
}

test('country loader verifies every declared output fingerprint, including noncatalogue source files', async () => {
  const root = await mkdtemp(join(tmpdir(), 'otthonra-country-'));
  try {
    assert.equal(await loadCountrySource(root), null);
    const {directory, manifest} = await writeSource(root);
    const loaded = await loadCountrySource(root);
    assert.equal(loaded.document.features.length, 1);
    assert.equal(loaded.manifest.input.sha256, pbfSha256);
    for (const {file} of manifest.outputs) {
      const path = join(directory, file), original = await readFile(path);
      await writeFile(path, Buffer.concat([original, Buffer.from(' ')]));
      await assert.rejects(loadCountrySource(root), /hash|fingerprint|mismatch/i, `${file} tampering must fail`);
      await writeFile(path, original);
    }
  } finally {
    await rm(root, {recursive: true, force: true});
  }
});

test('gzip sources retain separate stored and decompressed fingerprints and still reject tampering', async () => {
  const root = await mkdtemp(join(tmpdir(), 'otthonra-country-gzip-'));
  try {
    const {directory, manifest} = await writeSource(root);
    const rawPath = join(directory, 'polygons.geojson'), bytes = await readFile(rawPath);
    const compressed = gzipSync(bytes);
    await writeFile(rawPath + '.gz', compressed);
    await rm(rawPath);
    const loaded = await loadCountrySource(root);
    assert.ok(loaded.path.endsWith('polygons.geojson.gz'));
    assert.equal(loaded.sha256, digest(compressed));
    assert.equal(loaded.rawSha256, manifest.outputs.find(item => item.file === 'polygons.geojson').sha256);
    assert.deepEqual(collect(loaded).features[0].geometry, square);
    const altered = gzipSync(Buffer.concat([bytes, Buffer.from(' ')]));
    await writeFile(rawPath + '.gz', altered);
    await assert.rejects(loadCountrySource(root), /hash|fingerprint|mismatch/i);
  } finally {
    await rm(root, {recursive: true, force: true});
  }
});

test('the preserved country snapshot supplies actual nationwide geometry with complete candidate accounting', async t => {
  const realRoot = fileURLToPath(new URL('..', import.meta.url));
  const input = await loadCountrySource(realRoot);
  if (!input) {
    t.skip('Country snapshot has not yet been acquired');
    return;
  }
  const settlements = JSON.parse(await readFile(join(realRoot, 'dist/data/settlements.json'), 'utf8')).settlements;
  const result = collectCountryCandidates(input, settlements, validateGeometry);
  const originals = new Map(input.document.features.map(feature => [feature.id, feature]));
  assert.equal(originals.size, input.document.features.length);
  assert.equal(result.candidateRecords, input.manifest.counts.sourcePolygonCandidates + input.manifest.counts.namedNodes);
  assert.equal(result.candidateRecords, result.features.length + result.excluded.length);
  assert.equal(result.namedNodes.length, input.manifest.counts.namedNodes);
  for (const feature of input.document.features) assert.match(feature.id, /^osm:(?:way|relation):[1-9]\d*$/);
  for (const feature of result.namedNodes) {
    assert.match(feature.id, /^osm:node:[1-9]\d*$/);
    assert.equal(feature.geometry.type, 'Point');
  }
  for (const feature of result.features) {
    const original = originals.get(feature.id);
    assert.ok(original, `${feature.id} must come from the preserved source inventory`);
    assert.deepEqual(feature.geometry, original.geometry, `${feature.id} source geometry must remain exact`);
    assert.equal(feature.properties.source.geometrySha256, digest(JSON.stringify(original.geometry)));
    assert.equal(feature.properties.source.pbfSha256, input.manifest.input.sha256);
    assert.equal(feature.properties.usableForAddressAssignment, false);
  }
  const previousCities = new Set(['Budapest', 'Debrecen', 'Székesfehérvár', 'Budaörs', 'Dorog', 'Sopron']);
  assert.ok(result.features.some(feature => !previousCities.has(feature.properties.municipality)),
    'The country source must add a municipality beyond the original six-city catalogue');
});
