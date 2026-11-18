import assert from 'node:assert/strict';
import { gunzipSync } from 'node:zlib';
import { mkdir, readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { chromium } from '../.local/browser-tests/node_modules/playwright/index.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const catalog = JSON.parse(gunzipSync(await readFile(path.join(root, 'data/neighborhoods/catalog.geojson.gz'))).toString('utf8'));
const populatedCity = catalog.features[0]?.properties.municipality;
assert.ok(populatedCity, 'The review scenario needs an actual source polygon.');
await mkdir(path.join(root, '.local/neighborhoods'), {recursive: true});
const browser = await chromium.launch({headless: true,
  ...(process.env.OTTHONRA_REVIEW_CHROMIUM_PATH ? {executablePath:process.env.OTTHONRA_REVIEW_CHROMIUM_PATH} : {})});
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
    assert.match(await page.locator('#detail').innerText(), /Név ellenőrzése/);
    assert.match(await page.locator('#detail').innerText(), /Forráskivonat dátuma/);
    assert.match(await page.locator('#detail').innerText(), /mai pontossága nincs igazolva/);
    assert.ok((await page.locator('#detail a').getAttribute('href'))?.startsWith('https://'));
    await page.locator('#all').click();
    assert.equal(await page.locator('#list button[aria-pressed=true]').count(), 0);
    await page.locator('#query').fill('nincs-ilyen-varosresz-ellenorzesi-proba');
    assert.equal(await page.locator('#map path').count(), 0);
    assert.equal(await page.locator('#empty').isVisible(), true);
    await page.locator('#query').fill('');
    assert.ok(await page.locator('#map path').count() > 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${populatedCity} must fit the viewport`);
    const budapestFeatures = catalog.features.filter(feature => feature.properties.municipality === 'Budapest');
    if (budapestFeatures.length) {
      await page.selectOption('#city', 'Budapest');
      assert.equal(await page.locator('#list button').count(), budapestFeatures.length, 'Budapest lists every collected area and district');
      assert.ok(await page.locator('#map path').count() > 0, 'The full Budapest collection must render actual SVG paths');
      assert.ok(budapestFeatures.some(feature => feature.properties.name === 'Orbánhegy'), 'The Budapest scenario needs the actual Orbánhegy boundary');
      await page.locator('#list').getByRole('button', {name: /^Orbánhegy(?:\s*·|$)/}).first().click();
      assert.equal(await page.locator('#map path').count(), 1);
      const details = await page.locator('#detail').innerText();
      assert.match(details, /Orbánhegy/);
      assert.match(details, /Név ellenőrzése/);
      assert.match(details, /Forráskivonat dátuma/);
      assert.match(details, /mai pontossága nincs igazolva/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Budapest must fit the viewport after selecting an actual boundary');
    }
    const dorogAssociation = catalog.features.find(feature => feature.properties.municipality === 'Dorog' &&
      feature.properties.geometryAssociation?.status === 'crosses_2025_reference_municipal_boundaries');
    if (dorogAssociation) {
      await page.selectOption('#city', 'Dorog');
      await page.locator('#list button').first().click();
      assert.ok(await page.locator('#map path').count() > 0);
      const details = await page.locator('#detail').innerText();
      assert.match(details, /Településhatárt átlépő jelölt/);
      assert.match(details, /Dorog:\s*10/);
      assert.match(details, /Esztergom:\s*8/);
      assert.match(details, /18 különböző forráscsúcspont/);
      assert.match(details, /csúcspontszám, nem területarány/);
      assert.match(details, /Nem használható: a poligon a vizsgált településhatárt keresztezi/);
      const officialEvidence = (dorogAssociation.properties.sourceAssociationAudit?.evidenceUrls ?? [])
        .find(url => new URL(url).hostname === 'www.dorog.hu');
      assert.ok(officialEvidence, 'The Dorog scenario needs its official municipal name evidence');
      assert.ok((await page.locator('#detail a').evaluateAll(links => links.map(link => link.href))).includes(officialEvidence),
        'The official Dorog evidence must be linked in the actual detail panel');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'The cross-boundary warning must fit the viewport');
    }
    const emptyCity = await page.locator('#city option').evaluateAll((options, citiesWithAreas) =>
      options.map(option => option.value).find(name => !citiesWithAreas.includes(name)),
    [...new Set(catalog.features.map(feature => feature.properties.municipality))]);
    if (emptyCity) {
      await page.selectOption('#city', emptyCity);
      assert.equal(await page.locator('#map path').count(), 0);
      assert.equal(await page.locator('#empty').isVisible(), true);
      await page.selectOption('#city', populatedCity);
    }
    await page.locator('#query').fill('');
    const estimated = JSON.parse(await readFile(path.join(root, 'data/neighborhoods/estimated-candidates.geojson'), 'utf8'));
    assert.ok(estimated.features.length, 'The separate-layer scenario needs an actual inferred source.');
    const inferredCity = estimated.features[0].properties.municipality;
    const summaryBefore = await page.locator('#summary').innerText();
    await page.selectOption('#layer', 'inferred');
    await page.selectOption('#city', inferredCity);
    const expectedInferred = estimated.features.filter(f => f.properties.municipality === inferredCity).length;
    assert.equal(await page.locator('#list button').count(), expectedInferred);
    assert.equal(await page.locator('#map path.inferred').count(), expectedInferred);
    assert.match(await page.locator('#count').innerText(), /nem növelik.*lefedettséget/);
    await page.locator('#list button').first().click();
    assert.match(await page.locator('#detail').innerText(), /Becsült kutatási jelölt/);
    assert.match(await page.locator('#detail').innerText(), /nem hitelesített/);
    assert.ok((await page.locator('#detail a').first().getAttribute('href'))?.startsWith('https://'));
    assert.equal(await page.locator('#summary').innerText(), summaryBefore, 'Layer changes must not inflate source coverage.');
    await page.selectOption('#layer', 'source');
    assert.equal(await page.locator('#map path.inferred').count(), 0);
    assert.equal(await page.locator('#list button[aria-pressed=true]').count(), 0);
    await page.selectOption('#city', populatedCity);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    assert.deepEqual(remoteRequests, [], 'Reviewing stored polygons must not call any external map service.');
    await page.screenshot({path: path.join(root, `.local/neighborhoods/review-${viewport.width}.png`), fullPage: true});
    await page.close();
  }
  console.log('Neighborhood review passed on desktop, tablet and mobile without external requests.');
} finally {await browser.close();}
