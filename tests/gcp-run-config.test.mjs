import assert from 'node:assert/strict';
import test from 'node:test';
import {copyFile, mkdtemp, mkdir, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {buildCloudRunService, SQL_PROXY_IMAGE} from '../scripts/gcp/prepare-run.mjs';

const config = {
  projectId: 'ingatlan-513620', projectNumber: '123456789012', region: 'europe-west1',
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  connectionName: 'ingatlan-513620:europe-west1:otthonra-mysql-dev', databaseName: 'otthonra_dev', databaseUser: 'otthonra_dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev', siteId: 'otthonra-dev-123456789012',
  runtimeServiceAccount: 'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  deployServiceAccount: 'otthonra-deploy-dev@ingatlan-513620.iam.gserviceaccount.com',
  workloadIdentityProvider: 'projects/123456789012/locations/global/workloadIdentityPools/otthonra-dev/providers/github'
};
const existingService = {
  metadata: {name: config.serviceName, namespace: config.projectNumber, labels: {
    app: 'otthonra', environment: 'dev', 'managed-by': 'otthonra-bootstrap', 'cloud.googleapis.com/location': config.region
  }},
  spec: {traffic: [{latestRevision: true, percent: 100}]}
};
const imageDigest = 'europe-west1-docker.pkg.dev/ingatlan-513620/otthonra-dev/otthonra-api@sha256:' + 'a'.repeat(64);
const input = {config, existingService, imageDigest, revisionSuffix: 'dev-20261104-123'};

function service(change = {}) { return buildCloudRunService({...input, ...change}); }

async function deploymentProbe(manifest, args, action) {
  const root = await mkdtemp(join(tmpdir(), 'otthonra-geocoding-config-'));
  try {
    const bin = join(root, 'bin'), script = join(root, 'scripts/gcp'), local = join(root, '.local/gcp');
    await Promise.all([mkdir(bin), mkdir(script, {recursive: true}), mkdir(local, {recursive: true})]);
    for (const name of ['deploy-dev.sh', 'prepare-site.mjs'])
      await copyFile(new URL('../scripts/gcp/' + name, import.meta.url), join(script, name));
    const original = JSON.stringify(manifest, null, 2) + '\n';
    const configPath = join(local, 'config with spaces.json'), observed = join(root, 'observed.json');
    await writeFile(configPath, original, {mode: 0o600});
    // Stop at the very first gcloud call, before credentials, Docker or cloud
    // mutations. Observe the real script's private effective manifest.
    await writeFile(join(bin, 'gcloud'), `#!/usr/bin/env node
const fs=require('node:fs'),path=require('node:path');
fs.appendFileSync('calls.jsonl',JSON.stringify(process.argv.slice(2))+'\\n');
if(process.argv.slice(2,5).join(' ')==='run services describe') {
 const dir=fs.readdirSync('.local/gcp').find(name=>name.startsWith('deployment.'));
 const file=path.join('.local/gcp',dir,'config.json');
 fs.writeFileSync(process.env.OBSERVED,JSON.stringify({config:JSON.parse(fs.readFileSync(file,'utf8')),mode:fs.statSync(file).mode&0o777}));
 process.exit(42);
}
process.exit(91);
`, {mode: 0o700});
    const result = spawnSync('bash', ['scripts/gcp/deploy-dev.sh', '--config', configPath, ...args], {
      cwd: root, encoding: 'utf8', timeout: 10000, env: {...process.env, PATH: bin + ':' + process.env.PATH, OBSERVED: observed}
    });
    await action({root, result, observed});
    assert.equal(await readFile(configPath, 'utf8'), original, 'Stored config must remain byte-identical.');
    assert.deepEqual((await readdir(local)).sort(), ['config with spaces.json'], 'Private deployment staging must be removed.');
  } finally { await rm(root, {recursive: true, force: true}); }
}

test('Cloud Shell enables the existing Google secret without editing a legacy config or reading its payload', async () => {
  for (const enabled of [false, true]) await deploymentProbe(config, enabled ? ['--google-geocoding'] : [], async ({root, result, observed}) => {
    assert.equal(result.status, 42, result.stderr);
    const effective = JSON.parse(await readFile(observed, 'utf8'));
    assert.equal(effective.mode, 0o600);
    assert.deepEqual(effective.config, enabled ? {...config, googleGeocodingSecret: 'otthonra-geocoding-dev'} : config);
    const calls = (await readFile(join(root, 'calls.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0].slice(0, 4), ['run', 'services', 'describe', config.serviceName]);
    const built = service({config: effective.config});
    const google = built.spec.template.spec.containers[0].env.filter(item => item.name === 'Geocoding__Google__ApiKey');
    assert.deepEqual(google, enabled ? [{name: 'Geocoding__Google__ApiKey', valueFrom: {secretKeyRef: {name: 'otthonra-geocoding-dev', key: 'latest'}}}] : []);
  });
});

test('a previously explicit Google binding is retained without the new flag', async () => {
  const explicit = {...config, googleGeocodingSecret: 'otthonra-geocoding-dev'};
  await deploymentProbe(explicit, [], async ({result, observed}) => {
    assert.equal(result.status, 42, result.stderr);
    assert.deepEqual(JSON.parse(await readFile(observed, 'utf8')).config, explicit);
  });
});

test('the Google opt-in cannot repair an untrusted config by hiding an invalid secret or credential field', async () => {
  for (const invalid of [{...config, googleGeocodingSecret: 'otthonra-geocoding-prod'}, {...config, apiKey: 'private-test-marker-never-log'}])
    await deploymentProbe(invalid, ['--google-geocoding'], async ({root, result}) => {
      assert.notEqual(result.status, 0);
      assert.doesNotMatch(result.stdout + result.stderr, /private-test-marker-never-log/);
      await assert.rejects(readFile(join(root, 'calls.jsonl')), {code: 'ENOENT'});
    });
});

test('the Actions deploy command uses the checked default without changing GCP_DEV_CONFIG', async () => {
  const workflow = await readFile(new URL('../.github/workflows/deploy-dev.yml', import.meta.url), 'utf8');
  assert.match(workflow, /use_google_geocoding:\s+description:[^\n]+\s+type: boolean\s+default: true/);
  const step = workflow.split('- name: Build and deploy the test API and frontend')[1];
  assert.match(step, /USE_GOOGLE_GEOCODING: \$\{\{ inputs\.use_google_geocoding \}\}/);
  const command = step.split('run: |\n')[1].split('\n').map(line => line.startsWith('          ') ? line.slice(10) : line).join('\n');
  const root = await mkdtemp(join(tmpdir(), 'otthonra-actions-geocoding-'));
  try {
    await mkdir(join(root, 'scripts/gcp'), {recursive: true});
    await writeFile(join(root, 'scripts/gcp/deploy-dev.sh'), 'printf "%s\\n" "$@" > observed-args\n');
    for (const enabled of ['true', 'false']) {
      const result = spawnSync('bash', ['-e', '-c', command], {cwd: root, encoding: 'utf8', timeout: 5000,
        env: {...process.env, USE_GOOGLE_GEOCODING: enabled, GCP_DEV_CONFIG: JSON.stringify(config)}});
      assert.equal(result.status, 0, result.stderr);
      assert.deepEqual((await readFile(join(root, 'observed-args'), 'utf8')).trim().split('\n'),
        ['--config', '.local/gcp/dev-config.json', ...(enabled === 'true' ? ['--google-geocoding'] : [])]);
    }
  } finally { await rm(root, {recursive: true, force: true}); }
});

test('the API waits for the pinned proxy and uses its private loopback TCP endpoint with no integrated Unix mount', () => {
  const value = service();
  const template = value.spec.template;
  const [api, proxy] = template.spec.containers;
  assert.equal(api.name, 'api'); assert.equal(api.image, imageDigest);
  assert.deepEqual(api.ports, [{name: 'http1', containerPort: 8080}]);
  assert.equal(proxy.name, 'cloud-sql-proxy');
  assert.equal(proxy.image, SQL_PROXY_IMAGE);
  assert.equal(proxy.image, 'gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.26.3');
  assert.ok(proxy.args.includes('--address=127.0.0.1'));
  assert.ok(proxy.args.includes('--port=3306'));
  assert.ok(proxy.args.includes('--lazy-refresh'));
  assert.equal(proxy.args.at(-1), config.connectionName);
  assert.ok(!proxy.args.some(arg => /unix-socket|credentials-file|auto-iam-authn|private-ip/.test(arg)));
  assert.equal(proxy.ports, undefined);
  assert.equal(proxy.env, undefined);
  assert.deepEqual(JSON.parse(template.metadata.annotations['run.googleapis.com/container-dependencies']), {api: ['cloud-sql-proxy']});
  assert.equal(template.metadata.annotations['run.googleapis.com/cloudsql-instances'], undefined);
  assert.equal(template.spec.volumes, undefined);
  assert.equal(api.volumeMounts, undefined);
});

test('both startup probes and resource bounds remain explicit and a failed database cannot be masked by the proxy health check', () => {
  const value = service(), template = value.spec.template;
  const [api, proxy] = template.spec.containers;
  assert.deepEqual(api.startupProbe.httpGet, {path: '/api/health', port: 8080});
  assert.deepEqual(proxy.startupProbe.httpGet, {path: '/startup', port: 9090});
  assert.ok(proxy.args.includes('--health-check'));
  assert.ok(proxy.args.includes('--http-address=0.0.0.0'));
  assert.ok(proxy.args.includes('--http-port=9090'));
  assert.equal(template.metadata.annotations['run.googleapis.com/execution-environment'], 'gen2');
  assert.equal(value.metadata.annotations['run.googleapis.com/minScale'], '0');
  assert.equal(value.metadata.annotations['run.googleapis.com/maxScale'], '2');
  assert.equal(template.metadata.annotations['autoscaling.knative.dev/maxScale'], '2');
  assert.equal(template.spec.containerConcurrency, 20);
  assert.equal(template.spec.timeoutSeconds, 60);
  for (const container of [api, proxy]) {
    assert.deepEqual(container.resources.limits, {cpu: '1000m', memory: '512Mi'});
    assert.equal(container.startupProbe.periodSeconds * container.startupProbe.failureThreshold, 240);
  }
});

test('only secret references enter the API environment and runtime permissions remain on the existing account', () => {
  const value = service(), template = value.spec.template;
  assert.equal(template.spec.serviceAccountName, config.runtimeServiceAccount);
  const env = Object.fromEntries(template.spec.containers[0].env.map(item => [item.name, item]));
  assert.equal(env.ASPNETCORE_ENVIRONMENT.value, 'Production');
  assert.equal(env.Deployment__Environment.value, 'test');
  assert.equal(env.Database__SeedDemo.value, 'false');
  assert.equal(env.Database__SeedTestFixtures.value, 'true');
  assert.equal(env.Scheduler__Audience.value, `https://${config.serviceName}-${config.projectNumber}.${config.region}.run.app`);
  assert.equal(env.Scheduler__ServiceAccountEmail.value, `otthonra-refunds-dev@${config.projectId}.iam.gserviceaccount.com`);
  assert.equal(env.Credits__EnableDemoTopup.value, 'true');
  assert.equal(env.Cors__Origins__0.value, `https://${config.siteId}.web.app`);
  assert.deepEqual(env.ConnectionStrings__MySql.valueFrom, {secretKeyRef: {name: config.mysqlSecret, key: 'latest'}});
  assert.deepEqual(env.Jwt__Key.valueFrom, {secretKeyRef: {name: config.jwtSecret, key: 'latest'}});
  assert.equal(env.ConnectionStrings__MySql.value, undefined);
  assert.equal(env.Jwt__Key.value, undefined);
  assert.equal(env.Geocoding__Google__ApiKey, undefined);
  assert.equal(env.Geocoding__EnableTestGeocoder, undefined);
  assert.equal(value.status, undefined);
});

test('Google geocoding is opt-in and binds only a server-side Secret Manager reference', () => {
  const value = service({config: {...config, googleGeocodingSecret: 'otthonra-geocoding-dev'}});
  const [api, proxy] = value.spec.template.spec.containers;
  const google = api.env.filter(item => item.name === 'Geocoding__Google__ApiKey');
  assert.deepEqual(google, [{name: 'Geocoding__Google__ApiKey', valueFrom: {secretKeyRef: {name: 'otthonra-geocoding-dev', key: 'latest'}}}]);
  assert.equal(google[0].value, undefined);
  assert.equal(proxy.env, undefined);
  assert.equal(JSON.stringify(value).includes('googleGeocodingSecret'), false);
  for (const secret of ['', null, 1, true, {}, 'AIza-private-google-key', 'otthonra-geocoding-prod', 'projects/another/secrets/otthonra-geocoding-dev', 'otthonra-geocoding-dev:latest']) {
    assert.throws(() => service({config: {...config, googleGeocodingSecret: secret}}), /googleGeocodingSecret/);
  }
});

test('replacing the service keeps Firebase revision tags while routing normal traffic to the new revision', () => {
  const prior = structuredClone(existingService);
  prior.spec.traffic.push({tag: 'fh-old-release', revisionName: config.serviceName + '-00002-abc', percent: 20, url: 'ignored-server-field'});
  const value = service({existingService: prior});
  assert.deepEqual(value.spec.traffic, [
    {latestRevision: true, percent: 100},
    {tag: 'fh-old-release', revisionName: config.serviceName + '-00002-abc', percent: 0}
  ]);
  assert.equal(prior.spec.traffic[1].percent, 20);
  assert.equal(JSON.stringify(value).includes('ignored-server-field'), false);
});

test('foreign resources, mutable images and invalid revisions cannot produce a deployable spec', () => {
  for (const change of [{serviceName: 'otthonra-api-prod'}, {region: 'us-central1'}, {runtimeServiceAccount: config.deployServiceAccount}, {connectionName: 'another-project:europe-west1:otthonra-mysql-dev'}]) {
    assert.throws(() => service({config: {...config, ...change}}));
  }
  for (const path of ['metadata.name', 'metadata.namespace', 'metadata.labels.environment', 'metadata.labels.cloud.googleapis.com/location']) {
    const prior = structuredClone(existingService);
    if (path === 'metadata.labels.cloud.googleapis.com/location') prior.metadata.labels['cloud.googleapis.com/location'] = 'us-central1';
    else {const keys=path.split('.');let node=prior;for(const key of keys.slice(0,-1))node=node[key];node[keys.at(-1)]='foreign';}
    assert.throws(() => service({existingService: prior}));
  }
  for (const image of [imageDigest.replace('otthonra-dev/', 'otthonra-prod/'), imageDigest.replace('ingatlan-513620/', 'different-project/'), imageDigest.replace('@sha256:'+'a'.repeat(64), ':latest'), imageDigest+';echo unsafe']) {
    assert.throws(() => service({imageDigest: image}));
  }
  for (const suffix of ['', '../other-service', 'A'.repeat(10), 'dev-'+'a'.repeat(60)]) assert.throws(() => service({revisionSuffix: suffix}));
});

test('foreign, duplicate or unresolved tagged revisions are rejected instead of overwriting traffic', () => {
  for (const extra of [
    [{tag: 'fh-release', revisionName: 'otthonra-api-prod-00001-abc'}],
    [{tag: 'fh-release', revisionName: config.serviceName+'-00001-abc'}, {tag: 'fh-release', latestRevision: true}],
    [{tag: 'fh-release'}]
  ]) {
    const prior = structuredClone(existingService); prior.spec.traffic.push(...extra);
    assert.throws(() => service({existingService: prior}));
  }
});
