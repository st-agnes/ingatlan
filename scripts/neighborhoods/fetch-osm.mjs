import { mkdir, rename, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// This is an explicit, infrequently run data-acquisition utility, not a runtime API.
export const TARGET_CITIES = Object.freeze([
  'Budapest', 'Baja', 'Békéscsaba', 'Debrecen', 'Dunaújváros', 'Eger', 'Érd',
  'Esztergom', 'Győr', 'Hódmezővásárhely', 'Kaposvár', 'Kecskemét', 'Miskolc',
  'Nagykanizsa', 'Nyíregyháza', 'Pécs', 'Salgótarján', 'Sopron', 'Szeged',
  'Székesfehérvár', 'Szekszárd', 'Szolnok', 'Szombathely', 'Tatabánya',
  'Veszprém', 'Zalaegerszeg'
]);
export const CORE_CITIES = Object.freeze([
  'Budapest', 'Debrecen', 'Szeged', 'Miskolc', 'Pécs', 'Győr', 'Nyíregyháza'
]);
export const ENDPOINTS = Object.freeze([
  'https://overpass-api.de/api/interpreter',
  'https://overpass.private.coffee/api/interpreter'
]);
export const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;
export const REQUEST_TIMEOUT_MS = 40_000;

export function validateCities(cities) {
  if (!Array.isArray(cities) || !cities.length || cities.length > TARGET_CITIES.length)
    throw new Error('Select one or more supported target cities.');
  if (cities.some(city => !TARGET_CITIES.includes(city)) || new Set(cities).size !== cities.length)
    throw new Error('Unknown or duplicate target city.');
  return [...cities];
}

export function municipalityAdminLevel(city) {
  validateCities([city]);
  // Budapest also has a separate city-level relation. Use the capital/county
  // boundary consistently: OSM relation 37244, documented as admin_level=6.
  // https://wiki.openstreetmap.org/wiki/Hu:Hungary/Boundaries
  return city === 'Budapest' ? '6' : '8';
}

export function queryFor(city) {
  validateCities([city]);
  // Resolve the known capital relation directly before its large boundary export.
  const municipality = city === 'Budapest'
    ? 'relation(37244)["boundary"="administrative"]["admin_level"="6"]["name"="Budapest"]'
    : `relation(area.hungary)["boundary"="administrative"]["admin_level"="${municipalityAdminLevel(city)}"]["name"=${JSON.stringify(city)}]`;
  return `[out:json][timeout:30][maxsize:67108864];
area["ISO3166-1"="HU"]["admin_level"="2"]->.hungary;
${municipality}->.municipality;
.municipality out tags center;
.municipality map_to_area ->.city;
(
  relation(area.city)["boundary"="administrative"]["admin_level"~"^(9|10|11)$"]["name"];
  relation(area.city)["place"~"^(suburb|quarter|neighbourhood)$"]["name"];
  way(area.city)["place"~"^(suburb|quarter|neighbourhood)$"]["name"](if:is_closed());
);
out geom;
`;
}

export function fileNameFor(city) {
  validateCities([city]);
  return `${city.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()}.json`;
}

class AcquisitionError extends Error {
  constructor(code, retryable = false, retryAfterMs = 0) {
    super(code);
    this.code = code;
    this.retryable = retryable;
    this.retryAfterMs = retryAfterMs;
  }
}

async function boundedText(response, maxBytes) {
  const announced = Number(response.headers.get('content-length'));
  if (Number.isFinite(announced) && announced > maxBytes)
    throw new AcquisitionError('response-too-large');
  if (!response.body) throw new AcquisitionError('empty-response');
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        throw new AcquisitionError('response-too-large');
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  return Buffer.concat(chunks).toString('utf8');
}

function classifyTransport(error) {
  if (error instanceof AcquisitionError) return error;
  const code = error?.cause?.code ?? error?.code;
  if (['AbortError', 'TimeoutError'].includes(error?.name))
    return new AcquisitionError('request-timeout', true);
  if (['ECONNREFUSED', 'ECONNRESET', 'ETIMEDOUT', 'EAI_AGAIN', 'ENETUNREACH', 'UND_ERR_CONNECT_TIMEOUT'].includes(code))
    return new AcquisitionError('network-unavailable', true);
  return new AcquisitionError('transport-failed');
}

export function summarizeResponse(document, city) {
  if (!document || document.remark || !Array.isArray(document.elements))
    throw new AcquisitionError(document?.remark ? 'overpass-incomplete-result' : 'invalid-response', Boolean(document?.remark));
  const municipalities = document.elements.filter(element => element.type === 'relation'
    && element.tags?.boundary === 'administrative' && element.tags?.admin_level === municipalityAdminLevel(city)
    && element.tags?.name === city);
  if (municipalities.length !== 1)
    throw new AcquisitionError(municipalities.length ? 'ambiguous-municipality' : 'municipality-not-found');
  const candidates = document.elements.filter(element => element !== municipalities[0]);
  const ids = new Set();
  const byAdminLevel = {};
  let relationsWithWayGeometry = 0;
  let closedWays = 0;
  for (const element of candidates) {
    if (!['way', 'relation'].includes(element.type) || !Number.isSafeInteger(element.id)
      || typeof element.tags?.name !== 'string' || !element.tags.name.trim())
      throw new AcquisitionError('unexpected-candidate');
    const key = `${element.type}/${element.id}`;
    if (ids.has(key)) throw new AcquisitionError('duplicate-candidate');
    ids.add(key);
    const level = element.tags?.admin_level ?? 'place-only';
    byAdminLevel[level] = (byAdminLevel[level] ?? 0) + 1;
    if (element.type === 'relation' && element.members?.some(member => member.type === 'way'
      && Array.isArray(member.geometry) && member.geometry.length >= 2)) relationsWithWayGeometry++;
    if (element.type === 'way' && Array.isArray(element.geometry) && element.geometry.length >= 4) {
      const first = element.geometry[0], last = element.geometry.at(-1);
      if (first?.lat === last?.lat && first?.lon === last?.lon) closedWays++;
    }
  }
  return {
    municipalityRelationId: municipalities[0].id,
    municipalityAdminLevel: municipalityAdminLevel(city),
    candidates: candidates.length,
    byAdminLevel,
    relationsWithWayGeometry,
    closedWays,
    osmTimestamp: document.osm3s?.timestamp_osm_base ?? null,
    // A returned relation is not yet a validated polygon or a complete city partition.
    completeCoverage: false,
    reviewStatus: 'unreviewed',
    usableForAddressAssignment: false
  };
}

export async function fetchCity(city, {
  fetchImpl = globalThis.fetch,
  pause = ms => new Promise(resolvePause => setTimeout(resolvePause, ms)),
  timeoutMs = REQUEST_TIMEOUT_MS,
  maxBytes = MAX_RESPONSE_BYTES,
  now = () => new Date().toISOString()
} = {}) {
  validateCities([city]);
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 60_000)
    throw new Error('Request timeout must be between 1 and 60000 milliseconds.');
  const query = queryFor(city);
  const attempts = [];
  for (let index = 0; index < ENDPOINTS.length; index++) {
    const endpoint = ENDPOINTS[index];
    try {
      const response = await fetchImpl(endpoint, {
        method: 'POST',
        redirect: 'error',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
          'User-Agent': 'Otthonra-neighborhood-data/1.0 (https://github.com/st-agnes/ingatlan)'
        },
        body: new URLSearchParams({ data: query }),
        signal: AbortSignal.timeout(timeoutMs)
      });
      if (!response.ok) {
        const retryable = [429, 502, 503, 504].includes(response.status);
        const seconds = Number(response.headers.get('retry-after'));
        // Honor short server pacing; don't switch endpoint early on longer waits.
        const retryAfterMs = Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : 1000;
        await response.body?.cancel();
        throw new AcquisitionError(`http-${response.status}`, retryable && retryAfterMs <= 15_000, retryAfterMs);
      }
      const raw = await boundedText(response, maxBytes);
      let document;
      try { document = JSON.parse(raw); }
      catch { throw new AcquisitionError('invalid-json'); }
      const summary = summarizeResponse(document, city);
      return {
        raw,
        provenance: {
          city,
          endpoint,
          query,
          retrievedAt: now(),
          sha256: createHash('sha256').update(raw).digest('hex'),
          bytes: Buffer.byteLength(raw),
          attribution: '© OpenStreetMap contributors',
          license: 'ODbL-1.0',
          licenseUrl: 'https://www.openstreetmap.org/copyright',
          ...summary,
          attempts: [...attempts, { endpoint, status: 'ok' }]
        }
      };
    } catch (error) {
      const failure = classifyTransport(error);
      attempts.push({ endpoint, status: failure.code });
      if (!failure.retryable || index === ENDPOINTS.length - 1)
        return { failure: { city, status: 'failed', reason: failure.code, attempts } };
      await pause(Math.max(1000, failure.retryAfterMs));
    }
  }
  throw new Error('Unreachable endpoint state.');
}

