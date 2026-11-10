import assert from 'node:assert/strict';
import test from 'node:test';
import {spawnSync} from 'node:child_process';
import {mkdtemp, mkdir, readFile, readdir, rm, symlink, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {hostingConfig, prepareSite, validateDevConfig} from '../scripts/gcp/prepare-site.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const config = Object.freeze({
  projectId: 'ingatlan-513620', projectNumber: '123456789012', region: 'europe-west1',
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  connectionName: 'ingatlan-513620:europe-west1:otthonra-mysql-dev',
  databaseName: 'otthonra_dev', databaseUser: 'otthonra_dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev',
  siteId: 'otthonra-dev-123456789012',
  runtimeServiceAccount: 'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  deployServiceAccount: 'otthonra-deploy-dev@ingatlan-513620.iam.gserviceaccount.com',
  workloadIdentityProvider: 'projects/123456789012/locations/global/workloadIdentityPools/otthonra-dev/providers/github'
});
const required = ['index.html','app.js','style.css','api.js','model.js','matching.js','public-profile.js','feedback.js','locations.js','locations-data.js','agglomerations-data.js', 'regions-data.js','attributes.js','accounts.js','runtime-config.js','data/settlements.json','data/agglomerations.json','THIRD-PARTY-NOTICES.txt'];

async function fixture(run) {
  const source = await mkdtemp(join(tmpdir(), 'otthonra-hosting-source-'));
  const stagingRoot = join(root, '.local/gcp');
  await mkdir(stagingRoot, {recursive: true});
  const workspace = await mkdtemp(join(stagingRoot, 'hosting-test-'));
  const output = join(workspace, 'site');
  for (const name of required) {
    await mkdir(join(source, name, '..'), {recursive: true});
    await writeFile(join(source, name), name === 'runtime-config.js' ? 'globalThis.OTTHONRA_CONFIG={mode:"demo"};' : `fixture: ${name}`);
  }
  await mkdir(join(source, 'assets'));
  await writeFile(join(source, 'assets/living.jpg'), 'image-fixture');
  try { await run({source, output, workspace}); }
  finally { await rm(source, {recursive: true, force: true}); await rm(workspace, {recursive: true, force: true}); }
}

test('test deployment selectors cannot redirect a release to production or a different project identity', () => {
  assert.equal(validateDevConfig(config).projectId, config.projectId);
  for (const change of [
    {serviceName: 'otthonra-api-prod'}, {registry: 'otthonra-prod'}, {sqlInstance: 'otthonra-mysql-prod'},
    {mysqlSecret: 'otthonra-mysql-prod'}, {jwtSecret: 'otthonra-jwt-prod'},
    {databaseName: 'otthonra_prod'}, {databaseUser: 'root'}, {region: 'us-central1'},
    {projectId: 'another-project-123'}, {connectionName: 'another-project-123:europe-west1:otthonra-mysql-dev'},
    {siteId: 'production-site'}, {runtimeServiceAccount: config.deployServiceAccount},
    {deployServiceAccount: 'owner@another-project-123.iam.gserviceaccount.com'},
    {workloadIdentityProvider: 'projects/999999999999/locations/global/workloadIdentityPools/otthonra-dev/providers/github'}
  ]) assert.throws(() => validateDevConfig({...config, ...change}));
});

test('a public deployment manifest rejects accidental credential fields', () => {
  for (const name of ['password','connectionString','jwtKey','token','GOOGLE_APPLICATION_CREDENTIALS']) {
    assert.throws(() => validateDevConfig({...config, [name]: 'must-not-be-published'}), /unexpected field/);
  }
});

