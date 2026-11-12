import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  CORE_CITIES, ENDPOINTS, TARGET_CITIES, collect, fetchCity, fileNameFor,
  municipalityAdminLevel, parseArguments, queryFor, summarizeResponse
} from '../scripts/neighborhoods/fetch-osm.mjs';

const documents = city => ({
  version: 0.6,
  osm3s: { timestamp_osm_base: '2026-11-12T00:00:00Z' },
  elements: [
    { type: 'relation', id: city === 'Budapest' ? 37244 : 101,
      tags: { name: city, boundary: 'administrative', admin_level: city === 'Budapest' ? '6' : '8' } },
    { type: 'relation', id: 102, tags: { name: 'Városrész', boundary: 'administrative', admin_level: '11' },
      members: [{ type: 'way', ref: 103, role: 'outer', geometry: [{ lat: 47, lon: 21 }, { lat: 47.01, lon: 21.01 }] }] }
  ]
});
const jsonResponse = document => new Response(JSON.stringify(document), { headers: { 'content-type': 'application/json' } });
const immediately = async () => {};

assert.equal(TARGET_CITIES.length, 26);
assert.equal(CORE_CITIES.length, 7);
assert.deepEqual(parseArguments([]).cities, CORE_CITIES);
assert.deepEqual(parseArguments(['--cities', 'Budapest, Debrecen']).cities, ['Budapest', 'Debrecen']);
assert.deepEqual(parseArguments(['--scope', 'all']).cities, TARGET_CITIES);
assert.equal(fileNameFor('Győr'), 'gyor.json');
assert.equal(municipalityAdminLevel('Budapest'), '6');
assert.equal(municipalityAdminLevel('Debrecen'), '8');
assert.match(queryFor('Budapest'), /admin_level.*6.*name.*Budapest/);
assert.match(queryFor('Budapest'), /relation\(37244\)/);
assert.equal(summarizeResponse(documents('Budapest'), 'Budapest').municipalityRelationId, 37244);
assert.equal(summarizeResponse(documents('Budapest'), 'Budapest').municipalityAdminLevel, '6');
const wrongBudapestLevel = documents('Budapest');
wrongBudapestLevel.elements[0].tags.admin_level = '8';
assert.throws(() => summarizeResponse(wrongBudapestLevel, 'Budapest'), /municipality-not-found/);
for (const args of [['--cities', 'Budapest,Budapest'], ['--cities', 'Budapest"];out;'], ['--scope', 'unknown'], ['--cities'], ['--scope', 'all', '--cities', 'Budapest']])
  assert.throws(() => parseArguments(args));

const query = queryFor('Debrecen');
assert.match(query, /ISO3166-1.*HU/);
assert.match(query, /admin_level.*8.*name.*Debrecen/);
assert.match(query, /map_to_area/);
assert.match(query, /\^\(9\|10\|11\)\$/);
assert.match(query, /suburb\|quarter\|neighbourhood/);
assert.match(query, /is_closed/);
assert.match(query, /way\(area\.city\)\["boundary"="administrative"\]/);
assert.match(query, /out geom/);
assert.doesNotMatch(query, /node\(/);

let attempts = 0;
const pauses = [];
const result = await fetchCity('Debrecen', {
  fetchImpl: async (url, options) => {
    assert.equal(url, ENDPOINTS[attempts]);
    assert.equal(options.method, 'POST');
    assert.equal(options.redirect, 'error');
    assert.ok(options.signal instanceof AbortSignal);
    assert.equal(options.body.get('data'), query);
    attempts++;
    return attempts === 1 ? new Response('', { status: 503 }) : jsonResponse(documents('Debrecen'));
  },
  pause: async ms => pauses.push(ms),
  now: () => '2026-11-12T01:00:00Z'
});
assert.equal(attempts, 2);
assert.deepEqual(pauses, [1000]);
assert.equal(result.provenance.candidates, 1);
assert.equal(result.provenance.relationsWithWayGeometry, 1);
assert.equal(result.provenance.completeCoverage, false);
assert.equal(result.provenance.usableForAddressAssignment, false);
assert.equal(result.provenance.license, 'ODbL-1.0');
assert.match(result.provenance.sha256, /^[0-9a-f]{64}$/);
assert.deepEqual(JSON.parse(result.raw), documents('Debrecen'));

for (const status of [400, 401, 403, 404]) {
  let count = 0;
  const failure = await fetchCity('Budapest', { fetchImpl: async () => { count++; return new Response('', { status }); }, pause: immediately });
  assert.equal(failure.failure.reason, `http-${status}`);
  assert.equal(count, 1);
}
let count = 0;
const longWait = await fetchCity('Budapest', { fetchImpl: async () => { count++; return new Response('', { status: 429, headers: { 'retry-after': '120' } }); }, pause: immediately });
assert.equal(longWait.failure.reason, 'http-429');
assert.equal(count, 1);
const oversized = await fetchCity('Budapest', { fetchImpl: async () => jsonResponse(documents('Budapest')), maxBytes: 10, pause: immediately });
assert.equal(oversized.failure.reason, 'response-too-large');
const partial = await fetchCity('Budapest', { fetchImpl: async () => jsonResponse({ ...documents('Budapest'), remark: 'runtime error' }), pause: immediately });
assert.equal(partial.failure.reason, 'overpass-incomplete-result');
assert.equal(partial.failure.attempts.length, 2);
assert.throws(() => summarizeResponse({ elements: [] }, 'Budapest'), /municipality-not-found/);
assert.throws(() => summarizeResponse({ elements: [documents('Budapest').elements[0], documents('Budapest').elements[0]] }, 'Budapest'), /ambiguous-municipality/);
assert.throws(() => summarizeResponse({ elements: [...documents('Budapest').elements, { type: 'node', id: 202, tags: { name: 'A point is not a boundary' } }] }, 'Budapest'), /unexpected-candidate/);
await assert.rejects(() => fetchCity('Budapest', { timeoutMs: 60_001 }), /timeout/);

const output = await mkdtemp(join(tmpdir(), 'otthonra-neighborhood-acquisition-'));
try {
  let cityIndex = 0;
  const summary = await collect({
    cities: ['Budapest', 'Debrecen'], output, pause: immediately, onProgress: () => {},
    fetchOptions: { pause: immediately, fetchImpl: async () => ++cityIndex === 1 ? jsonResponse(documents('Budapest')) : new Response('', { status: 403 }) }
  });
  assert.equal(summary.successfulCities, 1);
  assert.equal(summary.failedCities, 1);
  assert.equal(summary.candidateCount, 1);
  assert.equal(summary.completeCoverage, false);
  assert.deepEqual(JSON.parse(await readFile(join(output, 'budapest.json'), 'utf8')), documents('Budapest'));
  assert.deepEqual(JSON.parse(await readFile(join(output, 'summary.json'), 'utf8')), summary);
  assert.deepEqual((await readdir(output)).sort(), ['budapest.json', 'budapest.source.json', 'summary.json']);
  await assert.rejects(() => collect({cities: ['Budapest'], output, pause: immediately,
    fetchOptions: {fetchImpl: async () => {throw new Error('An occupied output directory must stop before network.');}}}),
  /output-directory-not-empty/);
} finally { await rm(output, { recursive: true, force: true }); }

console.log('Neighborhood acquisition safeguards passed.');
