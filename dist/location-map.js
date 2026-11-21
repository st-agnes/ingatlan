// Public, display-only neighborhood map. Search membership still uses the full
// canonical boundaries in MySQL; this module never handles property addresses.
const DATA_ROOT = new URL('./data/map/', import.meta.url);
const MIN_AREA_ZOOM = 11;
const MAX_CITIES = 8;
const MAX_FEATURES = 650;
const MAX_OPTIONS = 120;
const MAX_CITY_POINTS = 200000;
const REQUEST_TIMEOUT = 15000;
const assetPromises = new Map();
const featureAreas = new WeakMap();
let manifestPromise;

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

function areaBand(area, largest) {
  return Math.min(7, Math.max(0, Math.floor(Math.log(largest / area) / Math.log(4) + 1e-10)));
}

/** Each town has its own scale; even the tiniest quarters are available at 18. */
export function neighborhoodZoom(feature, cityFeatures) {
  const area = featureArea(feature);
  if (!(area > 0) || !Array.isArray(cityFeatures)) return MIN_AREA_ZOOM;
  const largest = cityFeatures.reduce((max, item) => item?.properties?.city === feature?.properties?.city
    ? Math.max(max, featureArea(item)) : max, area);
  return MIN_AREA_ZOOM + areaBand(area, largest);
}

/** One size band per visible town, falling back when that viewport has no finer areas. */
export function chooseVisibleNeighborhoods(features, bounds, zoom) {
  if (!Array.isArray(features) || !validBounds(bounds) || !finite(zoom) || zoom < MIN_AREA_ZOOM) return [];
  const requested = Math.min(7, Math.floor(zoom) - MIN_AREA_ZOOM), cities = new Map();
  for (const feature of features) {
    const area = featureArea(feature), city = feature?.properties?.city;
    if (!(area > 0) || typeof city !== 'string') continue;
    if (!cities.has(city)) cities.set(city, {largest: 0, features: []});
    const group = cities.get(city);
    group.largest = Math.max(group.largest, area); group.features.push(feature);
  }
  const result = [];
  for (const group of cities.values()) {
    let deepest = -1, visible = [];
    for (const feature of group.features) {
      if (!boundsIntersect(feature.bbox, bounds)) continue;
      const band = areaBand(featureArea(feature), group.largest);
      if (band > requested || band < deepest) continue;
      if (band > deepest) { deepest = band; visible = []; }
      visible.push(feature);
    }
    result.push(...visible);
  }
  return result;
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

async function loadLeaflet() {
  await Promise.all([
    loadAsset('./location-map.css', 'style', 'otthonra-location-map-css'),
    loadAsset('./vendor/leaflet/leaflet.css', 'style', 'otthonra-leaflet-css'),
    window.L?.version === '1.9.4' ? Promise.resolve()
      : loadAsset('./vendor/leaflet/leaflet.js', 'script', 'otthonra-leaflet-js')
  ]);
  if (!window.L || window.L.version !== '1.9.4') throw new Error('A térkép megjelenítője nem érhető el.');
  return window.L;
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
    || !Number.isInteger(value.count) || value.count < 1 || !Array.isArray(value.cities) || !value.focus) throw new Error('A térképadatok nem érvényesek.');
  const names = new Set();
  const cities = value.cities.map(row => {
    if (!row || typeof row.city !== 'string' || !row.city || names.has(row.city) || !validBounds(row.bounds)
      || !/^city-[a-f0-9]{16,64}\.json$/.test(row.file) || !Number.isInteger(row.count) || row.count < 1 || row.count > 4308) throw new Error('A térképadatok nem érvényesek.');
    names.add(row.city);
    return {city: row.city, bounds: row.bounds, file: row.file, count: row.count};
  });
  const focus = Object.create(null);
  for (const [id, bounds] of Object.entries(value.focus)) if (validBounds(bounds)) focus[id] = bounds;
  return {version: value.version, count: value.count, cities, focus};
}

