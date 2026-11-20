/** Keep browser regressions deterministic without requesting public OSM tiles. */
const transparentTile = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAXpeqz8AAAAASUVORK5CYII=', 'base64');

export async function mockMapTiles(context) {
  await context.route('https://tile.openstreetmap.org/**', route => route.fulfill({
    status: 200, contentType: 'image/png', body: transparentTile,
    headers: {'Cache-Control': 'public, max-age=86400'}
  }));
}
