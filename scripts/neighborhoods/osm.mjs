import {createHash} from 'node:crypto';
import {readFile, readdir} from 'node:fs/promises';
import {basename, join, relative, sep} from 'node:path';

const digest = value => createHash('sha256').update(value).digest('hex');
const equalPoint = (a, b) => a[0] === b[0] && a[1] === b[1];
const supportedPlaces = new Set(['suburb', 'neighbourhood', 'quarter']);
const boundaryRoles = new Set(['', 'outer', 'inner']);

function position(value) {
  if (!value || !Number.isFinite(value.lon) || !Number.isFinite(value.lat) ||
      Math.abs(value.lon) > 180 || Math.abs(value.lat) > 90) throw new Error('missing_member_geometry');
  return [value.lon, value.lat];
}

function segment(way, elements, ref = way.id) {
  const stored = elements.get(`way:${ref}`);
  const source = Array.isArray(way.geometry) ? way : stored ?? way;
  const nodes = Array.isArray(source.nodes) ? source.nodes : stored?.nodes;
  let points;
  if (Array.isArray(source.geometry)) points = source.geometry.map(position);
  else if (Array.isArray(nodes)) points = nodes.map(id => position(elements.get(`node:${id}`)));
  else throw new Error('missing_member_geometry');
  if (points.length < 2) throw new Error('short_member_geometry');
  if (Array.isArray(nodes) && nodes.length !== points.length) throw new Error('member_node_geometry_mismatch');
  return {ref, points, nodes};
}

function equalEndpoint(a, aIndex, b, bIndex) {
  const aNode = a.nodes?.[aIndex], bNode = b.nodes?.[bIndex];
  if (aNode !== undefined && bNode !== undefined && aNode !== bNode) return false;
  return equalPoint(a.points[aIndex], b.points[bIndex]);
}

/** Connect only endpoints actually present in OSM; never snap or invent a closing segment. */
export function stitchRings(input) {
  const remaining = input.map(item => ({...item, points: item.points.map(point => [...point]), nodes: item.nodes ? [...item.nodes] : undefined}));
  const rings = [];
  while (remaining.length) {
    const current = remaining.shift();
    const first = {points: [current.points[0]], nodes: current.nodes ? [current.nodes[0]] : undefined};
    while (!equalEndpoint(current, current.points.length - 1, first, 0)) {
      const matches = [];
      for (let index = 0; index < remaining.length; index++) {
        const next = remaining[index];
        if (equalEndpoint(current, current.points.length - 1, next, 0)) matches.push({index, reverse: false});
        if (equalEndpoint(current, current.points.length - 1, next, next.points.length - 1)) matches.push({index, reverse: true});
      }
      if (!matches.length) throw new Error('unclosed_member_ring');
      if (matches.length !== 1) throw new Error('ambiguous_member_join');
      const {index, reverse} = matches[0];
      const next = remaining.splice(index, 1)[0];
      if (reverse) { next.points.reverse(); next.nodes?.reverse(); }
      current.points.push(...next.points.slice(1));
      // Missing node identities stay unknown. Matching coordinates remain exact.
      if (current.nodes || next.nodes) {
        current.nodes ??= Array(current.points.length - next.points.length + 1).fill(undefined);
        current.nodes.push(...(next.nodes ?? Array(next.points.length).fill(undefined)).slice(1));
      }
    }
    rings.push(current.points);
  }
  return rings;
}