function getManifest() {
  if (!manifestPromise) manifestPromise = requestJSON(new URL('index.json', DATA_ROOT)).then(validateManifest)
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

/**
 * Mount independently of editor/auth/network busy state. The callback adds an
 * existing canonical neighborhood ID through the ordinary location picker.
 */
export function createLocationMap(container, {selectedIds = [], getLocation, onSelect, onError} = {}) {
  if (!container || typeof getLocation !== 'function' || typeof onSelect !== 'function') throw new TypeError('A térképes helyszínválasztó beállításai hiányoznak.');
  let selected = new Set(Array.isArray(selectedIds) ? selectedIds : []), disposed = false;
  let map, leaflet, tileLayer, areaLayer, manifest, currentFeatures = [], pendingFocus = [...selected][0] || null, focusedCity = null, pendingAreaFocus = null;
  let viewportAbort, timer, generation = 0, booting = false, tileUnavailable = false, failed = false, focusing = false;
  const cityCache = new Map(), pathListeners = [];
  container.classList.add('location-map');
  container.innerHTML = '<div class="location-map-heading"><strong>Válassz a térképen is</strong><span>Közelíts a kisebb városrészekhez.</span></div><div class="location-map-canvas" role="region" aria-label="Városrészek térképes kiválasztása"></div><div class="location-map-status" role="status" aria-live="polite">Térkép betöltése…</div><button type="button" class="location-map-retry" hidden>Újrapróbálom</button><details class="location-map-list" hidden><summary>Látható városrészek</summary><div class="location-map-options"></div><p class="location-map-list-note" hidden>Nagyíts közelebb a további városrészekhez.</p></details><div class="location-map-legend"><span class="location-map-legend-area">Városrész</span><span class="location-map-legend-selected">Kiválasztva</span><a href="/THIRD-PARTY-NOTICES.txt" target="_blank" rel="noopener noreferrer">Területhatárok forrásai</a></div>';
  const canvas = container.querySelector('.location-map-canvas'), status = container.querySelector('.location-map-status');
  const retry = container.querySelector('.location-map-retry'), options = container.querySelector('.location-map-options');
  const details = container.querySelector('.location-map-list'), summary = details.querySelector('summary'), listNote = container.querySelector('.location-map-list-note');
  const visible = () => !disposed && canvas.getBoundingClientRect().width > 0 && canvas.getBoundingClientRect().height > 0 && !document.hidden;
  const tell = message => { if (!disposed) status.textContent = message; };
  const style = feature => ({color: selected.has(feature.id) ? '#c6623e' : '#49756a', weight: selected.has(feature.id) ? 3 : 1.5,
    opacity: 0.95, fillColor: selected.has(feature.id) ? '#e7855e' : '#7ba793', fillOpacity: selected.has(feature.id) ? 0.34 : 0.13});
  const fail = () => {
    if (disposed) return;
    failed = true; retry.hidden = false;
    tell('A térkép most nem tölthető be. A helyszíneket a keresőmezőben továbbra is kiválaszthatod.');
    try { onError?.(new Error('A térképes helyszínválasztó most nem érhető el.')); } catch {}
  };
  function removePathListeners() { for (const dispose of pathListeners.splice(0)) dispose(); }
  function syncSelection() {
    if (disposed) return;
    areaLayer?.setStyle(style);
    for (const element of container.querySelectorAll('[data-map-neighborhood-id]')) {
      const active = selected.has(element.dataset.mapNeighborhoodId);
      element.setAttribute('aria-pressed', String(active)); element.classList.toggle('is-selected', active);
    }
  }
  function choose(id) {
    if (disposed || !getLocation(id) || !currentFeatures.some(feature => feature.id === id)) return;
    const location = getLocation(id);
    try {
      // The picker owns duplicates and the 50-choice limit. It may replace a
      // selected whole town with this neighborhood, even at the limit.
      if (onSelect(id) === false) return;
      if (disposed) return;
      selected.add(id); syncSelection(); tell(`${location.label} hozzáadva a kereséshez.`);
    } catch { tell('A városrészt most nem sikerült hozzáadni. Próbáld újra, vagy válaszd ki a keresőmezőben.'); }
  }
  function option(feature) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'location-map-option';
    button.dataset.mapNeighborhoodId = feature.id; button.setAttribute('aria-pressed', String(selected.has(feature.id)));
    button.textContent = feature.properties.label; button.classList.toggle('is-selected', selected.has(feature.id));
    button.addEventListener('click', () => choose(feature.id));
    return button;
  }
  function clearAreas() {
    removePathListeners(); areaLayer?.clearLayers(); currentFeatures = []; options.replaceChildren(); details.hidden = true;
  }
  function renderAreas(features, truncated) {
    clearAreas(); currentFeatures = features;
    areaLayer.addData({type: 'FeatureCollection', features});
    areaLayer.eachLayer(layer => {
      const feature = layer.feature, path = layer.getElement();
      if (!path) return;
      path.dataset.mapNeighborhoodId = feature.id; path.setAttribute('tabindex', '0'); path.setAttribute('role', 'button');
      path.setAttribute('aria-label', `${feature.properties.label} hozzáadása a kereséshez`);
      const keydown = event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); event.stopPropagation(); choose(feature.id); } };
      path.addEventListener('keydown', keydown); pathListeners.push(() => path.removeEventListener('keydown', keydown));
    });
    const sorted = [...features].sort((a, b) => a.properties.label.localeCompare(b.properties.label, 'hu'));
    for (const feature of sorted.slice(0, MAX_OPTIONS)) options.append(option(feature));
    summary.textContent = `Látható városrészek (${features.length})`; details.hidden = features.length === 0;
    listNote.hidden = sorted.length <= MAX_OPTIONS;
    syncSelection(); failed = false; retry.hidden = true;
    if (truncated) tell(`${features.length} városrész látható. Nagyíts közelebb a többi terület megjelenítéséhez.`);
    else if (!features.length) tell('Nagyíts közelebb, vagy mozdítsd el a térképet a városrészek megjelenítéséhez.');
    else if (tileUnavailable) tell('A háttértérkép most nem érhető el. A városrészek továbbra is kiválaszthatók.');
    else tell(`${features.length} városrész látható. Egy kattintással kiválaszthatod; közelítve kisebb területek jelennek meg.`);
  }

  function refineFocus(features) {
    if (!pendingAreaFocus) return false;
    const location = getLocation(pendingAreaFocus);
    const feature = location?.kind === 'neighborhood' ? features.find(item => item.id === location.id)
      : location?.kind === 'district' ? features.find(item => item.properties.city === location.city
        && item.properties.name === `${location.district} kerület`) : null;
    pendingAreaFocus = null;
    if (!feature) return false;
    const zoom = neighborhoodZoom(feature, features);
    if (map.getZoom() === zoom) return false;
    // A named quarter or ward must be shown at its own band, including tiny
    // areas above the old zoom16 ceiling. Further user zooming is unrestricted.
    focusing = true;
    try { map.setZoom(zoom, {animate: false}); } finally { focusing = false; }
    return true;
  }
  async function refreshViewport() {
    if (!map || !manifest || !visible()) return;
    const request = ++generation; viewportAbort?.abort(); viewportAbort = new AbortController();
    const signal = viewportAbort.signal;
    if (map.getZoom() < MIN_AREA_ZOOM) { clearAreas(); retry.hidden = true; tell('Nagyíts rá egy városra, hogy kiválaszthasd a városrészeket.'); return; }
    const view = map.getBounds(), bounds = [view.getWest(), view.getSouth(), view.getEast(), view.getNorth()];
    const chosen = chooseVisibleCities(manifest.cities, bounds, {preferredCity: focusedCity});
    if (!chosen.items.length) { renderAreas([], false); return; }
    tell('Városrészek betöltése…');
    try {
      const batches = await Promise.all(chosen.items.map(async row => {
        if (cityCache.has(row.file)) {
          const stored = cityCache.get(row.file); cityCache.delete(row.file); cityCache.set(row.file, stored); return stored;
        }
        const value = await requestJSON(new URL(row.file, DATA_ROOT), signal);
        const features = readCityFeatures(row, value, manifest, getLocation);
        if (disposed || signal.aborted || request !== generation) return [];
        cityCache.set(row.file, features);
        while (cityCache.size > MAX_CITIES) cityCache.delete(cityCache.keys().next().value);
        return features;
      }));
      if (disposed || signal.aborted || request !== generation) return;
      const allFeatures = batches.flat();
      if (refineFocus(allFeatures)) return;
      const seen = new Set();
      const features = chooseVisibleNeighborhoods(allFeatures, bounds, map.getZoom()).filter(feature => !seen.has(feature.id) && seen.add(feature.id))
        .sort((a, b) => Number(selected.has(b.id)) - Number(selected.has(a.id)) || a.properties.label.localeCompare(b.properties.label, 'hu'));
      const visibleFeatures = features.slice(0, MAX_FEATURES).sort((a, b) => featureArea(b) - featureArea(a) || String(a.id).localeCompare(String(b.id)));
      renderAreas(visibleFeatures, chosen.truncated || features.length > MAX_FEATURES);
    } catch { if (!disposed && !signal.aborted && request === generation) fail(); }
  }
  function scheduleViewport() {
    clearTimeout(timer); viewportAbort?.abort(); generation++;
    timer = setTimeout(() => { timer = null; void refreshViewport(); }, 180);
  }
  function focus(id) {
    if (disposed || typeof id !== 'string') return;
    const location = getLocation(id);
    if (!location) return;
    pendingFocus = id; focusedCity = location.city || null;
    pendingAreaFocus = ['neighborhood', 'district'].includes(location.kind) ? id : null;
    if (!map || !manifest || !visible()) return;
    let bounds = manifest.focus[id];
    if (!bounds && location.city === 'Budapest' && location.district) {
      const roman = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX','XXI','XXII','XXIII'];
      const district = roman.indexOf(String(location.district).replace(/\./g, '').trim()) + 1;
      if (district) bounds = manifest.focus[`district:Budapest:${district}`];
    }
    if (!bounds && location.city) bounds = manifest.focus[`city:${location.city}`];
    if (!validBounds(bounds)) { pendingFocus = null; return; }
    pendingFocus = null;
    focusing = true;
    try {
      map.fitBounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], {padding: [18, 18], maxZoom: location.kind === 'neighborhood' ? 18 : 14, animate: false});
      if (map.getZoom() < MIN_AREA_ZOOM) map.setZoom(MIN_AREA_ZOOM, {animate: false});
    } finally { focusing = false; }
    scheduleViewport();
  }
  function resize() {
    if (!map || !visible()) return;
    map.invalidateSize({animate: false, pan: false});
    if (pendingFocus) focus(pendingFocus); else scheduleViewport();
  }
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
  observer?.observe(canvas);
  const visibility = () => {
    if (document.hidden) { clearTimeout(timer); viewportAbort?.abort(); generation++; }
    else resize();
  };
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('resize', resize);
  async function boot() {
    if (disposed || booting) return;
    booting = true; failed = false; retry.hidden = true; tell('Térkép betöltése…');
    try {
      const [library, index] = await Promise.all([loadLeaflet(), getManifest()]);
      if (disposed) return;
      leaflet = library; manifest = index;
      if (!map) {
        map = leaflet.map(canvas, {minZoom: 6, maxZoom: 18, scrollWheelZoom: false,
          maxBounds: [[44.5, 15], [49.5, 24]], maxBoundsViscosity: 0.7, attributionControl: true, zoomControl: false});
        leaflet.control.zoom({zoomInTitle: 'Nagyítás', zoomOutTitle: 'Kicsinyítés'}).addTo(map);
        map.attributionControl.setPrefix(false);
        tileLayer = leaflet.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'}).addTo(map);
        tileLayer.on('tileerror', () => { if (!disposed) { tileUnavailable = true; if (currentFeatures.length && !failed) tell('A háttértérkép most nem érhető el. A városrészek továbbra is kiválaszthatók.'); } });
        areaLayer = leaflet.geoJSON(null, {style, onEachFeature(feature, layer) {
          const label = document.createElement('span'); label.textContent = feature.properties.label;
          layer.bindTooltip(label, {sticky: true, direction: 'top'});
        }}).addTo(map);
        map.on('moveend', scheduleViewport);
        map.on('zoomstart', () => {
          if (!focusing) pendingAreaFocus = null;
          clearTimeout(timer); viewportAbort?.abort(); generation++; clearAreas();
        });
        map.on('dragstart', () => { pendingAreaFocus = null; });
        map.on('focus', () => map.scrollWheelZoom.enable()); map.on('blur', () => map.scrollWheelZoom.disable());
        map.on('click', event => {
          const point = [event.latlng.lng, event.latlng.lat];
          const feature = chooseSmallestFeature(currentFeatures, point);
          if (feature) choose(feature.id);
        });
        map.setView([47.16, 19.5], 7);
      }
      if (pendingFocus) focus(pendingFocus); else scheduleViewport();
      resize();
    } catch { fail(); }
    finally { booting = false; }
  }
  const retryClick = () => {
    if (disposed || booting) return;
    retry.hidden = true; failed = false;
    if (map && manifest) { tileLayer?.redraw(); void refreshViewport(); } else void boot();
  };
  retry.addEventListener('click', retryClick);
  void boot();
  return {
    setSelection(ids, {focusId} = {}) {
      if (disposed) return;
      selected = new Set(Array.isArray(ids) ? ids : []);
      if (pendingFocus && !selected.has(pendingFocus)) pendingFocus = null;
      if (pendingAreaFocus && !selected.has(pendingAreaFocus)) pendingAreaFocus = null;
      syncSelection();
      if (focusId) focus(focusId);
    },
    focus,
    destroy() {
      if (disposed) return;
      disposed = true; generation++; clearTimeout(timer); viewportAbort?.abort(); observer?.disconnect();
      document.removeEventListener('visibilitychange', visibility); window.removeEventListener('resize', resize);
      retry.removeEventListener('click', retryClick); removePathListeners(); map?.remove();
      cityCache.clear(); currentFeatures = []; pendingAreaFocus = null; container.replaceChildren();
    }
  };
}
