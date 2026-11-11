/** The repeatable hosted TEST feedback scenario, through the real API and MySQL.
 * No API response or authenticated state is mocked; run after startup fixture proof.
 */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {DEMO_PASSWORD, DEMO_USERS, DEMO_FIXTURES, FEEDBACK_TEST_SCENARIO} from '../scripts/gcp/demo-data.mjs';

const modulePath = process.env.PLAYWRIGHT_MODULE;
const playwrightUrl = modulePath
  ? (modulePath.startsWith('file:') ? modulePath : pathToFileURL(resolve(modulePath)).href)
  : new URL('../.local/browser-tests/node_modules/playwright/index.mjs', import.meta.url).href;
const {chromium} = await import(playwrightUrl);
const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000').origin;
const screenshots = resolve('.local/browser-tests/screenshots');
const buyer = DEMO_USERS.find(user => user.key === FEEDBACK_TEST_SCENARIO.buyer);
const seller = DEMO_USERS.find(user => user.key === FEEDBACK_TEST_SCENARIO.seller);
const property = DEMO_FIXTURES.find(fixture => fixture.key === FEEDBACK_TEST_SCENARIO.property);
assert.ok(buyer && seller && property, 'The canonical hosted feedback scenario must exist');
const choices = [
  'Túl kevés információ van megosztva az ingatlanról',
  'Nem tetszik az ingatlan elrendezése',
  'Nem jók a fényviszonyok az ingatlanban',
  'Az ingatlan elhelyezkedése nem szimpatikus',
  'Nem tetszik, vagy nem látszik a képeken a kilátás az ablakokból',
  'Az ingatlan nem felel meg a róla feltüntetett paramétereknek',
  'Egyéb',
  'Nem szeretnék válaszolni'
];
const viewports = [
  {name: 'desktop', width: 1280, height: 900, touch: false},
  {name: 'tablet', width: 800, height: 1100, touch: true},
  {name: 'mobile', width: 390, height: 844, touch: true}
];
const pathIs = (response, path, method) => new URL(response.url()).pathname === path && response.request().method() === method;
const readState = page => page.evaluate(async () => {
  const model = (await import('/api.js')).getModel();
  if (model?.mode !== 'api') throw new Error('The hosted scenario must use the real API');
  return model.getState();
});

