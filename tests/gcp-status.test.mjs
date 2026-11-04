import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectDeployment} from '../scripts/gcp/status-dev.mjs';

const config = {
  projectId: 'ingatlan-513620', projectNumber: '123456789012', region: 'europe-west1',
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  connectionName: 'ingatlan-513620:europe-west1:otthonra-mysql-dev', databaseName: 'otthonra_dev', databaseUser: 'otthonra_dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev', siteId: 'otthonra-dev-123456789012',
  runtimeServiceAccount: 'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  deployServiceAccount: 'otthonra-deploy-dev@ingatlan-513620.iam.gserviceaccount.com',
  workloadIdentityProvider: 'projects/123456789012/locations/global/workloadIdentityPools/otthonra-dev/providers/github'
};
const api = 'https://otthonra-api-dev-example-ew.a.run.app';
const describeService = async () => ({status: {url: api}});
const health = {status: 200, text: JSON.stringify({status: 'ready', deployment: 'test', testCreditsEnabled: true})};
const runtime = {status: 200, text: 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});'};
const fetchResponse = async url => url.endsWith('/runtime-config.js') ? runtime : health;

test('only a real test backend, database and hosted API configuration establish success', async () => {
  const calls = [];
  const result = await inspectDeployment({config, describeService, fetchResponse: async url => {calls.push(url);return fetchResponse(url);}});
  assert.equal(result.ready, true);assert.equal(result.backend, true);assert.equal(result.web, true);
  assert.equal(calls.length, 3);assert.ok(calls.every(url => new URL(url).protocol === 'https:'));
  assert.equal(result.url, 'https://otthonra-dev-123456789012.web.app');
});

test('a Cloud Run hello placeholder cannot count as a deployed application', async () => {
  const result = await inspectDeployment({config, describeService, fetchResponse: async url => url.startsWith(api)
    ? {status: 200, text: '<html>Hello from Cloud Run</html>'} : fetchResponse(url)});
  assert.equal(result.backend, false);assert.equal(result.ready, false);
});

test('a static demo or incorrect server capabilities never establish hosted test readiness', async () => {
  for (const replacement of [
    {status: 200, text: 'globalThis.OTTHONRA_CONFIG = {mode: "demo", environment: "local"};'},
    {status: 404, text: 'not found'}
  ]) {
    const result = await inspectDeployment({config, describeService, fetchResponse: async url => url.endsWith('/runtime-config.js') ? replacement : health});
    assert.equal(result.backend, true);assert.equal(result.web, false);assert.equal(result.ready, false);
  }
  for (const value of [{status: 'database-unavailable', deployment: 'test', testCreditsEnabled: true},
    {status: 'ready', deployment: 'production', testCreditsEnabled: false},
    {status: 'ready', deployment: 'test', testCreditsEnabled: false}]) {
    const result = await inspectDeployment({config, describeService, fetchResponse: async url => url.endsWith('/runtime-config.js') ? runtime : {status: 200, text: JSON.stringify(value)}});
    assert.equal(result.ready, false);assert.equal(result.web, false);assert.equal(result.backend, false);
  }
});

test('cloud and network failures remain inconclusive and do not print full SDK help', async () => {
  const result = await inspectDeployment({config,
    describeService: async () => {throw Object.assign(new Error('do not display stack'), {stderr: 'ERROR: service not found\nUsage: gcloud help\nToken: not-for-output'});},
    fetchResponse: async () => {throw new Error('network failure');}});
  assert.equal(result.ready, false);assert.equal(result.backend, false);assert.equal(result.web, false);
  assert.equal(result.detail, 'ERROR: service not found');assert.doesNotMatch(result.detail, /help|Token|stack/);
});
