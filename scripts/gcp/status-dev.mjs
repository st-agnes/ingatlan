/** Read-only, bounded deployment checks for a small terminal. */
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {readDevConfig, validateDevConfig} from './prepare-site.mjs';

const execute = promisify(execFile);
async function describe(config) {
  const {stdout} = await execute('gcloud', ['run', 'services', 'describe', config.serviceName,
    '--project', config.projectId, '--region', config.region, '--format=json', '--quiet'],
  {timeout: 30000, maxBuffer: 256 * 1024});
  return JSON.parse(stdout);
}
async function request(url) {
  const response = await fetch(url, {signal: AbortSignal.timeout(8000), redirect: 'error'});
  return {status: response.status, text: await response.text()};
}
const healthy = response => {
  if (response?.status !== 200) return false;
  try {
    const value = JSON.parse(response.text);
    return value.status === 'ready' && value.deployment === 'test' && value.testCreditsEnabled === true;
  } catch { return false; }
};

export async function inspectDeployment({config, describeService = describe, fetchResponse = request}) {
  config = validateDevConfig(config);
  const url = `https://${config.siteId}.web.app`;
  let backend = false, detail = '';
  const checkBackend = async () => {
    try {
      const service = await describeService(config);
      const origin = new URL(service.status?.url);
      if (origin.protocol !== 'https:' || !origin.hostname.endsWith('.run.app') || origin.username || origin.password) return;
      backend = healthy(await fetchResponse(new URL('/api/health', origin).href));
    } catch (error) {
      // Only this metadata command's short SDK error is eligible for display.
      // HTTP bodies, command arguments and stack traces are never printed.
      const first = String(error.stderr || '').split('\n').find(line => /^ERROR[: ]/.test(line));
      detail = first ? first.replace(/[\x00-\x1f\x7f]/g, ' ').slice(0, 160) : 'A backend állapota nem ellenőrizhető.';
    }
  };
  let web = false;
  const checkWeb = async () => {
    try {
      const [health, runtime] = await Promise.all(['/api/health', '/runtime-config.js'].map(path => fetchResponse(url + path)));
      web = healthy(health) && runtime.status === 200
        && /\bmode:\s*["']api["']/.test(runtime.text)
        && /\benvironment:\s*["']test["']/.test(runtime.text);
    } catch { /* An unreachable deployment is not a successful deployment. */ }
  };
  await Promise.all([checkBackend(), checkWeb()]);
  return {ready: backend && web, backend, web, url, detail};
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length && (args.length !== 2 || args[0] !== '--config')) {
    console.error('Használat: node scripts/gcp/status-dev.mjs [--config FILE]');
    process.exitCode = 1; return;
  }
  const path = args[1] || fileURLToPath(new URL('../../.local/gcp/dev-config.json', import.meta.url));
  let config;
  try { config = await readDevConfig(path); }
  catch (error) {
    console.error(error.code === 'ENOENT'
      ? 'Az előkészítés nem fejeződött be: nincs dev-config.json.'
      : 'A tesztkörnyezet konfigurációja nem olvasható vagy érvénytelen.');
    console.error('Következő lépés: bash scripts/gcp/bootstrap-dev.sh --project ingatlan-513620');
    process.exitCode = 1; return;
  }
  const result = await inspectDeployment({config});
  console.log(`Backend: ${result.backend ? 'KÉSZ (MySQL elérhető)' : 'NEM IGAZOLT'}`);
  console.log(`Web: ${result.web ? 'KÉSZ (teszt API)' : 'NEM IGAZOLT'}`);
  console.log(`Eredmény: ${result.ready ? 'SIKERES TELEPÍTÉS' : 'MÉG NEM IGAZOLT'}`);
  if (result.detail) console.log(`Hiba: ${result.detail}`);
  console.log(`Cím: ${result.url}/`);
  if (!result.ready) process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(() => { console.error('Az állapotellenőrzés nem fejeződött be.'); process.exitCode = 1; });
}
