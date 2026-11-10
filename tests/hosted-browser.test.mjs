/** Hosted-mode browser integration against the real Production-hosted test API.
 * Run only with a disposable test database. API responses are never mocked.
 */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const modulePath = process.env.PLAYWRIGHT_MODULE;
const playwrightUrl = modulePath
  ? (modulePath.startsWith('file:') ? modulePath : pathToFileURL(resolve(modulePath)).href)
  : new URL('../.local/browser-tests/node_modules/playwright/index.mjs', import.meta.url).href;
const {chromium} = await import(playwrightUrl);
const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000').origin;
const screenshots = resolve('.local/browser-tests/screenshots');
const viewports = [
  {name: 'desktop', width: 1280, height: 900, touch: false},
  {name: 'tablet', width: 800, height: 1100, touch: true},
  {name: 'mobile', width: 390, height: 844, touch: true}
];

async function serverState(page) {
  return page.evaluate(async () => {
    const model = (await import('/api.js')).getModel();
    return model ? model.getState() : null;
  });
}

async function navigate(page, interact, destination, viewport) {
  if (viewport.width <= 720) await interact(page.locator('.mobile-menu'));
  await interact(page.locator(`.nav-button[data-page="${destination}"]`));
  await page.waitForFunction(expected => location.hash === `#${expected}`, destination);
}

async function chooseLocation(page, interact, query, id) {
  await page.locator('#location-input').fill(query);
  await interact(page.locator(`#location-options [data-location-id="${id}"]`));
  assert.equal(await page.locator('#location-input').inputValue(), '');
}

