// Public, display-only neighborhood map. Search membership still uses the full
// canonical boundaries in MySQL; this module never handles property addresses.
const DATA_ROOT = new URL('./data/map/', import.meta.url);
const MIN_AREA_ZOOM = 8;
const MAX_CITIES = 8;
const MAX_FEATURES = 650;
const MAX_OPTIONS = 120;
const MAX_CITY_POINTS = 200000;
const MAX_SELECTED = 50;
const OUTLINE_CONCURRENCY = 4;
const MAX_SELECTED_POINTS = 2000000;
const REQUEST_TIMEOUT = 15000;
const assetPromises = new Map();
const featureAreas = new WeakMap();
const hierarchyDepths = new WeakMap();
const EMPTY_PARENTS = Object.freeze(Object.create(null));
let manifestPromise, mapLibrePromise;
let demoRegistryPromise;
const demoGeometryLayers = new Map();
let moduleAttempt = 0;
const LABEL_SOURCE = 'otthonra-places';
const LABEL_LAYERS = ['otthonra-place-labels'];
const OUTLINE_SOURCE = 'otthonra-outlines';
const emptyCollection = () => ({type: 'FeatureCollection', features: []});

export function selectablePlaceLabelLayout() {
  return {'text-field': ['format', '+ ', {'font-scale': 0.85}, ['get', 'name'], {}],
    'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 6, 12, 11, 14, 15, 16],
    'text-padding': 5, 'text-max-width': 13,
    // The visible add/select affordance is constant in both selection states.
    // Selection changes paint only, so neither the name nor its hit box moves.
    'text-anchor': ['case', ['==', ['get', 'kind'], 'city'], 'bottom', 'top'],
    'text-offset': ['case', ['==', ['get', 'kind'], 'city'], ['literal', [0, -0.65]], ['literal', [0, 0.65]]],
    'text-allow-overlap': false,
    'text-ignore-placement': false, 'symbol-sort-key': ['get', 'priority']};
}

const finite = value => typeof value === 'number' && Number.isFinite(value);
const validBounds = bounds => Array.isArray(bounds) && bounds.length === 4 && bounds.every(finite)
  && bounds[0] <= bounds[2] && bounds[1] <= bounds[3]
  && bounds[0] >= -180 && bounds[2] <= 180 && bounds[1] >= -90 && bounds[3] <= 90;

export function boundsIntersect(left, right) {
  return validBounds(left) && validBounds(right)
    && left[0] <= right[2] && left[2] >= right[0] && left[1] <= right[3] && left[3] >= right[1];
}

function ringPosition(point, ring) {
  if (!Array.isArray(ring) || ring.length < 4) return 0;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[j], b = ring[i];
    if (!Array.isArray(a) || !Array.isArray(b) || !finite(a[0]) || !finite(a[1]) || !finite(b[0]) || !finite(b[1])) return 0;
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const cross = (point[0] - a[0]) * dy - (point[1] - a[1]) * dx;
    if (Math.abs(cross) <= 1e-10 * Math.max(1, Math.abs(dx), Math.abs(dy))
      && point[0] >= Math.min(a[0], b[0]) - 1e-10 && point[0] <= Math.max(a[0], b[0]) + 1e-10
      && point[1] >= Math.min(a[1], b[1]) - 1e-10 && point[1] <= Math.max(a[1], b[1]) + 1e-10) return 2;
    if ((a[1] > point[1]) !== (b[1] > point[1])
      && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside ? 1 : 0;
}

/** Boundary-inclusive Polygon/MultiPolygon hit testing, including hole edges. */
export function pointInGeometry(point, geometry) {
  if (!Array.isArray(point) || !finite(point[0]) || !finite(point[1]) || !geometry) return false;
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates]
    : geometry.type === 'MultiPolygon' ? geometry.coordinates : [];
  if (!Array.isArray(polygons)) return false;
  return polygons.some(polygon => {
    if (!Array.isArray(polygon) || !polygon.length) return false;
    const outer = ringPosition(point, polygon[0]);
    if (!outer) return false;
    if (outer === 2) return true;
    for (const hole of polygon.slice(1)) {
      const position = ringPosition(point, hole);
      if (position === 2) return true;
      if (position === 1) return false;
    }
    return true;
  });
}

/** Spherical square metres, subtracting holes and summing every polygon part. */
export function geometryArea(geometry) {
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates]
    : geometry?.type === 'MultiPolygon' ? geometry.coordinates : [];
  if (!Array.isArray(polygons) || !polygons.length) return 0;
  const radians = Math.PI / 180, radius = 6371008.8;
  function ringArea(ring) {
    if (!Array.isArray(ring) || ring.length < 4) return NaN;
    const origin = ring[0];
    if (!Array.isArray(origin) || !finite(origin[0]) || !finite(origin[1])) return NaN;
    const baseline = Math.sin(origin[1] * radians);
    let sum = 0;
    for (let i = 1; i < ring.length; i++) {
      const left = ring[i - 1], right = ring[i];
      if (!Array.isArray(right) || !finite(right[0]) || !finite(right[1])) return NaN;
      // Removing the constant latitude term avoids cancellation in tiny areas.
      sum += (right[0] - left[0]) * radians
        * (Math.sin(left[1] * radians) + Math.sin(right[1] * radians) - 2 * baseline);
    }
    if (origin[0] !== ring.at(-1)[0] || origin[1] !== ring.at(-1)[1]) return NaN;
    return Math.abs(sum) * radius * radius / 2;
  }
  let total = 0;
  for (const polygon of polygons) {
    if (!Array.isArray(polygon) || !polygon.length) return 0;
    const outer = ringArea(polygon[0]);
    const holes = polygon.slice(1).reduce((sum, ring) => sum + ringArea(ring), 0);
    if (!finite(outer) || !finite(holes)) return 0;
    total += Math.max(0, outer - holes);
  }
  return total;
}

function featureArea(feature) {
  if (!feature || typeof feature !== 'object') return 0;
  if (!featureAreas.has(feature)) featureAreas.set(feature, geometryArea(feature.geometry));
  return featureAreas.get(feature);
}

