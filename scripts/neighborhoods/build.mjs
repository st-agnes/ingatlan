import {createHash} from 'node:crypto';
import {readFile, readdir, writeFile} from 'node:fs/promises';
import {dirname, join, relative, resolve, sep} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {collectOsmCandidates, loadOsmSources} from './osm.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const EPSILON = 1e-12;
export const TARGET_CITIES = Object.freeze(['Budapest', 'Baja', 'Békéscsaba', 'Debrecen', 'Dunaújváros',
  'Eger', 'Érd', 'Esztergom', 'Győr', 'Hódmezővásárhely', 'Kaposvár', 'Kecskemét', 'Miskolc',
  'Nagykanizsa', 'Nyíregyháza', 'Pécs', 'Salgótarján', 'Sopron', 'Szeged', 'Székesfehérvár',
  'Szekszárd', 'Szolnok', 'Szombathely', 'Tatabánya', 'Veszprém', 'Zalaegerszeg']);

const sorted = values => [...values].sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
const sha256 = value => createHash('sha256').update(value).digest('hex');
const normalizedName = value => value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().replace(/[\s\p{Punctuation}]/gu, '');
const samePoint = (a, b) => a[0] === b[0] && a[1] === b[1];
const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const onSegment = (a, b, p) => Math.abs(cross(a, b, p)) <= EPSILON &&
  p[0] >= Math.min(a[0], b[0]) - EPSILON && p[0] <= Math.max(a[0], b[0]) + EPSILON &&
  p[1] >= Math.min(a[1], b[1]) - EPSILON && p[1] <= Math.max(a[1], b[1]) + EPSILON;

function intersects(a, b, c, d) {
  const abC = cross(a, b, c), abD = cross(a, b, d), cdA = cross(c, d, a), cdB = cross(c, d, b);
  if (((abC > EPSILON && abD < -EPSILON) || (abC < -EPSILON && abD > EPSILON)) &&
      ((cdA > EPSILON && cdB < -EPSILON) || (cdA < -EPSILON && cdB > EPSILON))) return true;
  return onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b);
}

function ringArea(ring) {
  // Translating first avoids cancellation when small polygons have large absolute coordinates.
  const origin = ring[0];
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) sum += cross(origin, ring[i], ring[i + 1]);
  return sum / 2;
}

