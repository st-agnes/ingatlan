import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp, mkdir, writeFile, readFile, rm, readdir} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const script = fileURLToPath(new URL('../scripts/gcp/push-image.sh', import.meta.url));
const image = 'europe-west1-docker.pkg.dev/ingatlan-513620/otthonra-dev/otthonra-api:' + 'a'.repeat(40);
async function fixture(sequence, action) {
  const root = await mkdtemp(join(tmpdir(), 'otthonra-push-'));
  try {
    const bin = join(root, 'bin'), temp = join(root, 'temp');
    await mkdir(bin); await mkdir(temp);
    const state = join(root, 'state.json');
    await writeFile(state, JSON.stringify({calls: [], timeouts: [], sleeps: [], sequence}));
    const executable = async (name, source) => writeFile(join(bin, name), source, {mode: 0o700});
    await executable('docker', `#!/usr/bin/env node
const fs=require('node:fs'),file=process.env.PUSH_STATE,s=JSON.parse(fs.readFileSync(file,'utf8')),index=s.calls.length;
s.calls.push(process.argv.slice(2));fs.writeFileSync(file,JSON.stringify(s));
const result=s.sequence[index]||s.sequence.at(-1);process.stdout.write(result.output||'');process.exit(result.status);
`);
    await executable('timeout', `#!/usr/bin/env node
const fs=require('node:fs'),cp=require('node:child_process'),file=process.env.PUSH_STATE,s=JSON.parse(fs.readFileSync(file,'utf8')),a=process.argv.slice(2);
s.timeouts.push(a.slice(0,3));fs.writeFileSync(file,JSON.stringify(s));
const result=cp.spawnSync(a[3],a.slice(4),{stdio:'inherit',env:process.env});process.exit(result.status??1);
`);
    await executable('sleep', `#!/usr/bin/env node
const fs=require('node:fs'),file=process.env.PUSH_STATE,s=JSON.parse(fs.readFileSync(file,'utf8'));s.sleeps.push(process.argv[2]);fs.writeFileSync(file,JSON.stringify(s));
`);
    const run = value => spawnSync('bash', [script, value ?? image], {encoding: 'utf8', timeout: 5000,
      env: {...process.env, PATH: bin + ':' + process.env.PATH, TMPDIR: temp, PUSH_STATE: state}});
    const read = async () => JSON.parse(await readFile(state, 'utf8'));
    await action({run, read, temp});
  } finally { await rm(root, {recursive: true, force: true}); }
}

test('a refused connection retries the identical image and cleans private attempt logs after success', async () => {
  await fixture([{status: 1, output: 'dial tcp 142.250.145.82:443: connect: connection refused\n'}, {status: 0, output: 'digest: sha256:ready\n'}], async ({run, read, temp}) => {
    const result = run(); assert.equal(result.status, 0, result.stderr);
    const state = await read(); assert.deepEqual(state.calls, [['push', image], ['push', image]]);
    assert.deepEqual(state.sleeps, ['2']); assert.match(result.stdout, /upload completed/);
    assert.ok(state.timeouts.every(a => a.join(' ') === '--signal=TERM --kill-after=5s 180s'));
    assert.deepEqual(await readdir(temp), []);
  });
});

test('persistent network failure stops after three attempts and preserves the nonzero status', async () => {
  await fixture([{status: 7, output: 'connect: connection refused\n'}], async ({run, read, temp}) => {
    const result = run(); assert.equal(result.status, 7);
    const state = await read(); assert.equal(state.calls.length, 3); assert.deepEqual(state.sleeps, ['2', '4']);
    assert.match(result.stderr, /ERROR: Docker image upload failed after 3 attempts: the registry connection was refused/);
    assert.deepEqual(await readdir(temp), []);
  });
});

test('access, certificate and unknown failures stop immediately even alongside network text', async () => {
  for (const output of ['unauthorized: authentication required; connection refused', 'denied: permission denied; i/o timeout', 'x509: certificate signed by unknown authority; connection reset', 'manifest unknown', 'unsupported media type', 'surprising upload failure']) {
    await fixture([{status: 1, output: output + '\n'}], async ({run, read}) => {
      const result = run(); assert.equal(result.status, 1); assert.equal((await read()).calls.length, 1);
      assert.deepEqual((await read()).sleeps, []); assert.match(result.stderr, /no retry/);
    });
  }
});

test('an enforced timeout is retryable without a matching error string and remains bounded', async () => {
  await fixture([{status: 124, output: ''}], async ({run, read}) => {
    const result = run(); assert.equal(result.status, 124); assert.equal((await read()).calls.length, 3);
    assert.match(result.stderr, /timed out after 180 seconds/);
  });
});

test('invalid or non-dev image selectors cannot invoke Docker', async () => {
  for (const value of [image.replace('otthonra-dev/', 'otthonra-prod/'), image.replace('europe-west1-', 'us-central1-'), image.replace(':' + 'a'.repeat(40), ':latest'), image + ';echo unsafe', 'not-an-image']) {
    await fixture([{status: 0}], async ({run, read}) => {
      assert.equal(run(value).status, 2); assert.equal((await read()).calls.length, 0);
    });
  }
});
