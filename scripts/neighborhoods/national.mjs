import {createHash} from 'node:crypto';
import {readFile, readdir} from 'node:fs/promises';
import {join, relative, sep} from 'node:path';

const digest = value => createHash('sha256').update(value).digest('hex');
const sourceFiles = ['admin10.cpg', 'admin10.dbf', 'admin10.prj', 'admin10.shp', 'admin10.shx'];
const relativePath = (root, path) => relative(root, path).split(sep).join('/');

/** Read a preserved historical export, checking originals and the derived GeoJSON independently. */
export async function loadNationalSource(root, collectionDirectory = 'national-osm') {
  if (!/^national-osm(?:-\d{4})?$/.test(collectionDirectory)) throw new Error('Unsupported national source directory');
  const directory = join(root, 'data/neighborhoods/sources', collectionDirectory);
  try { await readdir(directory); } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
  if (manifest.license !== 'ODbL-1.0' || manifest.inputCrs !== 'EPSG:3857' || manifest.outputCrs !== 'EPSG:4326' ||
      !/^[a-f0-9]{40}$/.test(manifest.sourceCommit ?? '') || !Number.isFinite(Date.parse(manifest.sourceCommitDate))) {
    throw new Error('Unsupported national OSM source manifest');
  }
  const entries = manifest.sourceFiles;
  if (!Array.isArray(entries) || entries.length !== sourceFiles.length ||
      new Set(entries.map(item => item.path)).size !== sourceFiles.length ||
      sourceFiles.some(path => !entries.some(item => item.path === path))) throw new Error('National source manifest must pin every original shapefile component');
  for (const entry of entries) {
    const bytes = await readFile(join(directory, entry.path));
    const gitBlobSha1 = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
    if (bytes.length !== entry.bytes || digest(bytes) !== entry.sha256 || gitBlobSha1 !== entry.gitBlobSha1) {
      throw new Error(`National source hash mismatch: ${entry.path}`);
    }
  }
  const metadata = manifest.geojson;
  if (metadata?.path !== 'admin10.geojson' || !/^[a-f0-9]{64}$/.test(metadata.sha256 ?? '')) throw new Error('National GeoJSON fingerprint is missing');
  const path = join(directory, metadata.path), bytes = await readFile(path);
  if (bytes.length !== metadata.bytes || digest(bytes) !== metadata.sha256) throw new Error('National GeoJSON hash mismatch');
  const document = JSON.parse(bytes);
  if (document.type !== 'FeatureCollection' || !Array.isArray(document.features) || document.features.length !== manifest.featureCount ||
      manifest.records?.length !== manifest.featureCount) throw new Error('National feature inventory mismatch');
  const records = new Map(manifest.records.map(item => [item.id, item]));
  if (records.size !== document.features.length) throw new Error('Duplicate national manifest identity');
  const ids = new Set(), rows = new Set();
  for (const feature of document.features) {
    const properties = feature.properties ?? {}, record = records.get(feature.id);
    if (!record || feature.type !== 'Feature' || properties.id !== feature.id || !Number.isSafeInteger(properties.sourceRecord) ||
        properties.sourceRecord <= 0 || properties.sourceRecord !== record.record || properties.name !== record.name ||
        properties.city !== record.city || feature.geometry?.type !== record.geometryType || properties.sourceCommit !== manifest.sourceCommit ||
        properties.sourceSnapshotDate !== manifest.sourceCommitDate.slice(0, 10) || properties.adminLevel !== 10 ||
        !manifest.cities.some(item => item.city === properties.city) || ids.has(feature.id) || rows.has(properties.sourceRecord)) {
      throw new Error(`National source record identity mismatch: ${feature.id}`);
    }
    ids.add(feature.id); rows.add(properties.sourceRecord);
  }
  for (const city of manifest.cities) if (document.features.filter(feature => feature.properties.city === city.city).length !== city.neighborhoodCount) {
    throw new Error(`National city inventory mismatch: ${city.city}`);
  }
  return {manifest, document, path: relativePath(root, path), sha256: digest(bytes),
    manifestPath: relativePath(root, join(directory, 'manifest.json')),
    sourceFiles: entries.map(entry => ({...entry, path: relativePath(root, join(directory, entry.path))})),
    converterPath: relativePath(root, join(directory, 'convert.py'))};
}

