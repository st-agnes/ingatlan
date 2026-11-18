import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {basename, join, relative, sep} from 'node:path';
import {classifyOsmBoundary} from './osm.mjs';

const digest = value => createHash('sha256').update(value).digest('hex');
const relativePath = (root, path) => relative(root, path).split(sep).join('/');
const fingerprint = value => /^[a-f0-9]{64}$/.test(value ?? '');
const empty = () => ({features: [], excluded: [], namedNodes: [], sourceRecords: 0, candidateRecords: 0,
  neighbourhoodRecords: 0, districtRecords: 0, sourceSnapshots: 0, countrySourceSnapshots: 0,
  countryCandidateRecords: 0, countryNamedNodeRecords: 0});

/** Verify every preserved country extract output, including optional gzip storage. */
export async function loadCountrySource(root) {
  const directory = join(root, 'data/neighborhoods/sources/country-osm');
  const manifestPath = join(directory, 'manifest.json');
  let manifest;
  try { manifest = JSON.parse(await readFile(manifestPath, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  if (manifest.version !== 1 || manifest.license !== 'ODbL-1.0' ||
      !fingerprint(manifest.input?.sha256) || !Number.isSafeInteger(manifest.input?.bytes) || manifest.input.bytes <= 0 ||
      !Array.isArray(manifest.outputs) || !manifest.counts) throw new Error('Unsupported country OSM source manifest');
  const names = new Set(), files = new Map();
  for (const entry of manifest.outputs) {
    if (typeof entry.file !== 'string' || entry.file !== basename(entry.file) ||
        !/^[a-z][a-z-]*\.(?:geojson|json)$/.test(entry.file) || names.has(entry.file) ||
        !fingerprint(entry.sha256) || !Number.isSafeInteger(entry.bytes) || entry.bytes <= 0) {
      throw new Error('Invalid country output fingerprint');
    }
    names.add(entry.file);
    let path = join(directory, entry.file), stored;
    try { stored = await readFile(path); }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      path += '.gz';
      stored = await readFile(path);
    }
    const bytes = path.endsWith('.gz') ? gunzipSync(stored) : stored;
    if (bytes.length !== entry.bytes || digest(bytes) !== entry.sha256) throw new Error(`Country source hash mismatch: ${entry.file}`);
    files.set(entry.file, {path: relativePath(root, path), sha256: digest(stored), rawSha256: entry.sha256,
      bytes: stored.length, rawBytes: bytes.length,
      ...(entry.file === 'polygons.geojson' || entry.file === 'named-nodes.geojson' || entry.file === 'audit.json' ?
        {document: JSON.parse(bytes)} : {})});
  }
  for (const filename of ['polygons.geojson', 'named-nodes.geojson', 'municipalities.geojson', 'audit.json']) {
    if (!files.has(filename)) throw new Error(`Missing country output: ${filename}`);
  }
  const polygons = files.get('polygons.geojson'), nodes = files.get('named-nodes.geojson'), audit = files.get('audit.json').document;
  if (polygons.document.type !== 'FeatureCollection' || !Array.isArray(polygons.document.features) ||
      nodes.document.type !== 'FeatureCollection' || !Array.isArray(nodes.document.features) ||
      polygons.document.features.length !== manifest.counts.polygons || nodes.document.features.length !== manifest.counts.namedNodes ||
      !Array.isArray(audit.rejectedCandidates) || audit.rejectedCandidates.length !== manifest.counts.rejectedPolygonCandidates ||
      manifest.counts.sourcePolygonCandidates !== polygons.document.features.length + audit.rejectedCandidates.length) {
    throw new Error('Country feature inventory mismatch');
  }
  return {manifest, document: polygons.document, namedNodes: nodes.document, audit,
    path: polygons.path, sha256: polygons.sha256, rawSha256: polygons.rawSha256,
    nodePath: nodes.path, nodeSha256: nodes.sha256, nodeRawSha256: nodes.rawSha256,
    manifestPath: relativePath(root, manifestPath), sourceFiles: [...files].map(([file, value]) => ({file,
      path: value.path, sha256: value.sha256, rawSha256: value.rawSha256, bytes: value.bytes, rawBytes: value.rawBytes}))};
}

function provenance(snapshot, original, geometry, node = false) {
  return {...original, provider: 'openstreetmap', collection: 'country-osm',
    path: node ? snapshot.nodePath : snapshot.path, sha256: node ? snapshot.nodeSha256 : snapshot.sha256,
    rawSha256: node ? snapshot.nodeRawSha256 : snapshot.rawSha256,
    manifestPath: snapshot.manifestPath, pbfSha256: snapshot.manifest.input.sha256,
    pbfBytes: snapshot.manifest.input.bytes,
    osmTimestamp: snapshot.manifest.input.header?.osmosis_replication_timestamp ?? original?.osmTimestamp ?? null,
    countryAcquisition: snapshot.manifest.input.acquisition ?? null,
    geometryUnmodified: true, extractionGeometrySha256: original?.geometrySha256 ?? null,
    geometrySha256: geometry ? digest(JSON.stringify(geometry)) : null,
    license: 'ODbL-1.0', licenseUrl: 'https://opendatacommons.org/licenses/odbl/1-0/',
    attribution: '© OpenStreetMap contributors', attributionUrl: 'https://www.openstreetmap.org/copyright'};
}

/** Points remain inventory/exclusions. Only verified source containment admits polygons. */
export function collectCountryCandidates(snapshot, canonicalSettlements, validateGeometry) {
  if (typeof validateGeometry !== 'function') throw new Error('Geometry validator is required');
  if (!snapshot) return empty();
  const canonical = new Set(canonicalSettlements), features = [], excluded = [], seen = new Set();
  const nodes = Array.isArray(snapshot.namedNodes) ? snapshot.namedNodes : snapshot.namedNodes?.features ?? [];
  const sourceIdentity = (feature, allowedTypes) => {
    const source = feature.properties?.source, match = /^osm:(node|way|relation):([1-9]\d*)$/.exec(feature.id ?? '');
    return match && allowedTypes.includes(match[1]) && source?.osmType === match[1] &&
      Number.isSafeInteger(source.osmId) && source.osmId === Number(match[2]) &&
      source.pbfSha256 === snapshot.manifest.input.sha256;
  };
  const reject = (feature, reason, node = false, extra = {}) => excluded.push({id: feature.id,
    name: feature.properties?.name ?? feature.name ?? null,
    municipality: canonical.has(feature.properties?.municipality) ? feature.properties.municipality : null,
    boundaryKind: node ? 'neighbourhood' : feature.properties?.boundaryKind ?? 'neighbourhood',
    geometryType: feature.geometry?.type ?? null, reason,
    source: provenance(snapshot, feature.properties?.source ?? feature.source, feature.geometry, node), ...extra});
  let neighbourhoodRecords = 0, districtRecords = 0;
  for (const original of snapshot.document.features) {
    const properties = original.properties ?? {};
    const kind = classifyOsmBoundary(properties.source?.tags, properties.municipality);
    if (kind?.boundaryKind === 'district') districtRecords++; else neighbourhoodRecords++;
    if (!sourceIdentity(original, ['way', 'relation']) || seen.has(original.id)) throw new Error(`Country source identity mismatch: ${original.id}`);
    seen.add(original.id);
    if (!kind || original.type !== 'Feature' || typeof properties.name !== 'string' || !properties.name.trim()) {
      reject(original, 'invalid_country_feature'); continue;
    }
    if (!properties.municipality || !['source_full_containment', 'source_subarea_hierarchy_and_full_containment'].includes(properties.municipalityEvidence)) {
      reject(original, 'country_unresolved_municipality', false, {municipalityEvidence: properties.municipalityEvidence ?? null}); continue;
    }
    if (!canonical.has(properties.municipality) || properties.municipalityId !== `city:${properties.municipality}`) {
      reject(original, 'unknown_municipality'); continue;
    }
    if (properties.coveringMunicipalityOsmIds?.length !== 1 ||
        properties.coveringMunicipalityOsmIds[0] !== properties.municipalityOsmId) {
      reject(original, 'country_inconsistent_containment_evidence'); continue;
    }
    const validation = validateGeometry(original.geometry, original.bbox);
    if (!validation.valid) { reject(original, validation.reason); continue; }
    features.push({...original, bbox: validation.bbox, properties: {...properties, id: original.id, ...kind,
      nameReviewNeeded: true, nameVerificationStatus: 'source_label_not_individually_rechecked',
      geometryVerificationStatus: 'same_snapshot_municipal_containment', reviewStatus: 'unreviewed',
      usableForAddressAssignment: false, sourceIsOfficial: false, sourceIsHardBoundary: false,
      source: provenance(snapshot, properties.source, original.geometry)}});
  }
  for (const record of snapshot.audit?.rejectedCandidates ?? []) {
    const original = {id: record.id, properties: {name: record.name, source: record.source}};
    if (!sourceIdentity(original, ['way', 'relation']) || seen.has(record.id)) throw new Error(`Country rejected-source identity mismatch: ${record.id}`);
    seen.add(record.id);
    const kind = classifyOsmBoundary(record.source?.tags);
    if (kind?.boundaryKind === 'district') districtRecords++; else neighbourhoodRecords++;
    reject(original, record.reason ?? 'no_valid_assembled_source_polygon');
  }
  for (const original of nodes) {
    neighbourhoodRecords++;
    if (!sourceIdentity(original, ['node']) || seen.has(original.id) || original.geometry?.type !== 'Point') {
      throw new Error(`Country named-node identity mismatch: ${original.id}`);
    }
    seen.add(original.id);
    reject(original, 'not_polygon', true);
  }
  const candidateRecords = snapshot.document.features.length + (snapshot.audit?.rejectedCandidates?.length ?? 0) + nodes.length;
  return {features, excluded, namedNodes: nodes, sourceRecords: candidateRecords, candidateRecords,
    neighbourhoodRecords, districtRecords, sourceSnapshots: 1, countrySourceSnapshots: 1,
    countryCandidateRecords: candidateRecords, countryNamedNodeRecords: nodes.length,
    countryInputRecords: Object.entries(snapshot.manifest.counts).filter(([key]) => /Read$/.test(key)).reduce((sum, [, value]) => sum + value, 0)};
}

/** Merge actual OSM identities before name dedupe; audits stay bound to their original city source. */
export function mergeCurrentOsmSources(city, country) {
  const result = {...city, features: [], excluded: [...city.excluded, ...country.excluded],
    namedNodes: country.namedNodes, queryResults: city.queryResults};
  const groups = new Map();
  for (const [cohort, features] of [['city', city.features], ['country', country.features]]) {
    for (const feature of features) {
      const group = groups.get(feature.id) ?? [];
      group.push({cohort, feature}); groups.set(feature.id, group);
    }
  }
  const timestamp = value => {
    const parsed = Date.parse(value.feature.properties.source.osmTimestamp);
    return Number.isFinite(parsed) ? parsed : -Infinity;
  };
  for (const group of groups.values()) {
    group.sort((a, b) => timestamp(b) - timestamp(a) || Number(b.cohort === 'country') - Number(a.cohort === 'country'));
    const winner = group[0];
    result.features.push(winner.feature);
    for (const {feature} of group.slice(1)) result.excluded.push({id: feature.id, name: feature.properties.name,
      municipality: feature.properties.municipality, boundaryKind: feature.properties.boundaryKind,
      geometryType: feature.geometry.type, reason: winner.cohort === 'country' ? 'superseded_by_country_osm' : 'superseded_by_newer_city_osm',
      shadowedBy: winner.feature.id, source: feature.properties.source,
      ...(feature.properties.sourceAssociationAudit ? {sourceAssociationAudit: feature.properties.sourceAssociationAudit} : {})});
  }
  // Same-name dedupe in mergeCatalogs uses input ordering. Put fresh country
  // geometry ahead of older city snapshots while retaining distinct OSM IDs.
  result.features.sort((a, b) => {
    const aTime = Date.parse(a.properties.source.osmTimestamp), bTime = Date.parse(b.properties.source.osmTimestamp);
    return (Number.isFinite(bTime) ? bTime : -Infinity) - (Number.isFinite(aTime) ? aTime : -Infinity) ||
      Number(b.properties.source.collection === 'country-osm') - Number(a.properties.source.collection === 'country-osm') || a.id.localeCompare(b.id, 'en');
  });
  for (const key of ['sourceRecords', 'candidateRecords', 'neighbourhoodRecords', 'districtRecords', 'sourceSnapshots']) {
    result[key] = (city[key] ?? 0) + (country[key] ?? 0);
  }
  result.countrySourceSnapshots = country.countrySourceSnapshots ?? 0;
  result.countryCandidateRecords = country.countryCandidateRecords ?? 0;
  result.countryNamedNodeRecords = country.countryNamedNodeRecords ?? 0;
  return result;
}