function hierarchyDepth(id, parents) {
  if (!parents || typeof parents !== 'object' || Array.isArray(parents)) return 0;
  if (!hierarchyDepths.has(parents)) hierarchyDepths.set(parents, new Map());
  const depths = hierarchyDepths.get(parents), path = [], seen = new Set();
  let current = id;
  while (!depths.has(current) && Object.hasOwn(parents, current)) {
    // Runtime metadata validation rejects cycles. Keep the pure selector safe
    // with malformed caller-supplied data as well.
    if (seen.has(current) || path.length > 4308 || typeof parents[current] !== 'string') return 0;
    seen.add(current); path.push(current); current = parents[current];
  }
  let depth = depths.get(current) || 0;
  if (!depths.has(current)) depths.set(current, depth);
  for (let index = path.length - 1; index >= 0; index--) depths.set(path[index], ++depth);
  return depths.get(id) || 0;
}

export function neighborhoodAncestors(id, parents = EMPTY_PARENTS) {
  const result = [], seen = new Set([id]);
  while (parents && Object.hasOwn(parents, id) && result.length < 4308) {
    const parent = parents[id];
    if (typeof parent !== 'string' || seen.has(parent)) break;
    seen.add(parent); result.push(parent); id = parent;
  }
  return result;
}

/** Only genuine containment adds a zoom level; adjacent areas share a level. */
export function neighborhoodZoom(feature, cityFeatures, parents = EMPTY_PARENTS) {
  return MIN_AREA_ZOOM + Math.min(10, hierarchyDepth(feature?.id, parents) * 2);
}

/** Ancestor outlines stay available while contained areas appear closer in. */
export function chooseVisibleNeighborhoods(features, bounds, zoom, parents = EMPTY_PARENTS) {
  if (!Array.isArray(features) || !validBounds(bounds) || !finite(zoom) || zoom < MIN_AREA_ZOOM) return [];
  return features.filter(feature => typeof feature?.properties?.city === 'string'
    && featureArea(feature) > 0 && boundsIntersect(feature.bbox, bounds)
    && neighborhoodZoom(feature, features, parents) <= zoom);
}

/** A map click always resolves directly to the smallest currently visible hit. */
export function chooseSmallestFeature(features, point) {
  if (!Array.isArray(features) || !Array.isArray(point) || !finite(point[0]) || !finite(point[1])) return null;
  let chosen = null, smallest = Infinity;
  for (const feature of features) {
    const area = featureArea(feature);
    if (!(area > 0) || area > smallest || !boundsIntersect(feature?.bbox, [...point, ...point])
      || !pointInGeometry(point, feature.geometry)) continue;
    if (area < smallest || !chosen || String(feature.id) < String(chosen.id)) { chosen = feature; smallest = area; }
  }
  return chosen;
}

/** Bounded viewport selection; no country-wide geometry request is needed. */
export function chooseVisibleCities(cities, bounds, {maxCities = MAX_CITIES, preferredCity = null} = {}) {
  if (!Array.isArray(cities) || !validBounds(bounds)) return {items: [], truncated: false};
  const count = Number.isFinite(maxCities) ? Math.max(1, Math.min(16, Math.trunc(maxCities))) : MAX_CITIES;
  const x = (bounds[0] + bounds[2]) / 2, y = (bounds[1] + bounds[3]) / 2;
  const distance = row => ((row.bounds[0] + row.bounds[2]) / 2 - x) ** 2 + ((row.bounds[1] + row.bounds[3]) / 2 - y) ** 2;
  const visible = cities.filter(row => row && validBounds(row.bounds) && boundsIntersect(row.bounds, bounds))
    .sort((a, b) => Number(b.city === preferredCity) - Number(a.city === preferredCity)
      || distance(a) - distance(b) || String(a.city).localeCompare(String(b.city), 'hu'));
  return {items: visible.slice(0, count), truncated: visible.length > count};
}

function loadAsset(path, type, id) {
  if (assetPromises.has(id)) return assetPromises.get(id);
  const promise = new Promise((resolve, reject) => {
    const node = document.createElement(type === 'style' ? 'link' : 'script');
    node.id = id;
    if (type === 'style') { node.rel = 'stylesheet'; node.href = new URL(path, import.meta.url).href; }
    else { node.src = new URL(path, import.meta.url).href; node.async = true; }
    const timeout = setTimeout(() => finish(false), REQUEST_TIMEOUT);
    function finish(ok) {
      clearTimeout(timeout); node.onload = null; node.onerror = null;
      if (ok) resolve();
      else { node.remove(); reject(new Error('A térkép megjelenítője nem érhető el.')); }
    }
    node.onload = () => finish(true); node.onerror = () => finish(false);
    document.head.append(node);
  }).catch(error => { assetPromises.delete(id); throw error; });
  assetPromises.set(id, promise);
  return promise;
}

async function loadMapLibre() {
  await Promise.all([
    loadAsset('./location-map.css', 'style', 'otthonra-location-map-css'),
    loadAsset('./vendor/maplibre/maplibre-gl.css', 'style', 'otthonra-maplibre-css')
  ]);
  if (!mapLibrePromise) {
    const url = new URL('./vendor/maplibre/maplibre-gl.mjs', import.meta.url);
    if (moduleAttempt++) url.searchParams.set('retry', String(moduleAttempt));
    const module = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('A térkép megjelenítője nem érhető el.')), REQUEST_TIMEOUT);
      import(url.href).then(value => { clearTimeout(timeout); resolve(value); }, error => { clearTimeout(timeout); reject(error); });
    });
    mapLibrePromise = module.then(library => {
      if (typeof library.Map !== 'function' || typeof library.setWorkerUrl !== 'function') throw new Error('Invalid map renderer.');
      library.setWorkerUrl(new URL('./vendor/maplibre/maplibre-gl-worker.mjs', import.meta.url).href);
      return library;
    }).catch(error => { mapLibrePromise = null; throw error; });
  }
  return mapLibrePromise;
}

async function requestJSON(url, signal) {
  const request = new AbortController();
  const abort = () => request.abort();
  if (signal?.aborted) request.abort();
  else signal?.addEventListener('abort', abort, {once: true});
  const timeout = setTimeout(abort, REQUEST_TIMEOUT);
  try {
    const response = await fetch(url, {signal: request.signal, credentials: 'omit', redirect: 'error', cache: 'no-cache'});
    if (!response.ok) throw new Error('A térképadatok most nem érhetők el.');
    const text = await response.text();
    if (text.length > 8000000) throw new Error('A térképadatok túl nagyok.');
    return JSON.parse(text);
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort); }
}

