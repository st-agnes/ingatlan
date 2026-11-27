import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile,mkdir,mkdtemp,writeFile,rm,access} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {BROWSER_GROUPS} from '../scripts/ci/browser-runner.mjs';
import {REQUIRED_JOBS,REQUIRED_JOB_NAMES,readCheckoutIdentity,makeValidationReceipt,receiptArtifactName} from '../scripts/ci/reuse-validation.mjs';

const root=new URL('../',import.meta.url),workflowText=await readFile(new URL('.github/workflows/ci.yml',root),'utf8');
const require=createRequire(import.meta.url);
let parseYaml;
try {parseYaml=require('../.local/ci-tools/node_modules/yaml').parse;}
catch {
 // The CI installs pinned yaml@2.8.2. Local managed workspaces may instead use
 // their supplied PyYAML; BaseLoader preserves GitHub's literal `on` key.
 parseYaml=value=>JSON.parse(execFileSync('python3',['-c','import base64,json,sys,yaml; print(json.dumps(yaml.load(base64.b64decode(sys.argv[1]).decode(), Loader=yaml.BaseLoader)))',Buffer.from(value).toString('base64')],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:5000}));
}
const workflow=parseYaml(workflowText),jobs=workflow.jobs;
const runText=job=>(job.steps||[]).map(step=>step.run||'').join('\n');
const scriptFor=id=>jobs[id].steps.find(step=>step.uses==='actions/github-script@v7').with.script;
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const browserFiles=[
 'tests/browser.test.mjs','tests/street-search-browser.test.mjs','tests/attributes-browser.test.mjs',
 'tests/areas-browser.test.mjs','tests/neighborhood-search-browser.test.mjs','tests/neighborhood-map-browser.test.mjs',
 'tests/wizard-dock-browser.test.mjs','tests/seller-form-browser.test.mjs','tests/broker-browser.test.mjs',
 'tests/interaction-browser.test.mjs','tests/matching-browser.test.mjs','tests/seller-feedback-browser.test.mjs','tests/conversation-layout-browser.test.mjs',
 'tests/onboarding-browser.test.mjs','tests/landing-refund-browser.test.mjs','tests/tab-resume-browser.test.mjs',
 'tests/activity-notifications-browser.test.mjs','tests/public-listings-browser.test.mjs'
];

test('CI validates every PR and manual run without duplicate feature-branch push jobs',()=>{
 assert.deepEqual(workflow.on.push.branches,['main','codex/google-cloud-test']);
 assert.ok(Object.hasOwn(workflow.on,'pull_request')&&Object.hasOwn(workflow.on,'workflow_dispatch'));
 assert.ok(!Object.hasOwn(workflow.on,'pull_request_target'));
 for(const event of Object.values(workflow.on))if(event&&typeof event==='object')assert.ok(!event.paths&&!event['paths-ignore'],'Changed-path heuristics must not drop tests');
 assert.equal(workflow.permissions.contents,'read');assert.equal(workflow.permissions.actions,'read');
 assert.ok(Object.values(workflow.permissions).every(value=>value==='read'));
});

test('every required full group runs unless the verified plan explicitly reuses an identical tree',()=>{
 assert.deepEqual(Object.keys(jobs).sort(),['plan',...REQUIRED_JOBS,'ci-validation'].sort());
 for(const name of REQUIRED_JOBS.filter(name=>name!=='guided-forms-and-discovery')){
  assert.equal(jobs[name].needs,'plan',name);
  assert.equal(jobs[name].if,"needs.plan.outputs.reuse != 'true'",name);
 }
 assert.equal(jobs['guided-forms-and-discovery'].name,'Guided forms and discovery controls');
 assert.equal(jobs['guided-forms-and-discovery'].if,'always()');
 assert.deepEqual(jobs['guided-forms-and-discovery'].needs,['plan','browser-tests']);
 assert.equal(jobs['ci-validation'].if,'always()');
 assert.deepEqual(jobs['ci-validation'].needs,['plan',...REQUIRED_JOBS]);
});