test('one pinned rewrite covers exactly the API namespace without concurrent updates of the same Run service', () => {
  const value = hostingConfig(config).hosting;
  assert.equal(value.site, config.siteId);
  // Firebase CLI pins once per rewrite, including repeated references to the
  // same service. Both API patterns must therefore share a single rewrite.
  assert.equal(value.rewrites.length, 1);
  const [rule] = value.rewrites;
  assert.equal(rule.source, undefined);
  assert.deepEqual(rule.run, {serviceId: config.serviceName, region: config.region, pinTag: true});
  const pattern = new RegExp(rule.regex);
  for (const path of ['/api','/api/','/api/health','/api/auth/login','/api/locations?q=Budapest']) {
    assert.equal(pattern.test(path), true, `API route missing: ${path}`);
  }
  for (const path of ['/','/apix','/api-extra','/API/health','/runtime-config.js','/assets/api/image.jpg']) {
    assert.equal(pattern.test(path), false, `Frontend route wrongly sent to API: ${path}`);
  }
  const headers = Object.fromEntries(value.headers[0].headers.map(header => [header.key, header.value]));
  assert.equal(headers['Cache-Control'], 'no-store');
  assert.equal(headers['X-Robots-Tag'], 'noindex, nofollow');
});

test('frontend packaging enables the real hosted test API while preserving the source demo and excluding deployment metadata', async () => {
  await fixture(async ({source, output}) => {
    const result = await prepareSite({config, source, output});
    assert.equal(result.url, `https://${config.siteId}.web.app`);
    const runtime = await readFile(join(output, 'public/runtime-config.js'), 'utf8');
    assert.match(runtime, /mode: "api"/); assert.match(runtime, /environment: "test"/);
    assert.match(await readFile(join(source, 'runtime-config.js'), 'utf8'), /mode:"demo"/);
    assert.equal(await readFile(join(output, 'public/assets/living.jpg'), 'utf8'), 'image-fixture');
    assert.equal(await readFile(join(output, 'public/THIRD-PARTY-NOTICES.txt'), 'utf8'), 'fixture: THIRD-PARTY-NOTICES.txt');
    assert.deepEqual((await readdir(output)).sort(), ['firebase.json','public']);
    assert.deepEqual(JSON.parse(await readFile(join(output, 'firebase.json'), 'utf8')), hostingConfig(config));
  });
});

test('invalid selectors leave a previous staged site intact', async () => {
  await fixture(async ({source, output}) => {
    await mkdir(output); await writeFile(join(output, 'sentinel'), 'previous-release');
    await assert.rejects(prepareSite({config: {...config, siteId: 'prod-site'}, source, output}));
    assert.equal(await readFile(join(output, 'sentinel'), 'utf8'), 'previous-release');
  });
});

test('hidden files, unknown files and symlinks are refused before replacing a previous staged release', async () => {
  for (const kind of ['hidden','unknown','symlink']) await fixture(async ({source, output}) => {
    await mkdir(output); await writeFile(join(output, 'sentinel'), 'previous-release');
    if (kind === 'hidden') await writeFile(join(source, '.env'), 'private');
    if (kind === 'unknown') await writeFile(join(source, 'credentials.json'), 'private');
    if (kind === 'symlink') await symlink(join(source, 'api.js'), join(source, 'assets/private.svg'));
    await assert.rejects(prepareSite({config, source, output}), /cannot be published|refusing to publish/);
    assert.equal(await readFile(join(output, 'sentinel'), 'utf8'), 'previous-release');
  });
});

test('an incomplete frontend cannot replace a working staged release', async () => {
  for (const missing of ['locations.js','accounts.js','matching.js','public-profile.js','feedback.js']) await fixture(async ({source, output}) => {
    await mkdir(output); await writeFile(join(output, 'sentinel'), 'previous-release');
    await rm(join(source, missing));
    await assert.rejects(prepareSite({config, source, output}), new RegExp('Missing frontend file '+missing.replaceAll('.', '\\.')));
    assert.equal(await readFile(join(output, 'sentinel'), 'utf8'), 'previous-release');
  });
});