function contains(point, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length - 1; j = i++) {
    const a = ring[i], b = ring[j];
    const cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]);
    if (Math.abs(cross) <= 1e-12 && point[0] >= Math.min(a[0], b[0]) && point[0] <= Math.max(a[0], b[0]) &&
        point[1] >= Math.min(a[1], b[1]) && point[1] <= Math.max(a[1], b[1])) return false;
    if ((a[1] > point[1]) !== (b[1] > point[1]) &&
        point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

/** Decode a closed OSM way or a complete boundary/multipolygon relation. */
export function osmGeometry(element, elements = new Map()) {
  if (element.type === 'way') {
    const way = segment(element, elements);
    if (!equalEndpoint(way, 0, way, way.points.length - 1)) throw new Error('unclosed_way');
    return {type: 'Polygon', coordinates: [way.points]};
  }
  if (element.type !== 'relation') throw new Error('not_polygon');
  if (!['boundary', 'multipolygon'].includes(element.tags?.type)) throw new Error('unsupported_relation_type');
  if (!Array.isArray(element.members) || !element.members.length) throw new Error('missing_members');
  const outers = [], inners = [], seen = new Set();
  for (const member of element.members) {
    const role = member.role ?? '';
    if (['label', 'admin_centre', 'admin_center', 'subarea'].includes(role)) continue;
    if (!boundaryRoles.has(role)) throw new Error('unsupported_member_role');
    if (member.type === 'relation') throw new Error('unsupported_boundary_subrelation');
    if (member.type !== 'way') throw new Error('unsupported_boundary_member');
    if (seen.has(member.ref)) throw new Error('duplicate_boundary_member');
    seen.add(member.ref);
    const part = segment(member, elements, member.ref);
    (role === 'inner' ? inners : outers).push(part);
  }
  if (!outers.length) throw new Error('missing_outer_ring');
  const polygons = stitchRings(outers).map(ring => [ring]);
  for (let i = 0; i < polygons.length; i++) {
    for (let j = i + 1; j < polygons.length; j++) {
      if (polygons[i][0].some(point => contains(point, polygons[j][0])) ||
          polygons[j][0].some(point => contains(point, polygons[i][0]))) throw new Error('nested_outer_rings');
    }
  }
  for (const hole of stitchRings(inners)) {
    const containing = polygons.filter(polygon => contains(hole[0], polygon[0]));
    if (containing.length !== 1) throw new Error(containing.length ? 'ambiguous_inner_ring' : 'unassigned_inner_ring');
    containing[0].push(hole);
  }
  return polygons.length === 1 ? {type: 'Polygon', coordinates: polygons[0]} : {type: 'MultiPolygon', coordinates: polygons};
}

export function classifyOsmBoundary(tags, municipality) {
  if (!tags || (!supportedPlaces.has(tags.place) && tags.boundary !== 'administrative')) return null;
  if (municipality === 'Budapest' && tags.admin_level === '9') {
    return {boundaryKind: 'district', classificationReason: 'budapest_admin_9'};
  }
  if (supportedPlaces.has(tags.place)) return {boundaryKind: 'neighbourhood', classificationReason: `place_${tags.place}`};
  if (['10', '11'].includes(tags.admin_level)) return {boundaryKind: 'neighbourhood', classificationReason: `admin_${tags.admin_level}`};
  return {boundaryKind: 'district', classificationReason: 'administrative_fallback'};
}

function provenance(snapshot, element, geometry) {
  const manifest = snapshot.manifest;
  return {provider: 'openstreetmap', url: `https://www.openstreetmap.org/${element.type}/${element.id}`,
    path: snapshot.path, rawPath: snapshot.path, sha256: snapshot.sha256, rawSha256: snapshot.sha256,
    geometrySource: 'openstreetmap', osmTimestamp: manifest.osmTimestamp ?? snapshot.document.osm3s?.timestamp_osm_base ?? null,
    objectVersion: element.version ?? null, endpoint: manifest.endpoint ?? null, query: manifest.query ?? null,
    license: 'ODbL-1.0', licenseUrl: 'https://opendatacommons.org/licenses/odbl/1-0/',
    attribution: '© OpenStreetMap contributors', attributionUrl: 'https://www.openstreetmap.org/copyright',
    geometryUnmodified: false,
    geometryProcessing: 'Actual OSM way vertices assembled with endpoint joins and reversal only; no snapping, simplification, interpolation or invented closing edge.',
    geometrySha256: geometry ? digest(JSON.stringify(geometry)) : null};
}

/** Source city is the explicitly queried canonical city, not inferred from a centroid or name. */
export function collectOsmCandidates(snapshots, canonicalSettlements, validateGeometry) {
  if (typeof validateGeometry !== 'function') throw new Error('Geometry validator is required');
  const canonical = new Set(canonicalSettlements);
  const accepted = [], excluded = [], occurrence = new Map();
  let candidateRecords = 0, neighbourhoodRecords = 0, districtRecords = 0;
  for (const snapshot of snapshots) {
    const municipality = snapshot.manifest.city;
    const elements = new Map();
    let conflictingIdentity = false;
    for (const element of snapshot.document.elements) {
      const key = `${element.type}:${element.id}`;
      if (elements.has(key) && JSON.stringify(elements.get(key)) !== JSON.stringify(element)) conflictingIdentity = true;
      else elements.set(key, element);
    }
    const seen = new Set();
    for (const element of snapshot.document.elements) {
      // The collector emits the city relation as tags/center for source context, not as a candidate.
      if (element.type === 'relation' && element.id === snapshot.manifest.municipalityRelationId) continue;
      const classification = classifyOsmBoundary(element.tags, municipality);
      const name = element.tags?.['name:hu'] || element.tags?.name;
      if (!classification || typeof name !== 'string' || !name.trim()) continue;
      candidateRecords++;
      if (classification.boundaryKind === 'neighbourhood') neighbourhoodRecords++; else districtRecords++;
      const id = `osm:${element.type}:${element.id}`;
      const reject = reason => excluded.push({id, name, municipality: canonical.has(municipality) ? municipality : null,
        boundaryKind: classification.boundaryKind, geometryType: element.type === 'node' ? 'Point' : null,
        reason, source: provenance(snapshot, element)});
      if (!Number.isSafeInteger(element.id) || element.id <= 0 || !['node', 'way', 'relation'].includes(element.type)) { reject('invalid_osm_identity'); continue; }
      if (seen.has(id)) { reject('duplicate_osm_element'); continue; }
      seen.add(id);
      if (conflictingIdentity) { reject('conflicting_osm_identity'); continue; }
      if (!canonical.has(municipality)) { reject('unknown_municipality'); continue; }
      if (element.visible === false) { reject('deleted_osm_element'); continue; }
      let geometry;
      try { geometry = osmGeometry(element, elements); }
      catch (error) { reject(error.message); continue; }
      const validation = validateGeometry(geometry);
      if (!validation.valid) { reject(validation.reason); continue; }
      const feature = {type: 'Feature', id, bbox: validation.bbox, properties: {
        id, name, sourceName: element.tags.name ?? name, preferredHungarianName: element.tags['name:hu'] ?? null,
        nameReviewNeeded: false, municipality, municipalityId: `city:${municipality}`,
        municipalityEvidence: 'canonical_query_context', boundaryKind: classification.boundaryKind,
        classificationReason: classification.classificationReason, adminLevel: element.tags.admin_level ?? null,
        reviewStatus: 'unreviewed', usableForAddressAssignment: false, sourceIsOfficial: false, sourceIsHardBoundary: false,
        source: provenance(snapshot, element, geometry)}, geometry};
      accepted.push(feature);
      const contexts = occurrence.get(id) ?? new Set();
      contexts.add(municipality); occurrence.set(id, contexts);
    }
  }
  const features = [], grouped = new Map();
  for (const feature of accepted) {
    const group = grouped.get(feature.id) ?? [];
    group.push(feature); grouped.set(feature.id, group);
  }
  const signature = feature => digest(JSON.stringify([feature.properties.name, feature.properties.boundaryKind,
    feature.properties.adminLevel, feature.geometry]));
  const rejectedFeature = (feature, reason) => excluded.push({id: feature.id, name: feature.properties.name,
    municipality: feature.properties.municipality, boundaryKind: feature.properties.boundaryKind,
    geometryType: feature.geometry.type, reason, source: feature.properties.source});
  for (const [id, group] of grouped) {
    if (occurrence.get(id).size > 1) { group.forEach(feature => rejectedFeature(feature, 'ambiguous_municipality_context')); continue; }
    if (group.length === 1) { features.push(group[0]); continue; }
    const signatures = new Set(group.map(signature));
    const timestamps = group.map(feature => Date.parse(feature.properties.source.osmTimestamp));
    if (signatures.size > 1 && !timestamps.every(Number.isFinite)) {
      group.forEach(feature => rejectedFeature(feature, 'conflicting_osm_snapshots')); continue;
    }
    const newest = Math.max(...timestamps.filter(Number.isFinite));
    const latest = Number.isFinite(newest) ? group.filter((_, index) => timestamps[index] === newest) : group;
    if (new Set(latest.map(signature)).size > 1) {
      group.forEach(feature => rejectedFeature(feature, 'conflicting_osm_snapshots')); continue;
    }
    const winner = latest[0];
    features.push(winner);
    for (const feature of group) if (feature !== winner) rejectedFeature(feature,
      signature(feature) === signature(winner) ? 'duplicate_osm_snapshot' : 'superseded_osm_snapshot');
  }
  return {features, excluded, sourceRecords: snapshots.reduce((sum, snapshot) => sum + snapshot.document.elements.length, 0),
    candidateRecords, neighbourhoodRecords, districtRecords, sourceSnapshots: snapshots.length,
    queryResults: (snapshots.queryResults ?? snapshots.map(snapshot => ({city: snapshot.manifest.city,
      status: snapshot.manifest.status ?? 'downloaded', osmTimestamp: snapshot.manifest.osmTimestamp ?? null}))).filter(item => canonical.has(item.city))};
}

/** Local, hash-pinned Overpass snapshots only. Missing directory means no OSM cohort yet. */
export async function loadOsmSources(root) {
  const directory = join(root, 'data/neighborhoods/sources/openstreetmap');
  let entries;
  try { entries = await readdir(directory, {withFileTypes: true}); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const snapshots = [];
  const usedFiles = new Set();
  for (const entry of entries.filter(item => item.isFile() && item.name.endsWith('.source.json')).sort((a, b) => a.name.localeCompare(b.name, 'en'))) {
    const manifest = JSON.parse(await readFile(join(directory, entry.name), 'utf8'));
    const file = manifest.file ?? manifest.rawFile ?? entry.name.replace(/\.source\.json$/, '.json');
    if (typeof file !== 'string' || file !== basename(file) || !file.endsWith('.json')) throw new Error(`Invalid OSM snapshot path in ${entry.name}`);
    if (usedFiles.has(file)) throw new Error(`Duplicate OSM source manifest for ${file}`);
    usedFiles.add(file);
    if (!/^[a-f0-9]{64}$/.test(manifest.sha256 ?? '')) throw new Error(`Missing OSM source fingerprint in ${entry.name}`);
    const bytes = await readFile(join(directory, file));
    const sha256 = digest(bytes);
    if (sha256 !== manifest.sha256) throw new Error(`OSM source SHA256 mismatch: ${file}`);
    const document = JSON.parse(bytes);
    if (!Array.isArray(document.elements)) throw new Error(`Missing OSM elements: ${file}`);
    if (document.remark) throw new Error(`Overpass returned an incomplete/error response: ${file}`);
    if (manifest.municipalityRelationId !== undefined) {
      const context = document.elements.find(element => element.type === 'relation' && element.id === manifest.municipalityRelationId);
      const expectedLevel = String(manifest.municipalityAdminLevel ?? '8');
      if (!context || context.tags?.name !== manifest.city || context.tags?.admin_level !== expectedLevel) throw new Error(`OSM municipality context mismatch: ${file}`);
    }
    snapshots.push({manifest, document, sha256, path: relative(root, join(directory, file)).split(sep).join('/')});
  }
  const rawFiles = entries.filter(item => item.isFile() && item.name.endsWith('.json') &&
    !item.name.endsWith('.source.json') && item.name !== 'summary.json');
  if (rawFiles.length !== snapshots.length || rawFiles.some(entry => !usedFiles.has(entry.name))) throw new Error('OSM snapshot/source manifest mismatch');
  let summary;
  try { summary = JSON.parse(await readFile(join(directory, 'summary.json'), 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const queryResults = snapshots.map(snapshot => ({city: snapshot.manifest.city,
    status: snapshot.manifest.status ?? 'downloaded', osmTimestamp: snapshot.manifest.osmTimestamp ?? null}));
  if (summary) {
    if (summary.schemaVersion !== 1 || summary.provider !== 'openstreetmap' || !Array.isArray(summary.results)) throw new Error('Unsupported OSM collection summary');
    for (const result of summary.results) {
      const loaded = snapshots.find(snapshot => snapshot.manifest.city === result.city);
      if (result.status === 'downloaded' && (!loaded || result.sha256 !== loaded.sha256)) throw new Error(`OSM summary snapshot mismatch: ${result.city}`);
      const index = queryResults.findIndex(item => item.city === result.city);
      const value = {city: result.city, status: result.status, reason: result.reason ?? null,
        osmTimestamp: loaded?.manifest.osmTimestamp ?? null};
      if (index < 0) queryResults.push(value); else queryResults[index] = value;
    }
  }
  Object.defineProperty(snapshots, 'queryResults', {value: queryResults});
  return snapshots;
}