test('static browser shards retain every existing suite once and leave actual hosted flows on both databases',async()=>{
 assert.deepEqual(Object.keys(BROWSER_GROUPS).sort(),jobs['browser-tests'].strategy.matrix.group.toSorted());
 const files=Object.values(BROWSER_GROUPS).flat();
 assert.equal(new Set(files).size,files.length);assert.deepEqual(files.toSorted(),browserFiles.toSorted());
 for(const file of files)await access(new URL(file,root));
 const main=runText(jobs['build-and-test']);
 for(const file of files)assert.ok(!main.includes(`node ${file} `),file+' must not be repeated in a database matrix');
 for(const file of ['tests/hosted-browser.test.mjs','tests/feedback-scenario-browser.test.mjs']){
  assert.match(main,new RegExp('node '+file.replaceAll('.','\\.')+' http://127\\.0\\.0\\.1:3000'));
  assert.ok(!files.includes(file));
 }
 assert.deepEqual(jobs['build-and-test'].strategy.matrix.mysql,['8.0','8.4']);
 assert.equal(jobs['build-and-test'].name,'Build and test (MySQL ${{ matrix.mysql }})');
});

test('every database service has real credentials, health checks, ports and an isolated application environment',()=>{
 for(const name of ['build-and-test','postal-street-integration','onboarding-integration','seed-importer']){
  const job=jobs[name],mysql=job.services.mysql;
  assert.equal(mysql.env.MYSQL_DATABASE,'otthonra_ci',name);assert.equal(mysql.env.MYSQL_USER,'otthonra');
  assert.equal(mysql.env.MYSQL_PASSWORD,'ci-only-password');assert.equal(mysql.env.MYSQL_ROOT_PASSWORD,'ci-only-root-password');
  assert.deepEqual(mysql.ports,['3306:3306']);assert.match(mysql.options,/--health-cmd=.*SELECT 1/);
  assert.match(job.env.ConnectionStrings__MySql,/^Server=127\.0\.0\.1;Port=3306;Database=otthonra_ci;User=otthonra;/);
  assert.equal(String(job.env.Database__Initialize),'true');
 }
 const importer=jobs['seed-importer'];
 assert.deepEqual(importer.strategy.matrix.mysql,['8.0','8.4']);
 assert.equal(importer.env.ASPNETCORE_ENVIRONMENT,'Production');assert.equal(importer.env.Deployment__Environment,'test');
 assert.equal(String(importer.env.Database__SeedDemo),'false');assert.equal(String(importer.env.Database__SeedTestFixtures),'false');
 assert.equal(String(importer.env.Geocoding__EnableTestGeocoder),'true');
 assert.match(runText(importer),/node backend\/seed-smoke\.mjs http:\/\/127\.0\.0\.1:3000/);
 assert.ok(!runText(jobs['build-and-test']).includes('backend/seed-smoke.mjs'),'The paced importer must run independently, not twice');
});

test('backend matrices retain actual authentication, schema upgrades, matching, refunds and fixture lifecycle cases',()=>{
 const main=runText(jobs['build-and-test']);
 assert.equal(String(jobs['build-and-test'].env.OTTHONRA_TEST_MYSQL_CACHING_SHA2),'true');
 for(const required of ['IDENTIFIED WITH caching_sha2_password','dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj',
  'node tests/development-smoke.mjs','node backend/smoke.mjs','node backend/neighborhood-smoke.mjs',
  'node backend/matching-smoke.mjs','node backend/seller-feedback-smoke.mjs','backend/fixtures/previous-schema.sql',
  'node backend/upgrade-smoke.mjs','node backend/attributes-smoke.mjs','node backend/areas-smoke.mjs',
  'node backend/seller-form-smoke.mjs','node backend/broker-smoke.mjs','node backend/interaction-smoke.mjs',
  'node backend/landing-refund-smoke.mjs','node backend/landing-selection-smoke.mjs',
  'node backend/deployment-smoke.mjs','node backend/startup-seed-smoke.mjs'])assert.ok(main.includes(required),required);
 for(const mode of ['--initial','--preserved','--reset','--production'])assert.ok(main.includes('startup-seed-smoke.mjs http://127.0.0.1:3000 '+mode),mode);
 assert.ok(main.includes('K_REVISION=ci-fixtures-a')&&main.includes('K_REVISION=ci-fixtures-b'));
 assert.ok(main.indexOf('backend/fixtures/previous-schema.sql')<main.indexOf('backend/upgrade-smoke.mjs'));
});