function pointInside(point, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length - 1; j = i++) {
    const a = ring[i], b = ring[j];
    if (onSegment(a, b, point)) return false;
    if ((a[1] > point[1]) !== (b[1] > point[1]) &&
        point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

function ringsIntersect(a, b) {
  for (let i = 0; i < a.length - 1; i++) {
    for (let j = 0; j < b.length - 1; j++) if (intersects(a[i], a[i + 1], b[j], b[j + 1])) return true;
  }
  return false;
}

/** Validate source geometry; do not repair, simplify, invent, or mutate a boundary. */
export function validateGeometry(geometry, expectedBbox = undefined) {
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) {
    return {valid: false, reason: 'not_polygon'};
  }
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  if (!Array.isArray(polygons) || !polygons.length) return {valid: false, reason: 'empty_geometry'};
  const bbox = [Infinity, Infinity, -Infinity, -Infinity];
  let vertices = 0;
  for (const polygon of polygons) {
    if (!Array.isArray(polygon) || !polygon.length) return {valid: false, reason: 'empty_polygon'};
    const checkedRings = [];
    for (const original of polygon) {
      if (!Array.isArray(original) || original.length < 4) return {valid: false, reason: 'short_ring'};
      if (original.some(point => !Array.isArray(point) || point.length !== 2 ||
          !point.every(Number.isFinite) || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90)) {
        return {valid: false, reason: 'invalid_coordinate'};
      }
      if (!samePoint(original[0], original.at(-1))) return {valid: false, reason: 'open_ring'};
      // Consecutive duplicate vertices are harmless; ignore them only in the validation copy.
      const ring = original.filter((point, index) => index === 0 || !samePoint(point, original[index - 1]));
      if (ring.length < 4 || Math.abs(ringArea(ring)) <= EPSILON) return {valid: false, reason: 'degenerate_ring'};
      for (let i = 0; i < ring.length - 1; i++) {
        for (let j = i + 2; j < ring.length - 1; j++) {
          if (i === 0 && j === ring.length - 2) continue;
          if (intersects(ring[i], ring[i + 1], ring[j], ring[j + 1])) return {valid: false, reason: 'self_intersection'};
        }
      }
      checkedRings.push(ring);
      vertices += original.length;
      for (const [lon, lat] of original) {
        bbox[0] = Math.min(bbox[0], lon); bbox[1] = Math.min(bbox[1], lat);
        bbox[2] = Math.max(bbox[2], lon); bbox[3] = Math.max(bbox[3], lat);
      }
    }
    for (let i = 1; i < checkedRings.length; i++) {
      if (!pointInside(checkedRings[i][0], checkedRings[0]) || ringsIntersect(checkedRings[i], checkedRings[0])) {
        return {valid: false, reason: 'hole_outside_shell'};
      }
      for (let j = 1; j < i; j++) {
        if (ringsIntersect(checkedRings[i], checkedRings[j]) || pointInside(checkedRings[i][0], checkedRings[j]) ||
            pointInside(checkedRings[j][0], checkedRings[i])) return {valid: false, reason: 'overlapping_holes'};
      }
    }
  }
  if (expectedBbox !== undefined && (!Array.isArray(expectedBbox) || expectedBbox.length !== 4 ||
      !expectedBbox.every(Number.isFinite) || expectedBbox.some((value, index) => Math.abs(value - bbox[index]) > 1e-6))) {
    return {valid: false, reason: 'bbox_mismatch'};
  }
  return {valid: true, bbox, vertices};
}

function isRetired(properties) {
  const cessation = properties['edtf:cessation'];
  const deprecated = properties['edtf:deprecated'];
  return properties['mz:is_current'] === 0 || (properties['wof:superseded_by']?.length ?? 0) > 0 ||
    (typeof cessation === 'string' && /\d{4}/.test(cessation)) ||
    (typeof deprecated === 'string' && /\d{4}/.test(deprecated));
}

function resolveMunicipality(feature, localities, canonical) {
  const properties = feature.properties;
  const hierarchy = Array.isArray(properties['wof:hierarchy']) ? properties['wof:hierarchy'] : [];
  const ids = new Set(hierarchy.map(item => item?.locality_id).filter(Number.isSafeInteger));
  const parent = properties['wof:parent_id'];
  if (Number.isSafeInteger(parent) && localities.has(parent)) ids.add(parent);
  const matches = [...ids].map(id => ({id, name: localities.get(id)?.properties['wof:name']}))
    .filter(item => canonical.has(item.name));
  const names = new Set(matches.map(item => item.name));
  if (names.size !== 1) return {reason: names.size > 1 ? 'ambiguous_municipality' : 'unknown_municipality'};
  const match = matches.find(item => item.name === [...names][0]);
  return {name: match.name, localitySourceId: match.id};
}

function provenance(record) {
  const properties = record.feature.properties;
  return {provider: 'whosonfirst', url: record.sourceUrl ?? null, path: record.path,
    sha256: record.sha256, gitBlobSha: record.gitBlobSha ?? null,
    geometrySource: properties['src:geom'] ?? 'unknown',
    licenseUrl: 'https://github.com/whosonfirst-data/whosonfirst-data-admin-hu/blob/master/LICENSE.md',
    attribution: 'Data from Who’s On First; original source attribution is retained in sources/whosonfirst/LICENSE.md.',
    geometryUnmodified: true,
    geometrySha256: sha256(JSON.stringify(record.feature.geometry))};
}

/** Build a quarantined draft catalogue. Municipality identity comes from source parent records only. */
export function buildCatalog(records, canonicalSettlements) {
  const canonical = new Set(canonicalSettlements);
  const localities = new Map(records.filter(record => record.feature.properties?.['wof:placetype'] === 'locality')
    .map(record => [record.feature.properties['wof:id'], record.feature]));
  const features = [], excluded = [];
  const seen = new Set();
  let neighbourhoodRecords = 0;
  for (const record of records) {
    const feature = record.feature;
    const properties = feature.properties ?? {};
    if (properties['wof:placetype'] !== 'neighbourhood') continue;
    neighbourhoodRecords++;
    const id = properties['wof:id'];
    if (!Number.isSafeInteger(id) || id <= 0) throw new Error(`Invalid source ID in ${record.path}`);
    if (seen.has(id)) throw new Error(`Duplicate neighbourhood source ID ${id}`);
    seen.add(id);
    const preferred = properties['name:hun_x_preferred'];
    const preferredHungarianName = (Array.isArray(preferred) ? preferred.find(value => typeof value === 'string' && value.trim()) : null) ?? null;
    const primaryName = properties['wof:name'];
    // Some source translations describe a whole borough instead of this neighbourhood.
    // Restore accents/case only; a different translated identity needs manual review.
    const sameName = typeof primaryName === 'string' && preferredHungarianName &&
      normalizedName(primaryName) === normalizedName(preferredHungarianName);
    const name = sameName ? preferredHungarianName : primaryName;
    const city = resolveMunicipality(feature, localities, canonical);
    const rejected = reason => excluded.push({id: `wof:${id}`, name: name ?? null, municipality: city.name ?? null, boundaryKind: 'neighbourhood',
      geometryType: feature.geometry?.type ?? null, reason, source: provenance(record)});
    if (feature.type !== 'Feature' || typeof name !== 'string' || !name.trim()) { rejected('invalid_feature'); continue; }
    if ((properties['wof:country'] ?? properties['iso:country']) !== 'HU') { rejected('not_hungary'); continue; }
    if (isRetired(properties)) { rejected('retired_record'); continue; }
    const geometry = validateGeometry(feature.geometry, feature.bbox);
    if (!geometry.valid) { rejected(geometry.reason); continue; }
    if (city.reason) { rejected(city.reason); continue; }
    features.push({type: 'Feature', id: `wof:${id}`, bbox: geometry.bbox, properties: {
      id: `wof:${id}`, name, municipality: city.name, municipalityId: `city:${city.name}`,
      boundaryKind: 'neighbourhood',
      sourceName: primaryName, preferredHungarianName,
      nameReviewNeeded: Boolean(preferredHungarianName && !sameName),
      localitySourceId: city.localitySourceId, reviewStatus: 'unreviewed',
      usableForAddressAssignment: false, sourceIsOfficial: properties['mz:is_official'] === 1,
      sourceIsHardBoundary: properties['mz:is_hard_boundary'] === 1,
      source: provenance(record)}, geometry: feature.geometry});
  }
  return assembleCatalog(features, excluded, {sourceRecords: records.length, candidateRecords: neighbourhoodRecords,
    neighbourhoodRecords, districtRecords: 0, ignoredParentRecords: records.length - neighbourhoodRecords,
    providers: {whosonfirst: {sourceRecords: records.length, candidateRecords: neighbourhoodRecords}}});
}

function assembleCatalog(features, excluded, counts) {
  features.sort((a, b) => a.properties.municipality < b.properties.municipality ? -1 :
    a.properties.municipality > b.properties.municipality ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  excluded.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  const cityNames = sorted(new Set([...features.map(feature => feature.properties.municipality),
    ...excluded.map(item => item.municipality).filter(Boolean), ...(counts.queryResults ?? []).map(item => item.city)]));
  const cityCoverage = municipality => {
    const all = features.filter(feature => feature.properties.municipality === municipality);
    const polygons = all.filter(feature => feature.properties.boundaryKind === 'neighbourhood');
    const districtCount = all.filter(feature => feature.properties.boundaryKind === 'district').length;
    const rejected = excluded.filter(item => item.municipality === municipality);
    const pointOnlyCount = rejected.filter(item => item.reason === 'not_polygon' && item.geometryType === 'Point').length;
    return {municipality, municipalityId: `city:${municipality}`, polygonCount: polygons.length, districtCount, pointOnlyCount,
      excludedCount: rejected.length, status: polygons.length ? 'unreviewed_polygons' : districtCount ? 'district_fallback_only' : pointOnlyCount ? 'points_only' : 'no_polygon_found',
      osmQuery: counts.queryResults?.find(item => item.city === municipality) ?? {status: 'not_requested'},
      completeCoverage: false, completeness: 'not_assessed', reviewStatus: 'unreviewed', usableForAddressAssignment: false};
  };
  const municipalities = cityNames.map(cityCoverage);
  const targetCities = TARGET_CITIES.map(cityCoverage);
  const reasonCounts = {};
  for (const reason of sorted(new Set(excluded.map(item => item.reason)))) reasonCounts[reason] = excluded.filter(item => item.reason === reason).length;
  const providers = {};
  for (const [provider, metadata] of Object.entries(counts.providers)) {
    const included = features.filter(feature => feature.properties.source.provider === provider);
    providers[provider] = {...metadata, polygonCandidates: included.length,
      neighbourhoodPolygons: included.filter(feature => feature.properties.boundaryKind === 'neighbourhood').length,
      districtFallbackPolygons: included.filter(feature => feature.properties.boundaryKind === 'district').length,
      excludedRecords: excluded.filter(item => item.source.provider === provider).length};
  }
  return {
    catalog: {type: 'FeatureCollection', schemaVersion: 1, status: 'draft', reviewStatus: 'unreviewed',
      usableForAddressAssignment: false, processing: 'WOF geometries retained unchanged; OSM boundaries assembled from actual member-way vertices only. No point/bounding-box approximation, snapping, interpolation or invented closing edges. Basic ring/bounding-box checks only. City completeness, source accuracy, inter-feature/MultiPolygon component overlaps and address samples are not certified.',
      features},
    coverage: {schemaVersion: 1, status: 'draft', usableForAddressAssignment: false,
      summary: {sourceRecords: counts.sourceRecords, candidateRecords: counts.candidateRecords,
        neighbourhoodRecords: counts.neighbourhoodRecords, districtRecords: counts.districtRecords, ignoredParentRecords: counts.ignoredParentRecords,
        polygonCandidates: features.length, excludedRecords: excluded.length,
        neighbourhoodPolygons: features.filter(feature => feature.properties.boundaryKind === 'neighbourhood').length,
        districtFallbackPolygons: features.filter(feature => feature.properties.boundaryKind === 'district').length,
        municipalitiesWithPolygons: municipalities.filter(item => item.polygonCount > 0).length,
        targetCitiesWithPolygons: targetCities.filter(item => item.polygonCount > 0).length, reasons: reasonCounts, providers},
      targetCities, municipalities, excluded}
  };
}

const duplicateName = name => name.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim().replace(/\s+/g, ' ');
export function mergeCatalogs(wof, osm) {
  const currentNames = new Map(osm.features.filter(feature => feature.properties.boundaryKind === 'neighbourhood')
    .map(feature => [`${feature.properties.municipality}\0${duplicateName(feature.properties.name)}`, feature.id]));
  const features = [...osm.features], excluded = [...wof.coverage.excluded, ...osm.excluded];
  for (const feature of wof.catalog.features) {
    const shadowedBy = currentNames.get(`${feature.properties.municipality}\0${duplicateName(feature.properties.name)}`);
    if (shadowedBy) excluded.push({id: feature.id, name: feature.properties.name, municipality: feature.properties.municipality,
      boundaryKind: feature.properties.boundaryKind, geometryType: feature.geometry.type,
      reason: 'shadowed_by_current_osm', shadowedBy, source: feature.properties.source});
    else features.push(feature);
  }
  return assembleCatalog(features, excluded, {
    sourceRecords: wof.coverage.summary.sourceRecords + osm.sourceRecords,
    candidateRecords: wof.coverage.summary.candidateRecords + osm.candidateRecords,
    neighbourhoodRecords: wof.coverage.summary.neighbourhoodRecords + osm.neighbourhoodRecords,
    districtRecords: osm.districtRecords, ignoredParentRecords: wof.coverage.summary.ignoredParentRecords,
    queryResults: osm.queryResults,
    providers: {whosonfirst: wof.coverage.summary.providers.whosonfirst,
      openstreetmap: {sourceSnapshots: osm.sourceSnapshots, sourceRecords: osm.sourceRecords, candidateRecords: osm.candidateRecords}}
  });
}

async function filesBelow(directory) {
  const result = [];
  for (const entry of await readdir(directory, {withFileTypes: true})) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await filesBelow(path));
    else if (entry.isFile() && entry.name.endsWith('.geojson')) result.push(path);
  }
  return sorted(result);
}

