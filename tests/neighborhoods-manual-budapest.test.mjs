import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {validateGeometry} from '../scripts/neighborhoods/build.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = async path => JSON.parse(await readFile(join(root, path), 'utf8'));
const definitions = await read('data/neighborhoods/manual/budapest-definitions.json');
assert.equal(definitions.records.length, 9);
assert.equal(new Set(definitions.records.map(r => r.sourceParagraph)).size, 9);
assert.ok(definitions.records.every(r => r.boundaryText && r.district === 23 && r.usableForAddressAssignment === false));

function segments(geometry) {
  const result = [];
  function line(points) {
    for (let i = 1; i < points.length; i++) result.push([points[i - 1], points[i]]);
  }
  if (geometry.type === 'LineString') line(geometry.coordinates);
  else if (geometry.type === 'Polygon') geometry.coordinates.forEach(line);
  else if (geometry.type === 'MultiPolygon') geometry.coordinates.forEach(p => p.forEach(line));
  else if (geometry.type === 'Point') return []; // Name evidence supplies no boundary segments.
  else throw new Error(`Unexpected source geometry: ${geometry.type}`);
  return result;
}
function onSegment(p, [a, b]) {
  const length = Math.hypot(b[0]-a[0], b[1]-a[1]);
  if (length === 0) return Math.hypot(p[0]-a[0], p[1]-a[1]) < 1e-10;
  const cross = Math.abs((p[0]-a[0])*(b[1]-a[1])-(p[1]-a[1])*(b[0]-a[0]));
  return cross/length < 1e-9 && p.every((v, i) => v >= Math.min(a[i], b[i])-1e-9 && v <= Math.max(a[i], b[i])+1e-9);
}
for (const suffix of ['molnar', 'apostolhegy', 'orban', 'peterimajor']) {
  const document = await read(`data/neighborhoods/manual/budapest-${suffix}.geojson`);
  const source = await read(`data/neighborhoods/manual/sources/budapest-${suffix}-input.geojson`);
  const support = source.features.flatMap(f => segments(f.geometry));
  assert.equal(document.features.length, 1);
  const feature = document.features[0], p = feature.properties;
  assert.equal(validateGeometry(feature.geometry).valid, true, `${p.name}: invalid polygon`);
  assert.equal(p.usableForAddressAssignment, false);
  assert.ok(p.sourceDocuments.some(d => /^[a-f0-9]{64}$/.test(d.sha256)), `${p.name}: no pinned legal source`);
  assert.ok(p.sourceLineIds.length > 0);
  assert.ok(p.evidenceUrls.length > 0 && p.method);
  const inputPath = p.sourceGeometry?.path ?? p.source?.inputPath;
  const inputSha = p.sourceGeometry?.sha256 ?? p.source?.inputSha256;
  const bytes = await readFile(join(root, inputPath));
  assert.equal(createHash('sha256').update(bytes).digest('hex'), inputSha);
  const inferred = p.constructionProof?.inferredSegments ?? [];
  support.push(...inferred.map(s => [s.from, s.to]));
  for (const edge of segments(feature.geometry)) {
    assert.ok(support.some(segment => edge.every(point => onSegment(point, segment))),
      `${p.name}: output edge has neither retained source support nor an explicit inferred segment: ${JSON.stringify(edge)}`);
  }
  if (suffix === 'orban') {
    assert.equal(p.name, 'Orbánhegy (XXIII. kerület)');
    assert.equal(p.referenceName, 'Orbánhegy');
    assert.equal(p.district, 23);
    assert.ok(inferred.length > 0 && inferred.every(s => s.reason && s.lengthMetres > 0));
    assert.ok(inferred.some(s => s.reason.includes('Millennium utca') && s.lengthMetres > 100));
  } else assert.equal(inferred.length, 0);
}
console.log('Budapest manual legal-boundary polygons: geometry and source-edge support verified');
