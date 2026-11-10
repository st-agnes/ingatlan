import test from 'node:test';
import assert from 'node:assert/strict';
import {seedTestData, parseSeedArguments} from '../scripts/gcp/seed-dev.mjs';
import {DEMO_USERS, DEFAULT_BATCH, createDemoCatalog} from '../scripts/gcp/demo-data.mjs';

const config = Object.freeze({
  projectId: 'ingatlan-513620', projectNumber: '123456789012', region: 'europe-west1',
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  connectionName: 'ingatlan-513620:europe-west1:otthonra-mysql-dev', databaseName: 'otthonra_dev', databaseUser: 'otthonra_dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev', siteId: 'otthonra-dev-123456789012',
  runtimeServiceAccount: 'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  deployServiceAccount: 'otthonra-deploy-dev@ingatlan-513620.iam.gserviceaccount.com',
  workloadIdentityProvider: 'projects/123456789012/locations/global/workloadIdentityPools/otthonra-dev/providers/github'
});
const runtime = 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});';
const health = {status: 'ready', deployment: 'test', testCreditsEnabled: true};
const password = 'OtthonraDemo2026!';
const initialState = () => ({version: 1, projectId: config.projectId, siteId: config.siteId, accounts: {}});
function fastClock() {
  let time = 0;
  const waits = [];
  return {now: () => time, wait: async milliseconds => {waits.push(milliseconds); time += milliseconds;}, waits};
}
const runSeed = options => seedTestData({...fastClock(), ...options});
const writes = calls => calls.filter(call => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(call.method)
  && call.path !== '/api/auth/login');

function server() {
  let nextId = 1;
  const id = () => `00000000-0000-4000-8000-${String(nextId++).padStart(12, '0')}`;
  const users = new Map(), calls = [];
  const options = {health, runtime, failAtCreate: 0, createdEntities: 0, profileAccountTypes: true};
  function addUser(email, extra = {}) {
    const user = {id: id(), email, name: 'Existing tester', phone: '', password, credits: 0, accountType: 'private',
      activeKind: null, activeEntityId: null, properties: [], searches: [], ledger: [], ...extra};
    users.set(email, user);
    return user;
  }
  const profile = user => ({id: user.id, email: user.email, name: user.name, phone: user.phone,
    credits: user.credits, activeKind: user.activeKind, activeEntityId: user.activeEntityId,
    ...(options.profileAccountTypes ? {accountType: user.accountType} : {})});
  const session = user => ({accessToken: `private-test-token:${user.email}`, expiresIn: 43200, user: profile(user)});
  const json = (body, status = 200) => Response.json(body, {status});
  async function fetchImpl(url, init = {}) {
    url = new URL(url);
    assert.equal(url.origin, `https://${config.siteId}.web.app`, 'All seed calls must target the validated test Hosting origin');
    const method = init.method ?? 'GET';
    const body = init.body ? JSON.parse(init.body) : undefined;
    calls.push({path: url.pathname, method, body, redirect: init.redirect});
    if (url.pathname === '/api/health') {
      return options.healthResponse?.() ?? json(options.health);
    }
    if (url.pathname === '/runtime-config.js') return new Response(options.runtime);
    if (url.pathname === '/api/auth/login') {
      const user = users.get(body.email);
      return user && user.password === body.password ? json(session(user)) : json({message: 'Invalid credentials'}, 401);
    }
    if (url.pathname === '/api/auth/register') {
      if (users.has(body.email)) return json({message: 'Already registered'}, 409);
      return json(session(addUser(body.email, {name: body.name, phone: body.phone ?? '', password: body.password, accountType: body.accountType ?? 'private'})));
    }
    const token = new Headers(init.headers).get('Authorization');
    const user = [...users.values()].find(user => token === `Bearer private-test-token:${user.email}`);
    if (!user) return json({message: 'Unauthorized'}, 401);
    if (url.pathname === '/api/me' && method === 'GET') return json(profile(user));
    if (url.pathname === '/api/me/entities' && method === 'GET') {
      return json({properties: user.properties.filter(value => !value.archived),
        searchRequests: user.searches.filter(value => !value.archived), decisions: [],
        active: user.activeKind ? {kind: user.activeKind, id: user.activeEntityId} : null});
    }
    if ((url.pathname === '/api/properties' || url.pathname === '/api/searches') && method === 'GET') {
      return json((url.pathname === '/api/properties' ? user.properties : user.searches).filter(value => !value.archived));
    }
    if ((url.pathname === '/api/properties' || url.pathname === '/api/searches') && method === 'POST') {
      options.createdEntities++;
      if (options.failAtCreate === options.createdEntities) return json({message: 'Temporary interruption'}, 503);
      const entity = {...body, id: id(), ownerId: user.id, archived: false};
      (url.pathname === '/api/properties' ? user.properties : user.searches).push(entity);
      return json(entity, 201);
    }
    if (url.pathname === '/api/credits/ledger' && method === 'GET') return json(user.ledger);
    if (url.pathname === '/api/credits/demo-topup' && method === 'POST') {
      assert.equal(body.amount, 100);
      user.credits += body.amount;
      user.ledger.push({id: id(), amount: body.amount, description: 'Test seed credits'});
      return json({credits: user.credits});
    }
    if (url.pathname === '/api/me/active' && method === 'PUT') {
      const entities = body.kind === 'property' ? user.properties : user.searches;
      assert.ok(entities.some(entity => entity.id === body.id && !entity.archived), 'Active seed entity must belong to its user');
      user.activeKind = body.kind;
      user.activeEntityId = body.id;
      return json(body);
    }
    throw new Error(`Unexpected test request: ${method} ${url.pathname}`);
  }
  return {users, calls, options, addUser, fetchImpl};
}