/** Old actual polygons remain draft candidates; a commit date is not a geometry verification date. */
export function collectNationalCandidates(snapshot, canonicalSettlements, validateGeometry) {
  if (typeof validateGeometry !== 'function') throw new Error('Geometry validator is required');
  if (Array.isArray(snapshot)) {
    const cohorts = snapshot.map(item => collectNationalCandidates(item, canonicalSettlements, validateGeometry));
    return {features: cohorts.flatMap(item => item.features), excluded: cohorts.flatMap(item => item.excluded),
      ...Object.fromEntries(['sourceRecords', 'candidateRecords', 'neighbourhoodRecords', 'sourceSnapshots']
        .map(key => [key, cohorts.reduce((sum, item) => sum + item[key], 0)]))};
  }
  const canonical = new Set(canonicalSettlements), features = [], excluded = [];
  if (!snapshot) return {features, excluded, sourceRecords: 0, candidateRecords: 0, neighbourhoodRecords: 0, sourceSnapshots: 0};
  const {manifest} = snapshot;
  for (const feature of snapshot.document.features) {
    const properties = feature.properties ?? {}, municipality = properties.city;
    const source = {provider: 'openstreetmap', collection: 'national-osm-admin10',
      url: manifest.upstreamArchiveUrl ?? `${manifest.upstreamDirectoryUrl.replace('/tree/', '/blob/')}/admin10.shp`,
      originalDownloadUrl: manifest.originalDownloadUrl,
      path: snapshot.path, sha256: snapshot.sha256, manifestPath: snapshot.manifestPath,
      sourceRecord: properties.sourceRecord, identifierScheme: 'source_shapefile_record', osmObjectId: null,
      sourceCommit: manifest.sourceCommit, sourceCommitDate: manifest.sourceCommitDate,
      sourceArchive: manifest.archive ? {url: manifest.upstreamArchiveUrl, ...manifest.archive} : null,
      snapshotDate: manifest.sourceCommitDate.slice(0, 10), snapshotDateMeaning: 'mirror_commit_not_exact_osm_extraction',
      retrievedAt: manifest.retrievedAt, osmTimestamp: null, historical: true,
      license: manifest.license, licenseUrl: manifest.licenseUrl, attribution: manifest.attribution,
      originalFiles: snapshot.sourceFiles, inputCrs: manifest.inputCrs, outputCrs: manifest.outputCrs,
      converterPath: snapshot.converterPath, geometryUnmodified: false,
      processing: 'Original shapefile vertices transformed EPSG:3857 to EPSG:4326, rounded to 8 decimals, ring ordering/orientation normalized. No interpolated, simplified, buffered or bounding-box boundary.',
      geometrySha256: digest(JSON.stringify(feature.geometry))};
    const reject = reason => excluded.push({id: feature.id, name: properties.name ?? null,
      municipality: canonical.has(municipality) ? municipality : null, boundaryKind: 'neighbourhood',
      geometryType: feature.geometry?.type ?? null, reason, source});
    if (!canonical.has(municipality)) { reject('unknown_municipality'); continue; }
    if (feature.type !== 'Feature' || typeof properties.name !== 'string' || !properties.name.trim()) { reject('invalid_feature'); continue; }
    const validation = validateGeometry(feature.geometry, feature.bbox);
    if (!validation.valid) { reject(validation.reason); continue; }
    features.push({type: 'Feature', id: feature.id, bbox: validation.bbox,
      properties: {id: feature.id, name: properties.name, sourceName: properties.name,
        preferredHungarianName: null, nameReviewNeeded: true, nameVerificationStatus: 'not-individually-rechecked',
        geometryVerificationStatus: 'historical-not-rechecked', municipality, municipalityId: `city:${municipality}`,
        municipalityEvidence: 'source_export_inventory', boundaryKind: 'neighbourhood', adminLevel: 10,
        reviewStatus: 'unreviewed', usableForAddressAssignment: false,
        sourceIsOfficial: false, sourceIsHardBoundary: false, source}, geometry: feature.geometry});
  }
  return {features, excluded, sourceRecords: snapshot.document.features.length,
    candidateRecords: snapshot.document.features.length, neighbourhoodRecords: snapshot.document.features.length, sourceSnapshots: 1};
}
