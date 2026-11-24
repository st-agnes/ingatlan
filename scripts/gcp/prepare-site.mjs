import {cp, lstat, mkdir, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {dirname, extname, join, resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';

const projectRoot = fileURLToPath(new URL('../../', import.meta.url));
const expected = {
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev'
};
const assetExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.ico', '.woff', '.woff2']);
const codeFiles = new Set(['index.html', 'app.js', 'attribute-card-art.js', 'contact-policy.js', 'style.css', 'api.js', 'model.js', 'matching.js', 'public-profile.js', 'feedback.js', 'onboarding.js', 'locations.js', 'locations-data.js', 'agglomerations-data.js', 'neighborhoods-data.js', 'neighborhood-demo-points.js', 'street-demo-data.js', 'data/streets.json.gz', 'regions-data.js', 'attributes.js', 'accounts.js', 'runtime-config.js', 'data/settlements.json', 'data/agglomerations.json', 'THIRD-PARTY-NOTICES.txt']);
for (const file of ['location-map.js', 'location-map.css', 'data/map/index.json', 'data/map/hierarchy.json', 'data/map/labels.json', 'data/map/style.json', 'vendor/maplibre/maplibre-gl.mjs', 'vendor/maplibre/maplibre-gl-worker.mjs', 'vendor/maplibre/maplibre-gl.css', 'vendor/maplibre/LICENSE.txt', 'vendor/maplibre/provenance.json']) codeFiles.add(file);
// Old vendored assets may remain during the renderer transition, but the new
// map cannot be published with a missing module, worker, stylesheet or licence.
const optionalCodeFiles = new Set(['vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css', 'vendor/leaflet/LICENSE']);
const mapCityFile = /^data\/map\/city-[a-f0-9]{20}\.json$/;
const mapTownFile = /^data\/map\/town-[a-f0-9]{20}\.json$/;
// Verified from the integrity-checked public npm 6.19.0 archive. Pin the bytes
// independently of provenance.json so editing a module and its manifest together
// cannot accidentally publish an unreviewed renderer/worker combination.
const mapLibreRelease = Object.freeze({
  package: 'maplibre-gl', version: '6.19.0', registry: 'https://registry.npmjs.org/maplibre-gl/6.19.0',
  integrity: 'sha512-3bOrnfddggUYudLGJFsYFvqulUyvSxy4iQzd/uURI7ZhgYEZifdSrECujRSghaCpc+v/ZsFI0Y6ZsGSilEtE+w==',
  tarballSha256: '8a0648e7a1f3baf757f3a9d994c3fdc7383ea0ebfc52ce1e90f3e7264dc9a20f',
  files: {
    'maplibre-gl.mjs': {bytes:1106041,sha256:'01590c9875ea5bb0e8cdc534479f607f7d1695ca5debbccaf730edf5fa5f39e5'},
    'maplibre-gl-worker.mjs': {bytes:550754,sha256:'c8564c4a4147326a587c9cc4c2a871c4b02a6c37c3f1ea51da55be3220d4b112'},
    'maplibre-gl.css': {bytes:71596,sha256:'a90798a1953017790e590f7e1bd35ff103a8a4263972cb47290b78adf86f8c20'},
    'LICENSE.txt': {bytes:5984,sha256:'ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2'}
  }
});
const configFields = new Set(['projectId', 'projectNumber', 'region', 'serviceName', 'registry', 'sqlInstance', 'connectionName', 'databaseName', 'databaseUser', 'mysqlSecret', 'jwtSecret', 'googleGeocodingSecret', 'siteId', 'runtimeServiceAccount', 'deployServiceAccount', 'workloadIdentityProvider']);

/** Validate every resource selector before any cloud or filesystem mutation. */
export function validateDevConfig(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('A development config object is required.');
  if (Object.keys(input).some(key => !configFields.has(key))) throw new Error('The development manifest contains an unexpected field; credentials must not be included.');
  const config = {...input};
  if (!/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(config.projectId ?? '')) throw new Error('Invalid GCP projectId.');
  if (!/^[1-9][0-9]{5,19}$/.test(String(config.projectNumber ?? ''))) throw new Error('Invalid GCP projectNumber.');
  config.projectNumber = String(config.projectNumber);
  if (config.region !== 'europe-west1') throw new Error('This test deployment is configured for europe-west1.');
  for (const [field, value] of Object.entries(expected)) {
    if (config[field] !== value) throw new Error(`Only the test ${field} (${value}) may be deployed.`);
  }
  if (Object.hasOwn(config, 'googleGeocodingSecret') && config.googleGeocodingSecret !== 'otthonra-geocoding-dev') {
    throw new Error('The optional googleGeocodingSecret must name otthonra-geocoding-dev; API keys must stay in Secret Manager.');
  }
  if (config.databaseName !== 'otthonra_dev' || config.databaseUser !== 'otthonra_dev') throw new Error('Only the test database and user may be deployed.');
  if (config.connectionName !== `${config.projectId}:${config.region}:${config.sqlInstance}`) throw new Error('Cloud SQL connectionName does not match the test instance.');
  if (config.siteId !== `otthonra-dev-${config.projectNumber}` || config.siteId.length > 30) throw new Error('Only this project’s otthonra-dev Hosting site may be deployed.');
  const account = role => `otthonra-${role}-dev@${config.projectId}.iam.gserviceaccount.com`;
  if (config.runtimeServiceAccount !== account('runtime') || config.deployServiceAccount !== account('deploy')) throw new Error('Unexpected development service account.');
  if (config.workloadIdentityProvider !== `projects/${config.projectNumber}/locations/global/workloadIdentityPools/otthonra-dev/providers/github`) throw new Error('Unexpected development Workload Identity provider.');
  return config;
}

export async function readDevConfig(path) {
  return validateDevConfig(JSON.parse(await readFile(path, 'utf8')));
}

export function hostingConfig(config) {
  config = validateDevConfig(config);
  return {hosting: {
    site: config.siteId,
    public: 'public',
    ignore: ['firebase.json', '**/.*', '**/node_modules/**'],
    headers: [{source: '**', headers: [
      {key: 'Cache-Control', value: 'no-store'},
      {key: 'X-Content-Type-Options', value: 'nosniff'},
      {key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin'},
      {key: 'X-Robots-Tag', value: 'noindex, nofollow'}
    ]}, {source: '**/*.mjs', headers: [
      {key: 'Content-Type', value: 'text/javascript; charset=utf-8'}
    ]}],
    // Firebase CLI 14.17.0 pins each rewrite independently and updates duplicate
    // services concurrently. One regex covers both /api and its descendants,
    // avoiding conflicting replacements of the same Cloud Run service.
    rewrites: [{regex: '^/api(/.*)?$', run: {
      serviceId: config.serviceName, region: config.region, pinTag: true
    }}]
  }};
}

async function collectFiles(directory, relative = '') {
  const result = [];
  for (const name of await readdir(directory)) {
    const path = join(directory, name), key = relative ? `${relative}/${name}` : name;
    const details = await lstat(path);
    if (details.isSymbolicLink()) throw new Error(`A symlink cannot be published: ${key}`);
    if (name.startsWith('.')) throw new Error(`A hidden file cannot be published: ${key}`);
    if (details.isDirectory()) result.push(...await collectFiles(path, key));
    else if (details.isFile()) {
      // Exact search boundaries remain server-only; map layers are separate,
      // simplified and content-addressed city files loaded by the viewport.
      if (key === 'data/neighborhoods.json.gz') continue;
      if (!codeFiles.has(key) && !optionalCodeFiles.has(key) && !mapCityFile.test(key) && !mapTownFile.test(key) && !(key.startsWith('assets/') && assetExtensions.has(extname(name).toLowerCase()))) throw new Error(`Unexpected frontend file; refusing to publish: ${key}`);
      result.push({path, key});
    } else throw new Error(`Not a regular frontend file: ${key}`);
  }
  return result;
}

async function assertNoSymlinkParents(target, stopAt) {
  for (let path = target;; path = dirname(path)) {
    try {
      const details = await lstat(path);
      if (details.isSymbolicLink() || !details.isDirectory()) throw new Error('Staging directories must be real directories, not symlinks or files.');
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (path === stopAt) return;
    if (path === dirname(path)) throw new Error('Invalid staging root.');
  }
}

const validBounds = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
  && value[0] >= -180 && value[2] <= 180 && value[1] >= -90 && value[3] <= 90
  && value[0] <= value[2] && value[1] <= value[3];
const hashPattern = /^[a-f0-9]{64}$/;
const mapLocationKind = id => typeof id !== 'string' ? null : /^neighborhood:[a-f0-9]{24}$/.test(id) ? 'neighborhood'
  : /^district:Budapest:(?:[1-9]|1[0-9]|2[0-3])$/.test(id) ? 'district'
    : /^city:[^\u0000-\u001f]{1,100}$/.test(id) ? 'city' : null;

function validPolygon(geometry, maximumPoints = 200000) {
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates]
    : geometry?.type === 'MultiPolygon' ? geometry.coordinates : null;
  if (!Array.isArray(polygons) || !polygons.length) return false;
  let count = 0;
  return polygons.every(polygon => Array.isArray(polygon) && polygon.length > 0 && polygon.every(ring => {
    if (!Array.isArray(ring) || ring.length < 4) return false;
    for (const point of ring) {
      if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)
        || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90 || ++count > maximumPoints) return false;
    }
    return ring[0][0] === ring.at(-1)[0] && ring[0][1] === ring.at(-1)[1];
  }));
}

async function validateMapLibre(source) {
  let provenance;
  try { provenance = JSON.parse(await readFile(join(source, 'vendor/maplibre/provenance.json'), 'utf8')); }
  catch { throw new Error('Invalid MapLibre release provenance.'); }
  if (!provenance || ['package','version','registry','integrity','tarballSha256'].some(key => provenance[key] !== mapLibreRelease[key])
    || !provenance.files || Object.keys(provenance.files).length !== Object.keys(mapLibreRelease.files).length) {
    throw new Error('MapLibre release provenance does not match the pinned release.');
  }
  for (const [name, expected] of Object.entries(mapLibreRelease.files)) {
    const declared = provenance.files[name];
    const content = await readFile(join(source, 'vendor/maplibre', name));
    const digest = createHash('sha256').update(content).digest('hex');
    const gitBlob = createHash('sha1').update(Buffer.from(`blob ${content.length}\0`)).update(content).digest('hex');
    if (!declared || content.length !== expected.bytes || declared.bytes !== expected.bytes
      || digest !== expected.sha256 || declared.sha256 !== expected.sha256 || declared.gitBlob !== gitBlob) {
      throw new Error(`MapLibre asset does not match the pinned release: ${name}.`);
    }
  }
}

/** Validate local display data completely before touching a staged release. */
async function validateMapLabels(source, filesByKey, mapIndex) {
  let labels, style;
  try {
    labels = JSON.parse(await readFile(join(source, 'data/map/labels.json'), 'utf8'));
    style = JSON.parse(await readFile(join(source, 'data/map/style.json'), 'utf8'));
  } catch { throw new Error('Invalid map labels or basemap style.'); }
  if (style?.version !== 8 || !Array.isArray(style.layers) || style.sources?.openmaptiles?.type !== 'vector'
    || style.sources.openmaptiles.url !== 'https://tiles.openfreemap.org/planet'
    || typeof style.glyphs !== 'string' || !style.glyphs.startsWith('https://tiles.openfreemap.org/fonts/')) {
    throw new Error('Invalid map basemap style.');
  }
  if (!labels || labels.schemaVersion !== 1 || labels.type !== 'FeatureCollection' || labels.displayOnly !== true
    || typeof labels.version !== 'string' || !labels.version || labels.version.length > 160
    || labels.mapVersion !== mapIndex.version || labels.sourceSha256 !== mapIndex.sourceSha256
    || labels.municipalitiesSha256 !== mapIndex.municipalitiesSha256
    || !hashPattern.test(labels.namedNodesSha256 ?? '') || !hashPattern.test(labels.sourceSha256 ?? '')
    || !hashPattern.test(labels.municipalitiesSha256 ?? '') || !Array.isArray(labels.features)
    || labels.features.length > 8000 || labels.count !== labels.features.length
    || !Array.isArray(labels.towns) || !labels.districtBoundaries || typeof labels.districtBoundaries !== 'object'
    || Array.isArray(labels.districtBoundaries) || !validPolygon(labels.coverage, 50000)) {
    throw new Error('Invalid map labels manifest.');
  }
  const features = new Map(), counts = {city: 0, district: 0, neighborhood: 0};
  for (const feature of labels.features) {
    const id = feature?.id, kind = mapLocationKind(id), properties = feature?.properties;
    const point = feature?.geometry?.coordinates;
    if (feature?.type !== 'Feature' || !kind || !Object.hasOwn(mapIndex.focus ?? {}, id) || features.has(id)
      || properties?.id !== id || properties.kind !== kind
      || typeof properties.name !== 'string' || !properties.name || properties.name.length > 512
      || typeof properties.label !== 'string' || !properties.label || properties.label.length > 512
      || typeof properties.city !== 'string' || !properties.city || properties.city.length > 100
      || !Number.isFinite(properties.minZoom) || properties.minZoom < 0 || properties.minZoom > 22
      || !Number.isFinite(properties.priority) || properties.priority < 0 || properties.priority > 100000
      || !Object.hasOwn(mapIndex.focus, properties.boundaryId)
      || feature.geometry?.type !== 'Point' || !Array.isArray(point) || point.length !== 2
      || !point.every(Number.isFinite) || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90) {
      throw new Error('Invalid or duplicate map label.');
    }
    if (kind === 'city' && (id !== 'city:' + properties.city || properties.boundaryId !== id)
      || kind === 'neighborhood' && properties.boundaryId !== id
      || kind === 'district' && !/^neighborhood:[a-f0-9]{24}$/.test(properties.boundaryId)) {
      throw new Error('Invalid map label boundary reference.');
    }
    counts[kind]++; features.set(id, feature);
  }
  for (const id of Object.keys(mapIndex.focus ?? {})) {
    if (mapLocationKind(id) && !features.has(id)) throw new Error('Missing canonical map label.');
  }
  if (counts.neighborhood !== mapIndex.count || Object.keys(counts).some(kind => labels.counts?.[kind] !== counts[kind])
    || labels.towns.length !== counts.city || Object.keys(labels.districtBoundaries).length !== counts.district) {
    throw new Error('Map label counts do not match the map manifest.');
  }
  for (const [id, boundaryId] of Object.entries(labels.districtBoundaries)) {
    if (features.get(id)?.properties.kind !== 'district' || features.get(id).properties.boundaryId !== boundaryId
      || features.get(boundaryId)?.properties.kind !== 'neighborhood'
      || features.get(boundaryId).properties.city !== 'Budapest') throw new Error('Unknown map district boundary reference.');
  }
  const townIds = new Set(), listed = new Set();
  for (const town of labels.towns) {
    const key = 'data/map/' + town?.file;
    if (features.get(town?.id)?.properties.kind !== 'city' || townIds.has(town.id)
      || !mapTownFile.test(key) || listed.has(key) || !validBounds(town.bounds)) throw new Error('Invalid map town layer reference.');
    const file = filesByKey.get(key);
    if (!file) throw new Error(`Missing map town layer ${key}.`);
    const content = await readFile(file.path);
    const digest = createHash('sha256').update(content).digest('hex').slice(0, 20);
    if (town.file !== `town-${digest}.json`) throw new Error(`Map town layer checksum mismatch: ${key}.`);
    let value;
    try { value = JSON.parse(content.toString('utf8')); } catch { throw new Error('Invalid map town layer.'); }
    if (value?.type !== 'Feature' || value.id !== town.id || value.properties?.id !== town.id
      || value.version !== labels.version || value.mapVersion !== mapIndex.version
      || !validBounds(value.bbox) || !value.bbox.every((number, index) => number === town.bounds[index])
      || !validPolygon(value.geometry)) throw new Error('Invalid map town layer.');
    townIds.add(town.id); listed.add(key);
  }
  if ([...filesByKey.keys()].some(key => mapTownFile.test(key) && !listed.has(key))) throw new Error('Unlisted map town layer cannot be published.');
}

export async function prepareSite({config, source = join(projectRoot, 'dist'), output = join(projectRoot, '.local/gcp/site')}) {
  config = validateDevConfig(config);
  const target = resolve(output), allowedRoot = resolve(projectRoot, '.local/gcp');
  if (!target.startsWith(allowedRoot + '/')) throw new Error('Staging output must be a child of .local/gcp.');
  const sourceRoot = resolve(source), sourceDetails = await lstat(sourceRoot);
  if (sourceDetails.isSymbolicLink() || !sourceDetails.isDirectory()) throw new Error('The frontend source must be a real directory.');
  if (sourceRoot === target || sourceRoot.startsWith(target + '/') || target.startsWith(sourceRoot + '/')) throw new Error('Frontend source and staging output must not overlap.');
  await assertNoSymlinkParents(target, resolve(projectRoot));
  const files = await collectFiles(source);
  const filesByKey = new Map(files.map(file => [file.key, file]));
  for (const required of codeFiles) if (!files.some(file => file.key === required)) throw new Error(`Missing frontend file ${required}.`);
  await validateMapLibre(source);
  const mapIndex = JSON.parse(await readFile(join(source, 'data/map/index.json'), 'utf8'));
  if (mapIndex.schemaVersion !== 1 || !Array.isArray(mapIndex.cities) || !mapIndex.cities.length) throw new Error('Invalid neighborhood map manifest.');
  const listed = new Set();
  for (const city of mapIndex.cities) {
    const key = 'data/map/' + city.file;
    if (typeof city.file !== 'string' || !mapCityFile.test(key) || listed.has(key)) throw new Error('Invalid neighborhood map layer path.');
    listed.add(key);
    const file = filesByKey.get(key);
    if (!file) throw new Error(`Missing neighborhood map layer ${key}.`);
    const hash = createHash('sha256').update(await readFile(file.path)).digest('hex').slice(0, 20);
    if (city.file !== `city-${hash}.json`) throw new Error(`Neighborhood map layer checksum mismatch: ${key}.`);
  }
  if (files.some(file => mapCityFile.test(file.key) && !listed.has(file.key))) throw new Error('Unlisted neighborhood map layer cannot be published.');
  let hierarchy;
  try { hierarchy = JSON.parse(await readFile(join(source, 'data/map/hierarchy.json'), 'utf8')); }
  catch { throw new Error('Invalid neighborhood map hierarchy.'); }
  if (!hierarchy || hierarchy.schemaVersion !== 1 || typeof hierarchy.version !== 'string' || !hierarchy.version
    || hierarchy.mapVersion !== mapIndex.version || hierarchy.sourceSha256 !== mapIndex.sourceSha256
    || !Number.isInteger(hierarchy.count) || hierarchy.count < 0 || hierarchy.count !== mapIndex.count
    || !hierarchy.parents || typeof hierarchy.parents !== 'object' || Array.isArray(hierarchy.parents)
    || Object.keys(hierarchy.parents).length > hierarchy.count) throw new Error('Invalid neighborhood map hierarchy.');
  const areaId = /^neighborhood:[a-f0-9]{24}$/;
  for (const [child, parent] of Object.entries(hierarchy.parents)) {
    if (!areaId.test(child) || typeof parent !== 'string' || !areaId.test(parent)
      || !Object.hasOwn(mapIndex.focus ?? {}, child) || !Object.hasOwn(mapIndex.focus ?? {}, parent)) throw new Error('Unknown neighborhood map hierarchy reference.');
    const ancestors = new Set([child]);
    for (let id = parent; id !== undefined; id = hierarchy.parents[id]) {
      if (ancestors.has(id)) throw new Error('Cyclic neighborhood map hierarchy.');
      ancestors.add(id);
    }
  }
  await validateMapLabels(source, filesByKey, mapIndex);
  // Validate the entire tree first, then replace only this ignored staging directory.
  await rm(target, {recursive: true, force: true});
  await mkdir(join(target, 'public'), {recursive: true});
  for (const file of files) {
    const destination = join(target, 'public', file.key);
    await mkdir(dirname(destination), {recursive: true});
    await cp(file.path, destination);
  }
  await writeFile(join(target, 'public/runtime-config.js'), 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});\n');
  await writeFile(join(target, 'firebase.json'), JSON.stringify(hostingConfig(config), null, 2) + '\n');
  return {directory: target, url: `https://${config.siteId}.web.app`};
}

async function main() {
  const [configPath = '.local/gcp/dev-config.json', output] = process.argv.slice(2);
  const result = await prepareSite({config: await readDevConfig(resolve(configPath)), output});
  console.log(`Prepared test Hosting files: ${result.directory}`);
  console.log(`Test web address: ${result.url}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { await main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