function counts(mock) {
  const users = [...mock.users.values()];
  return {createdUsers: users.length,
    createdProperties: users.reduce((sum, user) => sum + user.properties.length, 0),
    createdSearches: users.reduce((sum, user) => sum + user.searches.length, 0)};
}

test('fresh test installation receives ready accounts, properties, searches and credits only after test checks', async () => {
  const mock = server(), state = initialState(), saves = [];
  const result = await runSeed({config, fetchImpl: mock.fetchImpl, state,
    saveState: async value => saves.push(JSON.stringify(value))});
  assert.ok(result.createdUsers >= 3);
  assert.ok(result.createdProperties >= 3);
  assert.ok(result.createdSearches >= 3);
  const actual = counts(mock);
  for (const key of Object.keys(actual)) assert.equal(result[key], actual[key]);
  const firstWrite = mock.calls.findIndex(call => call.method === 'POST');
  const healthIndex = mock.calls.findIndex(call => call.path === '/api/health');
  const runtimeIndex = mock.calls.findIndex(call => call.path === '/runtime-config.js');
  assert.ok(healthIndex >= 0 && healthIndex < firstWrite);
  assert.ok(runtimeIndex >= 0 && runtimeIndex < firstWrite);
  assert.ok(saves.length > result.createdUsers);
  assert.doesNotMatch(JSON.stringify(state), /private-test-token|accessToken|OtthonraDemo2026!/);
  for (const user of mock.users.values()) {
    assert.equal(user.credits, 100);
    assert.ok(user.activeEntityId);
    assert.equal(state.accounts[user.email].id, user.id);
    assert.equal(state.accounts[user.email].complete, true);
    assert.equal(state.accounts[user.email].credited, true);
    assert.equal(state.accounts[user.email].activated, true);
  }
});

test('repeat seed preserves archived and renamed fixtures, manual data, balances and active selections', async () => {
  const mock = server(), state = initialState();
  await runSeed({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}});
  for (const user of mock.users.values()) {
    user.name = 'Manually edited test profile';
    user.credits = 7;
    if (user.properties.length) user.properties[0].archived = true;
    if (user.searches.length) user.searches[0].title = 'My edited search';
    const manual = {id: `manual:${user.email}`, ownerId: user.id, title: 'Manually created property', archived: false};
    user.properties.push(manual);
    user.activeKind = 'property'; user.activeEntityId = manual.id;
  }
  const before = JSON.stringify([...mock.users]);
  mock.calls.length = 0;
  const result = await runSeed({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}});
  assert.equal(result.createdUsers, 0);
  assert.equal(result.createdProperties, 0);
  assert.equal(result.createdSearches, 0);
  assert.equal(JSON.stringify([...mock.users]), before);
  assert.deepEqual(writes(mock.calls), []);
});