function validateManifest(value) {
  if (!value || value.schemaVersion !== 1 || typeof value.version !== 'string' || !value.version || value.version.length > 128
    || !/^[a-f0-9]{64}$/.test(value.sourceSha256) || !Number.isInteger(value.count) || value.count < 1
    || !Array.isArray(value.cities) || !value.focus) throw new Error('A térképadatok nem érvényesek.');
  const names = new Set();
  const cities = value.cities.map(row => {
    if (!row || typeof row.city !== 'string' || !row.city || names.has(row.city) || !validBounds(row.bounds)
      || !/^city-[a-f0-9]{16,64}\.json$/.test(row.file) || !Number.isInteger(row.count) || row.count < 1 || row.count > 4308) throw new Error('A térképadatok nem érvényesek.');
    names.add(row.city);
    return {city: row.city, bounds: row.bounds, file: row.file, count: row.count};
  });
  const focus = Object.create(null);
  for (const [id, bounds] of Object.entries(value.focus)) if (validBounds(bounds)) focus[id] = bounds;
  return {version: value.version, sourceSha256: value.sourceSha256, count: value.count, cities, focus};
}

/** Parent edges are precomputed from polygons, never guessed from screen size. */
export function validateNeighborhoodHierarchy(value, manifest, getLocation) {
  if (!value || value.schemaVersion !== 1 || value.mapVersion !== manifest.version
    || value.sourceSha256 !== manifest.sourceSha256 || value.count !== manifest.count
    || !value.parents || typeof value.parents !== 'object' || Array.isArray(value.parents)
    || !finite(value.policy?.minimumCoverage) || value.policy.minimumCoverage < 0.9 || value.policy.minimumCoverage > 1
    || !finite(value.policy?.maximumChildAreaRatio) || value.policy.maximumChildAreaRatio <= 0 || value.policy.maximumChildAreaRatio >= 1
    || Object.keys(value.parents).length > manifest.count) throw new Error('A városrészek területi hierarchiája nem érvényes.');
  const parents = Object.create(null);
  for (const [childId, parentId] of Object.entries(value.parents)) {
    const child = getLocation(childId), parent = getLocation(parentId);
    if (typeof parentId !== 'string' || childId === parentId || child?.kind !== 'neighborhood'
      || parent?.kind !== 'neighborhood' || child.city !== parent.city) throw new Error('A városrészek területi hierarchiája nem érvényes.');
    parents[childId] = parentId;
  }
  for (const child of Object.keys(parents)) {
    const seen = new Set();
    let current = child;
    while (Object.hasOwn(parents, current)) {
      if (seen.has(current)) throw new Error('A városrészek területi hierarchiája nem érvényes.');
      seen.add(current); current = parents[current];
    }
  }
  return Object.freeze(parents);
}

function getManifest() {
  if (!manifestPromise) manifestPromise = Promise.all([
    requestJSON(new URL('index.json', DATA_ROOT)), requestJSON(new URL('hierarchy.json', DATA_ROOT)),
    requestJSON(new URL('labels.json', DATA_ROOT)), requestJSON(new URL('style.json', DATA_ROOT))
  ]).then(([index, hierarchy, labels, style]) => ({...validateManifest(index), hierarchy, labels, style}))
    .catch(error => { manifestPromise = null; throw error; });
  return manifestPromise;
}

function geometryPointCount(geometry) {
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) return -1;
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  if (!Array.isArray(polygons) || !polygons.length) return -1;
  let count = 0;
  for (const polygon of polygons) {
    if (!Array.isArray(polygon) || !polygon.length) return -1;
    for (const ring of polygon) {
      if (!Array.isArray(ring) || ring.length < 4) return -1;
      for (const point of ring) {
        if (!Array.isArray(point) || point.length < 2 || !finite(point[0]) || !finite(point[1])
          || point[0] < -180 || point[0] > 180 || point[1] < -90 || point[1] > 90) return -1;
        if (++count > MAX_CITY_POINTS) return -1;
      }
      if (ring[0][0] !== ring.at(-1)[0] || ring[0][1] !== ring.at(-1)[1]) return -1;
    }
  }
  return count;
}

function readCityFeatures(row, value, manifest, getLocation) {
  if (!value || value.type !== 'FeatureCollection' || value.version !== manifest.version || value.city !== row.city
    || !Array.isArray(value.features) || value.features.length !== row.count) throw new Error('A városrészadatok nem érvényesek.');
  let points = 0;
  const seen = new Set();
  return value.features.map(feature => {
    const id = feature?.id || feature?.properties?.id, location = getLocation(id);
    const count = geometryPointCount(feature?.geometry);
    if (feature?.type !== 'Feature' || !location || location.kind !== 'neighborhood' || location.city !== row.city
      || seen.has(id) || !validBounds(feature.bbox) || count < 0 || (points += count) > MAX_CITY_POINTS) throw new Error('A városrészadatok nem érvényesek.');
    seen.add(id);
    return {type: 'Feature', id, bbox: feature.bbox, geometry: feature.geometry,
      properties: {id, name: location.name || location.label, label: location.label, city: location.city, estimated: !!location.estimated}};
  });
}

