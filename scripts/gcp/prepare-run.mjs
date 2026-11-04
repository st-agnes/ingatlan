/** Test-only Cloud Run service definition with a controlled TCP SQL proxy. */
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readDevConfig, validateDevConfig} from './prepare-site.mjs';

export const SQL_PROXY_IMAGE = 'gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.26.3';
const ownedLabels = {app: 'otthonra', environment: 'dev', 'managed-by': 'otthonra-bootstrap'};

function existingTraffic(config, existing) {
  const metadata = existing?.metadata;
  if (metadata?.name !== config.serviceName || String(metadata.namespace) !== config.projectNumber
      || metadata.labels?.['cloud.googleapis.com/location'] !== config.region
      || Object.entries(ownedLabels).some(([name, value]) => metadata.labels?.[name] !== value)) {
    throw new Error('Only this project’s bootstrap-managed test service may be replaced.');
  }
  const result = [], seen = new Set();
  for (const item of existing.spec?.traffic ?? []) {
    if (!item.tag) continue;
    if (!/^[a-z](?:[a-z0-9-]*[a-z0-9])?$/.test(item.tag) || item.tag.length > 63 || seen.has(item.tag)) {
      throw new Error('Existing Cloud Run traffic tags are invalid or duplicated.');
    }
    seen.add(item.tag);
    if (item.revisionName) {
      if (!item.revisionName.startsWith(config.serviceName + '-') || item.revisionName.length > 63
          || !/^[a-z0-9-]+$/.test(item.revisionName)) throw new Error('A tagged revision belongs to an unexpected service.');
      result.push({tag: item.tag, revisionName: item.revisionName, percent: 0});
    } else if (item.latestRevision === true) {
      result.push({tag: item.tag, latestRevision: true, percent: 0});
    } else throw new Error('A traffic tag has no supported revision selector.');
  }
  return result;
}

export function buildCloudRunService({config, existingService, imageDigest, revisionSuffix}) {
  config = validateDevConfig(config);
  const expectedImage = `${config.region}-docker.pkg.dev/${config.projectId}/${config.registry}/otthonra-api@sha256:`;
  if (typeof imageDigest !== 'string' || !imageDigest.startsWith(expectedImage)
      || !/^[0-9a-f]{64}$/.test(imageDigest.slice(expectedImage.length))) {
    throw new Error('Only a digest-pinned image in this project’s test registry may be deployed.');
  }
  const revisionName = `${config.serviceName}-${revisionSuffix}`;
  if (typeof revisionSuffix !== 'string' || !/^[a-z](?:[a-z0-9-]*[a-z0-9])?$/.test(revisionSuffix)
      || revisionName.length > 63) throw new Error('Invalid test revision suffix.');
  const tags = existingTraffic(config, existingService);
  const literal = (name, value) => ({name, value});
  const secret = (name, secretName) => ({name, valueFrom: {secretKeyRef: {name: secretName, key: 'latest'}}});
  const probe = (path, port) => ({httpGet: {path, port}, timeoutSeconds: 3, periodSeconds: 5, failureThreshold: 48});
  return {
    apiVersion: 'serving.knative.dev/v1', kind: 'Service',
    metadata: {
      name: config.serviceName, namespace: config.projectNumber,
      labels: {...ownedLabels, 'cloud.googleapis.com/location': config.region},
      annotations: {'run.googleapis.com/minScale': '0', 'run.googleapis.com/maxScale': '2'}
    },
    spec: {
      template: {
        metadata: {
          name: revisionName, labels: {...ownedLabels},
          annotations: {
            'run.googleapis.com/execution-environment': 'gen2',
            'run.googleapis.com/container-dependencies': JSON.stringify({api: ['cloud-sql-proxy']}),
            'autoscaling.knative.dev/minScale': '0', 'autoscaling.knative.dev/maxScale': '2'
          }
        },
        spec: {
          serviceAccountName: config.runtimeServiceAccount, containerConcurrency: 20, timeoutSeconds: 60,
          containers: [
            {
              name: 'api', image: imageDigest, ports: [{name: 'http1', containerPort: 8080}],
              resources: {limits: {cpu: '1000m', memory: '512Mi'}},
              env: [
                literal('ASPNETCORE_ENVIRONMENT', 'Production'), literal('Deployment__Environment', 'test'),
                literal('Database__Initialize', 'true'), literal('Database__SeedDemo', 'false'),
                literal('Credits__EnableDemoTopup', 'true'), literal('Cors__Origins__0', `https://${config.siteId}.web.app`),
                secret('ConnectionStrings__MySql', config.mysqlSecret), secret('Jwt__Key', config.jwtSecret)
              ],
              startupProbe: probe('/api/health', 8080)
            },
            {
              name: 'cloud-sql-proxy', image: SQL_PROXY_IMAGE,
              args: ['--address=127.0.0.1', '--port=3306', '--structured-logs', '--health-check',
                '--http-address=0.0.0.0', '--http-port=9090', '--lazy-refresh', config.connectionName],
              resources: {limits: {cpu: '1000m', memory: '512Mi'}},
              startupProbe: probe('/startup', 9090)
            }
          ]
        }
      },
      traffic: [{latestRevision: true, percent: 100}, ...tags]
    }
  };
}

async function main() {
  const [configPath, servicePath, imageDigest, revisionSuffix, output] = process.argv.slice(2);
  if (!output || process.argv.length !== 7) throw new Error('Usage: node prepare-run.mjs CONFIG EXISTING_SERVICE IMAGE_DIGEST REVISION_SUFFIX OUTPUT');
  const config = await readDevConfig(configPath);
  const existingService = JSON.parse(await readFile(servicePath, 'utf8'));
  const service = buildCloudRunService({config, existingService, imageDigest, revisionSuffix});
  await writeFile(output, JSON.stringify(service, null, 2) + '\n', {mode: 0o600});
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