test('existing account without a seed receipt keeps all its manual data and receives no automatic writes', async () => {
  const mock = server(), state = initialState();
  const existing = mock.addUser('anna@otthonra.local', {credits: 13, name: 'My existing account', activeKind: 'search', activeEntityId: 'my-search',
    searches: [{id: 'my-search', title: 'My own search', archived: false}]});
  const before = JSON.stringify(existing);
  const result = await runSeed({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}});
  assert.equal(JSON.stringify(existing), before);
  assert.ok(result.existingUsers >= 1);
  assert.ok(result.warnings.length > 0);
  assert.ok(mock.users.size >= 3, 'Other missing demo accounts should still be created');
  assert.ok(!state.accounts[existing.email]?.complete, 'Existing account must not be adopted as a managed fixture account');
});

test('a conflicting account with a different password stops without changing credentials or exposing tokens', async () => {
  const mock = server(), state = initialState();
  mock.addUser('anna@otthonra.local', {password: 'different-private-password', credits: 19});
  const before = JSON.stringify([...mock.users]);
  await assert.rejects(seedTestData({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}}), error => {
    assert.doesNotMatch(error.message, /OtthonraDemo2026!|different-private-password|private-test-token/);
    return true;
  });
  assert.equal(JSON.stringify([...mock.users]), before);
  assert.ok(writes(mock.calls).every(call => call.path === '/api/auth/login' || call.path === '/api/auth/register'));
});

test('a managed account whose email or password changed is never registered again on a later seed', async () => {
  for (const change of ['password', 'email']) {
    const mock = server(), state = initialState();
    await runSeed({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}});
    const user = mock.users.get('anna@otthonra.local');
    assert.equal(state.accounts[user.email].complete, true);
    if (change === 'password') user.password = 'changed-private-password';
    else {
      mock.users.delete(user.email);
      user.email = 'my-changed-address@example.test';
      mock.users.set(user.email, user);
    }
    const before = JSON.stringify([...mock.users]);
    const receipt = JSON.stringify(state);
    mock.calls.length = 0;
    await assert.rejects(seedTestData({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}}), error => {
      assert.match(error.message, /anna@otthonra\.local/);
      assert.doesNotMatch(error.message, /OtthonraDemo2026!|changed-private-password|private-test-token/);
      return true;
    });
    assert.equal(JSON.stringify([...mock.users]), before);
    assert.equal(JSON.stringify(state), receipt);
    assert.deepEqual(writes(mock.calls), [], 'A completed managed account must not trigger registration or any data change');
    assert.equal(mock.users.size, DEMO_USERS.length);
  }
});

test('registration race adopts no existing account and preserves its data after a successful login', async () => {
  const mock = server(), state = initialState();
  let racedUser, racedSnapshot;
  const fetchImpl = async (url, init = {}) => {
    const path = new URL(url).pathname;
    if (path === '/api/auth/register' && JSON.parse(init.body).email === 'anna@otthonra.local' && !racedUser) {
      racedUser = mock.addUser('anna@otthonra.local', {name: 'Created concurrently', credits: 17,
        properties: [{id: 'concurrent-property', title: 'Concurrent user property', archived: false}]});
      racedSnapshot = JSON.stringify(racedUser);
    }
    return mock.fetchImpl(url, init);
  };
  const result = await runSeed({config, fetchImpl, state, saveState: async () => {}});
  assert.ok(result.existingUsers >= 1);
  assert.ok(result.warnings.length > 0);
  assert.equal(JSON.stringify(racedUser), racedSnapshot);
  assert.equal(state.accounts['anna@otthonra.local'], undefined);
});