async function verifyViewport(browser, viewport) {
  const context = await browser.newContext({
    viewport: {width: viewport.width, height: viewport.height},
    hasTouch: viewport.touch, reducedMotion: 'reduce'
  });
  // Match the other functional browser suites: a late third-party font swap
  // must not move the form between the touch action's hit test and its tap.
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  await context.route('https://fonts.gstatic.com/**', route => route.abort());
  // Emulate the one public file changed by prepare-site.mjs; every API call
  // continues through the real web proxy and the real MySQL-backed API.
  await context.route(`${origin}/runtime-config.js`, route => route.fulfill({
    status: 200, contentType: 'text/javascript; charset=utf-8',
    headers: {'Cache-Control': 'no-store'},
    body: 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});\n'
  }));
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(30000);
  const errors = [], paymentRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname === '/api/credits/checkout' || url.hostname === 'checkout.stripe.com') paymentRequests.push(url.pathname);
  });
  const interact = locator => viewport.touch ? locator.tap() : locator.click();
  const suffix = `${Date.now()}-${viewport.name}-${Math.random().toString(16).slice(2)}`;
  const email = `hosted-${suffix}@example.test`, password = 'HostedTestPassword2026!';
  const title = `Felhős keresés – ${suffix}`;
  try {
    await page.goto(origin + '/#login', {waitUntil: 'domcontentloaded'});
    await page.locator('#hosted-auth-form').waitFor();
    assert.equal(await page.locator('.sidebar').count(), 0, 'A guest must not see a demo workspace');
    assert.equal(await page.locator('input[name="baseUrl"]').count(), 0, 'Hosted users must not select a backend URL');
    assert.equal(await page.locator('[data-action="reset"]').count(), 0);
    assert.match(await page.locator('#app').innerText(), /Tesztkörnyezet/);
    assert.doesNotMatch(await page.locator('#app').innerText(), /Demó munkatér|Vissza a demóhoz/);
    assert.equal(await serverState(page), null);

    await interact(page.locator('[data-action="auth-mode"][data-mode="register"]'));
    assert.equal(new URL(page.url()).hash, '#register', 'The registration action must switch the auth route');
    await page.getByRole('heading', {name: 'Hozd létre a fiókodat.', exact: true}).waitFor();
    await page.locator('#f-name').fill(`Felhős Teszt ${viewport.name}`);
    await page.locator('#f-email').fill(email);
    await page.locator('#f-password').fill(password);
    const registration = page.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/register' && response.request().method() === 'POST');
    await interact(page.locator('#hosted-auth-form button[type="submit"]'));
    assert.equal((await registration).status(), 200, 'Registration must reach the real API');
    await page.getByRole('heading', {name: 'Hozd létre az első profilodat.', exact: true}).waitFor();
    assert.equal(await page.locator('#hosted-auth-form').count(), 0);
    const fresh = await serverState(page);
    assert.equal(fresh.user.email, email);
    assert.equal(fresh.credits, 0);
    assert.equal(fresh.active.id, null);
    assert.equal(fresh.searches.length, 0);
    assert.equal(fresh.properties.length, 0);

    await interact(page.locator('.page-heading [data-action="new"]'));
    await interact(page.locator('.choose-type [data-action="new"][data-kind="search"]'));
    await page.locator('#entity-form').waitFor();
    await page.waitForFunction(() => document.activeElement?.id === 'f-title');
    await page.locator('#f-title').fill(title);
    await chooseLocation(page, interact, 'Debrecen', 'city:Debrecen');
    await chooseLocation(page, interact, 'Budapest V. kerület', 'district:Budapest:5');
    const save = page.waitForResponse(response => new URL(response.url()).pathname === '/api/searches' && response.request().method() === 'POST');
    await interact(page.locator('#entity-form button[type="submit"]'));
    assert.equal((await save).status(), 201);
    await page.getByRole('heading', {name: 'Elkészült a keresési igényed.', exact: true}).waitFor();
    const savedState = await serverState(page), saved = savedState.searches.find(item => item.title === title);
    assert.ok(saved, 'The saved search must exist in MySQL before confirmation');
    assert.deepEqual(saved.locationIds, ['city:Debrecen', 'district:Budapest:5']);
    assert.equal(saved.minPrice, null); assert.equal(saved.maxArea, null); assert.equal(saved.maxRooms, null);
    assert.equal(savedState.active.id, null, 'Saving must not implicitly activate the search');
    const activation = page.waitForResponse(response => new URL(response.url()).pathname === '/api/me/active' && response.request().method() === 'PUT');
    await interact(page.getByRole('button', {name: 'Ingatlanok felfedezése', exact: true}));
    assert.equal((await activation).status(), 200);
    await page.waitForFunction(expected => document.querySelector('.strip-title')?.textContent.includes(expected), title);
    assert.deepEqual((await serverState(page)).active, {kind: 'search', id: saved.id});

    await navigate(page, interact, 'credits', viewport);
    await page.locator('.credit-hero').waitFor();
    assert.match(await page.locator('#app').innerText(), /A tesztkreditek ingyenesek/);
    assert.equal(await page.getByRole('button', {name: 'Kreditet vásárolok', exact: true}).count(), 0);
    await interact(page.locator('.packages [data-action="buy"][data-amount="20"]'));
    await page.getByRole('heading', {name: 'Tesztkreditek feltöltése', exact: true}).waitFor();
    const topup = page.waitForResponse(response => new URL(response.url()).pathname === '/api/credits/demo-topup' && response.request().method() === 'POST');
    await interact(page.locator('[data-action="confirm-test-credits"][data-amount="20"]'));
    const credited = await topup;
    assert.equal(credited.status(), 200);
    assert.equal((await credited.json()).credits, 20);
    await page.waitForFunction(() => !document.querySelector('#modal-root .modal') && /20\s*tesztkredit/.test(document.querySelector('.credit-hero h2')?.textContent || ''));
    const funded = await serverState(page);
    assert.equal(funded.credits, 20);
    assert.ok(funded.ledger.some(entry => entry.amount === 20 && /Tesztkredit-feltöltés/.test(entry.description)));
    assert.deepEqual(paymentRequests, [], 'Test credits must never invoke a real payment checkout');
    assert.equal(new URL(page.url()).origin, origin);

    await page.reload({waitUntil: 'domcontentloaded'});
    await page.locator('.credit-hero').waitFor();
    const reloaded = await serverState(page);
    assert.equal(reloaded.user.id, fresh.user.id);
    assert.equal(reloaded.credits, 20);
    assert.equal(reloaded.searches.find(item => item.id === saved.id)?.title, title);

    await navigate(page, interact, 'settings', viewport);
    await page.locator('#profile-form').waitFor();
    assert.equal(await page.locator('input[name="baseUrl"]').count(), 0);
    const publicPreview=page.waitForResponse(response => new URL(response.url()).pathname === '/api/public/landing');
    await interact(page.getByRole('button', {name: 'Kijelentkezés', exact: true}));
    await page.locator('.landing-header').waitFor();
    assert.equal(new URL(page.url()).hash,'#landing');
    assert.equal(await serverState(page), null);
    assert.equal(await page.evaluate(()=>localStorage.getItem('otthonra.api')),null,'Logout removes the saved authenticated session');
    assert.equal(await page.locator('.sidebar,#hosted-auth-form').count(), 0);
    const publicResponse=await publicPreview;assert.equal(publicResponse.status(),200);assert.equal(publicResponse.request().headers().authorization,undefined,'The post-logout preview must be anonymous');
    assert.doesNotMatch(await page.locator('#app').innerText(), /Demó munkatér|Vissza a demóhoz/);
    await interact(page.locator('.landing-header [data-mode="login"]'));await page.locator('#hosted-auth-form').waitFor();

    await page.locator('#f-email').fill(email);
    await page.locator('#f-password').fill(password);
    const login = page.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/login' && response.request().method() === 'POST');
    await interact(page.locator('#hosted-auth-form button[type="submit"]'));
    assert.equal((await login).status(), 200);
    await page.waitForFunction(expected => document.querySelector('.strip-title')?.textContent.includes(expected), title);
    const signedIn = await serverState(page);
    assert.equal(signedIn.user.id, fresh.user.id);
    assert.equal(signedIn.credits, 20);
    assert.equal(signedIn.searches.find(item => item.id === saved.id)?.title, title);
    assert.deepEqual(signedIn.active, {kind: 'search', id: saved.id});
    assert.deepEqual(errors, [], 'The hosted flow must not produce unhandled browser errors');
    console.log(`Hosted browser ${viewport.name} ${viewport.width}x${viewport.height}: real registration, MySQL search, activation, free test credits, reload persistence and logout to anonymous landing and login passed.`);
  } catch (error) {
    await mkdir(screenshots, {recursive: true});
    await page.screenshot({path: resolve(screenshots, `hosted-${viewport.name}-failure.png`), fullPage: true}).catch(() => {});
    throw error;
  } finally {
    await context.close();
  }
}

const browser = await chromium.launch({headless: true});
let failures = 0;
try {
  for (const viewport of viewports) {
    try { await verifyViewport(browser, viewport); }
    catch (error) { failures++; console.error(`Hosted browser ${viewport.name} failed: ${error.stack || error}`); }
  }
} finally { await browser.close(); }
if (failures) process.exitCode = 1;
