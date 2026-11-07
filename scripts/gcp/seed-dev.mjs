/** Populate only the identified test site through its ordinary authenticated API. */
import {mkdir, readFile, writeFile, rename, rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {readDevConfig, validateDevConfig} from './prepare-site.mjs';
import {DEMO_PASSWORD, DEFAULT_BATCH, createDemoCatalog} from './demo-data.mjs';

function prepareState(state, config) {
  if (Object.keys(state).length === 0) Object.assign(state, {
    version: 1, projectId: config.projectId, siteId: config.siteId, accounts: {}
  });
  if (state.version !== 1 || state.projectId !== config.projectId || state.siteId !== config.siteId
      || !state.accounts || typeof state.accounts !== 'object' || Array.isArray(state.accounts)) {
    throw new Error('A tesztadat-feltöltés nyugtája nem ehhez a tesztoldalhoz tartozik.');
  }
  return state;
}

const AUTH_WINDOW_MS = 61000;
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

export async function seedTestData({config, batch = DEFAULT_BATCH, fetchImpl = fetch, state = {},
  saveState = async () => {}, now = Date.now, wait = pause, onWait = async () => {}}) {
  config = validateDevConfig(config);
  const {users, fixtures} = createDemoCatalog(batch);
  state = prepareState(state, config);
  const origin = `https://${config.siteId}.web.app`;
  const result = {createdUsers: 0, createdProperties: 0, createdSearches: 0, existingUsers: 0, warnings: []};
  let authRequests = [];
  async function delay(milliseconds, reason) {
    await onWait({milliseconds, reason});
    await wait(milliseconds);
  }
  async function paceAuthentication() {
    authRequests = authRequests.filter(time => time > now() - AUTH_WINDOW_MS);
    if (authRequests.length >= 10) {
      await delay(Math.max(1, authRequests[0] + AUTH_WINDOW_MS - now()), 'auth-window');
      authRequests = authRequests.filter(time => time > now() - AUTH_WINDOW_MS);
    }
    authRequests.push(now());
  }
  function retryDelay(response) {
    const header = response.headers.get('Retry-After');
    if (header == null || header.trim() === '') return AUTH_WINDOW_MS;
    const seconds = Number(header);
    const milliseconds = Number.isFinite(seconds) && seconds >= 0 ? seconds * 1000 : Date.parse(header) - now();
    // Never retry earlier than a valid server instruction. A very long limit
    // is left for a later invocation instead of holding a deployment open.
    if (!Number.isFinite(milliseconds) || milliseconds < 0) return AUTH_WINDOW_MS;
    if (milliseconds > 120000) throw new Error('A belépési korlát két percnél hosszabb várakozást kér. Futtasd újra később a feltöltőt.');
    return Math.max(1000, milliseconds);
  }
  async function request(path, {method = 'GET', token, body, accepted = [200]} = {}) {
    const authentication = path === '/api/auth/login' || path === '/api/auth/register';
    let response;
    for (let attempt = 0; ; attempt++) {
      if (authentication) await paceAuthentication();
      try {
        response = await fetchImpl(origin + path, {
          method, redirect: 'error', signal: AbortSignal.timeout(20000),
          headers: {...(body === undefined ? {} : {'Content-Type': 'application/json'}), ...(token ? {Authorization: `Bearer ${token}`} : {})},
          ...(body === undefined ? {} : {body: JSON.stringify(body)})
        });
      } catch { throw new Error(`A tesztoldal nem érhető el: ${method} ${path}. A feltöltés újraindítható.`); }
      if (response.redirected || (response.url && new URL(response.url).origin !== origin)) {
        throw new Error('A tesztadat-feltöltés nem követhet másik címre átirányítást.');
      }
      if (response.status !== 429) break;
      if (!authentication || attempt >= 2) throw new Error('A bejelentkezési próbák korlátja továbbra is aktív. Futtasd újra később a feltöltőt.');
      await response.text();
      await delay(retryDelay(response), 'rate-limit');
      authRequests = [];
    }
    if (!accepted.includes(response.status)) throw new Error(`Tesztadat-feltöltési hiba: ${method} ${path}, HTTP ${response.status}.`);
    const text = await response.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    return {status: response.status, data};
  }
  // Do not send demo passwords or mutate any account until both server and web
  // explicitly identify the validated Hosting origin as a test deployment.
  const health = (await request('/api/health')).data;
  if (health?.status !== 'ready' || health.deployment !== 'test' || health.testCreditsEnabled !== true) {
    throw new Error('Tesztadat csak működő, tesztkredites tesztkörnyezetbe tölthető.');
  }
  const runtime = (await request('/runtime-config.js')).data;
  if (typeof runtime !== 'string' || !/\bmode:\s*["']api["']/.test(runtime)
      || !/\benvironment:\s*["']test["']/.test(runtime)) {
    throw new Error('A weboldal nem a valódi teszt API-t használja.');
  }
  for (const account of users) {
    const managed = state.accounts[account.email];
    // Existing managed accounts authenticate first, so a changed email/password
    // can never cause the importer to register a replacement identity.
    let session, created = false;
    if (managed) {
      session = await request('/api/auth/login', {
        method: 'POST', body: {email: account.email, password: DEMO_PASSWORD}, accepted: [200, 401]
      });
      if (session.status !== 200) {
        throw new Error(`A korábban feltöltött példafiók belépési adatai megváltoztak: ${account.email}. Új fiókot nem hoztunk létre.`);
      }
      result.existingUsers++;
    } else {
      // Register first for a new batch: one authentication request per missing
      // account, rather than a guaranteed failed login followed by registration.
      session = await request('/api/auth/register', {method: 'POST', accepted: [200, 201, 409], body: {
        name: account.name, email: account.email, password: DEMO_PASSWORD, phone: account.phone,
        accountType: account.accountType ?? 'private'
      }});
      if (session.status === 409) {
        session = await request('/api/auth/login', {
          method: 'POST', body: {email: account.email, password: DEMO_PASSWORD}, accepted: [200, 401]
        });
        if (session.status !== 200) throw new Error(`A példafiók más jelszóval már létezik: ${account.email}. A meglévő fiókot nem módosítottuk.`);
        result.existingUsers++;
      } else {
        created = true;
        result.createdUsers++;
      }
    }
    const {accessToken: token, user} = session.data ?? {};
    if (typeof token !== 'string' || !token || typeof user?.id !== 'string' || !user.id) {
      throw new Error('A teszt API nem adott érvényes bejelentkezést.');
    }
    if (user.accountType !== (account.accountType ?? 'private')) {
      throw new Error(`A példafiók fióktípusa eltér a tesztadatban megadottól: ${account.email}. Előbb telepítsd a fióktípusokat támogató API-t; a meglévő fiókot nem módosítottuk.`);
    }
    let receipt = state.accounts[account.email];
    if (!receipt && !created) {
      // A receipt lost on another machine is not permission to recreate an
      // archived fixture or overwrite somebody's work in a shared test account.
      result.warnings.push(`Meglévő fiók megőrizve: ${account.email}; ezen a gépen nincs feltöltési nyugtája.`);
      continue;
    }
    if (!receipt) {
      receipt = state.accounts[account.email] = {id: user.id, fixtures: {}, credited: false, activated: false, complete: false};
      await saveState(state);
    }
    if (receipt.id !== user.id || !receipt.fixtures || typeof receipt.fixtures !== 'object' || Array.isArray(receipt.fixtures)) {
      throw new Error('A tesztfiók azonosítója eltér a feltöltési nyugtában tárolttól.');
    }
    const ownFixtures = fixtures.filter(item => item.owner === account.key);
    if (receipt.complete && ownFixtures.every(fixture => receipt.fixtures[fixture.key])) continue;
    const entities = (await request('/api/me/entities', {token})).data;
    if (!Array.isArray(entities?.properties) || !Array.isArray(entities?.searchRequests)) {
      throw new Error('A teszt API nem adott érvényes saját ingatlan- és kereséslistát.');
    }
    for (const fixture of ownFixtures) {
      // Saved IDs remain authoritative even after the tester renames/archives
      // an entity. Never rebuild an already acknowledged fixture on a rerun.
      if (receipt.fixtures[fixture.key]) continue;
      const own = fixture.kind === 'property' ? entities.properties : entities.searchRequests;
      let entity = own.find(item => item.title === fixture.input.title);
      if (!entity) {
        entity = (await request(fixture.kind === 'property' ? '/api/properties' : '/api/searches', {
          token, method: 'POST', body: fixture.input, accepted: [200, 201]
        })).data;
        if (fixture.kind === 'property') result.createdProperties++;
        else result.createdSearches++;
      }
      if (typeof entity?.id !== 'string' || !entity.id) throw new Error('A teszt API nem adott érvényes entitásazonosítót.');
      receipt.fixtures[fixture.key] = entity.id;
      await saveState(state);
    }
    if (!receipt.credited) {
      // The ledger also protects a retry if the first top-up succeeded but its
      // response or local receipt write was interrupted.
      const ledger = (await request('/api/credits/ledger', {token})).data;
      if (!Array.isArray(ledger)) throw new Error('A teszt API nem adott érvényes kreditnaplót.');
      if (!ledger.some(entry => entry.amount > 0)) {
        await request('/api/credits/demo-topup', {token, method: 'POST', body: {amount: 100}});
      }
      receipt.credited = true;
      await saveState(state);
    }
    if (!receipt.activated) {
      if (!entities.active) await request('/api/me/active', {token, method: 'PUT', body: {
        kind: account.active.kind, id: receipt.fixtures[account.active.key]
      }});
      receipt.activated = true;
      await saveState(state);
    }
    receipt.complete = true;
    await saveState(state);
  }
  return result;
}

export function parseSeedArguments(args) {
  const result = {configPath: null, batch: DEFAULT_BATCH};
  const seen = new Set();
  for (let index = 0; index < args.length; index += 2) {
    const option = args[index], value = args[index + 1];
    if (!['--config', '--batch'].includes(option) || seen.has(option) || !value || value.startsWith('--')) {
      throw new Error('Használat: node scripts/gcp/seed-dev.mjs [--config FILE] [--batch NEV]');
    }
    seen.add(option);
    if (option === '--config') result.configPath = value;
    else result.batch = value;
  }
  createDemoCatalog(result.batch); // Validate before touching any file or service.
  return result;
}

async function main() {
  const options = parseSeedArguments(process.argv.slice(2));
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const config = await readDevConfig(resolve(options.configPath || `${root}/.local/gcp/dev-config.json`));
  const directory = resolve(root, '.local/gcp');
  await mkdir(directory, {recursive: true, mode: 0o700});
  const lock = `${directory}/seed-dev.lock`;
  try { await mkdir(lock, {mode: 0o700}); }
  catch (error) {
    if (error.code === 'EEXIST') throw new Error('Már fut tesztadat-feltöltés ebben a munkamásolatban (seed-dev.lock).');
    throw error;
  }
  const receiptPath = `${directory}/demo-seed-${config.siteId}.json`;
  try {
    let state = {};
    try { state = JSON.parse(await readFile(receiptPath, 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw new Error('A privát feltöltési nyugta nem olvasható.'); }
    const saveState = async value => {
      const temporary = `${receiptPath}.${process.pid}.tmp`;
      await writeFile(temporary, JSON.stringify(value, null, 2) + '\n', {mode: 0o600});
      await rename(temporary, receiptPath);
    };
    const result = await seedTestData({config, batch: options.batch, state, saveState,
      onWait: async ({milliseconds}) => console.log(`Belépési korlát: ${Math.ceil(milliseconds / 1000)} másodperc várakozás, majd a feltöltés folytatódik.`)
    });
    console.log(`Tesztadatok: ${result.createdUsers} új fiók, ${result.createdProperties} új ingatlan, ${result.createdSearches} új keresés.`);
    for (const warning of result.warnings) console.log(warning);
    console.log(`Tesztoldal: https://${config.siteId}.web.app/`);
  } finally { await rm(lock, {recursive: true, force: true}); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(`ERROR: ${error.message}`); process.exitCode = 1; });
}