export async function loadSources(root = ROOT) {
  const directory = join(root, 'data/neighborhoods/sources/whosonfirst');
  const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
  if (manifest.schemaVersion !== 1 || manifest.provider !== 'whosonfirst') throw new Error('Unsupported source manifest');
  const metadataEntries = [...(manifest.records ?? []), ...(manifest.parents ?? [])];
  const metadata = new Map(metadataEntries.map(item => [item.file, item]));
  if (metadata.size !== metadataEntries.length) throw new Error('Duplicate file in source manifest');
  const paths = await filesBelow(directory);
  if (paths.length !== metadata.size) throw new Error('Source manifest does not enumerate exactly the original GeoJSON files');
  const records = [];
  for (const path of paths) {
    const file = relative(directory, path).split(sep).join('/');
    const metadataEntry = metadata.get(file);
    if (!metadataEntry) throw new Error(`Unpinned source file ${file}`);
    const bytes = await readFile(path);
    const gitSha = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
    if (metadataEntry.gitBlobSha && metadataEntry.gitBlobSha !== gitSha) throw new Error(`Source git blob hash mismatch: ${file}`);
    const feature = JSON.parse(bytes);
    if (metadataEntry.id !== feature.properties?.['wof:id']) throw new Error(`Source manifest identity mismatch: ${file}`);
    records.push({feature, path: relative(root, path).split(sep).join('/'), sha256: sha256(bytes),
      gitBlobSha: metadataEntry.gitBlobSha ?? gitSha, sourceUrl: metadataEntry.sourceUrl});
  }
  return records;
}

