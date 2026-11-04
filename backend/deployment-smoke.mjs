/** Non-mutating deployment probe: public health and anonymous authorization checks. */
import assert from 'node:assert/strict';

const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000').origin;
const expected = process.argv[3] || 'test';
assert.ok(['test', 'production'].includes(expected), 'Expected deployment must be test or production');

async function request(path, options = {}) {
  return fetch(new URL(path, origin), {signal: AbortSignal.timeout(30000), redirect: 'error', ...options});
}

const healthResponse = await request('/api/health');
assert.equal(healthResponse.status, 200, 'Deployment health must be available');
assert.match(healthResponse.headers.get('content-type') || '', /application\/json/i);
const health = await healthResponse.json();
assert.equal(health.status, 'ready', 'The deployment must connect to its database');
assert.equal(health.deployment, expected, 'The server must identify the expected deployment');
assert.equal(health.testCreditsEnabled, expected === 'test', 'Free test credits must match the explicit test deployment');

const profile = await request('/api/me');
assert.equal(profile.status, 401, 'Personal account data must require authentication');
await profile.arrayBuffer();

const topup = await request('/api/credits/demo-topup', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({amount: 20})
});
assert.equal(topup.status, expected === 'test' ? 401 : 404,
  expected === 'test' ? 'Test credits must require authentication' : 'Ordinary Production must not expose free credit topups');
await topup.arrayBuffer();

console.log(`Deployment ${expected} probe passed: database ready, personal data protected, free-credit endpoint ${expected === 'test' ? 'authenticated' : 'absent'}.`);