test('dependency caches never cache build output and receipts overwrite only their explicit safe proof file',async()=>{
 const dotnet=parseYaml(await readFile(new URL('.github/actions/ci-dotnet/action.yml',root),'utf8'));
 const node=parseYaml(await readFile(new URL('.github/actions/ci-node/action.yml',root),'utf8'));
 const nuget=dotnet.runs.steps.find(step=>step.uses==='actions/cache@v4');assert.equal(nuget.with.path,'~/.nuget/packages');
 const browser=node.runs.steps.find(step=>step.uses==='actions/cache@v4');assert.equal(browser.with.path,'~/.cache/ms-playwright');
 assert.match(runText(node.runs),/playwright@1\.56\.1/);assert.match(runText(node.runs),/playwright install --only-shell chromium/);
 const docker=jobs['container-package'].steps.find(step=>step.uses==='docker/build-push-action@v6');
 assert.equal(docker.with.file,'backend/Dockerfile');assert.equal(String(docker.with.push),'false');
 assert.match(docker.with['cache-from'],/^type=gha,/);assert.match(docker.with['cache-to'],/^type=gha,mode=max,/);
 const artifact=jobs['ci-validation'].steps.find(step=>step.uses==='actions/upload-artifact@v4');
 assert.equal(artifact.if,"steps.validation.outputs.full_validation == 'true'");
 assert.equal(artifact.with.path,'.local/ci/receipt.json');assert.equal(artifact.with['if-no-files-found'],'error');
 assert.equal(String(artifact.with['include-hidden-files']),'true');assert.equal(String(artifact.with.overwrite),'true');
 assert.match(runText(jobs['static-checks']),/--ignore-scripts .*yaml@2\.8\.2/);
});