test('staging cannot overwrite the source or escape the ignored deployment directory', async () => {
  await fixture(async ({source, output, workspace}) => {
    await assert.rejects(prepareSite({config, source, output: source}), /child of/);
    await assert.rejects(prepareSite({config, source, output: join(root, 'dist')}), /child of/);
    await assert.rejects(prepareSite({config, source: workspace, output: join(workspace, 'nested')}), /must not overlap/);
    assert.equal(await readFile(join(source, 'app.js'), 'utf8'), 'fixture: app.js');
  });
});

test('a symlinked staging directory cannot expose or remove files outside deployment staging', async () => {
  await fixture(async ({source, output, workspace}) => {
    const protectedFolder = await mkdtemp(join(tmpdir(), 'otthonra-protected-'));
    try {
      await writeFile(join(protectedFolder, 'sentinel'), 'private-file');
      await symlink(protectedFolder, join(workspace, 'linked'));
      await assert.rejects(prepareSite({config, source, output: join(workspace, 'linked/site')}), /symlinks/);
      assert.equal(await readFile(join(protectedFolder, 'sentinel'), 'utf8'), 'private-file');
      const sourceLink = join(workspace, 'source-link');
      await symlink(source, sourceLink);
      await assert.rejects(prepareSite({config, source: sourceLink, output}), /real directory/);
    } finally { await rm(protectedFolder, {recursive: true, force: true}); }
  });
});


test('the pinned Firebase process receives the selected quota project and isolated login config without changing the caller', async () => {
  const source = await readFile(join(root, 'scripts/gcp/deploy-dev.sh'), 'utf8');
  const start = source.indexOf('GOOGLE_CLOUD_QUOTA_PROJECT="$project_id" XDG_CONFIG_HOME=');
  const end = source.indexOf('\nnode scripts/gcp/verify-dev.mjs --hosting', start);
  assert.ok(start > 0 && end > start);
  const workspace = await mkdtemp(join(tmpdir(), 'otthonra-firebase-env-'));
  try {
    const binary = join(workspace, '.local/gcp/tools/node_modules/.bin/firebase');
    await mkdir(join(binary, '..'), {recursive: true});
    await writeFile(binary, '#!/usr/bin/env node\nrequire("node:fs").writeFileSync(process.env.OBSERVED, JSON.stringify({quota:process.env.GOOGLE_CLOUD_QUOTA_PROJECT,config:process.env.XDG_CONFIG_HOME,adc:process.env.GOOGLE_APPLICATION_CREDENTIALS,args:process.argv.slice(2)}));\n', {mode: 0o700});
    const result = spawnSync('bash', ['-c', 'set -eu\ncd "$WORKSPACE"\nproject_id=ingatlan-513620\nrepo_root="$WORKSPACE"\ndeployment_tmp="$WORKSPACE/private-deployment"\n'+source.slice(start,end)+'\nprintf "%s|%s" "$GOOGLE_CLOUD_QUOTA_PROJECT" "$XDG_CONFIG_HOME"'], {
      encoding: 'utf8', timeout: 5000,
      env: {...process.env, WORKSPACE: workspace, OBSERVED: join(workspace, 'observed.json'), GOOGLE_CLOUD_QUOTA_PROJECT: 'different-project-123', XDG_CONFIG_HOME: '/prior/firebase', GOOGLE_APPLICATION_CREDENTIALS: '/user/adc.json'}
    });
    assert.equal(result.status, 0, result.stderr);
    const observed = JSON.parse(await readFile(join(workspace, 'observed.json'), 'utf8'));
    assert.equal(observed.quota, 'ingatlan-513620');
    assert.equal(observed.config, join(workspace, 'private-deployment/firebase-config'));
    assert.equal(observed.adc, '/user/adc.json');
    assert.equal(observed.args[observed.args.indexOf('--project')+1], 'ingatlan-513620');
    assert.equal(result.stdout, 'different-project-123|/prior/firebase');
  } finally { await rm(workspace, {recursive: true, force: true}); }
});