export async function buildFiles({root = ROOT, check = false} = {}) {
  const canonical = JSON.parse(await readFile(join(root, 'dist/data/settlements.json'), 'utf8')).settlements;
  const records = await loadSources(root);
  const wof = buildCatalog(records, canonical);
  const osmSnapshots = await loadOsmSources(root);
  const result = osmSnapshots.length ? mergeCatalogs(wof, collectOsmCandidates(osmSnapshots, canonical, validateGeometry)) : wof;
  for (const [name, value] of [['catalog.geojson', result.catalog], ['coverage.json', result.coverage]]) {
    const path = join(root, 'data/neighborhoods', name);
    const content = `${JSON.stringify(value, null, 2)}\n`;
    if (check) {
      if (await readFile(path, 'utf8') !== content) throw new Error(`${name} is out of date; run node scripts/neighborhoods/build.mjs`);
    } else await writeFile(path, content);
  }
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  if (args.some(arg => arg !== '--check')) throw new Error('Usage: node scripts/neighborhoods/build.mjs [--check]');
  const {coverage} = await buildFiles({check: args.includes('--check')});
  console.log(`${args.includes('--check') ? 'Verified' : 'Built'} ${coverage.summary.polygonCandidates} unreviewed polygons; ${coverage.summary.excludedRecords} excluded records. No boundary is enabled for address assignment.`);
}
