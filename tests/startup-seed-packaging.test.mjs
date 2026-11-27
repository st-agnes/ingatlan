import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DEMO_PASSWORD, DEMO_USERS, DEMO_FIXTURES, FEEDBACK_TEST_SCENARIO, DEMO_STREET_SCENARIO, DEMO_ACTIVITY_SCENARIOS} from '../scripts/gcp/demo-data.mjs';
import {TEST_FIXTURE_VERSION, TEST_FIXTURE_PATH, exportTestFixtureCatalog} from '../scripts/gcp/export-demo-data.mjs';

test('the packaged backend catalog contains every canonical fictional account and entity', async()=>{
  await exportTestFixtureCatalog({check:true});
  const packaged=JSON.parse(await readFile(TEST_FIXTURE_PATH,'utf8'));
  assert.equal(packaged.version,TEST_FIXTURE_VERSION);
  assert.equal(packaged.password,DEMO_PASSWORD);
  assert.deepEqual(packaged.users,DEMO_USERS);
  assert.deepEqual(packaged.fixtures,DEMO_FIXTURES);
  assert.deepEqual(packaged.feedbackScenarios,[FEEDBACK_TEST_SCENARIO]);
  assert.deepEqual(packaged.activityScenarios,DEMO_ACTIVITY_SCENARIOS);
  assert.equal(packaged.activityScenarios.length,187);
  assert.equal(packaged.users.length,17);
  assert.equal(packaged.users.filter(user=>user.accountType==='agent').length,4);
  assert.equal(packaged.fixtures.filter(item=>item.kind==='property').length,481);
  assert.equal(packaged.fixtures.filter(item=>item.kind==='search').length,499);
  for(const fixture of packaged.fixtures.filter(item=>item.kind==='property')){
    const streetFixture=[DEMO_STREET_SCENARIO.firstProperty,DEMO_STREET_SCENARIO.secondProperty].includes(fixture.key);
    if(streetFixture){assert.equal(fixture.input.houseNumber,'99999');assert.match(fixture.input.streetId,/^street:[a-f0-9]{24}$/);}
    else{assert.equal(fixture.input.street,'OTTHONRA TEST');assert.match(fixture.input.houseNumber,/^[1-9][0-9]*$/);}
    for(const privateField of ['latitude','longitude','neighborhoodIds','geocodingProvider']){
      assert.equal(Object.hasOwn(fixture.input,privateField),false,'Point coordinates and membership must be assigned by the backend startup path');
    }
  }
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
  assert.match(deployment, /verify-dev\.mjs --api/);
  assert.match(deployment, /verify-dev\.mjs --hosting/);
  const verifier=await readFile(new URL('../scripts/gcp/verify-dev.mjs',import.meta.url),'utf8');
  assert.match(verifier, /import \{TEST_FIXTURE_VERSION\} from '\.\/export-demo-data\.mjs'/);
  assert.match(verifier, /health\?\.testDataVersion === TEST_FIXTURE_VERSION/);
  const runConfig=await readFile(new URL('../scripts/gcp/prepare-run.mjs',import.meta.url),'utf8');
  assert.match(runConfig,/literal\('Database__SeedTestFixtures', 'true'\)/);
  assert.match(runConfig,/literal\('Deployment__Environment', 'test'\)/);
});