test('production, unavailable database, missing test capability and local demo are rejected before authentication', async () => {
  for (const change of [
    {health: {...health, deployment: 'production'}},
    {health: {...health, status: 'database-unavailable'}},
    {health: {...health, testCreditsEnabled: false}},
    {runtime: 'globalThis.OTTHONRA_CONFIG={mode:"demo",environment:"test"};'},
    {runtime: 'globalThis.OTTHONRA_CONFIG={mode:"api",environment:"production"};'}
  ]) {
    const mock = server(); Object.assign(mock.options, change);
    await assert.rejects(seedTestData({config, fetchImpl: mock.fetchImpl, state: initialState(), saveState: async () => {}}));
    assert.deepEqual(writes(mock.calls), []);
    assert.ok(mock.calls.every(call => !call.path.startsWith('/api/auth/')), 'No authentication may precede the test checks');
    assert.equal(mock.users.size, 0);
  }
});

test('a redirect cannot send demo credentials to another origin', async () => {
  const mock = server();
  mock.options.healthResponse = () => new Response(null, {status: 302, headers: {Location: 'https://another-origin.example/api/health'}});
  await assert.rejects(seedTestData({config, fetchImpl: mock.fetchImpl, state: initialState(), saveState: async () => {}}));
  assert.deepEqual(writes(mock.calls), []);
  assert.ok(mock.calls.every(call => ['error', 'manual'].includes(call.redirect)), 'Fetch must not follow redirects');
});

test('an interrupted seed resumes from saved entity IDs without duplicating completed work', async () => {
  const mock = server(), state = initialState();
  mock.options.failAtCreate = 2;
  await assert.rejects(seedTestData({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}}));
  const savedEntities = [...mock.users.values()].flatMap(user => [...user.properties, ...user.searches]).map(entity => entity.id);
  assert.equal(savedEntities.length, 1);
  assert.ok(Object.values(state.accounts).some(account => Object.keys(account.fixtures).length));
  mock.options.failAtCreate = 0;
  await runSeed({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}});
  const allEntities = [...mock.users.values()].flatMap(user => [...user.properties, ...user.searches]);
  assert.ok(savedEntities.every(id => allEntities.some(entity => entity.id === id)));
  for (const user of mock.users.values()) {
    assert.equal(new Set(user.properties.map(entity => entity.title)).size, user.properties.length);
    assert.equal(new Set(user.searches.map(entity => entity.title)).size, user.searches.length);
  }
  mock.calls.length = 0;
  await runSeed({config, fetchImpl: mock.fetchImpl, state, saveState: async () => {}});
  assert.deepEqual(writes(mock.calls), []);
});

test('a topup committed before receipt persistence is detected in the ledger and never granted twice', async () => {
  const mock = server(), state = initialState();
  let stored = JSON.stringify(state), interrupted = false;
  await assert.rejects(seedTestData({config, fetchImpl: mock.fetchImpl, state, saveState: async next => {
    if (!interrupted && Object.values(next.accounts).some(account => account.credited)) {
      interrupted = true;
      throw new Error('Interrupted receipt persistence');
    }
    stored = JSON.stringify(next);
  }}));
  assert.equal(interrupted, true);
  const resumedState = JSON.parse(stored);
  await runSeed({config, fetchImpl: mock.fetchImpl, state: resumedState, saveState: async next => {stored = JSON.stringify(next);}});
  for (const user of mock.users.values()) {
    assert.equal(user.credits, 100);
    assert.equal(user.ledger.filter(entry => entry.amount > 0).length, 1);
  }
});


test('new accounts register once with their catalog type and use a paced authentication window', async () => {
  const mock = server(), clock = fastClock();
  const result = await seedTestData({config, fetchImpl: mock.fetchImpl, state: initialState(), ...clock});
  assert.equal(result.createdUsers, DEMO_USERS.length);
  const auth = mock.calls.filter(call => call.path.startsWith('/api/auth/'));
  assert.equal(auth.length, DEMO_USERS.length, 'Fresh accounts must not issue failed logins before registration');
  assert.ok(auth.every(call => call.path === '/api/auth/register'));
  assert.deepEqual(clock.waits, [61000]);
  assert.equal([...mock.users.values()].filter(user => user.accountType === 'agent').length, 3);
  for (const account of DEMO_USERS) assert.equal(mock.users.get(account.email).accountType, account.accountType ?? 'private');
});

