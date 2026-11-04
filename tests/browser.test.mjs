/** Real-browser regressions for the location picker and the create-search flow.
 * Install Playwright into ignored .local/browser-tests; see the CI workflow.
 */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const modulePath = process.env.PLAYWRIGHT_MODULE;
const playwrightUrl = modulePath
  ? (modulePath.startsWith('file:') ? modulePath : pathToFileURL(resolve(modulePath)).href)
  : new URL('../.local/browser-tests/node_modules/playwright/index.mjs', import.meta.url).href;
const { chromium } = await import(playwrightUrl);
const origin = new URL(process.argv[2] || 'http://127.0.0.1:8080').origin;
const screenshots = resolve('.local/browser-tests/screenshots');
const viewports = [
  { name: 'desktop', width: 1280, height: 900, touch: false },
  { name: 'tablet', width: 800, height: 1100, touch: true },
  { name: 'mobile', width: 390, height: 844, touch: true }
];

async function demoState(page) {
  return page.evaluate(async () => (await import('/model.js')).model.getState());
}

async function openSearch(page, interact) {
  await interact(page.locator('.page-heading [data-action="new"]'));
  if (!await page.locator('#entity-form').count()) {
    await interact(page.locator('.choose-type [data-action="new"][data-kind="search"]'));
  }
  await page.locator('#entity-form').waitFor();
  // Wait for the dialog's automatic focus before typing into another field.
  await page.waitForFunction(() => document.activeElement?.id === 'f-title');
}

async function choose(page, interact, id, query) {
  const input = page.locator('#location-input');
  await input.fill(query);
  await interact(page.locator(`#location-options [data-location-id="${id}"]`));
  assert.equal(await input.inputValue(), '');
  assert.equal(await page.locator('#location-options').isHidden(), true);
}