async function verify(browser, viewport) {
  const context = await browser.newContext({
    viewport: {width: viewport.width, height: viewport.height},
    hasTouch: viewport.touch, reducedMotion: 'reduce'
  });
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  await context.route('https://fonts.gstatic.com/**', route => route.abort());
  await context.route('https://get.geojs.io/**', route => route.abort());
  // This is the public deployment configuration, not an API or seed-data mock.
  await context.route(`${origin}/runtime-config.js`, route => route.fulfill({
    status: 200, contentType: 'text/javascript; charset=utf-8',
    headers: {'Cache-Control': 'no-store'},
    body: 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});\n'
  }));
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  page.setDefaultNavigationTimeout(30000);
  const errors = [], mutations = [], authRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path === '/api/auth/login') authRequests.push(path);
    if (request.method() !== 'GET' && (path === '/api/decisions' || /^\/api\/feedback\/[0-9a-f-]+$/i.test(path))) {
      mutations.push({path, body: request.postDataJSON()});
    }
  });
  // Let Playwright scroll and re-resolve the live locator during touch actions.
  const interact = locator => viewport.touch ? locator.tap() : locator.click();
  const navigate = async destination => {
    const menu = page.locator('.mobile-menu');
    if (await menu.isVisible()) await interact(menu);
    await interact(page.locator(`.nav-button[data-page="${destination}"]`));
    await page.waitForFunction(expected => location.hash === `#${expected}`, destination);
  };
  const login = async (user, role) => {
    await page.locator('#hosted-auth-form').waitFor();
    await page.locator('#f-email').fill(user.email);
    await page.locator('#f-password').fill(DEMO_PASSWORD);
    const authenticated = page.waitForResponse(response => pathIs(response, '/api/auth/login', 'POST'));
    const capability = page.waitForResponse(response => pathIs(response, '/api/test/feedback-scenario', 'GET'));
    await interact(page.locator('#hosted-auth-form button[type="submit"]'));
    assert.equal((await authenticated).status(), 200, 'The dedicated account must log in through the real API');
    const response = await capability;
    assert.equal(response.status(), 200);
    const scenario = await response.json();
    assert.equal(scenario.available, true);
    assert.equal(scenario.role, role);
    assert.equal(scenario.feedbackReady, true);
    assert.equal(scenario.buyerEmail, buyer.email);
    assert.equal(scenario.sellerEmail, seller.email);
    assert.ok(scenario.propertyId && scenario.searchId);
    await page.locator('.feedback-scenario').waitFor();
    assert.match(await page.locator('.feedback-scenario').innerText(), /Visszajelzés-próba/);
    assert.equal(await page.locator('[data-action="feedback-scenario-reset"]').innerText(), 'Teszt újraindítása');
    assert.equal((await readState(page)).user.email, user.email);
    return scenario;
  };
  const reset = async scenario => {
    const completed = page.waitForResponse(response => pathIs(response, '/api/test/feedback-scenario/reset', 'POST'));
    await interact(page.locator('[data-action="feedback-scenario-reset"]'));
    const response = await completed;
    assert.equal(response.status(), 200, 'The visible reset control must reset the actual test pair');
    assert.deepEqual(response.request().postDataJSON(), {});
    const restored = await response.json();
    assert.equal(restored.available, true);
    assert.equal(restored.feedbackReady, true);
    assert.equal(restored.role, scenario.role);
    assert.equal(restored.propertyId, scenario.propertyId);
    assert.equal(restored.searchId, scenario.searchId);
    return restored;
  };
  try {
    await page.goto(origin + '/#login', {waitUntil: 'domcontentloaded'});
    const scenario = await login(buyer, 'buyer');
    await reset(scenario);
    await page.locator('#candidate').waitFor();
    assert.equal(new URL(page.url()).hash, '#discover');
    assert.equal(await page.locator('#candidate h2').innerText(), property.input.title);
    assert.equal(await page.locator(`.report-button[data-id="${scenario.propertyId}"]`).count(), 1);
    const buyerState = await readState(page);
    assert.deepEqual(buyerState.active, {kind: 'search', id: scenario.searchId});
    const decision = page.waitForResponse(response => pathIs(response, '/api/decisions', 'POST'));
    await interact(page.locator('.card-actions [data-action="pass"]'));
    const decisionResponse = await decision;
    assert.equal(decisionResponse.status(), 200);
    const rejected = await decisionResponse.json();
    assert.equal(rejected.charged, 0);
    assert.equal(rejected.feedbackPrompt?.propertyId, scenario.propertyId, 'The first real rejection must immediately request feedback');
    assert.ok(rejected.feedbackPrompt?.id);
    await page.locator('.feedback-survey').waitFor();
    assert.equal(await page.locator('#feedback-prompt-title').innerText(), 'Segíts Péternek egy visszajelzéssel');
    assert.equal(await page.locator('#feedback-prompt-question').innerText(), 'Miért nem tetszett az ingatlan?');
    assert.deepEqual(await page.locator('.feedback-answer').allTextContents(), choices);
    assert.equal(await page.locator('#candidate').count(), 0, 'A pending prompt hides the next recommendation');
    assert.equal(await page.locator('.feedback-survey .modal-close,.feedback-survey select,.feedback-survey button[type="submit"]').count(), 0);
    const answer = page.waitForResponse(response => pathIs(response, `/api/feedback/${rejected.feedbackPrompt.id}`, 'POST'));
    await interact(page.locator('[data-action="feedback-answer"][data-reason="layout"]'));
    const answerResponse = await answer;
    assert.equal(answerResponse.status(), 200);
    assert.equal((await answerResponse.json()).accepted, true);
    await page.locator('.feedback-survey').waitFor({state: 'detached'});
    assert.equal((await readState(page)).credits, buyerState.credits, 'Answering the survey must not charge the buyer');
    assert.deepEqual(mutations, [
      {path: '/api/decisions', body: {propertyId: scenario.propertyId, searchRequestId: scenario.searchId, liked: false}},
      {path: `/api/feedback/${rejected.feedbackPrompt.id}`, body: {reason: 'layout'}}
    ], 'One rejection and one answer click must produce exactly one ordinary request each');

    await navigate('settings');
    await page.locator('#profile-form').waitFor();
    await interact(page.locator('[data-action="disconnect"]'));
    await page.locator('.landing-header').waitFor();
    assert.equal(await page.locator('.feedback-scenario').count(), 0, 'The test controls must disappear after logout');
    await interact(page.locator('.landing-header [data-mode="login"]'));
    const sellerScenario = await login(seller, 'seller');
    assert.equal(sellerScenario.propertyId, scenario.propertyId);
    await navigate('insights');
    await page.locator('.property-insights').waitFor();
    assert.equal(await page.locator('.property-insights').getAttribute('data-property-id'), scenario.propertyId);
    assert.equal(await page.locator('.feedback-total').innerText(), '1 db');
    assert.match(await page.locator('.feedback-history').innerText(), /Nem tetszik az ingatlan elrendezése/);
    assert.match(await page.locator('.feedback-package-counts').innerText(), /1\s*\/\s*10 beérkezett/);
    assert.doesNotMatch(await page.locator('.feedback-results').innerText(), /visszajelzes-kereso@|Teszt Anna/);
    await reset(sellerScenario);
    await page.waitForFunction(() => document.querySelector('.feedback-total')?.textContent.trim() === '0 db');
    assert.equal(new URL(page.url()).hash, '#insights');
    assert.equal(await page.locator('.property-insights').getAttribute('data-property-id'), scenario.propertyId);
    assert.equal(await page.locator('.feedback-history').count(), 0);
    assert.match(await page.locator('.feedback-package-counts').innerText(), /0\s*\/\s*10 beérkezett/);
    assert.equal(await page.locator('[data-action="feedback-toggle"]').count(), 0, 'A prepaid scenario campaign has no pause control');
    assert.match(await page.locator('.feedback-package-panel .feedback-panel-heading .tag').innerText(), /Aktív/);
    const sellerState = await readState(page);
    assert.deepEqual(sellerState.active, {kind: 'property', id: scenario.propertyId});
    assert.equal(sellerState.credits, 90, 'Reset restores the prepaid 10-response test package without repeat charges');
    assert.equal(authRequests.length, 2, 'Each viewport uses only the buyer and seller real logins');
    assert.deepEqual(errors, [], 'The hosted feedback scenario must not produce unhandled browser errors');
    console.log(`Hosted feedback ${viewport.name} ${viewport.width}x${viewport.height}: real buyer reset, first-pass prompt, eight direct answers, seller result and repeatable prepaid reset passed.`);
  } catch (error) {
    await mkdir(screenshots, {recursive: true});
    await page.screenshot({path: resolve(screenshots, `feedback-scenario-${viewport.name}-failure.png`), fullPage: true}).catch(() => {});
    throw error;
  } finally {
    await context.close();
  }
}

const browser = await chromium.launch({headless: true});
let failures = 0;
try {
  for (const viewport of viewports) {
    try { await verify(browser, viewport); }
    catch (error) { failures++; console.error(`Hosted feedback ${viewport.name} failed: ${error.stack || error}`); }
  }
} finally { await browser.close(); }
if (failures) process.exitCode = 1;
