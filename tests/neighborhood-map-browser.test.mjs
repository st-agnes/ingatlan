/** Real MapLibre + real pickers, with isolated background tiles and canonical
 * synthetic display fixtures. Address/search membership data is never replaced. */
import assert from 'node:assert/strict';
import {mkdir, readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {getLocation, searchLocations} from '../dist/locations.js';
import {neighborhoods} from '../dist/neighborhoods-data.js';
import {editorField, editorSave, editorStep} from './editor-browser-helpers.mjs';
import {mockMapTiles} from './map-browser-network.mjs';

const modulePath = process.env.PLAYWRIGHT_MODULE;
const playwrightUrl = modulePath ? (modulePath.startsWith('file:') ? modulePath : pathToFileURL(resolve(modulePath)).href) : new URL('../.local/browser-tests/node_modules/playwright/index.mjs', import.meta.url).href;
const {chromium} = await import(playwrightUrl);
const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000').origin;
const viewports = [{name: 'desktop', width: 1280, height: 900, touch: false}, {name: 'tablet', width: 800, height: 1100, touch: true}, {name: 'mobile', width: 390, height: 844, touch: true}];
const version = 'a'.repeat(64), labelVersion = 'isolated-map-labels-v1';
const city = getLocation('city:Debrecen'), otherCity = getLocation('city:Szeged'), solymar = getLocation('city:Solymár');
const quarter = (city, name) => getLocation(neighborhoods.find(item => item.city === city && item.name === name).id);
const central = quarter('Debrecen', 'Belváros'), venkert = quarter('Debrecen', 'Vénkert'), sestakert = quarter('Debrecen', 'Sestakert'), tocoskert = quarter('Debrecen', 'Tócóskert'), szeged = quarter('Szeged', 'Belváros');
const buda = quarter('Budapest', 'Buda'), pest = quarter('Budapest', 'Pest'), budapestWard = quarter('Budapest', 'V. kerület'), belvaros = quarter('Budapest', 'Belváros'), ward = getLocation('district:Budapest:5');
const rectangle = (west, south, east, north) => [[[west, south], [east, south], [east, north], [west, north], [west, south]]];
const makeFeature = (location, bbox) => ({type: 'Feature', id: location.id, bbox, properties: {id: location.id, name: location.name || location.label, city: location.city, label: location.label, estimated: !!location.estimated}, geometry: {type: 'Polygon', coordinates: rectangle(...bbox)}});
const debrecenBounds = [21.59, 47.50, 21.65, 47.56], szegedBounds = [20.12, 46.23, 20.18, 46.29], budapestBounds = [18.95, 47.40, 19.25, 47.60], solymarBounds = [18.90, 47.57, 18.95, 47.60];
// MapLibre uses a 512-pixel world: zoom13 preserves the geographic overview
// that the old 256-pixel renderer displayed at zoom14.
// The first two polygons overlap. A named-label tap must identify the named
// place, including the larger region, instead of selecting the smallest shape.
const centralFeature = makeFeature(central, [21.614, 47.522, 21.626, 47.532]);
const bulkTownBounds = ['Hajdúszoboszló', 'Hajdúböszörmény', 'Hajdúnánás', 'Hajdúsámson', 'Balmazújváros', 'Berettyóújfalu', 'Püspökladány', 'Derecske', 'Nádudvar'].map((name, index) => {
  const location = getLocation(`city:${name}`); assert.ok(location);
  const point = [21.60 + (index % 3) * .015, 47.51 + Math.floor(index / 3) * .015];
  return {location, point, bounds: [point[0] - .003, point[1] - .003, point[0] + .003, point[1] + .003]};
});
const polygons = [makeFeature(venkert, [21.602, 47.530, 21.620, 47.541]), makeFeature(sestakert, [21.608, 47.529, 21.628, 47.542]), makeFeature(tocoskert, [21.625, 47.520, 21.632, 47.525])];
const szegedFeature = makeFeature(szeged, [20.135, 46.245, 20.155, 46.265]);
const budapestPolygons = [makeFeature(buda, [18.95, 47.40, 19.08, 47.60]), makeFeature(pest, [19.08, 47.40, 19.25, 47.60]), makeFeature(budapestWard, [19.085, 47.48, 19.125, 47.52]), makeFeature(belvaros, [19.095, 47.49, 19.115, 47.51])];
// Include real catalogue IDs for the selection-limit fixture. Their synthetic
// points are outside the town viewport, exercising retained offscreen choices.
const extraLocations = neighborhoods.filter(item => item.city === 'Debrecen' && ![venkert.id, sestakert.id, tocoskert.id, central.id].includes(item.id)).slice(0, 49).map(item => getLocation(item.id));
assert.equal(extraLocations.length, 49);
const extras = extraLocations.map((location, index) => makeFeature(location, [21.80 + index * .002, 47.55, 21.801 + index * .002, 47.551]));
const allPolygons = [...polygons, centralFeature, szegedFeature, ...budapestPolygons, ...extras];
const cityRows = [
  {city: 'Debrecen', bounds: debrecenBounds, file: `city-${'a'.repeat(20)}.json`, count: polygons.length + 1 + extras.length},
  {city: 'Szeged', bounds: szegedBounds, file: `city-${'b'.repeat(20)}.json`, count: 1},
  {city: 'Budapest', bounds: budapestBounds, file: `city-${'c'.repeat(20)}.json`, count: 4}
];
const manifest = {schemaVersion: 1, version, sourceSha256: 'd'.repeat(64), count: allPolygons.length, cities: cityRows, focus: {'city:Debrecen': debrecenBounds, 'city:Szeged': szegedBounds, 'city:Budapest': budapestBounds, 'city:Solymár': solymarBounds, ...Object.fromEntries(bulkTownBounds.map(row => [row.location.id, debrecenBounds])), [ward.id]: budapestPolygons[2].bbox, ...Object.fromEntries(allPolygons.map(item => [item.id, item.bbox]))}, attribution: ['Isolated synthetic map display fixture, never address/search data.']};
const hierarchy = {schemaVersion: 1, version: 'isolated-hierarchy-v1', mapVersion: version, sourceSha256: manifest.sourceSha256, count: manifest.count, policy: {minimumCoverage: .95, maximumChildAreaRatio: .8}, parents: {[budapestWard.id]: pest.id, [belvaros.id]: budapestWard.id}};
const labelPoints = new Map([
  [city.id, [21.596, 47.505]], [otherCity.id, [20.128, 46.236]], ['city:Budapest', [19.06, 47.405]], [solymar.id, [18.925, 47.585]],
  [central.id, [21.620, 47.527]], [venkert.id, [21.611, 47.535]], [sestakert.id, [21.619, 47.532]], [tocoskert.id, [21.628, 47.524]], [szeged.id, [20.145, 46.255]],
  ...bulkTownBounds.map(row => [row.location.id, row.point]), [buda.id, [19.015, 47.50]], [pest.id, [19.165, 47.50]], [budapestWard.id, [19.10, 47.515]], [ward.id, [19.10, 47.515]], [belvaros.id, [19.107, 47.495]]
]);
const labelFeature = location => {
  const geometry = allPolygons.find(item => item.id === location.id);
  const coordinates = labelPoints.get(location.id) || [(geometry.bbox[0] + geometry.bbox[2]) / 2, (geometry.bbox[1] + geometry.bbox[3]) / 2];
  const minZoom = bulkTownBounds.some(row => row.location.id === location.id) ? 16 : location.kind === 'city' ? 6 : [buda.id, pest.id].includes(location.id) ? 8 : location.id === belvaros.id ? 12 : 10;
  return {type: 'Feature', id: location.id, geometry: {type: 'Point', coordinates}, properties: {id: location.id, name: location.name || (location.kind === 'district' ? 'V. kerület' : location.city) || location.label, label: location.label, city: location.city, kind: location.kind, minZoom, priority: location.id === 'city:Budapest' ? 0 : location.kind === 'city' ? 10 : [buda.id, pest.id].includes(location.id) ? 50 : location.id === ward.id ? 65 : location.id === budapestWard.id ? 70 : location.id === belvaros.id ? 120 : 100, boundaryId: location.id === ward.id ? budapestWard.id : location.id}};
};
const towns = [[city, debrecenBounds, 'e'], [otherCity, szegedBounds, 'f'], [getLocation('city:Budapest'), budapestBounds, '1'], [solymar, solymarBounds, '2'], ...bulkTownBounds.map((row, index) => [row.location, row.bounds, (index + 3).toString(16)])].map(([location, bounds, hex]) => ({id: location.id, file: `town-${hex.repeat(20)}.json`, bounds}));
const labels = {schemaVersion: 1, version: labelVersion, mapVersion: version, sourceSha256: manifest.sourceSha256, municipalitiesSha256: 'e'.repeat(64), namedNodesSha256: 'f'.repeat(64), displayOnly: true, coverage: {type: 'Polygon', coordinates: rectangle(16, 45.5, 23.1, 48.8)}, type: 'FeatureCollection', features: [...allPolygons.map(item => labelFeature(getLocation(item.id))), ...towns.map(item => labelFeature(getLocation(item.id))), labelFeature(ward)], towns, districtBoundaries: {[ward.id]: budapestWard.id}};
labels.count = labels.features.length;
const owner = {id: '10000000-0000-4000-8000-000000000001', name: 'Térképes Anna', email: 'map-browser@example.test', phone: '', accountType: 'private'};
const searchId = '20000000-0000-4000-8000-000000000001', propertyId = '30000000-0000-4000-8000-000000000001';
const labelLayers = ['otthonra-place-labels'];
const interact = (viewport, locator) => viewport.touch ? locator.tap() : locator.click();
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const mapZoom = map => map.locator('.location-map-canvas').evaluate(element => element.__mapBrowserInstance.getZoom());
const mapCenter = map => map.locator('.location-map-canvas').evaluate(element => {const center = element.__mapBrowserInstance.getCenter(); return [center.lng, center.lat];});
const inputChips = landing => landing ? '#landing-location-chips' : '#location-chips';
const chip = (page, id, landing = false) => page.locator(`${inputChips(landing)} [data-remove-location="${id}"]`);

async function waitMapPaint(map, expectedZoom) {
  await map.locator('.location-map-canvas').evaluate((element, expectedZoom) => new Promise((resolve, reject) => {
    const deadline = performance.now() + 15000;
    function check() {
      const map = element.__mapBrowserInstance, status = element.closest('.location-map').querySelector('.location-map-status')?.textContent || '';
      if (map && performance.now() - (element.__mapBrowserLastMove || 0) > 220 && !map.isMoving() && map.loaded() && (expectedZoom === undefined || Math.abs(map.getZoom() - expectedZoom) < .01) && !status.includes('betöltése')) {resolve(); return;}
      if (performance.now() > deadline) {reject(new Error('Map did not finish its viewport: ' + JSON.stringify({zoom: map?.getZoom(), status, loaded: map?.loaded()}))); return;}
      requestAnimationFrame(check);
    }
    check();
  }), expectedZoom);
}
async function zoom(map, viewport, direction) {
  await waitMapPaint(map); const before = await mapZoom(map);
  await interact(viewport, map.locator(`.maplibregl-ctrl-zoom-${direction}`));
  await waitMapPaint(map, before + (direction === 'in' ? 1 : -1));
}
async function zoomTo(map, viewport, level) {
  // Geographic fit intentionally produces fractional zoom. Arrange this
  // synthetic fixture at an exact starting level through the public camera
  // API, retaining its center; subsequent steps exercise the actual controls.
  // This keeps target labels inside the same fixture viewport on every device.
  const startingZoom = await mapZoom(map), arrangedZoom = Math.round(startingZoom);
  if (Math.abs(startingZoom - arrangedZoom) > 1e-8) {
    await map.locator('.location-map-canvas').evaluate((element, zoom) => element.__mapBrowserInstance.jumpTo({zoom}), arrangedZoom);
    await waitMapPaint(map, arrangedZoom);
  }
  for (let step = 0; step < 16; step++) {
    const current = await mapZoom(map);
    if (Math.abs(current - level) < .01) {await waitMapPaint(map, level); return;}
    await zoom(map, viewport, current < level ? 'in' : 'out');
  }
  assert.ok(Math.abs(await mapZoom(map) - level) < .01, 'Real zoom controls must reach the requested level');
}
async function assertCenter(map, expected, message) {
  const actual = await mapCenter(map);
  assert.ok(actual.every((value, index) => Math.abs(value - expected[index]) < .005), message + ': ' + JSON.stringify({actual, expected}));
}
async function placeState(map) {
  return map.locator('.location-map-canvas').evaluate((element, layers) => {
    const map = element.__mapBrowserInstance, liveLayers = layers.filter(id => map.getLayer(id));
    const rendered = liveLayers.length ? map.queryRenderedFeatures(undefined, {layers: liveLayers}) : [];
    const style = map.getStyle(), data = style.sources['otthonra-places']?.data;
    return {rendered: [...new Set(rendered.map(feature => feature.properties.id || feature.id))], candidates: typeof data === 'object' ? data.features.map(feature => ({id: feature.id, minZoom: feature.properties.minZoom})) : [], layers: style.layers};
  }, labelLayers);
}
async function waitLabel(map, id) {
  await map.locator('.location-map-canvas').evaluate((element, {id, layers}) => new Promise((resolve, reject) => {
    const deadline = performance.now() + 15000;
    function check() {
      const map = element.__mapBrowserInstance, available = layers.filter(layer => map?.getLayer(layer));
      if (available.length && map.queryRenderedFeatures(undefined, {layers: available}).some(feature => (feature.properties.id || feature.id) === id)) {resolve(); return;}
      if (performance.now() > deadline) {reject(new Error('Canonical label is not rendered: ' + id + ', zoom ' + map?.getZoom())); return;}
      requestAnimationFrame(check);
    }
    check();
  }), {id, layers: labelLayers});
}
async function clickLabel(map, id, viewport, {slop = false} = {}) {
  const canvas = map.locator('canvas.maplibregl-canvas'); await canvas.scrollIntoViewIfNeeded(); await waitLabel(map, id);
  const position = await map.locator('.location-map-canvas').evaluate((element, {id, layers, slop}) => {
    const map = element.__mapBrowserInstance, available = layers.filter(layer => map.getLayer(layer));
    const feature = map.queryRenderedFeatures(undefined, {layers: available}).find(feature => (feature.properties.id || feature.id) === id);
    const anchor = map.project(feature.geometry.coordinates), width = element.clientWidth, height = element.clientHeight;
    const xs = [0, -4, 4, -8, 8, -12, 12, -20, 20, -32, 32, -48, 48, -64, 64, -96, 96, -128, 128], ys = [0, -4, 4, -8, 8, -12, 12, -18, 18, -24, 24, -32, 32, -40, 40];
    for (const dy of ys) for (const dx of xs) {
      const point = [anchor.x + dx, anchor.y + dy];
      if (point[0] < 4 || point[1] < 4 || point[0] > width - 4 || point[1] > height - 4) continue;
      const hits = map.queryRenderedFeatures(point, {layers: available});
      if (hits.length && hits.every(hit => (hit.properties.id || hit.id) === id)) {
        if (!slop) return {x: point[0], y: point[1]};
        // Find a point just outside the glyph hitbox, within the mobile tap
        // tolerance, to verify the actual screen-space forgiving hit logic.
        for (const delta of [[0, -6], [0, 6], [-6, 0], [6, 0]]) {
          const outside = [point[0] + delta[0], point[1] + delta[1]];
          if (!map.queryRenderedFeatures(outside, {layers: available}).length) return {x: outside[0], y: outside[1]};
        }
      }
    }
    throw new Error('No unambiguous rendered-label hit point for ' + id);
  }, {id, layers: labelLayers, slop});
  await (viewport.touch ? canvas.tap({position}) : canvas.click({position}));
}
async function renderedLabelBox(map, id) {
  await waitMapPaint(map); await waitLabel(map, id);
  return map.locator('.location-map-canvas').evaluate((element, {id, layers}) => {
    const map = element.__mapBrowserInstance, available = layers.filter(layer => map.getLayer(layer));
    const feature = map.queryRenderedFeatures(undefined, {layers: available}).find(feature => (feature.properties.id || feature.id) === id);
    const anchor = map.project(feature.geometry.coordinates);
    const hasLabel = (x, y) => map.queryRenderedFeatures([x, y], {layers: available}).some(hit => (hit.properties.id || hit.id) === id);
    let seed;
    for (const dy of [0, -4, 4, -8, 8, -16, 16, -24, 24, -32, 32]) {
      for (const dx of [0, -8, 8, -16, 16, -32, 32, -64, 64]) if (hasLabel(anchor.x + dx, anchor.y + dy)) {seed = [anchor.x + dx, anchor.y + dy]; break;}
      if (seed) break;
    }
    if (!seed) throw new Error('Cannot measure the real rendered symbol: ' + id);
    function edge(x, y, dx, dy) {
      let inside = 0, outside = 1;
      while (outside < 512 && hasLabel(x + outside * dx, y + outside * dy)) {inside = outside; outside *= 2;}
      for (let step = 0; step < 12; step++) {
        const middle = (inside + outside) / 2;
        if (hasLabel(x + middle * dx, y + middle * dy)) inside = middle; else outside = middle;
      }
      return [x + inside * dx, y + inside * dy];
    }
    const left = edge(...seed, -1, 0)[0], right = edge(...seed, 1, 0)[0], middleX = (left + right) / 2;
    const top = edge(middleX, seed[1], 0, -1)[1], bottom = edge(middleX, seed[1], 0, 1)[1];
    return {coordinates: feature.geometry.coordinates, offset: [middleX - anchor.x, (top + bottom) / 2 - anchor.y], width: right - left, height: bottom - top, selected: map.getFeatureState({source: 'otthonra-places', id}).selected === true, zoom: map.getZoom()};
  }, {id, layers: labelLayers});
}
function assertSameLabelBox(actual, expected, message) {
  assert.deepEqual(actual.coordinates, expected.coordinates, message + ': geographic point');
  for (const key of ['width', 'height']) assert.ok(Math.abs(actual[key] - expected[key]) <= 1.25, `${message}: ${key} changed ${expected[key]} -> ${actual[key]}`);
  assert.ok(actual.offset.every((value, index) => Math.abs(value - expected.offset[index]) <= 1.25), message + ': symbol moved relative to its geographic point ' + JSON.stringify({actual: actual.offset, expected: expected.offset}));
}
async function pickerGeometry(page, {landing = false} = {}) {
  return page.locator(landing ? '.landing-location-layout' : '#location-picker.location-search-layout').evaluate(layout => {
    const map = layout.querySelector('.search-location-map').getBoundingClientRect(), input = layout.querySelector('input[role="combobox"]').getBoundingClientRect(), chips = layout.querySelector('.location-chips').getBoundingClientRect(), outer = layout.getBoundingClientRect();
    return {map: {left: map.left, top: map.top, right: map.right, width: map.width}, input: {left: input.left, top: input.top, right: input.right, bottom: input.bottom}, mapTop: map.top - outer.top, chipHeight: chips.height, chipWidth: chips.width, outerRight: outer.right};
  });
}
async function assertPickerLayout(page, viewport, options = {}) {
  const geometry = await pickerGeometry(page, options);
  if (viewport.width >= 768) {
    assert.ok(geometry.map.left >= geometry.input.right + 8, 'Tablet/desktop search controls sit to the left of the map');
    assert.ok(geometry.map.top <= geometry.input.bottom, 'The map starts beside the text controls, rather than below the selected places');
    assert.ok(geometry.map.width >= 200, 'The side-by-side map retains a usable viewport');
  } else {
    assert.ok(geometry.map.top >= geometry.input.bottom, 'Mobile keeps its map below the text search');
    assert.ok(geometry.chipHeight <= 34, 'Mobile selections occupy at most one compact row');
  }
  assert.ok(geometry.map.right <= geometry.outerRight + 1, 'The responsive picker does not overflow horizontally');
  return geometry;
}
async function outlineIds(map) {
  return map.locator('.location-map-canvas').evaluate(element => {
    const source = element.__mapBrowserInstance.getStyle().sources['otthonra-outlines']?.data;
    return typeof source === 'object' ? source.features.map(feature => feature.id || feature.properties.id).sort() : [];
  });
}
async function assertOutline(map, id, present = true) {
  // Acknowledged selection schedules bounded geometry loading separately from
  // the immediate text state; wait for that actual source acknowledgement.
  await map.locator('.location-map-canvas').evaluate((element, {id, present}) => new Promise((resolve, reject) => {
    const deadline = performance.now() + 15000;
    function check() {
      const data = element.__mapBrowserInstance.getStyle().sources['otthonra-outlines']?.data;
      const has = typeof data === 'object' && data.features.some(feature => (feature.id || feature.properties.id) === id);
      if (!!has === present) return resolve();
      if (performance.now() > deadline) return reject(new Error('Selected outline did not settle: ' + id + ' expected ' + present));
      requestAnimationFrame(check);
    }
    check();
  }), {id, present});
  await waitMapPaint(map);
  const state = await map.locator('.location-map-canvas').evaluate((element, id) => {
    const map = element.__mapBrowserInstance, style = map.getStyle(), source = style.sources['otthonra-outlines']?.data;
    const feature = typeof source === 'object' && source.features.find(feature => (feature.id || feature.properties.id) === id);
    return {present: !!feature, polygonal: feature && ['Polygon', 'MultiPolygon'].includes(feature.geometry.type), layers: style.layers.filter(layer => layer.source === 'otthonra-outlines')};
  }, id);
  assert.equal(state.present, present, `Only selected in-view areas may have an outline (${id})`);
  assert.ok(state.layers.some(layer => layer.type === 'line'), 'Selected boundaries use a real MapLibre line layer');
  assert.ok(state.layers.every(layer => layer.type === 'line'), 'No selected/unselected/focused polygon fill may paint over the map');
  if (present) assert.equal(state.polygonal, true);
}
async function clickEmptyInterior(map, viewport) {
  const canvas = map.locator('canvas.maplibregl-canvas'); await canvas.scrollIntoViewIfNeeded();
  const position = await map.locator('.location-map-canvas').evaluate((element, layers) => {
    const map = element.__mapBrowserInstance, available = layers.filter(layer => map.getLayer(layer));
    for (const point of [[21.606, 47.531], [21.613, 47.5304], [21.605, 47.533], [21.618, 47.540]]) {
      const p = map.project(point);
      if (p.x < 15 || p.x > element.clientWidth - 15 || p.y < 15 || p.y > element.clientHeight - 15) continue;
      if (!map.queryRenderedFeatures([[p.x - 12, p.y - 12], [p.x + 12, p.y + 12]], {layers: available}).length) return {x: p.x, y: p.y};
    }
    throw new Error('No empty interior target in the isolated overlapping polygon fixture');
  }, labelLayers);
  await (viewport.touch ? canvas.tap({position}) : canvas.click({position}));
}
async function assertSourceLink(page, {landing = false} = {}) {
  const wrapper = page.locator(landing ? '.landing-location-source' : '#location-picker .location-source');
  assert.equal(await wrapper.innerText(), 'Források'); assert.equal(await wrapper.locator('a').count(), 1);
  assert.equal(await wrapper.locator('a').getAttribute('href'), '/THIRD-PARTY-NOTICES.txt');
  assert.equal(await page.locator('#location-picker .neighborhood-source,#location-picker .street-source').count(), 0);
}
function gate() {let release; const promise = new Promise(resolve => {release = resolve;}); return {promise, release};}
async function readyMap(page, selector) {
  const map = page.locator(selector); await map.locator('.location-map-canvas.maplibregl-map').waitFor();
  await map.locator('.location-map-canvas').evaluate(element => new Promise((resolve, reject) => {
    const deadline = performance.now() + 15000;
    function check() {if (element.__mapBrowserInstance?.getLayer('otthonra-place-labels')) return resolve(); if (performance.now() > deadline) return reject(new Error('The real MapLibre label layer did not mount')); requestAnimationFrame(check);} check();
  }));
  const box = await map.locator('canvas.maplibregl-canvas').boundingBox();
  assert.ok(box && box.width > 200 && box.height > 100, 'The real WebGL canvas must retain its map viewport, independently of global icon CSS');
  await waitMapPaint(map); return map;
}
async function chooseText(page, viewport, id, value, {landing = false} = {}) {
  const prefix = landing ? 'landing-location' : 'location'; await page.locator(`#${prefix}-input`).fill(value);
  const item = page.locator(`#${prefix}-options [data-location-id="${id}"]`); await item.waitFor(); await interact(viewport, item);
}
async function removeChip(page, viewport, id, {landing = false} = {}) {
  const remove = chip(page, id, landing), chips = page.locator(inputChips(landing)), toggle = chips.locator('[data-location-selection-toggle]');
  if (!await remove.isVisible() && await toggle.isVisible()) await interact(viewport, toggle);
  await interact(viewport, remove);
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') === 'true') await toggle.press('Escape');
}
async function openEditor(page, viewport, kind = 'search') {
  await page.goto(`${origin}/#${kind === 'property' ? 'properties' : 'searches'}`, {waitUntil: 'domcontentloaded'});
  await interact(viewport, page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`)); await page.locator('#entity-form').waitFor();
}

async function fixture(browser, viewport, {authenticated = false, realStyle = false, coincidentLabels = false} = {}) {
  const context = await browser.newContext({viewport: {width: viewport.width, height: viewport.height}, hasTouch: viewport.touch, reducedMotion: 'reduce'});
  let frozenStyle;
  if (realStyle) {
    frozenStyle = JSON.parse(await readFile(new URL('../dist/data/map/style.json', import.meta.url), 'utf8'));
    // Keep the actual Liberty vector layers and filters. Removing only external
    // raster/glyph/sprite dependencies isolates the style-compatibility test;
    // MapLibre still decodes a real vector tile and compiles every place filter.
    delete frozenStyle.glyphs; delete frozenStyle.sprite;
    const vectors = new Set(Object.entries(frozenStyle.sources).filter(([, source]) => source.type === 'vector').map(([id]) => id));
    frozenStyle.sources = Object.fromEntries(Object.entries(frozenStyle.sources).filter(([id]) => vectors.has(id)));
    frozenStyle.layers = frozenStyle.layers.filter(layer => !layer.source || vectors.has(layer.source));
  }
  await mockMapTiles(context, frozenStyle ? {style: frozenStyle, vectorFixture: true} : {});
  // ESM re-export wrapper instruments the real Map constructor only in tests.
  // Selection still uses real WebGL-rendered symbol hit tests and real taps.
  await context.route('**/vendor/maplibre/maplibre-gl.mjs*', async route => {
    const url = new URL(route.request().url());
    if (url.searchParams.has('map-browser-original')) return route.continue();
    url.searchParams.set('map-browser-original', '1');
    return route.fulfill({status: 200, contentType: 'text/javascript', body: `export * from ${JSON.stringify(url.href)}; import {Map as OriginalMap} from ${JSON.stringify(url.href)}; export class Map extends OriginalMap { constructor(options) { super({...options, fadeDuration:0}); options.container.__mapBrowserInstance=this; options.container.__mapBrowserErrors=[]; this.on('error',event=>options.container.__mapBrowserErrors.push(event.error?.message||String(event.error))); options.container.__mapBrowserLastMove=performance.now(); this.on('moveend',()=>{options.container.__mapBrowserLastMove=performance.now();}); } }`});
  });
  await context.route('https://fonts.googleapis.com/**', route => route.abort()); await context.route('https://fonts.gstatic.com/**', route => route.abort());
  await context.route('https://get.geojs.io/**', route => route.fulfill({status: 200, contentType: 'application/json', body: '{"country_code":"XX"}'}));
  await context.route(`${origin}/runtime-config.js`, route => route.fulfill({status: 200, contentType: 'text/javascript', body: 'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
  if (authenticated) await context.addInitScript(origin => localStorage.setItem('otthonra.api', JSON.stringify({baseUrl: origin, token: 'map-browser-session'})), origin);
  const server = {requests: [], writes: [], errors: [], unhandled: [], failCity: null, holdCity: null, hold: null, townDelay: 0, activeTownRequests: 0, maxTownRequests: 0, searches: [{id: searchId, ownerId: owner.id, title: 'Meglévő keresésem', city: 'Debrecen', locationIds: [city.id], locations: [city], type: 'Lakás', maxPrice: 90000000, minArea: 40, minRooms: 1, conditions: [], buildings: [], floors: [], balcony: false, elevator: false}], properties: [{id: propertyId, ownerId: owner.id, title: 'Meglévő otthonom', city: 'Debrecen', locationId: city.id, type: 'Lakás', price: 60000000, area: 60, rooms: 2, wholeRooms: 2, halfRooms: 0, images: [], addressDetails: {street: 'Fiktív tesztutca', houseNumber: '1', postalCode: '4028'}}], active: {kind: 'search', id: searchId}};
  const activeTownRequests = new Set();
  context.on('request', request => {
    if (!/\/data\/map\/town-[a-f0-9]+\.json$/.test(new URL(request.url()).pathname)) return;
    activeTownRequests.add(request); server.activeTownRequests = activeTownRequests.size;
    server.maxTownRequests = Math.max(server.maxTownRequests, activeTownRequests.size);
  });
  const finishedTown = request => {activeTownRequests.delete(request); server.activeTownRequests = activeTownRequests.size;};
  context.on('requestfinished', finishedTown); context.on('requestfailed', finishedTown);
  await context.route(`${origin}/data/map/**`, async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/data/map/style.json') return route.fallback();
    server.requests.push(path);
    const reply = async (value, status = 200) => {try {await route.fulfill({status, contentType: 'application/json', body: JSON.stringify(value)});} catch (error) {if (!/closed|handled|abort|intercept|disposed/i.test(String(error))) throw error;}};
    if (path === '/data/map/index.json') return reply(manifest);
    if (path === '/data/map/hierarchy.json') return reply(hierarchy);
    if (path === '/data/map/labels.json') {
      if (!coincidentLabels) return reply(labels);
      const modified = structuredClone(labels);
      for (const feature of modified.features) if ([city.id, central.id].includes(feature.id)) feature.geometry.coordinates = [21.622989, 47.527651];
      return reply(modified);
    }
    const row = cityRows.find(item => path.endsWith(item.file)), town = towns.find(item => path.endsWith(item.file));
    const selected = row?.city || (town && getLocation(town.id).city);
    if (!selected) {server.unhandled.push(path); return reply({message: 'Unknown isolated map fixture'}, 404);}
    if (server.holdCity === selected && row && server.hold) await server.hold.promise;
    if (server.failCity === selected && row) {server.failCity = null; return reply({message: 'Temporary geometry failure'}, 503);}
    if (row) return reply({type: 'FeatureCollection', version, city: selected, features: selected === 'Debrecen' ? [...polygons, centralFeature, ...extras] : selected === 'Budapest' ? budapestPolygons : [szegedFeature]});
    if (server.townDelay) await delay(server.townDelay);
    return reply({...makeFeature(getLocation(town.id), town.bounds), version: labelVersion, mapVersion: version});
  });
  await context.route(`${origin}/api/**`, async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.slice(4), method = request.method();
    const json = (data, status = 200) => route.fulfill({status, contentType: 'application/json', body: JSON.stringify(data)});
    if (path === '/public/landing') return json({regions: [], region: null, scope: 'national', searches: [], properties: []});
    if (path === '/locations') return json({items: searchLocations(url.searchParams.get('q') || '', 12, {kind: url.searchParams.get('kind') || 'search'})});
    if (path === '/streets') return json({items: []});
    if (path === '/me') return json({...owner, credits: 100, unreadNotificationCount: 0});
    if (path === '/me/entities') return json({properties: server.properties, searchRequests: server.searches, active: server.active, decisions: [], reportedOwnerIds: [], reportedEntities: []});
    if (path === '/credits/ledger' || path === '/matches') return json([]);
    if (path === '/feedback/pending') return json({feedbackPrompt: null});
    if (path === '/test/feedback-scenario') return json({available: false});
    if (path === '/feed') return json({active: server.active, items: [], stage: 'empty', hasApproximate: false});
    if (path === '/me/active' && method === 'PUT') {server.active = request.postDataJSON(); return json(server.active);}
    if (path === '/searches' && method === 'POST') {
      const body = request.postDataJSON(), saved = {...body, id: '20000000-0000-4000-8000-000000000002', ownerId: owner.id, locations: body.locationIds.map(getLocation).filter(Boolean)};
      server.writes.push(body); server.searches.push(saved); return json(saved, 201);
    }
    server.unhandled.push(method + ' ' + path); return json({message: 'Unexpected isolated map API route'}, 404);
  });
  const page = await context.newPage(); page.setDefaultTimeout(15000); page.on('pageerror', error => server.errors.push(error.message));
  page.on('request', request => {if (new URL(request.url()).pathname.endsWith('neighborhoods.json.gz')) server.errors.push('The map requested complete server search geometry.');});
  return {context, page, server, frozenStyle};
}
async function inspect(f, viewport, name, run) {
  try {await run(); assert.deepEqual(f.server.unhandled, []); assert.deepEqual(f.server.errors, []);} catch (error) {
    const diagnostic = await f.page.locator('.location-map-canvas').evaluateAll(canvases => canvases.map(canvas => {
      const map = canvas.__mapBrowserInstance, style = map?.getStyle();
      return {zoom: map?.getZoom(), center: map?.getCenter(), status: canvas.closest('.location-map').querySelector('.location-map-status')?.textContent, sources: Object.keys(style?.sources || {}), rendered: map && ['otthonra-place-labels'].filter(id => map.getLayer(id)).flatMap(id => map.queryRenderedFeatures(undefined, {layers: [id]}).map(feature => ({id: feature.properties.id || feature.id, layer: id}))), outlines: style?.sources['otthonra-outlines']?.data};
    })).catch(() => []);
    console.error(`Map failure diagnostics ${name} ${viewport.name}: ${JSON.stringify(diagnostic)}`);
    await mkdir(resolve('.local/browser-tests/screenshots'), {recursive: true});
    await f.page.screenshot({path: resolve('.local/browser-tests/screenshots', `neighborhood-map-${name}-${viewport.name}-failure.png`), fullPage: true}).catch(() => {}); throw error;
  } finally {f.server.hold?.release(); await f.context.close();}
}

async function landingSelection(browser, viewport) {
  const f = await fixture(browser, viewport), {page, server} = f;
  await inspect(f, viewport, 'landing', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const map = await readyMap(page, '#landing-location-map');
    assert.deepEqual(await outlineIds(map), [], 'An unselected map shows labels with no area outlines');
    assert.equal(server.requests.filter(path => /\/(city|town)-/.test(path)).length, 0, 'A country view never downloads all area geometry');
    assert.match(await map.locator('.maplibregl-ctrl-attrib').innerText(), /OpenStreetMap/); await assertSourceLink(page, {landing: true});
    await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await assertOutline(map, city.id);
    assert.equal(server.requests.filter(path => /\/city-/.test(path)).length, 0, 'Focusing a town does not fetch unselected quarter polygons');
    await removeChip(page, viewport, city.id, {landing: true}); await waitLabel(map, city.id); await clickLabel(map, city.id, viewport); await chip(page, city.id, true).waitFor({state: 'attached'});
    await zoomTo(map, viewport, 13); await waitLabel(map, venkert.id); await waitLabel(map, sestakert.id);
    await clickLabel(map, sestakert.id, viewport); await chip(page, sestakert.id, true).waitFor({state: 'attached'});
    assert.equal(await chip(page, venkert.id, true).count(), 0, 'A named tap selects that place even when its polygon is larger and overlaps another');
    assert.equal(await chip(page, city.id, true).count(), 0, 'Selecting a named quarter narrows the town filter');
    await assertOutline(map, sestakert.id); await assertOutline(map, venkert.id, false);
    assert.equal(await map.locator('.maplibregl-popup,.location-map-overlap').count(), 0, 'A label tap needs no secondary choice');
    const before = await page.locator('#landing-location-chips').innerText(); await clickEmptyInterior(map, viewport);
    assert.equal(await page.locator('#landing-location-chips').innerText(), before, 'Empty polygon interiors do not select arbitrary overlapping regions');
    // Arrange the isolated target at the center so it stays within even the
    // smallest viewport during the following real zoom-in/out controls.
    await map.locator('.location-map-canvas').evaluate((element, center) => element.__mapBrowserInstance.jumpTo({center}), labelPoints.get(tocoskert.id));
    await waitMapPaint(map);
    const toggleZoom = await mapZoom(map), toggleCenter = await mapCenter(map);
    const unselectedBox = await renderedLabelBox(map, tocoskert.id);
    await clickLabel(map, tocoskert.id, viewport, {slop: viewport.touch}); await chip(page, tocoskert.id, true).waitFor({state: 'attached'}); await assertOutline(map, tocoskert.id);
    const selectedBox = await renderedLabelBox(map, tocoskert.id);
    assert.equal(selectedBox.selected, true, 'A real glyph tap updates selected paint state');
    assertSameLabelBox(selectedBox, unselectedBox, 'Selecting a label cannot move or resize its glyph hit box');
    await clickLabel(map, tocoskert.id, viewport); assert.equal(await chip(page, tocoskert.id, true).count(), 0); await assertOutline(map, tocoskert.id, false);
    const deselectedBox = await renderedLabelBox(map, tocoskert.id);
    assert.equal(deselectedBox.selected, false);
    assertSameLabelBox(deselectedBox, unselectedBox, 'Deselecting restores the original label at its original point');
    await clickLabel(map, tocoskert.id, viewport); await chip(page, tocoskert.id, true).waitFor({state: 'attached'});
    await zoom(map, viewport, 'in'); const zoomedBox = await renderedLabelBox(map, tocoskert.id);
    assert.deepEqual(zoomedBox.coordinates, unselectedBox.coordinates, 'Zooming never replaces the named place anchor');
    assert.ok(Math.abs(zoomedBox.offset[0] - unselectedBox.offset[0]) < 1.5 && Math.sign(zoomedBox.offset[1]) === Math.sign(unselectedBox.offset[1]) && Math.abs(zoomedBox.offset[1] - unselectedBox.offset[1]) < 3, 'Zoom may grow the text gently but never choose another side of its anchor');
    await zoom(map, viewport, 'out'); assertSameLabelBox(await renderedLabelBox(map, tocoskert.id), unselectedBox, 'Returning to a zoom level restores the same label placement');
    assert.equal(await mapZoom(map), toggleZoom, 'Repeated label taps cannot double-tap zoom'); await assertCenter(map, toggleCenter, 'Label toggles retain the camera');
    await mkdir(resolve('.local/browser-tests/screenshots'), {recursive: true});
    await map.screenshot({path: resolve('.local/browser-tests/screenshots', `neighborhood-map-labels-${viewport.name}.png`)});
    await removeChip(page, viewport, sestakert.id, {landing: true}); await assertOutline(map, sestakert.id, false);
    await chooseText(page, viewport, otherCity.id, 'Szeged', {landing: true}); await waitLabel(map, szeged.id); await clickLabel(map, szeged.id, viewport); await chip(page, szeged.id, true).waitFor({state: 'attached'});
    await assertOutline(map, szeged.id); await assertOutline(map, tocoskert.id, false);
    await assertPickerLayout(page, viewport, {landing: true});
    await zoomTo(map, viewport, 7); await waitMapPaint(map);
    assert.ok(!((await placeState(map)).rendered.includes(venkert.id)), 'Distant views do not display every small label');
    assert.equal(new Set(server.requests.filter(path => /\/city-/.test(path))).size, 2, 'Only selected quarter cities have geometry loaded');
    console.log(`Neighborhood map landing ${viewport.name}: real label hits, selected-only outlines, town choice, overlap identity, forgiving touch, repeat removal, camera and lazy geometry passed.`);
  });
}
async function disjointZoomLevels(browser, viewport) {
  const f = await fixture(browser, viewport), {page} = f;
  await inspect(f, viewport, 'disjoint-levels', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const map = await readyMap(page, '#landing-location-map');
    await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await waitMapPaint(map); const center = await mapCenter(map);
    const naturalZoom = await mapZoom(map);
    assert.ok(Math.abs(naturalZoom - Math.round(naturalZoom)) > .01, 'Natural geographic fit supplies a genuine fractional-zoom regression fixture');
    await zoom(map, viewport, 'in');
    assert.ok(Math.abs(await mapZoom(map) - (naturalZoom + 1)) < .01, 'A real zoom button preserves the natural fractional component');
    await zoom(map, viewport, 'out');
    assert.ok(Math.abs(await mapZoom(map) - naturalZoom) < .01, 'Opposite real zoom controls return to the original fractional fit');
    await assertCenter(map, center, 'Fractional control steps must retain the geographic center');
    for (const level of [10, 11, 13]) {
      await zoomTo(map, viewport, level); await assertCenter(map, center, `Zoom ${level} keeps the selected eastern city centered`);
      const state = await placeState(map), peers = state.candidates.filter(item => polygons.some(feature => feature.id === item.id));
      assert.deepEqual(peers.map(item => item.id).sort(), polygons.map(item => item.id).sort(), 'All adjacent peers remain eligible; text collision alone controls density');
      assert.ok(peers.every(item => item.minZoom === 10), 'Unequal polygon sizes never assign disjoint peers different semantic zoom bands');
      for (const feature of polygons) await assertOutline(map, feature.id, false);
    }
    for (const feature of polygons) await waitLabel(map, feature.id);
    console.log(`Neighborhood map adjacent quarters ${viewport.name}: equal semantic eligibility, real collision layout, stable eastern camera and no unselected outlines passed.`);
  });
}
async function budapestZoomLevels(browser, viewport) {
  const f = await fixture(browser, viewport), {page, server} = f;
  await inspect(f, viewport, 'budapest-levels', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const map = await readyMap(page, '#landing-location-map');
    await chooseText(page, viewport, 'city:Budapest', 'Budapest', {landing: true}); await zoomTo(map, viewport, 8); await waitLabel(map, buda.id); await waitLabel(map, pest.id);
    const state = await placeState(map); assert.ok(!state.rendered.includes(ward.id) && !state.rendered.includes(belvaros.id), 'Distant Budapest offers broad named halves before finer names');
    const coarseZoom = await mapZoom(map), coarseCenter = await mapCenter(map);
    await clickLabel(map, buda.id, viewport); await chip(page, buda.id, true).waitFor({state: 'attached'}); assert.equal(await chip(page, 'city:Budapest', true).count(), 0);
    // An unfinished request may correctly be aborted by the next selection.
    // Establish an acknowledged, validated cache entry before asserting reuse.
    await assertOutline(map, buda.id);
    const cachedCityReads = server.requests.filter(path => path.endsWith(cityRows[2].file)).length;
    assert.ok(cachedCityReads >= 1, 'The cache checkpoint must follow an actual completed geometry read');
    await clickLabel(map, pest.id, viewport); await chip(page, pest.id, true).waitFor({state: 'attached'});
    assert.equal(await mapZoom(map), coarseZoom); await assertCenter(map, coarseCenter, 'Selecting named city halves retains camera');
    await assertOutline(map, buda.id); await assertOutline(map, pest.id);
    await zoomTo(map, viewport, 10); await waitLabel(map, ward.id); await clickLabel(map, ward.id, viewport); await chip(page, ward.id, true).waitFor({state: 'attached'});
    assert.equal(await chip(page, pest.id, true).count(), 0, 'A district name narrows the selected containing Pest area'); assert.equal(await chip(page, buda.id, true).count(), 1);
    await assertOutline(map, ward.id); await assertOutline(map, pest.id, false);
    await zoomTo(map, viewport, 12); await waitLabel(map, belvaros.id); await clickLabel(map, belvaros.id, viewport); await chip(page, belvaros.id, true).waitFor({state: 'attached'});
    assert.equal(await chip(page, ward.id, true).count(), 0, 'A child removes the selected district alias of its containing polygon'); assert.equal(await chip(page, buda.id, true).count(), 1);
    await assertOutline(map, belvaros.id); await assertOutline(map, ward.id, false);
    assert.equal(await map.locator('.maplibregl-popup,.location-map-overlap').count(), 0);
    assert.equal(server.requests.filter(path => path.endsWith(cityRows[2].file)).length, cachedCityReads, 'After acknowledged geometry loading, new Budapest selections and zoom levels reuse the cached city chunk');
    await removeChip(page, viewport, buda.id, {landing: true}); await chooseText(page, viewport, buda.id, 'Buda (Budapest)', {landing: true}); await waitLabel(map, buda.id); await assertOutline(map, buda.id);
    await chooseText(page, viewport, ward.id, 'Budapest V. kerület', {landing: true}); await waitLabel(map, ward.id); await assertOutline(map, ward.id);
    await removeChip(page, viewport, belvaros.id, {landing: true}); await chooseText(page, viewport, belvaros.id, 'Belváros (Budapest)', {landing: true}); await waitLabel(map, belvaros.id); await assertOutline(map, belvaros.id);
    console.log(`Neighborhood map Budapest ${viewport.name}: named broad halves, finer district/quarter names, canonical aliases, selected-only outlines, parent narrowing and text focus passed.`);
  });
}
async function ownedWizard(browser, viewport) {
  const f = await fixture(browser, viewport, {authenticated: true}), {page, server} = f;
  await inspect(f, viewport, 'owned', async () => {
    await openEditor(page, viewport); await page.locator('#f-type').selectOption('Lakás'); const map = await readyMap(page, '#search-location-map');
    await assertPickerLayout(page, viewport);
    await chooseText(page, viewport, solymar.id, 'Solymár'); await chooseText(page, viewport, city.id, 'Debrecen'); await zoomTo(map, viewport, 13); await clickLabel(map, tocoskert.id, viewport); await chip(page, tocoskert.id).waitFor({state: 'attached'});
    assert.equal(await chip(page, city.id).count(), 0); assert.equal(await chip(page, solymar.id).count(), 1); assert.equal(await page.locator('#location-chips .location-chip').count(), 2);
    assert.notEqual(await page.evaluate(() => document.activeElement?.id), 'location-input', 'Map taps never summon the mobile keyboard'); await assertSourceLink(page); await assertOutline(map, tocoskert.id);
    await clickLabel(map, tocoskert.id, viewport); assert.equal(await chip(page, tocoskert.id).count(), 0); assert.equal(await chip(page, solymar.id).count(), 1); await assertOutline(map, tocoskert.id, false); await clickLabel(map, tocoskert.id, viewport);
    await page.evaluate(() => {globalThis.__mapEditorNode = document.getElementById('search-location-map');});
    await (await editorField(page, '#f-maxPrice')).fill('90'); await (await editorField(page, '#f-minArea')).fill('40'); await (await editorField(page, '#f-minRooms')).fill('1'); await editorStep(page, 0);
    assert.equal(await page.evaluate(() => globalThis.__mapEditorNode === document.getElementById('search-location-map')), true); await assertOutline(map, tocoskert.id);
    await editorSave(page, locator => interact(viewport, locator)); await page.getByRole('heading', {name: 'Elkészült a keresési igényed.', exact: true}).waitFor();
    assert.deepEqual(server.writes[0].locationIds, [solymar.id, tocoskert.id]); assert.equal(server.writes[0].maxPrice, 90000000); assert.equal(server.writes.length, 1); assert.deepEqual(server.active, {kind: 'search', id: searchId});
    await interact(viewport, page.locator('.search-created-actions [data-action="close"]')); await openEditor(page, viewport, 'property');
    assert.equal(await page.locator('#search-location-map,.location-map-canvas').count(), 0, 'Exact address forms do not mount the search-only map'); await interact(viewport, page.locator('.modal-close'));
    console.log(`Neighborhood map wizard ${viewport.name}: label toggles, retained other choices, canonical save, mounted backward steps, keyboard isolation and cleanup passed.`);
  });
}
async function anonymousDraft(browser, viewport) {
  const f = await fixture(browser, viewport), {page} = f;
  await inspect(f, viewport, 'draft', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const landing = await readyMap(page, '#landing-location-map');
    await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await zoomTo(landing, viewport, 13); await clickLabel(landing, tocoskert.id, viewport); assert.equal(await chip(page, city.id, true).count(), 0);
    await interact(viewport, page.locator('#landing-search-form button[type="submit"]')); await page.locator('#onboarding-page #entity-form').waitFor(); await page.locator('#f-type').selectOption('Lakás'); const map = await readyMap(page, '#search-location-map');
    await waitLabel(map, tocoskert.id); await assertSourceLink(page); await assertOutline(map, tocoskert.id);
    await clickLabel(map, tocoskert.id, viewport); assert.equal(await chip(page, tocoskert.id).count(), 0); await assertOutline(map, tocoskert.id, false);
    await page.waitForFunction(async id => {const draft = (await import('/onboarding.js')).loadDraft(); return draft && !draft.data.locationIds.includes(id);}, tocoskert.id);
    await clickLabel(map, tocoskert.id, viewport); await chooseText(page, viewport, sestakert.id, 'Sestakert'); await waitLabel(map, sestakert.id); await assertOutline(map, sestakert.id);
    await page.waitForFunction(async ids => {const draft = (await import('/onboarding.js')).loadDraft(); return ids.every(id => draft?.data?.locationIds?.includes(id));}, [tocoskert.id, sestakert.id]);
    await page.reload({waitUntil: 'domcontentloaded'}); await readyMap(page, '#search-location-map'); assert.equal(await page.locator('#location-chips .location-chip').count(), 2); assert.equal(await page.locator('#f-type').inputValue(), 'Lakás');
    await interact(viewport, page.locator('[data-action="landing"]').first()); await readyMap(page, '#landing-location-map'); assert.equal(await page.locator('#landing-location-chips .location-chip').count(), 0); assert.equal(await page.locator('#search-location-map').count(), 0);
    console.log(`Neighborhood map draft ${viewport.name}: named selections/removals persist through guest wizard, text focus, reload and picker cleanup passed.`);
  });
}
async function failuresAndStaleReads(browser, viewport) {
  const f = await fixture(browser, viewport), {page, server} = f;
  await inspect(f, viewport, 'network', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const map = await readyMap(page, '#landing-location-map'); await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await zoomTo(map, viewport, 13);
    server.failCity = 'Debrecen'; await clickLabel(map, venkert.id, viewport); const retry = map.locator('.location-map-retry'); await retry.waitFor();
    assert.equal(await chip(page, venkert.id, true).count(), 1, 'Geometry failures retain the acknowledged selection'); await waitLabel(map, sestakert.id);
    await interact(viewport, retry); await assertOutline(map, venkert.id); assert.equal(await retry.isVisible(), false);
    await page.reload({waitUntil: 'domcontentloaded'}); const newMap = await readyMap(page, '#landing-location-map'); await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await zoomTo(newMap, viewport, 13);
    server.holdCity = 'Debrecen'; server.hold = gate(); const before = server.requests.length; await clickLabel(newMap, venkert.id, viewport);
    for (let index = 0; index < 80 && !server.requests.slice(before).some(path => path.endsWith(cityRows[0].file)); index++) await delay(25);
    assert.ok(server.requests.slice(before).some(path => path.endsWith(cityRows[0].file)), 'The delayed selected-outline request actually began');
    await chooseText(page, viewport, otherCity.id, 'Szeged', {landing: true}); await waitLabel(newMap, szeged.id); await assertOutline(newMap, otherCity.id);
    server.hold.release(); server.hold = null; await delay(350); await assertOutline(newMap, venkert.id, false);
    assert.ok(!((await placeState(newMap)).rendered.includes(venkert.id)), 'Late old-city data cannot repaint the new camera');
    await page.locator('#landing-location-input').fill('Debrecen'); await page.locator('#landing-location-options [data-location-id]').first().waitFor(); await interact(viewport, newMap.locator('.location-map-status'));
    assert.equal(await page.locator('#landing-location-options').isHidden(), true); assert.equal(await page.locator('#landing-location-input').inputValue(), 'Debrecen');
    await f.context.route('https://tiles.openfreemap.org/test-map-tiles/**', route => route.fulfill({status: 503, contentType: 'text/plain', body: 'Isolated background tile outage'})); await zoom(newMap, viewport, 'in');
    await page.waitForFunction(() => document.querySelector('#landing-location-map .location-map-status')?.textContent.includes('háttértérkép'));
    await newMap.locator('.location-map-list > summary').click(); const option = newMap.locator(`[data-map-neighborhood-id="${szeged.id}"]`); await option.waitFor(); await option.press('Enter'); await chip(page, szeged.id, true).waitFor({state: 'attached'});
    await option.press('Enter'); assert.equal(await chip(page, szeged.id, true).count(), 0, 'Keyboard selection also removes the chosen place during a background outage');
    console.log('Neighborhood map network desktop: failed outline retry, retained labels/text, stale response fences, outside dismissal, keyboard toggles and background outage passed.');
  });
}
async function narrowingAtLimit(browser, viewport) {
  const f = await fixture(browser, viewport, {authenticated: true}), {page, server} = f;
  await inspect(f, viewport, 'limit', async () => {
    const others = extraLocations.map(item => item.id); server.searches[0].locationIds = [city.id, ...others]; server.searches[0].locations = server.searches[0].locationIds.map(getLocation);
    await page.goto(`${origin}/#searches`, {waitUntil: 'domcontentloaded'}); await interact(viewport, page.locator(`[data-action="edit"][data-kind="search"][data-id="${searchId}"]`)); const map = await readyMap(page, '#search-location-map'); await zoomTo(map, viewport, 13); await waitLabel(map, tocoskert.id);
    assert.equal(await page.locator('#location-chips .location-chip').count(), 50); await clickLabel(map, tocoskert.id, viewport);
    assert.equal(await page.locator('#location-chips .location-chip').count(), 50); assert.equal(await chip(page, city.id).count(), 0); assert.equal(await chip(page, tocoskert.id).count(), 1); assert.equal(await page.locator('#location-error').innerText(), '');
    await removeChip(page, viewport, others[0]); await chooseText(page, viewport, city.id, 'Debrecen'); await zoomTo(map, viewport, 13); assert.equal(await page.locator('#location-chips .location-chip').count(), 50);
    await clickLabel(map, tocoskert.id, viewport); assert.equal(await page.locator('#location-chips .location-chip').count(), 49); assert.equal(await chip(page, tocoskert.id).count(), 0); assert.equal(await chip(page, city.id).count(), 1);
    await clickLabel(map, tocoskert.id, viewport); assert.equal(await page.locator('#location-chips .location-chip').count(), 49); assert.equal(await chip(page, city.id).count(), 0); assert.equal(await chip(page, tocoskert.id).count(), 1); assert.equal(await chip(page, others[1]).count(), 1);
    console.log('Neighborhood map limit desktop: named replacement at50, exact removal, retained offscreen choices and re-add narrowing passed.');
  });
}

async function realLibertyStyle(browser, viewport) {
  const f = await fixture(browser, viewport, {realStyle: true}), {page} = f;
  await inspect(f, viewport, 'real-liberty-style', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const map = await readyMap(page, '#landing-location-map');
    await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await zoomTo(map, viewport, 13); await waitLabel(map, venkert.id);
    const state = await map.locator('.location-map-canvas').evaluate(element => {
      const map = element.__mapBrowserInstance, style = map.getStyle();
      return {errors: element.__mapBrowserErrors, places: style.layers.filter(layer => layer['source-layer'] === 'place'), decoded: map.querySourceFeatures('openmaptiles', {sourceLayer: 'place'}).map(feature => feature.properties.name), rendered: map.queryRenderedFeatures().map(feature => feature.properties.name)};
    });
    assert.deepEqual(state.errors, [], 'The frozen Liberty vector style and converted filters must compile without map errors');
    const expectedLayers = f.frozenStyle.layers.filter(layer => layer['source-layer'] === 'place');
    assert.ok(expectedLayers.length > 3, 'This smoke uses the actual multi-layer Liberty place style');
    assert.deepEqual(state.places.map(layer => layer.id), expectedLayers.map(layer => layer.id), 'Real basemap place layers are preserved');
    assert.ok(state.places.every(layer => JSON.stringify(layer.filter).includes('within')), 'Each place layer retains its filter plus the HU duplicate-label exclusion');
    assert.ok(state.decoded.includes('Browser-only basemap quarter'), 'The test must decode a real MVT place feature before checking suppression');
    // Remove canonical symbols briefly so their collision boxes cannot make a
    // broken HU filter look successful. Then use the real original Liberty
    // filter as a positive control before restoring the production filter.
    await map.locator('.location-map-canvas').evaluate((element, layers) => {
      for (const id of layers) element.__mapBrowserInstance.setLayoutProperty(id, 'visibility', 'none');
    }, labelLayers);
    await waitMapPaint(map);
    const maskedNames = await map.locator('.location-map-canvas').evaluate(element => element.__mapBrowserInstance.queryRenderedFeatures().map(feature => feature.properties.name));
    assert.ok(!maskedNames.includes('Browser-only basemap quarter'), 'The HU filter excludes the point independently of canonical-label collisions');
    const originalFilter = expectedLayers.find(layer => layer.id === 'label_other').filter;
    await map.locator('.location-map-canvas').evaluate((element, filter) => element.__mapBrowserInstance.setFilter('label_other', filter), originalFilter);
    await waitMapPaint(map);
    const unmaskedNames = await map.locator('.location-map-canvas').evaluate(element => element.__mapBrowserInstance.queryRenderedFeatures().map(feature => feature.properties.name));
    assert.ok(unmaskedNames.includes('Browser-only basemap quarter'), 'The original Liberty filter can actually render the vector point as a positive control');
    await map.locator('.location-map-canvas').evaluate((element, {filter, layers}) => {
      const map = element.__mapBrowserInstance; map.setFilter('label_other', filter);
      for (const id of layers) map.setLayoutProperty(id, 'visibility', 'visible');
    }, {filter: state.places.find(layer => layer.id === 'label_other').filter, layers: labelLayers});
    await waitMapPaint(map); await waitLabel(map, venkert.id);
    await clickLabel(map, venkert.id, viewport); await chip(page, venkert.id, true).waitFor({state: 'attached'}); await assertOutline(map, venkert.id);
    assert.deepEqual(await map.locator('.location-map-canvas').evaluate(element => element.__mapBrowserErrors), []);
    console.log('Neighborhood map real Liberty desktop: actual vector-layer filters, MVT decoding, within suppression and canonical label click passed.');
  });
}
async function allSelectedTownOutlines(browser, viewport) {
  const f = await fixture(browser, viewport, {authenticated: true}), {page, server} = f;
  await inspect(f, viewport, 'all-selected-towns', async () => {
    const ids = bulkTownBounds.map(row => row.location.id);
    server.searches[0].locationIds = ids; server.searches[0].locations = ids.map(getLocation); server.townDelay = 150;
    await page.goto(`${origin}/#searches`, {waitUntil: 'domcontentloaded'});
    await interact(viewport, page.locator(`[data-action="edit"][data-kind="search"][data-id="${searchId}"]`)); const map = await readyMap(page, '#search-location-map');
    for (const id of ids) await assertOutline(map, id);
    assert.deepEqual(await outlineIds(map), [...ids].sort(), 'All nine in-view selected town outlines render, beyond the eight-entry cache budget');
    assert.equal(new Set(server.requests.filter(path => /\/town-/.test(path))).size, 9, 'All nine separate selected geometry files were actually requested');
    assert.ok(server.maxTownRequests > 1, 'The isolated slow responses exercise concurrent requests');
    assert.ok(server.maxTownRequests <= 4, 'Selected geometry loading keeps at most four live requests');
    assert.equal(await page.locator('#location-chips .location-chip').count(), 9);
    console.log('Neighborhood map selected towns desktop: all nine selected boundaries, four-request concurrency and canonical selections passed.');
  });
}
async function coincidentCityAndQuarter(browser, viewport) {
  const f = await fixture(browser, viewport, {coincidentLabels: true}), {page} = f;
  await inspect(f, viewport, 'coincident-city-quarter', async () => {
    await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'}); const map = await readyMap(page, '#landing-location-map');
    await chooseText(page, viewport, city.id, 'Debrecen', {landing: true}); await removeChip(page, viewport, city.id, {landing: true}); await zoomTo(map, viewport, 8);
    await waitLabel(map, city.id); assert.ok(!((await placeState(map)).rendered.includes(central.id)), 'The distant city name appears before the coincident quarter');
    await clickLabel(map, city.id, viewport); await chip(page, city.id, true).waitFor({state: 'attached'}); await zoomTo(map, viewport, 13);
    await waitLabel(map, central.id); await waitLabel(map, city.id);
    // Fixed opposite-side anchors keep a city and exact same-point quarter
    // independently visible/clickable, without selection-dependent placement.
    await clickLabel(map, central.id, viewport); await chip(page, central.id, true).waitFor({state: 'attached'});
    assert.equal(await chip(page, city.id, true).count(), 0, 'The actual quarter glyph narrows the selected whole city even with identical point coordinates');
    await assertOutline(map, central.id); await assertOutline(map, city.id, false);
    await clickLabel(map, central.id, viewport); assert.equal(await chip(page, central.id, true).count(), 0); await assertOutline(map, central.id, false);
    console.log('Neighborhood map coincident names desktop: production priorities, far city, close exact-coordinate quarter, separate glyph hits and narrowing passed.');
  });
}

async function responsiveSelections(browser, viewport) {
  for (const landing of [true, false]) {
    const f = await fixture(browser, viewport, {authenticated: !landing}), {page, server} = f;
    await inspect(f, viewport, landing ? 'responsive-landing' : 'responsive-wizard', async () => {
      const ids = [city.id, solymar.id, otherCity.id, 'city:Budapest', bulkTownBounds[0].location.id, bulkTownBounds[1].location.id];
      if (landing) await page.goto(`${origin}/#landing`, {waitUntil: 'domcontentloaded'});
      else {
        server.searches[0].locationIds = [city.id]; server.searches[0].locations = [city];
        await page.goto(`${origin}/#searches`, {waitUntil: 'domcontentloaded'});
        await interact(viewport, page.locator(`[data-action="edit"][data-kind="search"][data-id="${searchId}"]`));
      }
      const map = await readyMap(page, landing ? '#landing-location-map' : '#search-location-map');
      if (landing) await chooseText(page, viewport, city.id, 'Debrecen', {landing});
      const initial = await assertPickerLayout(page, viewport, {landing});
      for (const id of ids.slice(1)) await chooseText(page, viewport, id, getLocation(id).city, {landing});
      await waitMapPaint(map);
      const filled = await assertPickerLayout(page, viewport, {landing}), chips = page.locator(inputChips(landing));
      assert.equal(await chips.locator('[data-remove-location]').count(), ids.length, 'The summary retains every canonical selected place');
      if (viewport.width < 768) {
        assert.ok(Math.abs(initial.mapTop - filled.mapTop) <= 1, 'Adding many mobile places never pushes the working map downward');
        const toggle = chips.locator('[data-location-selection-toggle]'), more = chips.locator('.location-selection-more');
        assert.equal(await toggle.isVisible(), true); assert.equal(await more.isVisible(), true); assert.match(await more.innerText(), /\+\s*\d+\s+helyszín/);
        const names = chips.locator('.location-selection-names');
        assert.equal(await names.evaluate(element => getComputedStyle(element).whiteSpace), 'nowrap', 'Selected names never wrap onto a second mobile row');
        assert.ok(await names.evaluate(element => parseFloat(getComputedStyle(element).fontSize)) <= 12, 'The mobile selection summary uses compact text');
        await interact(viewport, toggle); assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
        const list = chips.locator('.location-selection-list'); assert.equal(await list.isVisible(), true);
        assert.equal(await list.locator('[data-remove-location]').count(), ids.length, 'The expanded accessible list exposes all selected places');
        assert.ok(Math.abs((await pickerGeometry(page, {landing})).mapTop - filled.mapTop) <= 1, 'Opening the bounded selection popup does not reflow the map');
        await interact(viewport, chip(page, solymar.id, landing));
        assert.equal(await chip(page, solymar.id, landing).count(), 0); assert.equal(await toggle.getAttribute('aria-expanded'), 'true', 'Removing a place keeps the other removal controls available');
        assert.notEqual(await page.evaluate(() => document.activeElement?.id), landing ? 'landing-location-input' : 'location-input', 'Removing from the compact list does not summon the mobile keyboard');
        await toggle.press('Escape'); assert.equal(await list.isHidden(), true);
        await interact(viewport, toggle); await interact(viewport, map.locator('.location-map-status')); assert.equal(await list.isHidden(), true, 'An outside map tap closes the selection popup');
        await page.setViewportSize({width: 800, height: 1100}); await assertPickerLayout(page, {width: 800}, {landing});
        assert.equal(await chips.locator('[data-remove-location]').count(), ids.length - 1, 'Responsive layout changes preserve all remaining choices');
        await page.setViewportSize({width: viewport.width, height: viewport.height}); await assertPickerLayout(page, viewport, {landing});
        assert.equal(await toggle.isVisible(), true);
      } else {
        assert.equal(await chips.locator('[data-location-selection-toggle]').isVisible(), false, 'Wider screens expose the full compact selected list below the text field');
        assert.equal(await chip(page, ids.at(-1), landing).isVisible(), true);
      }
      console.log(`Neighborhood map responsive ${landing ? 'landing' : 'wizard'} ${viewport.name}: compact selections, retained canonical IDs, popup removal/resize and side-by-side layout passed.`);
    });
  }
}

const browser = await chromium.launch({headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {}), args: ['--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader']}); let failed = 0;
try {
  for (const viewport of viewports) for (const test of [landingSelection, disjointZoomLevels, budapestZoomLevels, ownedWizard, anonymousDraft, responsiveSelections]) try {await test(browser, viewport);} catch (error) {failed++; console.error(`${test.name} ${viewport.name}: ${error.stack || error}`);}
  for (const test of [failuresAndStaleReads, narrowingAtLimit, realLibertyStyle, allSelectedTownOutlines, coincidentCityAndQuarter]) try {await test(browser, viewports[0]);} catch (error) {failed++; console.error(`${test.name} desktop: ${error.stack || error}`);}
} finally {await browser.close();}
if (failed) process.exitCode = 1;
