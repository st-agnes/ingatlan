import {spawn} from 'node:child_process';
import {createWriteStream} from 'node:fs';
import {mkdir} from 'node:fs/promises';
import {basename,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

// These suites use the local demo or an isolated API fixture. The two hosted
// browser suites remain with the real API on both MySQL versions.
export const BROWSER_GROUPS = Object.freeze({
  locations: Object.freeze([
    'tests/browser.test.mjs',
    'tests/street-search-browser.test.mjs',
    'tests/attributes-browser.test.mjs',
    'tests/areas-browser.test.mjs',
    'tests/neighborhood-search-browser.test.mjs',
    'tests/neighborhood-map-browser.test.mjs'
  ]),
  workspace: Object.freeze([
    'tests/wizard-dock-browser.test.mjs',
    'tests/seller-form-browser.test.mjs',
    'tests/broker-browser.test.mjs',
    'tests/interaction-browser.test.mjs',
    'tests/matching-browser.test.mjs',
    'tests/seller-feedback-browser.test.mjs'
  ]),
  onboarding: Object.freeze([
    'tests/onboarding-browser.test.mjs',
    'tests/landing-refund-browser.test.mjs',
    'tests/tab-resume-browser.test.mjs',
    'tests/activity-notifications-browser.test.mjs'
  ])
});

export async function runBrowserGroup(group, origin) {
  const files = BROWSER_GROUPS[group];
  if (!files) throw new Error('Unknown static browser test group.');
  const url = new URL(origin);
  if (url.protocol !== 'http:' || !['127.0.0.1','localhost','[::1]'].includes(url.hostname)
    || url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
    throw new Error('Browser CI accepts only a plain loopback HTTP origin.');
  }
  const directory = resolve('.local/browser-tests');
  await mkdir(directory, {recursive: true});
  for (const file of files) {
    console.log(`Running ${file}`);
    const log = createWriteStream(resolve(directory, `static-${basename(file)}.log`));
    const child = spawn(process.execPath, [file, url.origin], {stdio: ['ignore','pipe','pipe']});
    child.stdout.on('data', bytes => { process.stdout.write(bytes); log.write(bytes); });
    child.stderr.on('data', bytes => { process.stderr.write(bytes); log.write(bytes); });
    const code = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('close', resolve);
    }).finally(() => log.end());
    if (code !== 0) throw new Error(`${file} failed with exit ${code ?? 'signal'}.`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { await runBrowserGroup(process.argv[2], process.argv[3] || 'http://127.0.0.1:3000'); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