/** A small country-wide point registry; it contains no address/search geometry. */
export function validatePlaceLabels(value, manifest, getLocation) {
  if (!value || value.schemaVersion !== 1 || value.type !== 'FeatureCollection'
    || value.mapVersion !== manifest.version || value.sourceSha256 !== manifest.sourceSha256
    || typeof value.version !== 'string' || !value.version || value.version.length > 180
    || value.displayOnly !== true || !Array.isArray(value.features) || !value.features.length
    || value.features.length > 10000 || !Array.isArray(value.towns)
    || !value.districtBoundaries || typeof value.districtBoundaries !== 'object'
    || Array.isArray(value.districtBoundaries)) throw new Error('A térképfeliratok nem érvényesek.');
  const byId = new Map();
  const features = value.features.map(feature => {
    const id = feature?.id, location = getLocation(id), properties = feature?.properties, point = feature?.geometry?.coordinates;
    const boundary = getLocation(properties?.boundaryId);
    if (feature?.type !== 'Feature' || feature.geometry?.type !== 'Point' || !Array.isArray(point)
      || point.length !== 2 || !point.every(finite) || point[0] < 16 || point[0] > 23.1 || point[1] < 45.5 || point[1] > 48.8
      || !location || !['city', 'district', 'neighborhood'].includes(location.kind) || byId.has(id)
      || properties?.id !== id || properties.city !== location.city || properties.kind !== location.kind
      || typeof properties.name !== 'string' || !properties.name.trim() || properties.name.length > 200
      || !finite(properties.minZoom) || properties.minZoom < 0 || properties.minZoom > 18
      || !finite(properties.priority) || properties.priority < 0 || properties.priority > 100000
      || !boundary || boundary.city !== location.city
      || !['city', 'neighborhood'].includes(boundary.kind)) throw new Error('A térképfeliratok nem érvényesek.');
    const result = {type: 'Feature', id, geometry: {type: 'Point', coordinates: [...point]},
      properties: {id, name: properties.name, label: location.label, city: location.city, kind: location.kind,
        minZoom: properties.minZoom, priority: properties.priority, boundaryId: boundary.id}};
    byId.set(id, result);
    return result;
  });
  const towns = new Map();
  for (const row of value.towns) {
    if (!row || getLocation(row.id)?.kind !== 'city' || towns.has(row.id) || !validBounds(row.bounds)
      || !/^town-[a-f0-9]{20}\.json$/.test(row.file)) throw new Error('A településhatárok jegyzéke nem érvényes.');
    towns.set(row.id, {id: row.id, file: row.file, bounds: row.bounds});
  }
  for (const [districtId, boundaryId] of Object.entries(value.districtBoundaries)) {
    if (getLocation(districtId)?.kind !== 'district' || getLocation(boundaryId)?.kind !== 'neighborhood'
      || byId.get(districtId)?.properties.boundaryId !== boundaryId) throw new Error('A kerülethatárok jegyzéke nem érvényes.');
  }
  // A small national outline only controls duplicate basemap labels, not search
  // membership. It is deliberately distinct from the full municipal catalogue.
  const coverage = value.coverage ?? value.countryGeometry ?? null;
  if (coverage && (geometryPointCount(coverage) < 0 || geometryPointCount(coverage) > 20000)) throw new Error('A térkép lefedettsége nem érvényes.');
  return {version: value.version, features, byId, towns, districtBoundaries: value.districtBoundaries, coverage};
}

/** Browser-demo distance to a display polygon; the hosted API uses full MySQL geometry. */
export function demoDistanceToGeometryKm(point, geometry) {
  if (!Array.isArray(point) || point.length !== 2 || !point.every(finite)
    || point[0] < -180 || point[0] > 180 || point[1] < -90 || point[1] > 90
    || !geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) return null;
  if (pointInGeometry(point, geometry)) return 0;
  const radians = Math.PI / 180, radius = 6371.0088;
  const angle = (a, b) => {
    const lat = (b[1] - a[1]) * radians, lon = (b[0] - a[0]) * radians;
    const value = Math.sin(lat / 2) ** 2 + Math.cos(a[1] * radians) * Math.cos(b[1] * radians) * Math.sin(lon / 2) ** 2;
    return 2 * Math.asin(Math.sqrt(Math.max(0, Math.min(1, value))));
  };
  const bearing = (a, b) => {
    const lon = (b[0] - a[0]) * radians, start = a[1] * radians, end = b[1] * radians;
    return Math.atan2(Math.sin(lon) * Math.cos(end), Math.cos(start) * Math.sin(end) - Math.sin(start) * Math.cos(end) * Math.cos(lon));
  };
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  if (!Array.isArray(polygons) || !polygons.length || polygons.some(polygon => !Array.isArray(polygon)
    || !polygon.length || polygon.some(ring => !Array.isArray(ring) || ring.length < 4))) return null;
  let closest = Infinity;
  for (const polygon of polygons || []) for (const ring of polygon || []) for (let i = 1; i < (ring?.length || 0); i++) {
    const start = ring[i - 1], end = ring[i];
    if (!Array.isArray(start) || !Array.isArray(end) || !start.every(finite) || !end.every(finite)) return null;
    const segment = angle(start, end), fromStart = angle(start, point);
    const direction = bearing(start, point) - bearing(start, end);
    const along = Math.atan2(Math.sin(fromStart) * Math.cos(direction), Math.cos(fromStart));
    const distance = segment === 0 || along <= 0 ? fromStart : along >= segment ? angle(end, point)
      : Math.abs(Math.asin(Math.max(-1, Math.min(1, Math.sin(fromStart) * Math.sin(direction)))));
    closest = Math.min(closest, distance);
  }
  return finite(closest) ? closest * radius : null;
}

/** Load only the demo's requested nonstreet target boundaries, never the map renderer. */
export async function loadDemoMatchingGeometries(ids, getLocation, {signal} = {}) {
  if (signal?.aborted) return new Map();
  if (!demoRegistryPromise) demoRegistryPromise = getManifest().then(manifest => ({manifest,
    registry: validatePlaceLabels(manifest.labels, manifest, getLocation)})).catch(error => {demoRegistryPromise = null; throw error;});
  const {manifest, registry} = await demoRegistryPromise;
  if (signal?.aborted) return new Map();
  const requests = new Map(), choices = [];
  for (const id of new Set(ids || [])) {
    const location = getLocation(id);
    if (!location || !['city', 'district', 'neighborhood'].includes(location.kind)) continue;
    const boundaryId = registry.districtBoundaries[id] || id;
    const row = location.kind === 'city' ? registry.towns.get(id)
      : manifest.cities.find(item => item.city === location.city);
    if (!row) continue;
    choices.push({id, boundaryId, file: row.file});
    requests.set(row.file, {...row, town: location.kind === 'city'});
  }
  const rows = [...requests.values()], loaded = new Map();
  let cursor = 0;
  async function worker() {
    while (cursor < rows.length && !signal?.aborted) {
      const row = rows[cursor++];
      let features = demoGeometryLayers.get(row.file);
      if (!features) {
        const value = await requestJSON(new URL(row.file, DATA_ROOT), signal);
        if (row.town) {
          if (!value || value.type !== 'Feature' || value.version !== registry.version || value.mapVersion !== manifest.version
            || value.id !== row.id || !validBounds(value.bbox) || geometryPointCount(value.geometry) < 0) throw new Error('A településhatár nem érvényes.');
          features = [value];
        } else features = readCityFeatures(row, value, manifest, getLocation);
        if (signal?.aborted) return;
      }
      demoGeometryLayers.delete(row.file); demoGeometryLayers.set(row.file, features);
      while (demoGeometryLayers.size > MAX_CITIES) demoGeometryLayers.delete(demoGeometryLayers.keys().next().value);
      loaded.set(row.file, new Map(features.map(feature => [feature.id, feature.geometry])));
    }
  }
  await Promise.all(Array.from({length: Math.min(OUTLINE_CONCURRENCY, rows.length)}, worker));
  if (signal?.aborted) return new Map();
  return new Map(choices.map(choice => [choice.id, loaded.get(choice.file)?.get(choice.boundaryId)]).filter(([, geometry]) => geometry));
}