async function verifyViewport(browser, viewport) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    hasTouch: viewport.touch,
    reducedMotion: 'reduce'
  });
  // Local UI behaviour must not depend on third-party font availability.
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  await context.route('https://fonts.gstatic.com/**', route => route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  page.setDefaultNavigationTimeout(10000);
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  const interact = locator => viewport.touch ? locator.tap() : locator.click();
  try {
    await page.goto(origin + '/#searches', { waitUntil: 'domcontentloaded' });
    await page.locator('.page-heading [data-action="new"]').waitFor();
    const initialActive = (await demoState(page)).active;
    await openSearch(page, interact);
    const input = page.locator('#location-input');
    const list = page.locator('#location-options');

    await input.scrollIntoViewIfNeeded();
    await input.fill('Deb');
    await list.waitFor({ state: 'visible' });
    assert.equal(await input.inputValue(), 'Deb');
    const geometry = await input.evaluate(element => {
      const field = element.getBoundingClientRect();
      const popup = document.getElementById('location-options').getBoundingClientRect();
      return {
        inputBottom: field.bottom,
        listTop: popup.top,
        inputIsTopmost: document.elementFromPoint(field.left + field.width / 2, field.top + field.height / 2) === element
      };
    });
    assert.equal(geometry.inputIsTopmost, true, 'Suggestions must not cover the typed input');
    assert.ok(geometry.listTop >= geometry.inputBottom - 1, 'Suggestions must begin below the input');

    await interact(page.locator('#f-title'));
    assert.equal(await list.isHidden(), true, 'Clicking or tapping another field must close suggestions');
    assert.equal(await input.inputValue(), 'Deb', 'Dismissing must preserve the query');
    assert.equal(await page.locator('#location-chips .location-chip').count(), 0, 'Dismissing must not select a place');

    await interact(input);
    await list.waitFor({ state: 'visible' });
    await input.press('Escape');
    assert.equal(await list.isHidden(), true);
    assert.equal(await page.locator('#entity-form').isVisible(), true, 'Escape must dismiss the list before the dialog');
    await input.fill('Debr');
    await list.waitFor({ state: 'visible' });
    await input.press('Tab');
    assert.equal(await list.isHidden(), true, 'Tab must dismiss suggestions');
    assert.equal(await page.locator('#entity-form').isVisible(), true);
    await interact(input);
    await list.waitFor({ state: 'visible' });
    await interact(page.locator('#location-options [data-location-id="city:Debrecen"]'));
    assert.equal(await input.inputValue(), '');
    assert.equal(await page.locator('#location-chips .location-chip').count(), 1, 'An option click must still select its location');

    await input.fill('Budapest V. kerület');
    await input.press('ArrowDown');
    assert.ok(await input.getAttribute('aria-activedescendant'));
    await input.press('Enter');
    assert.equal(await list.isHidden(), true);
    assert.equal(await page.locator('#location-chips .location-chip').count(), 2);
    const title = `Böngészős próba – ${viewport.name}`;
    await page.locator('#f-title').fill(title);
    await interact(page.locator('#entity-form button[type="submit"]'));
    await page.getByRole('heading', { name: 'Elkészült a keresési igényed.', exact: true }).waitFor();
    const savedState = await demoState(page);
    const saved = savedState.searches.find(item => item.title === title);
    assert.ok(saved, 'The search must be saved before the confirmation appears');
    assert.deepEqual(saved.locationIds, ['city:Debrecen', 'district:Budapest:5']);
    assert.deepEqual(savedState.active, initialActive, 'Saving alone must not change the active search');
    const discover = page.getByRole('button', { name: 'Ingatlanok felfedezése', exact: true });
    assert.equal(await discover.getAttribute('data-action'), 'discover-search');
    assert.equal(await discover.getAttribute('data-id'), saved.id);
    await interact(discover);
    await page.waitForFunction(expected => location.hash === '#discover' && document.querySelector('.strip-title')?.textContent.includes(expected), title);
    assert.deepEqual((await demoState(page)).active, { kind: 'search', id: saved.id });
    assert.equal(await page.locator('#modal-root .modal').count(), 0);

    // Choosing "later" must retain the new search without replacing the active one.
    await openSearch(page, interact);
    await choose(page, interact, 'city:Debrecen', 'Debrecen');
    const laterTitle = `Később folytatom – ${viewport.name}`;
    await page.locator('#f-title').fill(laterTitle);
    await interact(page.locator('#entity-form button[type="submit"]'));
    await page.getByRole('heading', { name: 'Elkészült a keresési igényed.', exact: true }).waitFor();
    await interact(page.locator('.modal-actions [data-action="close"]'));
    assert.equal(await page.locator('#modal-root .modal').count(), 0);
    assert.deepEqual((await demoState(page)).active, { kind: 'search', id: saved.id });
    assert.ok((await demoState(page)).searches.some(item => item.title === laterTitle));
    if (viewport.width <= 720) await interact(page.locator('.mobile-menu'));
    await interact(page.locator('.nav-button[data-page="searches"]'));
    await page.getByRole('heading', { name: laterTitle, exact: true }).waitFor();
    assert.deepEqual(pageErrors, [], 'The browser must not report unhandled frontend errors');
    console.log(`Browser ${viewport.name} ${viewport.width}x${viewport.height}: input visibility, outside dismissal, keyboard selection, search confirmation, activation and later dismissal passed.`);
  } catch (error) {
    await mkdir(screenshots, { recursive: true });
    await page.screenshot({ path: resolve(screenshots, `${viewport.name}-failure.png`), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    await context.close();
  }
}

const browser = await chromium.launch({ headless: true });
let failures = 0;
try {
  for (const viewport of viewports) {
    try {
      await verifyViewport(browser, viewport);
    } catch (error) {
      failures++;
      console.error(`Browser ${viewport.name} failed: ${error.stack || error}`);
    }
  }
} finally {
  await browser.close();
}
if (failures) process.exitCode = 1;
