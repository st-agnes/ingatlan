import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DEMO_PASSWORD, DEMO_USERS, DEMO_FIXTURES} from '../scripts/gcp/demo-data.mjs';
import {TEST_FIXTURE_VERSION, TEST_FIXTURE_PATH, exportTestFixtureCatalog} from '../scripts/gcp/export-demo-data.mjs';

test('the packaged backend catalog contains every canonical fictional account and entity', async()=>{
  await exportTestFixtureCatalog({check:true});
  const packaged=JSON.parse(await readFile(TEST_FIXTURE_PATH,'utf8'));
  assert.equal(packaged.version,TEST_FIXTURE_VERSION);
  assert.equal(packaged.password,DEMO_PASSWORD);
  assert.deepEqual(packaged.users,DEMO_USERS);
  assert.deepEqual(packaged.fixtures,DEMO_FIXTURES);
  assert.equal(packaged.users.length,12);
  assert.equal(packaged.users.filter(user=>user.accountType==='agent').length,3);
  assert.equal(packaged.fixtures.filter(item=>item.kind==='property').length,114);
  assert.equal(packaged.fixtures.filter(item=>item.kind==='search').length,112);
});

test('check mode rejects missing or drifted packaged data without replacing it', async()=>{
  const directory=await mkdtemp(join(tmpdir(),'otthonra-startup-fixtures-'));
  const output=join(directory,'data/catalog.json');
  try{
    await assert.rejects(exportTestFixtureCatalog({output,check:true}),/missing/);
    await exportTestFixtureCatalog({output});
    await exportTestFixtureCatalog({output,check:true});
    await writeFile(output,'{"version":"stale"}\n');
    await assert.rejects(exportTestFixtureCatalog({output,check:true}),/differ/);
    assert.equal(await readFile(output,'utf8'),'{"version":"stale"}\n');
  }finally{await rm(directory,{recursive:true,force:true});}
});

test('deployment requires startup seed readiness and does not run the external API importer',async()=>{
  const deployment=await readFile(new URL('../scripts/gcp/deploy-dev.sh',import.meta.url),'utf8');
  assert.doesNotMatch(deployment,/seed-dev\.mjs/);
  assert.ok(deployment.includes(`health.testDataVersion !== '${TEST_FIXTURE_VERSION}'`));
  assert.ok(deployment.includes(`backend.testDataVersion !== '${TEST_FIXTURE_VERSION}'`));
  const runConfig=await readFile(new URL('../scripts/gcp/prepare-run.mjs',import.meta.url),'utf8');
  assert.match(runConfig,/literal\('Database__SeedTestFixtures', 'true'\)/);
  assert.match(runConfig,/literal\('Deployment__Environment', 'test'\)/);
});