/** Labels, rather than polygon areas, determine which named choices are shown. */
export function chooseVisiblePlaceLabels(features, bounds, zoom, selectedIds = [], maxFeatures = MAX_FEATURES) {
  if (!Array.isArray(features) || !validBounds(bounds) || !finite(zoom)) return [];
  const selected = new Set(selectedIds), x = (bounds[0] + bounds[2]) / 2, y = (bounds[1] + bounds[3]) / 2;
  // Let the city's eligible named parts win ordinary collisions as soon as
  // they appear (Budapest's Buda/Pest start at 8, most quarters at 10). This is a
  // zoom rule, never a consequence of selecting a name or moving its anchor.
  const detailedCities = new Set(features.filter(feature => ['neighborhood', 'district'].includes(feature?.properties?.kind)
    && finite(feature.properties.minZoom) && feature.properties.minZoom <= zoom).map(feature => feature.properties.city));
  const priority = feature => feature.properties.priority + (feature.properties.kind === 'city' && detailedCities.has(feature.properties.city) ? 10000 : 0);
  const distance = feature => (feature.geometry.coordinates[0] - x) ** 2 + (feature.geometry.coordinates[1] - y) ** 2;
  const result = features.filter(feature => feature?.geometry?.type === 'Point'
    && Array.isArray(feature.geometry.coordinates) && feature.geometry.coordinates.length === 2
    && feature.geometry.coordinates.every(finite) && finite(feature.properties?.minZoom)
    && (selected.has(feature.id) || feature.properties.minZoom <= zoom)
    && boundsIntersect(bounds, [...feature.geometry.coordinates, ...feature.geometry.coordinates]))
    .sort((left, right) => priority(left) - priority(right)
      || Number(right.properties.kind === 'district') - Number(left.properties.kind === 'district')
      || distance(left) - distance(right) || String(left.id).localeCompare(String(right.id)));
  // Budapest's district and its identically named search polygon are one label;
  // preserve the exact selected identity when it needs to be removed again.
  const boundaries = new Map();
  for (const feature of result) {
    const boundary = feature.properties.boundaryId || feature.id;
    const previous = boundaries.get(boundary);
    if (!previous || selected.has(feature.id) && !selected.has(previous.id)) boundaries.set(boundary, feature);
  }
  const limit = Math.max(1, Math.min(MAX_FEATURES, Math.trunc(maxFeatures) || MAX_FEATURES));
  const choices = [...boundaries.values()], pinned = choices.filter(feature => selected.has(feature.id));
  const retained = new Set([...pinned.slice(0, limit), ...choices.filter(feature => !selected.has(feature.id)).slice(0, Math.max(0, limit - pinned.length))]);
  // Selection may retain a label outside the normal viewport cap, but it must
  // not reorder existing symbols or change their collision-placement priority.
  return result.filter(feature => retained.has(feature))
    .map(feature => priority(feature) === feature.properties.priority ? feature : {...feature, properties: {...feature.properties, priority: priority(feature)}});
}

/** Resolve only a rendered text hit; empty polygon interiors are not targets. */
export function chooseLabelHit(features, point, project) {
  if (!Array.isArray(features) || !point || !finite(point.x) || !finite(point.y) || typeof project !== 'function') return null;
  const distinct = new Map();
  for (const feature of features) {
    const id = feature?.properties?.id;
    if (typeof id !== 'string' || distinct.has(id) || feature.geometry?.type !== 'Point') continue;
    const position = project(feature.geometry.coordinates);
    if (!position || !finite(position.x) || !finite(position.y)) continue;
    distinct.set(id, {feature, distance: (position.x - point.x) ** 2 + (position.y - point.y) ** 2});
  }
  return [...distinct.values()].sort((left, right) => left.distance - right.distance
    || String(left.feature.properties.id).localeCompare(String(right.feature.properties.id)))[0]?.feature || null;
}

function expressionFilter(filter) {
  if (!Array.isArray(filter) || !filter.length) return true;
  const [operator, ...args] = filter;
  const property = key => key === '$type' ? ['geometry-type'] : key === '$id' ? ['id'] : ['get', key];
  if (['all', 'any'].includes(operator)) return [operator, ...args.map(expressionFilter)];
  if (operator === 'none') return ['!', ['any', ...args.map(expressionFilter)]];
  if (operator === '!has') return ['!', ['has', args[0]]];
  if (operator === '!in' || operator === 'in' && typeof args[0] === 'string') {
    const result = ['in', property(args[0]), ['literal', args.slice(1)]];
    return operator === '!in' ? ['!', result] : result;
  }
  if (['==', '!=', '<', '<=', '>', '>='].includes(operator) && typeof args[0] === 'string') return [operator, property(args[0]), args[1]];
  return filter;
}

function suppressDuplicatePlaceLabels(map, coverage) {
  if (!coverage) return;
  const localClasses = ['city', 'town', 'village', 'hamlet', 'borough', 'suburb', 'quarter', 'neighbourhood'];
  for (const layer of map.getStyle().layers || []) {
    if (layer['source-layer'] !== 'place' || layer.type !== 'symbol') continue;
    map.setFilter(layer.id, ['all', expressionFilter(layer.filter), ['any',
      ['!', ['in', ['get', 'class'], ['literal', localClasses]]], ['!', ['within', coverage]]]]);
  }
}

/**
 * Public canonical labels are the selectable controls. Geometry is loaded only
 * for selected outlines; no exact property address ever reaches this module.
 */
