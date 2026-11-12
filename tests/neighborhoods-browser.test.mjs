import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { chromium } from '../.local/browser-tests/node_modules/playwright/index.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const catalog = JSON.parse(await readFile(path.join(root, 'data/neighborhoods/catalog.geojson'), 'utf8'));
const populatedCity = catalog.features[0]?.properties.municipality;
assert.ok(populatedCity, 'The review scenario needs an actual source polygon.');
await mkdir(path.join(root, '.local/neighborhoods'), {recursive: true});
const browser = await chromium.launch({headless: true});
try {
  for (const viewport of [{width: 1280, height: 900}, {width: 834, height: 1112}, {width: 390, height: 844}]) {
    const page = await browser.newPage({viewport});
    const errors = [], remoteRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {if (/^https?:/.test(request.url())) remoteRequests.push(request.url());});
    await page.goto(pathToFileURL(path.join(root, 'data/neighborhoods/review.html')).href);
    await page.selectOption('#city', populatedCity);
    await page.waitForSelector('#list button');
    assert.ok(await page.locator('#map path').count() > 0);
    assert.equal(await page.locator('#empty').isVisible(), false);
    await page.locator('#list button').first().click();
    assert.equal(await page.locator('#map path').count(), 1);
    assert.equal(await page.locator('#list button[aria-pressed=true]').count(), 1);
    assert.match(await page.locator('#detail').innerText(), /Ellenőrzésre vár/);
    assert.ok((await page.locator('#detail a').getAttribute('href'))?.startsWith('https://'));
    await page.locator('#all').click();
    assert.equal(await page.locator('#list button[aria-pressed=true]').count(), 0);
    await page.locator('#query').fill('nincs-ilyen-varosresz-ellenorzesi-proba');
    assert.equal(await page.locator('#map path').count(), 0);
    assert.equal(await page.locator('#empty').isVisible(), true);
    await page.locator('#query').fill('');
    assert.ok(await page.locator('#map path').count() > 0);
    const emptyCity = await page.locator('#city option').evaluateAll((options, citiesWithAreas) =>
      options.map(option => option.value).find(name => !citiesWithAreas.includes(name)),
    [...new Set(catalog.features.map(feature => feature.properties.municipality))]);
    if (emptyCity) {
      await page.selectOption('#city', emptyCity);
      assert.equal(await page.locator('#map path').count(), 0);
      assert.equal(await page.locator('#empty').isVisible(), true);
      await page.selectOption('#city', populatedCity);
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    assert.deepEqual(remoteRequests, [], 'Reviewing stored polygons must not call any external map service.');
    await page.screenshot({path: path.join(root, `.local/neighborhoods/review-${viewport.width}.png`), fullPage: true});
    await page.close();
  }
  console.log('Neighborhood review passed on desktop, tablet and mobile without external requests.');
} finally {await browser.close();}