test('a server without account types fails before creating fixtures or registering an agent', async () => {
  const mock = server();mock.options.profileAccountTypes = false;
  await assert.rejects(runSeed({config, fetchImpl: mock.fetchImpl, state: initialState()}), /fióktípusa eltér/);
  assert.equal(mock.options.createdEntities, 0);
  assert.ok(!mock.calls.some(call => call.path === '/api/auth/register' && call.body.accountType === 'agent'));
});

test('an existing account with the wrong declared type is not silently adopted or changed', async () => {
  const mock = server(), catalog = createDemoCatalog();
  const agent = catalog.users.find(user => user.accountType === 'agent');
  const existing = mock.addUser(agent.email, {accountType: 'private', credits: 17});
  const before = JSON.stringify(existing);
  await assert.rejects(runSeed({config, fetchImpl: mock.fetchImpl, state: initialState()}), /fióktípusa eltér/);
  assert.equal(JSON.stringify(existing), before);
});

test('auth rate limits honor Retry-After and retry without duplicate fixture work', async () => {
  const mock = server(), clock = fastClock();
  let rejected = false;
  const fetchImpl = async (url, init) => {
    if (!rejected && new URL(url).pathname.startsWith('/api/auth/')) {
      rejected = true;
      return new Response('', {status: 429, headers: {'Retry-After': '2'}});
    }
    return mock.fetchImpl(url, init);
  };
  const result = await seedTestData({config, fetchImpl, state: initialState(), ...clock});
  assert.equal(result.createdUsers, DEMO_USERS.length);
  assert.equal(clock.waits[0], 2000);
  for (const user of mock.users.values()) assert.equal(user.ledger.length, 1);
});

test('persistent auth throttling stops after bounded retries without changing any account', async () => {
  const mock = server(), clock = fastClock();let attempts = 0;
  const fetchImpl = async (url, init) => {
    if (new URL(url).pathname.startsWith('/api/auth/')) {attempts++;return new Response('', {status: 429});}
    return mock.fetchImpl(url, init);
  };
  await assert.rejects(seedTestData({config, fetchImpl, state: initialState(), ...clock}), /korlátja továbbra is aktív/);
  assert.equal(attempts, 3);assert.deepEqual(clock.waits, [61000, 61000]);assert.equal(mock.users.size, 0);
});

test('an explicitly named batch adds new identities once and preserves all previous accounts', async () => {
  const mock = server(), state = initialState();
  await runSeed({config, fetchImpl: mock.fetchImpl, state});
  const before = JSON.stringify([...mock.users]);
  const result = await runSeed({config, fetchImpl: mock.fetchImpl, state, batch: 'november-1'});
  assert.equal(result.createdUsers, DEMO_USERS.length - 3);
  const newOwners = new Set(createDemoCatalog('november-1').users.slice(3).map(user => user.key));
  const added = createDemoCatalog('november-1').fixtures.filter(fixture => newOwners.has(fixture.owner));
  assert.equal(result.createdProperties, added.filter(fixture => fixture.kind === 'property').length);
  assert.equal(result.createdSearches, added.filter(fixture => fixture.kind === 'search').length);
  assert.equal(JSON.stringify([...mock.users].slice(0, DEMO_USERS.length)), before);
  const complete = JSON.stringify([...mock.users]);
  const again = await runSeed({config, fetchImpl: mock.fetchImpl, state, batch: 'november-1'});
  assert.equal(again.createdUsers, 0);assert.equal(again.createdProperties, 0);assert.equal(again.createdSearches, 0);
  assert.equal(JSON.stringify([...mock.users]), complete);
});

test('CLI accepts config and batch in either order and rejects missing, duplicate or unsafe options', () => {
  assert.deepEqual(parseSeedArguments([]), {configPath: null, batch: DEFAULT_BATCH});
  for (const args of [['--config', 'manifest.json', '--batch', 'november-1'], ['--batch', 'november-1', '--config', 'manifest.json']]) {
    assert.deepEqual(parseSeedArguments(args), {configPath: 'manifest.json', batch: 'november-1'});
  }
  for (const args of [['--batch'], ['--config'], ['--batch', '--config'], ['--other', 'x'], ['--batch', 'one', '--batch', 'two'], ['--batch', '../outside'], ['--batch', 'UpperCase']]) {
    assert.throws(() => parseSeedArguments(args));
  }
});
