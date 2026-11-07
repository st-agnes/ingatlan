import assert from 'node:assert/strict';
import test from 'node:test';
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
  assert.equal(env.Credits__EnableDemoTopup.value, 'true');
  assert.equal(env.Cors__Origins__0.value, `https://${config.siteId}.web.app`);
  assert.deepEqual(env.ConnectionStrings__MySql.valueFrom, {secretKeyRef: {name: config.mysqlSecret, key: 'latest'}});
  assert.deepEqual(env.Jwt__Key.valueFrom, {secretKeyRef: {name: config.jwtSecret, key: 'latest'}});
  assert.equal(env.ConnectionStrings__MySql.value, undefined);
  assert.equal(env.Jwt__Key.value, undefined);
  assert.equal(value.status, undefined);
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
