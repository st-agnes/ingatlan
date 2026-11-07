// Exercise the test data importer through the real disposable CI API/MySQL.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {seedTestData} from '../scripts/gcp/seed-dev.mjs';
import {DEMO_USERS, DEMO_FIXTURES} from '../scripts/gcp/demo-data.mjs';

const base = new URL(process.argv[2] || 'http://127.0.0.1:3000');
if (base.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)
    || base.pathname !== '/' || base.search || base.hash || base.username || base.password) {
  throw new Error('Seed integration smoke accepts only a plain loopback HTTP origin.');
}
const config = {
  projectId: 'ingatlan-513620', projectNumber: '120611818277', region: 'europe-west1',
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  connectionName: 'ingatlan-513620:europe-west1:otthonra-mysql-dev',
  databaseName: 'otthonra_dev', databaseUser: 'otthonra_dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev', siteId: 'otthonra-dev-120611818277',
  runtimeServiceAccount: 'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  deployServiceAccount: 'otthonra-deploy-dev@ingatlan-513620.iam.gserviceaccount.com',
  workloadIdentityProvider: 'projects/120611818277/locations/global/workloadIdentityPools/otthonra-dev/providers/github'
};
const virtualOrigin = `https://${config.siteId}.web.app`;
const suffix = randomUUID().replaceAll('-', '');
const aliases = new Map(DEMO_USERS.map(user => [user.email, user.email.replace('@', `+seed-${suffix}@`)]));
const sessions = new Map();
const healthResponse = await fetch(new URL('/api/health', base), {signal: AbortSignal.timeout(20000)});
assert.equal(healthResponse.status, 200);
const health = await healthResponse.json();
assert.equal(health.status, 'ready');
assert.equal(health.deployment, 'test', 'Start the disposable API with Deployment__Environment=test.');
assert.equal(health.testCreditsEnabled, true);

