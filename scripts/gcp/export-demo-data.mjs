/** Package the canonical fictional catalog for the test backend, without API calls. */
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {DEMO_PASSWORD, DEMO_USERS, DEMO_FIXTURES, DEMO_FEEDBACK_SCENARIOS} from './demo-data.mjs';

export const TEST_FIXTURE_VERSION = '20261110-test-fixtures-v4';
export const TEST_FIXTURE_PATH = fileURLToPath(new URL('../../backend/Otthonra.Api/Data/test-fixtures.json', import.meta.url));
export function renderTestFixtureCatalog() {
  return JSON.stringify({version:TEST_FIXTURE_VERSION, password:DEMO_PASSWORD, users:DEMO_USERS, fixtures:DEMO_FIXTURES, feedbackScenarios:DEMO_FEEDBACK_SCENARIOS}, null, 2) + '\n';
}
export async function exportTestFixtureCatalog({output=TEST_FIXTURE_PATH, check=false}={}) {
  const expected = renderTestFixtureCatalog();
  if (check) {
    let actual;
    try { actual = await readFile(output, 'utf8'); }
    catch (error) {
      if (error.code === 'ENOENT') throw new Error('Packaged test fixtures are missing. Run node scripts/gcp/export-demo-data.mjs.');
      throw error;
    }
    if (actual !== expected) throw new Error('Packaged test fixtures differ from the canonical catalog. Run node scripts/gcp/export-demo-data.mjs.');
  } else {
    await mkdir(dirname(output), {recursive:true});
    await writeFile(output, expected);
  }
  return {version:TEST_FIXTURE_VERSION, users:DEMO_USERS.length, properties:DEMO_FIXTURES.filter(item=>item.kind==='property').length, searches:DEMO_FIXTURES.filter(item=>item.kind==='search').length};
}
async function main() {
  const args=process.argv.slice(2);
  if(args.length>1 || args.length===1 && args[0]!=='--check') throw new Error('Usage: node scripts/gcp/export-demo-data.mjs [--check]');
  const result=await exportTestFixtureCatalog({check:args[0]==='--check'});
  console.log(`Test backend fixtures ${args[0]==='--check'?'verified':'packaged'}: ${result.users} users, ${result.properties} properties, ${result.searches} searches.`);
}
if(process.argv[1] && import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error=>{console.error(error.message);process.exitCode=1;});
}