async function atomicJson(path, value) {
  const temporary = `${path}.tmp`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  await rename(temporary, path);
}

export async function collect({
  cities = CORE_CITIES,
  output = '.local/neighborhoods/osm',
  fetchOptions = {},
  pause = ms => new Promise(resolvePause => setTimeout(resolvePause, ms)),
  onProgress = text => process.stdout.write(`${text}\n`)
} = {}) {
  validateCities(cities);
  const directory = resolve(output);
  await mkdir(directory, { recursive: true });
  const results = [];
  for (let index = 0; index < cities.length; index++) {
    const city = cities[index];
    onProgress(`OSM ${index + 1}/${cities.length}: ${city}`);
    const result = await fetchCity(city, fetchOptions);
    if (result.failure) {
      results.push(result.failure);
      onProgress(`  Failed: ${result.failure.reason}`);
    } else {
      const file = fileNameFor(city);
      await writeFile(`${directory}/${file}.tmp`, result.raw, 'utf8');
      await rename(`${directory}/${file}.tmp`, `${directory}/${file}`);
      const record = { ...result.provenance, status: 'downloaded', file };
      results.push(record);
      await atomicJson(`${directory}/${file.replace(/\.json$/, '.source.json')}`, record);
      onProgress(`  Downloaded ${record.candidates} area candidates; boundary review required.`);
    }
    if (index < cities.length - 1) await pause(1000);
  }
  const successfulCities = results.filter(result => result.status === 'downloaded').length;
  const summary = {
    schemaVersion: 1,
    provider: 'openstreetmap',
    requestedCities: [...cities],
    successfulCities,
    failedCities: results.length - successfulCities,
    candidateCount: results.reduce((total, result) => total + (result.candidates ?? 0), 0),
    completeCoverage: false,
    reviewStatus: 'unreviewed',
    usableForAddressAssignment: false,
    attribution: '© OpenStreetMap contributors',
    license: 'ODbL-1.0',
    licenseUrl: 'https://www.openstreetmap.org/copyright',
    results
  };
  await atomicJson(`${directory}/summary.json`, summary);
  onProgress(`Finished: ${successfulCities}/${cities.length} city requests downloaded. This is a draft source collection.`);
  return summary;
}

