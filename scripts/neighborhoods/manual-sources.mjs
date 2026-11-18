import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {join, relative, resolve, sep} from 'node:path';
import {gunzipSync} from 'node:zlib';

const digest = value => createHash('sha256').update(value).digest('hex');

/** Curated derived datasets only; source descriptions never generate geometry here. */
export async function loadManualSources(root, registryName = 'manual-source-registry.json') {
  if (!['manual-source-registry.json','inferred-candidate-registry.json'].includes(registryName)) throw new Error('Unknown manual registry');
  let registry;
  try { registry = JSON.parse(await readFile(join(root, 'data/neighborhoods', registryName), 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  if (registry.schemaVersion !== 1 || !Array.isArray(registry.datasets)) throw new Error('Invalid manual source registry');
  const identifiers = new Set();
  const snapshots = [];
  for (const entry of registry.datasets) {
    if (typeof entry.id !== 'string' || !entry.id || identifiers.has(entry.id)) throw new Error('Duplicate manual source identity');
    identifiers.add(entry.id);
    if (typeof entry.path !== 'string' || !/\.geojson(?:\.gz)?$/.test(entry.path) || !/^[a-f0-9]{64}$/.test(entry.sha256 ?? '')) throw new Error('Unpinned manual geometry source');
    const path = resolve(root, entry.path), directory = resolve(root, 'data/neighborhoods') + sep;
    if (!path.startsWith(directory)) throw new Error('Manual source path leaves the public data directory');
    const stored = await readFile(path);
    const bytes = entry.path.endsWith('.gz') ? gunzipSync(stored) : stored;
    if (digest(bytes) !== entry.sha256) throw new Error(`Manual source fingerprint mismatch: ${entry.id}`);
    const document = JSON.parse(bytes);
    if (document.type !== 'FeatureCollection' || !Array.isArray(document.features)) throw new Error('Manual source is not a FeatureCollection');
    snapshots.push({entry, document, path: relative(root, path).split(sep).join('/')});
  }
  return snapshots;
}

export function collectManualCandidates(snapshots, canonicalSettlements, validateGeometry) {
  const canonical = new Set(canonicalSettlements), features = [], excluded = [], identifiers = new Set();
  let sourceRecords = 0;
  for (const snapshot of snapshots) for (const [featureIndex, original] of snapshot.document.features.entries()) {
    sourceRecords++;
    const p = {...original.properties, ...snapshot.entry.propertyOverrides}, municipality = p.municipality ?? snapshot.entry.municipality;
    const sourceId = original.id ?? p.id ?? `${snapshot.entry.id}:${featureIndex}`;
    const id = String(sourceId).startsWith('manual:') ? String(sourceId) : `manual:${snapshot.entry.id}:${sourceId}`;
    if (identifiers.has(id)) throw new Error(`Duplicate manual feature identity: ${id}`);
    identifiers.add(id);
    const evidenceUrls = p.evidenceUrls ?? snapshot.entry.evidenceUrls ?? [];
    const method = p.method ?? snapshot.entry.method;
    const source = {...p.source, provider: 'manual-derived', collection: snapshot.entry.id,
      path: snapshot.path, sha256: snapshot.entry.sha256, featureId: sourceId, featureIndex,
      url: evidenceUrls[0] ?? null, evidenceUrls, method,
      sourceDocuments: p.sourceDocuments ?? snapshot.entry.sourceDocuments ?? [],
      license: p.source?.license ?? snapshot.entry.license ?? 'See cited source and construction method',
      geometrySha256: digest(JSON.stringify(original.geometry)), geometryUnmodified: true,
      processing: 'Source-based construction occurred in the cited converter; catalogue import preserves its coordinates without repair or invented closing edges.'};
    const reject = reason => excluded.push({id, name: p.name ?? null, municipality: canonical.has(municipality) ? municipality : null,
      boundaryKind: p.boundaryKind ?? 'neighbourhood', geometryType: original.geometry?.type ?? null, reason, source});
    if (!canonical.has(municipality)) { reject('manual_unknown_municipality'); continue; }
    if (original.type !== 'Feature' || typeof p.name !== 'string' || !p.name.trim()) { reject('manual_invalid_feature'); continue; }
    if (typeof method !== 'string' || !method || !Array.isArray(evidenceUrls) || !evidenceUrls.length || evidenceUrls.some(url => !/^https?:\/\//.test(url))) {
      reject('manual_missing_construction_evidence'); continue;
    }
    if (p.estimated === true || p.boundaryKind === 'inferred_area') { reject('inferred_geometry_belongs_in_separate_layer'); continue; }
    const validation = validateGeometry(original.geometry, original.bbox);
    if (!validation.valid) { reject(`manual_${validation.reason}`); continue; }
    const boundaryKind = p.boundaryKind ?? 'neighbourhood';
    if (!['neighbourhood', 'planning_unit', 'local_area'].includes(boundaryKind)) { reject('manual_unknown_semantic_level'); continue; }
    features.push({...original, id, bbox: validation.bbox, properties: {...p, id, name: p.name.trim(),
      municipality, municipalityId: `city:${municipality}`, sourceName: p.sourceName ?? p.name,
      boundaryKind, canonicalNameSupported: true,
      canonicalNameIsNeighborhood: p.canonicalNameIsNeighborhood ?? boundaryKind === 'neighbourhood',
      nameVerificationStatus: 'cited_boundary_document', geometryVerificationStatus: 'source_based_manual_construction_review_required',
      reviewStatus: 'unreviewed', sourceIsOfficial: false, sourceIsHardBoundary: false,
      usableForAddressAssignment: false, source}});
  }
  return {features, excluded, sourceRecords, candidateRecords: sourceRecords,
    neighbourhoodRecords: sourceRecords, sourceSnapshots: snapshots.length};
}
