/** Deterministic map network fixtures. The real MapLibre module and worker run;
 * only background tiles/style are replaced, so browser tests never burden the
 * public OpenFreeMap/OSM servers or depend on an external glyph service. */
const transparentTile = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAXpeqz8AAAAASUVORK5CYII=', 'base64');

export const mapTestStyle = Object.freeze({
  version: 8,
  name: 'Isolated browser map background',
  sources: {background: {
    type: 'raster', tileSize: 256,
    tiles: ['https://tiles.openfreemap.org/test-map-tiles/{z}/{x}/{y}.png'],
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · OpenFreeMap · OpenMapTiles'
  }},
  // Omitting a glyphs URL deliberately uses MapLibre 6's local font renderer.
  // Canonical location symbols still use real text layout/collision/hit tests.
  layers: [
    {id: 'background', type: 'background', paint: {'background-color': '#f1f0e9'}},
    {id: 'test-map-background', type: 'raster', source: 'background'}
  ]
});

// Minimal valid MVT, using actual protobuf encoding rather than replacing the
// renderer. A single known HU point lets the real-style smoke test verify that
// the converted `within` filter is evaluated against decoded vector features.
const varint = value => {
  let number = BigInt(value); const bytes = [];
  do { const byte = Number(number & 127n); number >>= 7n; bytes.push(byte | (number ? 128 : 0)); } while (number);
  return Buffer.from(bytes);
};
const packed = values => Buffer.concat(values.map(varint));
const bytes = (field, value) => Buffer.concat([varint((field << 3) | 2), varint(value.length), value]);
const text = (field, value) => bytes(field, Buffer.from(value));
const integer = (field, value) => Buffer.concat([varint(field << 3), varint(value)]);
function isolatedPlaceTile(url) {
  const match = new URL(url).pathname.match(/\/(\d+)\/(\d+)\/(\d+)\.pbf$/);
  if (!match) return Buffer.alloc(0);
  const [, z, tx, ty] = match.map(Number), count = 2 ** z;
  const longitude = 21.611, latitude = 47.535, radians = latitude * Math.PI / 180;
  const x = (longitude + 180) / 360 * count, y = (1 - Math.log(Math.tan(radians) + 1 / Math.cos(radians)) / Math.PI) / 2 * count;
  if (Math.floor(x) !== tx || Math.floor(y) !== ty) return Buffer.alloc(0);
  const geometry = packed([9, Math.round((x - tx) * 4096) * 2, Math.round((y - ty) * 4096) * 2]);
  const feature = Buffer.concat([integer(1, 1), bytes(2, packed([0, 0, 1, 1, 2, 2, 3, 0])), integer(3, 1), bytes(4, geometry)]);
  const layer = Buffer.concat([
    text(1, 'place'), bytes(2, feature),
    ...['name', 'class', 'rank', 'name_en'].map(value => text(3, value)),
    bytes(4, text(1, 'Browser-only basemap quarter')), bytes(4, text(1, 'suburb')), bytes(4, integer(4, 1)),
    integer(5, 4096), integer(15, 2)
  ]);
  return bytes(3, layer);
}

export async function mockMapTiles(context, {style = mapTestStyle, vectorFixture = false} = {}) {
  // Retain the old tile interception for regression fixtures that open legacy
  // snapshots. New maps use the OpenFreeMap background below.
  await context.route('https://tile.openstreetmap.org/**', route => route.fulfill({
    status: 200, contentType: 'image/png', body: transparentTile,
    headers: {'Cache-Control': 'public, max-age=86400', 'Access-Control-Allow-Origin': '*'}
  }));
  await context.route('**/data/map/style.json', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(style)
  }));
  await context.route('https://tiles.openfreemap.org/**', route => {
    const url = new URL(route.request().url());
    if (vectorFixture && url.pathname === '/planet') return route.fulfill({
      status: 200, contentType: 'application/json', headers: {'Access-Control-Allow-Origin': '*'},
      body: JSON.stringify({tilejson: '3.0.0', minzoom: 0, maxzoom: 14, tiles: ['https://tiles.openfreemap.org/test-vector-tiles/{z}/{x}/{y}.pbf'], attribution: 'OpenStreetMap contributors · OpenMapTiles', vector_layers: [...new Set(style.layers.map(layer => layer['source-layer']).filter(Boolean))].map(id => ({id, fields: {name: 'String', class: 'String', rank: 'Number', name_en: 'String'}}))})
    });
    if (vectorFixture && /\/test-vector-tiles\/.*\.pbf$/.test(url.pathname)) return route.fulfill({
      status: 200, contentType: 'application/x-protobuf', body: isolatedPlaceTile(url), headers: {'Access-Control-Allow-Origin': '*'}
    });
    if (/\.png(?:\?|$)/.test(route.request().url())) return route.fulfill({
      status: 200, contentType: 'image/png', body: transparentTile,
      headers: {'Cache-Control': 'public, max-age=86400', 'Access-Control-Allow-Origin': '*'}
    });
    // A new unmocked style dependency should not silently reach the public map
    // service from any of the older functional browser suites.
    return route.abort();
  });
}