export function parseArguments(args) {
  let cities = [...CORE_CITIES];
  let output = '.local/neighborhoods/osm';
  let selected = false;
  for (let index = 0; index < args.length; index++) {
    const argument = args[index];
    if (argument === '--output' && args[index + 1]) output = args[++index];
    else if (argument === '--scope' && args[index + 1]) {
      if (selected) throw new Error('Select cities only once.');
      const scope = args[++index];
      if (!['core', 'all'].includes(scope)) throw new Error('Scope must be core or all.');
      cities = [...(scope === 'all' ? TARGET_CITIES : CORE_CITIES)]; selected = true;
    } else if (argument === '--cities' && args[index + 1]) {
      if (selected) throw new Error('Select cities only once.');
      cities = args[++index].split(',').map(city => city.trim()); selected = true;
    } else throw new Error('Usage: node scripts/neighborhoods/fetch-osm.mjs [--scope core|all | --cities Budapest,Debrecen] [--output DIRECTORY]');
  }
  return { cities: validateCities(cities), output };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const summary = await collect(parseArguments(process.argv.slice(2)));
    if (!summary.successfulCities) process.exitCode = 1;
  } catch (error) {
    process.stderr.write(`Neighborhood collection failed: ${error instanceof AcquisitionError ? error.code : 'configuration-or-file-error'}.\n`);
    process.exitCode = 1;
  }
}
