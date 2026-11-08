import {cp, lstat, mkdir, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {dirname, extname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const projectRoot = fileURLToPath(new URL('../../', import.meta.url));
const expected = {
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev'
};
const assetExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.ico', '.woff', '.woff2']);
const codeFiles = new Set(['index.html', 'app.js', 'style.css', 'api.js', 'model.js', 'locations.js', 'locations-data.js', 'agglomerations-data.js', 'regions-data.js', 'attributes.js', 'accounts.js', 'runtime-config.js', 'data/settlements.json', 'data/agglomerations.json', 'THIRD-PARTY-NOTICES.txt']);
const configFields = new Set(['projectId', 'projectNumber', 'region', 'serviceName', 'registry', 'sqlInstance', 'connectionName', 'databaseName', 'databaseUser', 'mysqlSecret', 'jwtSecret', 'siteId', 'runtimeServiceAccount', 'deployServiceAccount', 'workloadIdentityProvider']);

/** Validate every resource selector before any cloud or filesystem mutation. */
export function validateDevConfig(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('A development config object is required.');
  if (Object.keys(input).some(key => !configFields.has(key))) throw new Error('The development manifest contains an unexpected field; credentials must not be included.');
  const config = {...input};
  if (!/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(config.projectId ?? '')) throw new Error('Invalid GCP projectId.');
  if (!/^[1-9][0-9]{5,19}$/.test(String(config.projectNumber ?? ''))) throw new Error('Invalid GCP projectNumber.');
  config.projectNumber = String(config.projectNumber);
  if (config.region !== 'europe-west1') throw new Error('This test deployment is configured for europe-west1.');
  for (const [field, value] of Object.entries(expected)) {
    if (config[field] !== value) throw new Error(`Only the test ${field} (${value}) may be deployed.`);
  }
  if (config.databaseName !== 'otthonra_dev' || config.databaseUser !== 'otthonra_dev') throw new Error('Only the test database and user may be deployed.');
  if (config.connectionName !== `${config.projectId}:${config.region}:${config.sqlInstance}`) throw new Error('Cloud SQL connectionName does not match the test instance.');
  if (config.siteId !== `otthonra-dev-${config.projectNumber}` || config.siteId.length > 30) throw new Error('Only this project’s otthonra-dev Hosting site may be deployed.');
  const account = role => `otthonra-${role}-dev@${config.projectId}.iam.gserviceaccount.com`;
  if (config.runtimeServiceAccount !== account('runtime') || config.deployServiceAccount !== account('deploy')) throw new Error('Unexpected development service account.');
  if (config.workloadIdentityProvider !== `projects/${config.projectNumber}/locations/global/workloadIdentityPools/otthonra-dev/providers/github`) throw new Error('Unexpected development Workload Identity provider.');
  return config;
}

export async function readDevConfig(path) {
  return validateDevConfig(JSON.parse(await readFile(path, 'utf8')));
}

export function hostingConfig(config) {
  config = validateDevConfig(config);
  return {hosting: {
    site: config.siteId,
    public: 'public',
    ignore: ['firebase.json', '**/.*', '**/node_modules/**'],
    headers: [{source: '**', headers: [
      {key: 'Cache-Control', value: 'no-store'},
      {key: 'X-Content-Type-Options', value: 'nosniff'},
      {key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin'},
      {key: 'X-Robots-Tag', value: 'noindex, nofollow'}
    ]}],
    // Firebase CLI 14.17.0 pins each rewrite independently and updates duplicate
    // services concurrently. One regex covers both /api and its descendants,
    // avoiding conflicting replacements of the same Cloud Run service.
    rewrites: [{regex: '^/api(/.*)?$', run: {
      serviceId: config.serviceName, region: config.region, pinTag: true
    }}]
  }};
}

async function collectFiles(directory, relative = '') {
  const result = [];
  for (const name of await readdir(directory)) {
    const path = join(directory, name), key = relative ? `${relative}/${name}` : name;
    const details = await lstat(path);
    if (details.isSymbolicLink()) throw new Error(`A symlink cannot be published: ${key}`);
    if (name.startsWith('.')) throw new Error(`A hidden file cannot be published: ${key}`);
    if (details.isDirectory()) result.push(...await collectFiles(path, key));
    else if (details.isFile()) {
      if (!codeFiles.has(key) && !(key.startsWith('assets/') && assetExtensions.has(extname(name).toLowerCase()))) throw new Error(`Unexpected frontend file; refusing to publish: ${key}`);
      result.push({path, key});
    } else throw new Error(`Not a regular frontend file: ${key}`);
  }
  return result;
}

async function assertNoSymlinkParents(target, stopAt) {
  for (let path = target;; path = dirname(path)) {
    try {
      const details = await lstat(path);
      if (details.isSymbolicLink() || !details.isDirectory()) throw new Error('Staging directories must be real directories, not symlinks or files.');
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (path === stopAt) return;
    if (path === dirname(path)) throw new Error('Invalid staging root.');
  }
}

export async function prepareSite({config, source = join(projectRoot, 'dist'), output = join(projectRoot, '.local/gcp/site')}) {
  config = validateDevConfig(config);
  const target = resolve(output), allowedRoot = resolve(projectRoot, '.local/gcp');
  if (!target.startsWith(allowedRoot + '/')) throw new Error('Staging output must be a child of .local/gcp.');
  const sourceRoot = resolve(source), sourceDetails = await lstat(sourceRoot);
  if (sourceDetails.isSymbolicLink() || !sourceDetails.isDirectory()) throw new Error('The frontend source must be a real directory.');
  if (sourceRoot === target || sourceRoot.startsWith(target + '/') || target.startsWith(sourceRoot + '/')) throw new Error('Frontend source and staging output must not overlap.');
  await assertNoSymlinkParents(target, resolve(projectRoot));
  const files = await collectFiles(source);
  for (const required of codeFiles) if (!files.some(file => file.key === required)) throw new Error(`Missing frontend file ${required}.`);
  // Validate the entire tree first, then replace only this ignored staging directory.
  await rm(target, {recursive: true, force: true});
  await mkdir(join(target, 'public'), {recursive: true});
  for (const file of files) {
    const destination = join(target, 'public', file.key);
    await mkdir(dirname(destination), {recursive: true});
    await cp(file.path, destination);
  }
  await writeFile(join(target, 'public/runtime-config.js'), 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});\n');
  await writeFile(join(target, 'firebase.json'), JSON.stringify(hostingConfig(config), null, 2) + '\n');
  return {directory: target, url: `https://${config.siteId}.web.app`};
}

async function main() {
  const [configPath = '.local/gcp/dev-config.json', output] = process.argv.slice(2);
  const result = await prepareSite({config: await readDevConfig(resolve(configPath)), output});
  console.log(`Prepared test Hosting files: ${result.directory}`);
  console.log(`Test web address: ${result.url}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { await main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
