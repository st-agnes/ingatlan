/** Offline checks for Firebase REST authentication and useful, bounded errors. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp, mkdir, readFile, writeFile, rm} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const script = join(root, 'scripts/gcp/bootstrap-dev.sh');
const helper = join(root, 'scripts/gcp/bootstrap-dev.py');
const token = 'fixture-bearer-secret-42';
const project = 'ingatlan-513620';
const errorBody = {error: {code: 403, status: 'PERMISSION_DENIED', message: 'Firebase access denied.', details: [
  {'@type': 'type.googleapis.com/google.rpc.ErrorInfo', reason: 'SERVICE_DISABLED', domain: 'googleapis.com', metadata: {
    service: 'firebase.googleapis.com', consumer: 'projects/120611818277', permission: 'firebase.projects.get'
  }}
]}};

async function temporary(action) {
  const dir = await mkdtemp(join(tmpdir(), 'otthonra-firebase-'));
  try { await action(dir); } finally { await rm(dir, {recursive: true, force: true}); }
}
async function executable(path, text) { await writeFile(path, text, {mode: 0o700}); }
async function fixture(action) {
  await temporary(async dir => {
    const bin = join(dir, 'bin'); await mkdir(bin);
    const statePath = join(dir, 'requests.json'), responsePath = join(dir, 'response.json');
    await writeFile(statePath, JSON.stringify({requests: []}));
    await writeFile(responsePath, JSON.stringify(errorBody));
    await executable(join(bin, 'gcloud'), `#!/usr/bin/env node
if (process.env.TOKEN_MODE === 'fail') { console.error('Google token unavailable'); process.exit(1); }
if (process.env.TOKEN_MODE !== 'empty') process.stdout.write(${JSON.stringify(token)});
`);
    await executable(join(bin, 'sleep'), '#!/bin/sh\nexit 0\n');
    await executable(join(bin, 'curl'), `#!/usr/bin/env node
const fs = require('node:fs'), args = process.argv.slice(2);
const state = JSON.parse(fs.readFileSync(process.env.REQUEST_STATE, 'utf8'));
const configPath = args[args.indexOf('--config') + 1];
state.requests.push({args, method: args[args.indexOf('--request') + 1], url: args.at(-1), config: fs.readFileSync(configPath, 'utf8'), mode: fs.statSync(configPath).mode & 0o777});
fs.writeFileSync(process.env.REQUEST_STATE, JSON.stringify(state));
fs.copyFileSync(process.env.RESPONSE_PATH, args[args.indexOf('--output') + 1]);
const codes = process.env.HTTP_CODES.split(',');
process.stdout.write(codes[Math.min(state.requests.length - 1, codes.length - 1)]);
`);
    const source = await readFile(script, 'utf8');
    const start = source.indexOf('rest() {');
    const end = source.indexOf('code="$(rest GET "https://firebase.googleapis.com/v1beta1/projects/', start);
    assert.ok(start > 0 && end > start, 'The real bootstrap REST block must be located');
    const prelude = 'set -euo pipefail\numask 077\nhelper="$HELPER"\ntemporary="$FIREBASE_TEMP"\nproject_id=ingatlan-513620\nfield() { python3 "$helper" field "$1" "$2"; }\n' + source.slice(start, end);
    const run = async (body, overrides = {}) => {
      const program = join(dir, 'request.sh');
      await writeFile(program, prelude + '\n' + body + '\n');
      return spawnSync('bash', [program], {encoding: 'utf8', timeout: 5000, env: {
        ...process.env, PATH: bin + ':' + process.env.PATH, HELPER: helper, FIREBASE_TEMP: dir,
        REQUEST_STATE: statePath, RESPONSE_PATH: responsePath, HTTP_CODES: '403', ...overrides
      }});
    };
    await action({dir, run, source, firstRequest: end, requests: async () => JSON.parse(await readFile(statePath, 'utf8')).requests});
  });
}

test('quota attribution accompanies GET retries and POST while the bearer remains only in a private config', async () => {
  for (const [method, codes, count] of [['GET', '503,200', 2], ['GET', '403', 1], ['POST', '503', 1]]) {
    await fixture(async ({run, requests}) => {
      const result = await run(`rest ${method} https://firebase.googleapis.com/v1beta1/projects/$project_id "$temporary/result.json" ${method === 'POST' ? "'{}'" : ''}`, {HTTP_CODES: codes});
      assert.equal(result.status, 0, result.stderr);
      const calls = await requests(); assert.equal(calls.length, count);
      for (const call of calls) {
        assert.equal(call.method, method);
        assert.equal(call.mode, 0o600);
        assert.match(call.config, new RegExp('Authorization: Bearer ' + token));
        assert.match(call.config, new RegExp('X-Goog-User-Project: ' + project, 'i'));
        assert.ok(!call.args.join(' ').includes(token), 'Bearer must not enter curl process arguments');
      }
      assert.ok(!(result.stdout + result.stderr).includes(token));
      assert.equal(result.stdout.trim(), codes.split(',').at(-1));
    });
  }
});

test('failed or empty Google token retrieval stops before any HTTP request', async () => {
  for (const mode of ['fail', 'empty']) await fixture(async ({run, requests}) => {
    const result = await run('rest GET https://firebase.googleapis.com/v1beta1/projects/$project_id "$temporary/result.json"', {TOKEN_MODE: mode});
    assert.notEqual(result.status, 0);
    assert.equal((await requests()).length, 0);
    assert.ok(!(result.stdout + result.stderr).includes(token));
  });
});

test('structured errors retain actionable Google fields while secrets and unrelated data are removed', async () => {
  await temporary(async dir => {
    const path = join(dir, 'error.json'), auth = join(dir, 'curl-auth');
    const body = structuredClone(errorBody);
    body.error.message = `Access denied. Authorization: Bearer ${token}; access_token=ya29.FIXTURE_TOKEN; password=fixture-password; client_secret=fixture-client-secret.\u001b[31m\n` + 'context '.repeat(1500);
    body.private_key = 'unexpected-top-level-secret';
    body.error.details.push({'@type': 'type.googleapis.com/Unrelated', message: 'unexpected-detail-secret'});
    body.error.details[0].metadata.arbitrary = 'unexpected-metadata-secret';
    await writeFile(path, JSON.stringify(body));
    await writeFile(auth, `header = "Authorization: Bearer ${token}"\n`, {mode: 0o600});
    const result = spawnSync('python3', [helper, 'api-error', path, '403', 'Firebase project lookup', auth], {encoding: 'utf8'});
    const text = result.stdout + result.stderr;
    for (const expected of ['403', 'PERMISSION_DENIED', 'SERVICE_DISABLED', 'googleapis.com', 'firebase.googleapis.com', 'projects/120611818277', 'firebase.projects.get']) assert.ok(text.includes(expected), expected);
    for (const secret of [token, 'ya29.FIXTURE_TOKEN', 'fixture-password', 'fixture-client-secret', 'unexpected-top-level-secret', 'unexpected-detail-secret', 'unexpected-metadata-secret']) assert.ok(!text.includes(secret), secret);
    assert.ok(!text.includes('\u001b'));
    assert.ok(text.length < 4000, 'Error output must remain bounded on a small terminal');
    assert.doesNotMatch(text, /Traceback/);
  });
});

test('non-JSON or malformed error shapes do not expose raw responses', async () => {
  for (const body of ['<html>raw-response-secret</html>', 'null', '{"error":"raw-response-secret"}', '{"unexpected":"raw-response-secret"}', '{"error":{"code":{},"message":{"secret":"raw-response-secret"}}}']) {
    await temporary(async dir => {
      const path = join(dir, 'error.txt'); await writeFile(path, body);
      const result = spawnSync('python3', [helper, 'api-error', path, '403', 'Firebase project lookup'], {encoding: 'utf8'});
      const text = result.stdout + result.stderr;
      assert.match(text, /403/);
      assert.doesNotMatch(text, /raw-response-secret|Traceback/);
    });
  }
});

test('an explicit Firebase Terms of Service rejection points to the consent page', async () => {
  await temporary(async dir => {
    const path = join(dir, 'error.json');
    await writeFile(path, JSON.stringify({error: {code: 403, status: 'PERMISSION_DENIED', message: 'Firebase ToS not accepted.'}}));
    const result = spawnSync('python3', [helper, 'api-error', path, '403', 'Firebase project lookup'], {encoding: 'utf8'});
    const text = result.stdout + result.stderr;
    assert.match(text, /https:\/\/console\.firebase\.google\.com\//);
    assert.match(text, /forceCheckTos=true/);
  });
});

test('a forbidden Firebase project lookup stops without attempting addFirebase', async () => {
  await fixture(async ({run, source, firstRequest, requests}) => {
    const end = source.indexOf('code="$(rest GET "https://firebase.googleapis.com/v1beta1/projects/$project_id/webApps', firstRequest);
    assert.ok(end > firstRequest);
    const result = await run(source.slice(firstRequest, end));
    assert.notEqual(result.status, 0);
    const calls = await requests(); assert.equal(calls.length, 1);
    assert.equal(calls[0].method, 'GET');
    assert.ok(!calls.some(call => call.url.includes(':addFirebase')));
    assert.match(result.stderr, /403/);
    assert.match(result.stderr, /PERMISSION_DENIED|SERVICE_DISABLED/);
    assert.ok(!(result.stdout + result.stderr).includes(token));
  });
});
