/** Read-only, bounded verification while a new Hosting release propagates. */
import {randomUUID} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {TEST_FIXTURE_VERSION} from './export-demo-data.mjs';

const pause = milliseconds => new Promise(done => setTimeout(done, milliseconds));
const safeVersion = value => typeof value === 'string' && /^[a-z0-9._-]{1,80}$/.test(value) ? value : '<missing or invalid>';
const networkCodes = new Set(['ENOTFOUND','ECONNREFUSED','ECONNRESET','ETIMEDOUT','CERT_HAS_EXPIRED',
  'UNABLE_TO_VERIFY_LEAF_SIGNATURE','ERR_TLS_CERT_ALTNAME_INVALID']);

export async function verifyTestDeployment({origin, hosting = false, fetchImpl = fetch, wait = pause,
  log = console.log, attempts = 12, delayMs = 5000, timeoutMs = 10000} = {}) {
  const base = new URL(origin);
  if (base.protocol !== 'https:' || base.username || base.password || base.port || base.pathname !== '/'
      || base.search || base.hash || !(hosting ? /^otthonra-dev-[1-9][0-9]*\.web\.app$/.test(base.hostname)
        : base.hostname.endsWith('.run.app'))) throw new Error('Use the expected HTTPS test service origin.');
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 12 || !Number.isInteger(delayMs) || delayMs < 0 || delayMs > 5000
      || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 10000) throw new Error('Invalid bounded verification limits.');
  const paths = hosting ? ['/', '/runtime-config.js', '/api/health'] : ['/api/health'];
  const probeId = randomUUID();
  let failures = [];
  for (let attempt = 1; attempt <= attempts; attempt++) {
    const results = await Promise.all(paths.map(async path => {
      const url = new URL(path, base);
      // A unique query also avoids a cached prior release at an intermediary.
      url.searchParams.set('otthonra_deploy_check', `${probeId}-${attempt}`);
      try {
        const response = await fetchImpl(url, {redirect: 'error', cache: 'no-store',
          headers: {'Cache-Control': 'no-cache, no-store', Pragma: 'no-cache'}, signal: AbortSignal.timeout(timeoutMs)});
        if (response.status !== 200) return {path, status: response.status, failures: [`${path}: HTTP ${response.status}`]};
        const text = await response.text();
        if (path === '/') return {path, failures: /runtime-config\.js/.test(text) ? [] : ['/: runtime-config.js script is missing']};
        if (path === '/runtime-config.js') return {path, failures: [
          ...(/\bmode:\s*["']api["']/.test(text) ? [] : ['/runtime-config.js: API mode is missing']),
          ...(/\benvironment:\s*["']test["']/.test(text) ? [] : ['/runtime-config.js: test environment is missing'])
        ]};
        let health;
        try { health = JSON.parse(text); } catch { return {path, failures: ['/api/health: response is not JSON']}; }
        return {path, failures: [
          ...(health?.status === 'ready' ? [] : ['/api/health: status is not ready']),
          ...(health?.deployment === 'test' ? [] : ['/api/health: deployment is not test']),
          ...(health?.testCreditsEnabled === true ? [] : ['/api/health: test credits are not enabled']),
          ...(health?.testDataVersion === TEST_FIXTURE_VERSION ? [] : [
            `/api/health: testDataVersion=${safeVersion(health?.testDataVersion)} (expected ${TEST_FIXTURE_VERSION})`
          ])
        ]};
      } catch (error) {
        const code = networkCodes.has(error?.cause?.code) ? ` (${error.cause.code})` : '';
        return {path, failures: [`${path}: ${['TimeoutError','AbortError'].includes(error?.name) ? 'request timed out' : 'request failed' + code}`]};
      }
    }));
    failures = results.flatMap(result => result.failures);
    if (!failures.length) {
      log(hosting ? `Test application ready: ${base.origin}/` : 'The deployed test API, database and startup test fixtures are ready.');
      return {ready: true, attempts: attempt};
    }
    // An access denial needs a real repair, not repeated authenticated requests.
    if (results.some(result => result.status === 401 || result.status === 403) || attempt === attempts)
      throw new Error(`Test ${hosting ? 'Hosting' : 'API'} verification failed after ${attempt} check(s): ${failures.join('; ')}`);
    log(`Test ${hosting ? 'Hosting' : 'API'} verification ${attempt}/${attempts}: ${failures.join('; ')}. Checking again in ${delayMs / 1000}s.`);
    await wait(delayMs);
  }
}

async function main() {
  const [mode, origin, ...extra] = process.argv.slice(2);
  if (!['--api', '--hosting'].includes(mode) || !origin || extra.length)
    throw new Error('Usage: node scripts/gcp/verify-dev.mjs --api|--hosting HTTPS_ORIGIN');
  await verifyTestDeployment({origin, hosting: mode === '--hosting'});
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href)
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