export function createLocationMap(container, {selectedIds = [], getLocation, onSelect, onError} = {}) {
  if (!container || typeof getLocation !== 'function' || typeof onSelect !== 'function') throw new TypeError('A térképes helyszínválasztó beállításai hiányoznak.');
  let selected = new Set(Array.isArray(selectedIds) ? selectedIds.slice(0, MAX_SELECTED) : []), disposed = false, selectionRevision = 0;
  let map, library, manifest, registry, parents = EMPTY_PARENTS, ready = false, booting = false;
  let pendingFocus = [...selected][0] || null, viewportAbort, bootAbort, timer, generation = 0;
  let currentLabels = [], currentOutlines = [], failed = false, backgroundUnavailable = false, loading = false;
  let lastOptions = null, lastLabelPayload = '', lastOutlinePayload = '';
  let camera = {center: [19.5, 47.16], zoom: 7};
  const outlineCache = new Map();
  const labelSelection = new Map();
  container.classList.add('location-map');
  container.innerHTML = '<div class="location-map-heading"><strong>Válassz a helynevekre kattintva</strong></div><div class="location-map-canvas" role="region" aria-label="Helyszínek térképes kiválasztása"></div><div class="location-map-status" role="status" aria-live="polite">Térkép betöltése…</div><button type="button" class="location-map-retry" hidden>Újrapróbálom</button><details class="location-map-list" hidden><summary>Látható helynevek</summary><div class="location-map-options"></div><p class="location-map-list-note" hidden>Nagyíts közelebb a további helynevekhez.</p></details>';
  const canvas = container.querySelector('.location-map-canvas'), status = container.querySelector('.location-map-status');
  const retry = container.querySelector('.location-map-retry'), options = container.querySelector('.location-map-options');
  const details = container.querySelector('.location-map-list'), summary = details.querySelector('summary'), note = container.querySelector('.location-map-list-note');
  const visible = () => !disposed && !document.hidden && canvas.getBoundingClientRect().width > 0 && canvas.getBoundingClientRect().height > 0;
  const tell = message => { if (!disposed && status.textContent !== message) status.textContent = message; };
  const fail = () => {
    if (disposed) return;
    failed = true; loading = false; retry.hidden = false;
    tell('A térkép most nem tölthető be. A helyszíneket a keresőmezőben továbbra is kiválaszthatod.');
    try { onError?.(new Error('A térképes helyszínválasztó most nem érhető el.')); } catch {}
  };
  const bounds = () => {
    const value = map.getBounds();
    return [value.getWest(), value.getSouth(), value.getEast(), value.getNorth()];
  };
  function paintLabels() {
    if (!ready || disposed) return;
    const features = currentLabels;
    const payload = JSON.stringify(features);
    if (payload !== lastLabelPayload) { lastLabelPayload = payload; map.getSource(LABEL_SOURCE).setData({type: 'FeatureCollection', features}); }
    for (const feature of features) {
      const value = selected.has(feature.id);
      if (labelSelection.get(feature.id) === value) continue;
      map.setFeatureState({source: LABEL_SOURCE, id: feature.id}, {selected: value});
      labelSelection.set(feature.id, value);
    }
  }
  function paintOutlines() {
    if (!ready || disposed) return;
    // Remove deselections synchronously, including while a previous fetch waits.
    const features = currentOutlines.filter(feature => selected.has(feature.id));
    const payload = JSON.stringify(features.map(feature => feature.id));
    if (payload !== lastOutlinePayload) { lastOutlinePayload = payload; map.getSource(OUTLINE_SOURCE).setData({type: 'FeatureCollection', features}); }
  }
  function renderedLabels() {
    if (!ready || disposed) return [];
    const current = new Set(currentLabels.map(feature => feature.id)), unique = new Map();
    for (const feature of map.queryRenderedFeatures(undefined, {layers: LABEL_LAYERS})) {
      const id = feature.properties?.id;
      if (current.has(id) && !unique.has(id)) unique.set(id, registry.byId.get(id));
    }
    return [...unique.values()].filter(Boolean);
  }
  function refreshOptions() {
    if (!ready || !visible()) return;
    const features = renderedLabels().sort((left, right) => left.properties.label.localeCompare(right.properties.label, 'hu'));
    const key = features.map(feature => `${feature.id}:${Number(selected.has(feature.id))}`).join('|');
    if (key !== lastOptions) {
      const focusedId = options.contains(document.activeElement) ? document.activeElement.dataset.mapLocationId : null;
      lastOptions = key; options.replaceChildren();
      for (const feature of features.slice(0, MAX_OPTIONS)) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'location-map-option';
        button.dataset.mapLocationId = feature.id;
        if (feature.properties.kind === 'neighborhood') button.dataset.mapNeighborhoodId = feature.id;
        button.textContent = feature.properties.label; button.classList.toggle('is-selected', selected.has(feature.id));
        button.setAttribute('aria-pressed', String(selected.has(feature.id)));
        button.setAttribute('aria-label', `${feature.properties.label} ${selected.has(feature.id) ? 'eltávolítása a keresésből' : 'hozzáadása a kereséshez'}`);
        button.addEventListener('click', () => choose(feature.id)); options.append(button);
      }
      summary.textContent = `Látható helynevek (${features.length})`; details.hidden = !features.length;
      note.hidden = features.length <= MAX_OPTIONS;
      if (focusedId) [...options.children].find(button => button.dataset.mapLocationId === focusedId)?.focus({preventScroll: true});
    }
    if (failed || loading) return;
    if (backgroundUnavailable) tell('A háttértérkép egy része most nem érhető el. A helynevekre továbbra is kattinthatsz.');
    else if (!features.length) tell('Nagyíts rá egy településre a helynevek kiválasztásához.');
    else tell(`${features.length} helynév látható.`);
  }
  function selectAncestors(id) {
    const boundary = registry?.byId.get(id)?.properties.boundaryId || id;
    const ancestors = neighborhoodAncestors(boundary, parents);
    // Neighborhood selections also replace a selected administrative district
    // whose polygon is the actual containing ancestor.
    const aliases = Object.entries(registry?.districtBoundaries || {}).filter(([, area]) => ancestors.includes(area)).map(([district]) => district);
    return [...ancestors, ...aliases];
  }
  function choose(id) {
    if (!ready || disposed || !registry?.byId.has(id)) return;
    const location = getLocation(id), wasSelected = selected.has(id), revision = selectionRevision;
    const ancestorIds = selectAncestors(id);
    try {
      if (onSelect(id, {ancestorIds}) === false || disposed) return;
      if (selectionRevision === revision) {
        if (wasSelected) selected.delete(id);
        else { for (const ancestor of ancestorIds) selected.delete(ancestor); selected.add(id); }
      }
      syncSelection(); tell(`${location.label} ${wasSelected ? 'eltávolítva a keresésből.' : 'hozzáadva a kereséshez.'}`);
    } catch { tell('A helyszínt most nem sikerült hozzáadni. Próbáld újra, vagy válaszd ki a keresőmezőben.'); }
  }
  function syncSelection() {
    if (disposed) return;
    paintLabels(); paintOutlines(); lastOptions = null; refreshOptions(); scheduleViewport();
  }
  async function loadOutline(row, signal) {
    if (outlineCache.has(row.file)) {
      const cached = outlineCache.get(row.file); outlineCache.delete(row.file); outlineCache.set(row.file, cached); return cached;
    }
    const value = await requestJSON(new URL(row.file, DATA_ROOT), signal);
    let features;
    if (row.town) {
      if (!value || value.type !== 'Feature' || value.version !== registry.version || value.mapVersion !== manifest.version
        || value.id !== row.id || !validBounds(value.bbox) || geometryPointCount(value.geometry) < 0) throw new Error('A településhatár nem érvényes.');
      features = [value];
    } else features = readCityFeatures(row, value, manifest, getLocation);
    if (disposed || signal.aborted) return [];
    outlineCache.set(row.file, features);
    while (outlineCache.size > MAX_CITIES) outlineCache.delete(outlineCache.keys().next().value);
    return features;
  }
  async function refreshViewport() {
    if (!ready || !visible()) return;
    const request = ++generation; viewportAbort?.abort(); viewportAbort = new AbortController();
    const signal = viewportAbort.signal, view = bounds();
    currentLabels = chooseVisiblePlaceLabels(registry.features, view, map.getZoom(), [...selected]); paintLabels();
    const selectedBoundaries = [...selected].map(id => ({id, label: registry.byId.get(id)})).filter(item => item.label
      && boundsIntersect(view, manifest.focus[item.label.properties.boundaryId] || manifest.focus[item.id]));
    const jobs = new Map();
    for (const item of selectedBoundaries) {
      const boundaryId = item.label.properties.boundaryId, location = getLocation(boundaryId);
      const areaBounds = manifest.focus[boundaryId] || manifest.focus[item.id];
      if (!boundsIntersect(view, areaBounds)) continue;
      const row = location?.kind === 'city' ? registry.towns.get(boundaryId) : manifest.cities.find(city => city.city === location?.city);
      if (row) jobs.set(row.file, {...row, town: location.kind === 'city'});
    }
    loading = jobs.size > 0; failed = false; retry.hidden = true;
    if (loading) tell('A kiválasztott helyek körvonalának betöltése…');
    else { currentOutlines = []; paintOutlines(); refreshOptions(); }
    try {
      const rows = [...jobs.values()], requested = new Set(selectedBoundaries.map(item => item.label.properties.boundaryId));
      const allFeatures = new Map();
      let next = 0, points = 0;
      async function worker() {
        while (!disposed && !signal.aborted && request === generation && next < rows.length) {
          const row = rows[next++], features = await loadOutline(row, signal);
          if (disposed || signal.aborted || request !== generation) return;
          // Keep at most eight whole files in the LRU. Results retain only the
          // explicitly requested geometries, not fifty complete city layers.
          for (const feature of features) if (requested.has(feature.id) && !allFeatures.has(feature.id)) {
            points += geometryPointCount(feature.geometry);
            if (points > MAX_SELECTED_POINTS) throw new Error('A kiválasztott körvonalak túl nagyok.');
            allFeatures.set(feature.id, feature);
          }
        }
      }
      await Promise.all(Array.from({length: Math.min(OUTLINE_CONCURRENCY, rows.length)}, worker));
      if (disposed || signal.aborted || request !== generation) return;
      currentOutlines = selectedBoundaries.flatMap(({id, label}) => {
        const original = allFeatures.get(label.properties.boundaryId);
        return original ? [{...original, id, properties: {id}}] : [];
      });
      loading = false; paintOutlines(); refreshOptions();
    } catch { if (!disposed && !signal.aborted && request === generation) { viewportAbort.abort(); fail(); } }
  }
  function scheduleViewport() {
    if (!ready || disposed) return;
    clearTimeout(timer); viewportAbort?.abort(); generation++; loading = false;
    timer = setTimeout(() => { timer = null; void refreshViewport(); }, 140);
  }
  function focus(id) {
    if (disposed || typeof id !== 'string') return;
    const location = getLocation(id); if (!location) return;
    pendingFocus = id;
    if (!ready || !visible()) return;
    let target = manifest.focus[id];
    if (!target && location.city === 'Budapest' && location.district) {
      const roman = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX','XXI','XXII','XXIII'];
      const number = roman.indexOf(String(location.district).replace(/\./g, '').trim()) + 1;
      if (number) target = manifest.focus[`district:Budapest:${number}`];
    }
    if (!target && location.city) target = manifest.focus[`city:${location.city}`];
    pendingFocus = null;
    if (!validBounds(target)) return;
    map.fitBounds([[target[0], target[1]], [target[2], target[3]]], {padding: 20, maxZoom: location.kind === 'neighborhood' ? 17 : 14, duration: 0});
    scheduleViewport();
  }
  function resize() {
    if (!map || !visible()) return;
    map.resize();
    if (pendingFocus) focus(pendingFocus); else scheduleViewport();
  }
  function click(event) {
    if (!ready) return;
    const point = event.point, coarse = event.originalEvent?.pointerType === 'touch' || window.matchMedia?.('(pointer: coarse)').matches;
    const slop = coarse ? 12 : 4;
    // Search outward from the actual drawn glyph bounds. Town and quarter names
    // have fixed opposite offsets even when they share a geographic anchor.
    let hits = map.queryRenderedFeatures(point, {layers: LABEL_LAYERS});
    for (let radius = 2; !hits.length && radius <= slop; radius += 2) {
      hits = map.queryRenderedFeatures([[point.x - radius, point.y - radius], [point.x + radius, point.y + radius]], {layers: LABEL_LAYERS});
    }
    const ids = new Set(currentLabels.map(feature => feature.id));
    const chosen = chooseLabelHit(hits.filter(feature => ids.has(feature.properties?.id)), point, position => map.project(position));
    if (chosen) choose(chosen.properties.id);
  }
  function hover(event) {
    if (!ready) return;
    map.getCanvas().style.cursor = map.queryRenderedFeatures(event.point, {layers: LABEL_LAYERS}).length ? 'pointer' : '';
  }
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
  observer?.observe(canvas);
  const visibility = () => {
    if (document.hidden) { clearTimeout(timer); viewportAbort?.abort(); generation++; loading = false; }
    else resize();
  };
  const focusIn = () => map?.scrollZoom.enable();
  const focusOut = event => { if (!canvas.contains(event.relatedTarget)) map?.scrollZoom.disable(); };
  canvas.addEventListener('focusin', focusIn); canvas.addEventListener('focusout', focusOut);
  document.addEventListener('visibilitychange', visibility); window.addEventListener('resize', resize);
  async function boot() {
    if (disposed || booting) return;
    booting = true; ready = false; failed = false; retry.hidden = true; tell('Térkép betöltése…');
    clearTimeout(timer); viewportAbort?.abort(); generation++; loading = false;
    bootAbort?.abort(); bootAbort = new AbortController();
    try {
      if (map) {
        const center = map.getCenter(); camera = {center: [center.lng, center.lat], zoom: map.getZoom()};
        map.remove(); map = null;
      }
      currentLabels = []; currentOutlines = []; options.replaceChildren(); details.hidden = true;
      const [renderer, index] = await Promise.all([loadMapLibre(), getManifest()]);
      if (disposed) return;
      library = renderer; manifest = index;
      try { parents = validateNeighborhoodHierarchy(index.hierarchy, index, getLocation); registry = validatePlaceLabels(index.labels, index, getLocation); }
      catch (error) { manifestPromise = null; throw error; }
      lastLabelPayload = ''; lastOutlinePayload = ''; lastOptions = null; labelSelection.clear();
      map = new library.Map({container: canvas, style: structuredClone(index.style), center: camera.center, zoom: camera.zoom,
        minZoom: 6, maxZoom: 18, dragRotate: false, pitchWithRotate: false, scrollZoom: false, doubleClickZoom: false,
        attributionControl: false, locale: {'NavigationControl.ZoomIn': 'Nagyítás', 'NavigationControl.ZoomOut': 'Kicsinyítés', 'AttributionControl.ToggleAttribution': 'Források'}});
      map.touchZoomRotate.disableRotation();
      map.addControl(new library.NavigationControl({showCompass: false}), 'top-left');
      // Fixed credits remain visible when remote TileJSON cannot load. A custom
      // control avoids duplicate provider/source attribution strings.
      let attribution;
      map.addControl({
        onAdd() {
          attribution = document.createElement('div');
          attribution.className = 'maplibregl-ctrl maplibregl-ctrl-attrib';
          attribution.setAttribute('aria-label', 'Térkép forrásai');
          const inner = document.createElement('div'); inner.className = 'maplibregl-ctrl-attrib-inner';
          for (const [label, href] of [
            ['OpenFreeMap', 'https://openfreemap.org/'],
            ['© OpenMapTiles', 'https://openmaptiles.org/'],
            ['© OpenStreetMap contributors', 'https://www.openstreetmap.org/copyright']
          ]) {
            if (inner.childNodes.length) inner.append(document.createTextNode(' · '));
            const link = document.createElement('a'); link.textContent = label; link.href = href;
            link.target = '_blank'; link.rel = 'noopener noreferrer'; inner.append(link);
          }
          attribution.append(inner); return attribution;
        },
        onRemove() { attribution?.remove(); }
      }, 'bottom-right');
      map.on('error', () => { if (!disposed) { backgroundUnavailable = true; if (ready && !failed) { retry.hidden = false; refreshOptions(); } } });
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => finish(false), REQUEST_TIMEOUT);
        const loaded = () => finish(true), aborted = () => finish(false);
        function finish(success) { clearTimeout(timeout); map.off('load', loaded); bootAbort.signal.removeEventListener('abort', aborted); success ? resolve() : reject(new Error('A térkép betöltése megszakadt.')); }
        map.on('load', loaded); bootAbort.signal.addEventListener('abort', aborted, {once: true});
      });
      if (disposed) return;
      suppressDuplicatePlaceLabels(map, registry.coverage);
      map.addSource(OUTLINE_SOURCE, {type: 'geojson', data: emptyCollection()});
      map.addLayer({id: 'otthonra-selected-outlines', type: 'line', source: OUTLINE_SOURCE,
        paint: {'line-color': '#c6623e', 'line-width': 2.5, 'line-opacity': 0.95}});
      map.addSource(LABEL_SOURCE, {type: 'geojson', data: emptyCollection(), promoteId: 'id'});
      const layout = selectablePlaceLabelLayout();
      const selectedStyle = ['boolean', ['feature-state', 'selected'], false];
      map.addLayer({id: LABEL_LAYERS[0], type: 'symbol', source: LABEL_SOURCE, layout,
        paint: {'text-color': ['case', selectedStyle, '#a64c2c', '#284b41'],
          'text-halo-color': ['case', selectedStyle, '#fff8ec', '#fffdf7'], 'text-halo-width': 2.5}});
      ready = true; failed = false; booting = false;
      map.on('moveend', scheduleViewport); map.on('idle', refreshOptions); map.on('click', click); map.on('mousemove', hover);
      map.on('movestart', () => { viewportAbort?.abort(); generation++; loading = false; });
      if (pendingFocus) focus(pendingFocus); else scheduleViewport();
      resize();
    } catch { if (!disposed) fail(); }
    finally { booting = false; }
  }
  const retryClick = () => {
    if (disposed || booting) return;
    clearTimeout(timer); retry.hidden = true; failed = false;
    if (ready && !backgroundUnavailable) void refreshViewport();
    else { backgroundUnavailable = false; manifestPromise = null; bootAbort?.abort(); void boot(); }
  };
  retry.addEventListener('click', retryClick); void boot();
  return {
    setSelection(ids, {focusId} = {}) {
      if (disposed) return;
      selectionRevision++; selected = new Set(Array.isArray(ids) ? ids.slice(0, MAX_SELECTED) : []);
      if (pendingFocus && !selected.has(pendingFocus)) pendingFocus = null;
      syncSelection(); if (focusId) focus(focusId);
    },
    focus,
    destroy() {
      if (disposed) return;
      disposed = true; generation++; clearTimeout(timer); viewportAbort?.abort(); bootAbort?.abort(); observer?.disconnect();
      canvas.removeEventListener('focusin', focusIn); canvas.removeEventListener('focusout', focusOut);
      document.removeEventListener('visibilitychange', visibility); window.removeEventListener('resize', resize);
      retry.removeEventListener('click', retryClick); map?.remove(); outlineCache.clear(); currentLabels = []; currentOutlines = []; container.replaceChildren();
    }
  };
}