async function fixture(action){
 const directory=await mkdtemp(join(tmpdir(),'otthonra-ci-workflow-'));
 const previousDirectory=process.cwd(),previousEnv={};
 for(const key of ['GITHUB_WORKSPACE','GITHUB_RUN_ATTEMPT','CI_JOB_RESULTS','CI_BROWSER_RESULTS'])previousEnv[key]=process.env[key];
 try{
  await mkdir(join(directory,'.github/workflows'),{recursive:true});await mkdir(join(directory,'scripts/ci'),{recursive:true});
  await writeFile(join(directory,'.github/workflows/ci.yml'),workflowText);
  await writeFile(join(directory,'scripts/ci/reuse-validation.mjs'),await readFile(new URL('scripts/ci/reuse-validation.mjs',root)));
  const git=(...args)=>execFileSync('git',args,{cwd:directory,encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
  git('init','--quiet');git('add','.');git('-c','user.name=CI fixture','-c','user.email=ci@example.test','commit','--quiet','-m','Fixture');
  process.chdir(directory);process.env.GITHUB_WORKSPACE=directory;process.env.GITHUB_RUN_ATTEMPT='1';
  const identity=readCheckoutIdentity(directory);
  const context={repo:{owner:'st-agnes',repo:'ingatlan'},payload:{repository:{id:1441962351}},
   sha:identity.checkoutSha,eventName:'pull_request',ref:'refs/pull/35/merge',runId:1000};
  const outputs={reuse:'false',tree:identity.tree,checkout_sha:identity.checkoutSha,workflow_blob_sha:identity.workflowBlobSha};
  const needs={plan:{result:'success',outputs},...Object.fromEntries(REQUIRED_JOBS.map(name=>[name,{result:'success'}]))};
  const state={directory,identity,context,needs,outputs:{},messages:[]};
  state.execute=async(id,github={})=>{
   state.outputs={};process.env.CI_JOB_RESULTS=JSON.stringify(state.needs);process.env.CI_BROWSER_RESULTS=JSON.stringify(state.needs);
   const core={setOutput:(key,value)=>{state.outputs[key]=value;},info:message=>state.messages.push(message)};
   await new AsyncFunction('github','context','core',scriptFor(id))(github,state.context,core);
  };
  await action(state);
 }finally{
  process.chdir(previousDirectory);
  for(const [key,value]of Object.entries(previousEnv))if(value===undefined)delete process.env[key];else process.env[key]=value;
  await rm(directory,{recursive:true,force:true});
 }
}

test('the actual inline PR/manual plan selects full validation and emits the checked-out identity',()=>fixture(async f=>{
 for(const eventName of ['pull_request','workflow_dispatch']){
  f.context.eventName=eventName;await f.execute('plan',{rest:{}});
  assert.equal(f.outputs.reuse,'false');assert.equal(f.outputs.tree,f.identity.tree);
  assert.equal(f.outputs.checkout_sha,f.identity.checkoutSha);assert.equal(f.outputs.workflow_blob_sha,f.identity.workflowBlobSha);
  assert.equal(f.outputs.artifact_name,receiptArtifactName(f.identity.tree));
 }
}));

test('the actual inline aggregate writes one full receipt only after all required jobs succeed',()=>fixture(async f=>{
 await f.execute('ci-validation');assert.equal(f.outputs.full_validation,'true');
 const receipt=JSON.parse(await readFile(join(f.directory,'.local/ci/receipt.json'),'utf8'));
 assert.equal(receipt.tree,f.identity.tree);assert.deepEqual(receipt.requiredJobs,REQUIRED_JOBS);assert.equal(receipt.mode,'full');
}));

test('the actual inline aggregate rejects failed, missing or skipped groups and a failed or changed plan',()=>fixture(async f=>{
 for(const name of REQUIRED_JOBS)for(const result of ['failure','cancelled','skipped',undefined]){
  const before=f.needs[name];if(result===undefined)delete f.needs[name];else f.needs[name]={result};
  await assert.rejects(f.execute('ci-validation'),/requires successful/);f.needs[name]=before;
 }
 f.needs.plan.result='failure';await assert.rejects(f.execute('ci-validation'),/plan did not succeed/);f.needs.plan.result='success';
 f.needs.plan.outputs.tree='0'.repeat(40);await assert.rejects(f.execute('ci-validation'),/checkout identity changed/);
 await assert.rejects(access(join(f.directory,'.local/ci/receipt.json')));
}));

test('the actual inline main plan accepts verified full proof and its aggregate emits no chained receipt',()=>fixture(async f=>{
 f.context.eventName='push';f.context.ref='refs/heads/main';
 const sourceContext={...f.context,eventName:'workflow_dispatch',runId:900};
 const receipt=makeValidationReceipt({context:sourceContext,...f.identity,runAttempt:1,needs:f.needs});
 const archive=execFileSync('python3',['-c',"import base64,io,sys,zipfile\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z: z.writestr('receipt.json',base64.b64decode(sys.argv[1]))\nsys.stdout.buffer.write(b.getvalue())",Buffer.from(JSON.stringify(receipt)).toString('base64')],{stdio:['ignore','pipe','pipe'],timeout:5000});
 const run={id:900,run_attempt:1,head_sha:f.identity.checkoutSha,event:'workflow_dispatch',status:'completed',conclusion:'success',updated_at:new Date().toISOString(),
  path:'.github/workflows/ci.yml',repository:{id:1441962351},head_repository:{id:1441962351}};
 const artifact={id:901,name:receiptArtifactName(f.identity.tree),expired:false,size_in_bytes:archive.length,
  workflow_run:{id:900,repository_id:1441962351,head_repository_id:1441962351,head_sha:f.identity.checkoutSha}};
 const github={rest:{actions:{
  listArtifactsForRepo:async()=>({data:{artifacts:[artifact]}}),getWorkflowRun:async()=>({data:run}),
  downloadArtifact:async()=>({data:archive}),listJobsForWorkflowRun:async()=>({data:{jobs:[...REQUIRED_JOB_NAMES,'Plan CI validation','CI validation'].map(name=>({name,status:'completed',conclusion:'success'}))}})
 },git:{getCommit:async()=>({data:{sha:f.identity.checkoutSha,tree:{sha:f.identity.tree},parents:[]}})},
 repos:{getContent:async({path})=>({data:{type:'file',sha:path==='.github/workflows/ci.yml'?f.identity.workflowBlobSha:f.identity.reuseBlobSha}})}}};
 await f.execute('plan',github);assert.equal(f.outputs.reuse,'true');assert.equal(f.outputs.source_run_id,900);assert.equal(f.outputs.source_attempt,1);
 f.needs.plan.outputs=Object.fromEntries(Object.entries(f.outputs).map(([key,value])=>[key,String(value)]));
 for(const name of REQUIRED_JOBS)f.needs[name]={result:'skipped'};
 await f.execute('ci-validation');assert.equal(f.outputs.full_validation,'false');
 await assert.rejects(access(join(f.directory,'.local/ci/receipt.json')));
}));

test('the unchanged guided-browser check is a strict aggregate for full and verified reused runs',()=>fixture(async f=>{
 await f.execute('guided-forms-and-discovery');
 for(const result of ['failure','cancelled','skipped']){
  f.needs['browser-tests'].result=result;await assert.rejects(f.execute('guided-forms-and-discovery'),/Every browser regression/);
 }
 f.context.eventName='push';f.context.ref='refs/heads/main';
 f.needs.plan.outputs={...f.needs.plan.outputs,reuse:'true',source_run_id:'900',source_attempt:'1'};
 await f.execute('guided-forms-and-discovery');
 f.context.eventName='pull_request';await assert.rejects(f.execute('guided-forms-and-discovery'),/verified main-branch plan/);
}));