// Only the static hosted config is supplied by this harness. Every API call,
// including test-environment verification, reaches the actual .NET process.
const fetchImpl = async (input, options = {}) => {
  const url = new URL(input);
  assert.equal(url.origin, virtualOrigin);
  if (url.pathname === '/runtime-config.js') {
    return new Response('globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});', {
      status: 200, headers: {'Content-Type': 'text/javascript'}
    });
  }
  assert.ok(url.pathname.startsWith('/api/'));
  let accountEmail;
  if (url.pathname === '/api/auth/login' || url.pathname === '/api/auth/register') {
    const body = JSON.parse(options.body);
    accountEmail = body.email;
    assert.ok(aliases.has(accountEmail));
    body.email = aliases.get(accountEmail);
    options = {...options, body: JSON.stringify(body)};
  }
  const response = await fetch(new URL(url.pathname + url.search, base), options);
  const text = await response.text();
  if (accountEmail && response.ok) sessions.set(accountEmail, JSON.parse(text));
  // Native fetch exposes the local transport URL. Return the same HTTP result
  // without that URL, so the importer's redirect guard sees its virtual origin.
  return new Response(response.status === 204 ? null : text, {status: response.status, headers: response.headers});
};
let state = {};
let writes = 0;
const saveState = async value => { state = structuredClone(value); writes++; };
const first = await seedTestData({config, fetchImpl, state, saveState});
assert.equal(first.createdUsers, DEMO_USERS.length);
assert.equal(first.createdProperties, DEMO_FIXTURES.filter(item => item.kind === 'property').length);
assert.equal(first.createdSearches, DEMO_FIXTURES.filter(item => item.kind === 'search').length);
assert.equal(first.warnings.length, 0);
assert.ok(writes > 0);
const tokenFor = key => sessions.get(DEMO_USERS.find(user => user.key === key).email).accessToken;
const receiptFor = key => state.accounts[DEMO_USERS.find(user => user.key === key).email];
async function api(key, path, method = 'GET', body) {
  const response = await fetch(new URL('/api' + path, base), {
    method, redirect: 'error', signal: AbortSignal.timeout(20000),
    headers: {Authorization: `Bearer ${tokenFor(key)}`, ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})
  });
  assert.ok(response.ok, `${method} ${path}: HTTP ${response.status}`);
  return response.status === 204 ? null : response.json();
}
const initialFeeds = new Map();
const newOwnerIds = new Set(DEMO_USERS.filter(user => !['anna', 'peter', 'eszter'].includes(user.key)).map(user => receiptFor(user.key).id));
for (const user of DEMO_USERS) {
  const [profile, entities, feed] = await Promise.all([api(user.key, '/me'), api(user.key, '/me/entities'), api(user.key, '/feed')]);
  const accountType = user.accountType ?? 'private';
  assert.equal(profile.accountType, accountType, `${user.key} has the wrong registration type`);
  assert.equal(profile.credits, 100);
  for (const entity of [...entities.properties, ...entities.searchRequests]) {
    assert.equal(entity.ownerAccountType, accountType, 'Own entity badges must use the registered account type');
  }
  assert.equal(entities.properties.length, DEMO_FIXTURES.filter(item => item.owner === user.key && item.kind === 'property').length);
  assert.equal(entities.searchRequests.length, DEMO_FIXTURES.filter(item => item.owner === user.key && item.kind === 'search').length);
  assert.deepEqual(entities.active, {kind: user.active.kind, id: receiptFor(user.key).fixtures[user.active.key]});
  assert.ok(feed.items.length > 0, `${user.key} has no compatible initial recommendation`);
  assert.equal(feed.likeCost, user.active.kind === 'property' ? 2 : accountType === 'agent' ? 1 : 0);
  if(accountType==='agent'){
    const counterpart=item=>user.active.kind==='property'?item.searchRequest:item.property;
    assert.ok(feed.items.every(item=>counterpart(item).ownerAccountType==='private'),'Agents must not receive other agent listings or searches');
  }
  initialFeeds.set(user.key, feed);
}
// Refill existing testers through new counterpart entities; old decisions stay untouched.
for (const key of ['anna', 'peter', 'eszter']) {
  const ownerKind = DEMO_USERS.find(user => user.key === key).active.kind;
  const fresh = initialFeeds.get(key).items.map(item => ownerKind === 'search' ? item.property : item.searchRequest)
    .filter(entity => newOwnerIds.has(entity.ownerId));
  assert.ok(fresh.length >= 30, `${key} has only ${fresh.length} fresh counterpart recommendations`);
  assert.ok(fresh.some(entity => entity.ownerAccountType === 'agent'), `${key} cannot see an agent example`);
  assert.ok(fresh.some(entity => entity.ownerAccountType === 'private'), `${key} cannot see a private example`);
}
const pair = {propertyId: receiptFor('peter').fixtures['peter-pozsonyi'], searchRequestId: receiptFor('anna').fixtures['anna-budapest'], liked: true};
assert.equal((await api('anna', '/decisions', 'POST', pair)).charged, 0);
const match = await api('peter', '/decisions', 'POST', pair);
assert.equal(match.charged, 2);
assert.equal(match.credits, 98);
assert.ok(match.matchId);
await api('anna', `/matches/${match.matchId}/messages`, 'POST', {text: 'CI tesztüzenet: a mintapárosítás üzenetküldése működik.'});
assert.ok((await api('peter', '/matches')).some(item => item.id === match.matchId && item.messages.length === 1));
// New agent accounts start with an active search and usable paid-like examples.
const agent = DEMO_USERS.find(user => user.accountType === 'agent');
assert.ok(agent, 'The hosted catalog must contain an agent account');
assert.equal(agent.active.kind, 'search');
const agentPair = {propertyId: pair.propertyId, searchRequestId: receiptFor(agent.key).fixtures[agent.active.key], liked: true};
const agentLike = await api(agent.key, '/decisions', 'POST', agentPair);
assert.equal(agentLike.charged, 1);
assert.equal(agentLike.credits, 99);
assert.equal((await api(agent.key, '/decisions', 'POST', agentPair)).charged, 0, 'Retrying an agent like must not charge again');
const agentLedger = await api(agent.key, '/credits/ledger');
assert.equal(agentLedger.filter(entry => entry.amount < 0).length, 1);
assert.equal(agentLedger.find(entry => entry.amount < 0).amount, -1);
const agentMatch = await api('peter', '/decisions', 'POST', agentPair);
assert.equal(agentMatch.charged, 2);
assert.equal(agentMatch.credits, 96);
assert.ok(agentMatch.matchId);
const sellerMatch = (await api('peter', '/matches')).find(item => item.id === agentMatch.matchId);
assert.equal(sellerMatch.property.ownerAccountType, 'private');
assert.equal(sellerMatch.searchRequest.ownerAccountType, 'agent');
assert.equal(sellerMatch.contact.accountType, 'agent');
const editable = DEMO_FIXTURES.find(item => item.key === 'anna-solymar-house');
await api('anna', `/properties/${receiptFor('anna').fixtures[editable.key]}`, 'PUT', {...editable.input, title: 'CI-ben átnevezett és archivált minta', archived: true});
await api('anna', '/me/active', 'PUT', {kind: 'search', id: receiptFor('anna').fixtures['anna-debrecen']});
await api('peter', '/me/active', 'PUT', {kind: 'property', id: receiptFor('peter').fixtures['peter-rozsadomb']});
const snapshot = async () => Promise.all(DEMO_USERS.map(async user => ({
  key: user.key, profile: await api(user.key, '/me'), entities: await api(user.key, '/me/entities'),
  ledger: await api(user.key, '/credits/ledger'), matches: await api(user.key, '/matches')
})));
const before = await snapshot();
const second = await seedTestData({config, fetchImpl, state, saveState});
assert.deepEqual([second.createdUsers, second.createdProperties, second.createdSearches], [0, 0, 0]);
assert.equal(second.existingUsers, DEMO_USERS.length);
assert.equal(second.warnings.length, 0);
assert.deepEqual(await snapshot(), before, 'Rerun changed credits, entities, active selections, decisions, matches or messages.');
console.log(`Test seeding integration passed: ${DEMO_USERS.length} users (${DEMO_USERS.filter(user => user.accountType === 'agent').length} agents), ${first.createdProperties} properties, ${first.createdSearches} searches; existing testers each receive at least 30 fresh mixed-owner recommendations; private/agent/seller billing and messaging work; rerun preserves edits, archives, balances and activity.`);
