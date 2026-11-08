/** Offline Cloud Shell bootstrap contract checks; no Google services are called. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir,rm,stat} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const helper=join(root,'scripts/gcp/bootstrap-dev.py');
const script=join(root,'scripts/gcp/bootstrap-dev.sh');
const marker='Managed by st-agnes/ingatlan bootstrap-dev.';
const mapping={'google.subject':'assertion.sub','attribute.repository_id':'assertion.repository_id','attribute.repository_owner_id':'assertion.repository_owner_id','attribute.ref':'assertion.ref','attribute.workflow_ref':'assertion.workflow_ref'};
const invoke=(...args)=>spawnSync('python3',[helper,...args],{encoding:'utf8'});
async function temporary(action){const dir=await mkdtemp(join(tmpdir(),'otthonra-bootstrap-'));try{return await action(dir);}finally{await rm(dir,{recursive:true,force:true});}}
async function json(path,value){await writeFile(path,JSON.stringify(value));return path;}
async function executable(path,text){await writeFile(path,text,{mode:0o700});return path;}

test('plan is read-only, verifies billing, and rejects another region before cloud access',async()=>temporary(async dir=>{
 const bin=join(dir,'bin');await mkdir(bin);const calls=join(dir,'calls');
 await executable(join(bin,'gcloud'),'#!/usr/bin/env node\nconst fs=require("node:fs");fs.appendFileSync(process.env.CALLS,JSON.stringify(process.argv.slice(2))+"\\n");const a=process.argv.slice(2).join(" ");if(a.includes("billing projects describe"))console.log(JSON.stringify({billingEnabled:process.env.BILLING!=="false"}));else if(a.includes("projects describe"))console.log(JSON.stringify({lifecycleState:"ACTIVE",projectNumber:"123456789012"}));else process.exit(91);\n');
 const env={...process.env,PATH:bin+':'+process.env.PATH,CALLS:calls};
 const plan=spawnSync('bash',[script,'--project','ingatlan-513620','--plan'],{env,encoding:'utf8'});
 assert.equal(plan.status,0,plan.stderr);assert.match(plan.stdout,/Cloud SQL is continuously billable/);
 const commands=(await readFile(calls,'utf8')).trim().split('\n').map(JSON.parse);assert.equal(commands.length,2);assert.ok(commands.every(a=>a.includes('describe')));
 const denied=spawnSync('bash',[script,'--project','ingatlan-513620','--plan'],{env:{...env,BILLING:'false'},encoding:'utf8'});assert.notEqual(denied.status,0);assert.match(denied.stderr,/billing account/);
 const before=await readFile(calls,'utf8');const other=spawnSync('bash',[script,'--project','ingatlan-513620','--region','us-central1','--plan'],{env,encoding:'utf8'});assert.notEqual(other.status,0);assert.match(other.stderr,/only europe-west1/);assert.equal(await readFile(calls,'utf8'),before);
}));

test('secret creation, validation and gcloud flag files keep credentials private and reusable',async()=>temporary(async dir=>{
 const secret=join(dir,'mysql'),flags=join(dir,'user.json'),rootFlags=join(dir,'root.json');const connection='ingatlan-513620:europe-west1:otthonra-mysql-dev';
 let result=invoke('make-secret',secret,'mysql',connection);assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'');
 const original=await readFile(secret,'utf8');assert.match(original,/^ConnectionProtocol=Tcp;Server=127\.0\.0\.1;Port=3306;/);assert.equal((await stat(secret)).mode&0o777,0o600);
 for(let i=0;i<2;i++){result=invoke('secret-value',secret,'mysql',connection);assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'');assert.equal(await readFile(secret,'utf8'),original);}
 result=invoke('user-flags',secret,flags);assert.equal(result.status,0,result.stderr);const values=JSON.parse(await readFile(flags,'utf8'));assert.deepEqual(Object.keys(values),['--password']);assert.match(values['--password'],/^[0-9a-f]{64}$/);assert.ok(original.includes('Password='+values['--password']+';'));assert.equal((await stat(flags)).mode&0o777,0o600);
 result=invoke('root-flags',rootFlags);assert.equal(result.status,0,result.stderr);assert.match(JSON.parse(await readFile(rootFlags,'utf8'))['--root-password'],/^[0-9a-f]{64}$/);
 const legacy=original.replace('ConnectionProtocol=Tcp;Server=127.0.0.1;Port=3306;',`ConnectionProtocol=Unix;Server=/cloudsql/${connection};`);await writeFile(secret,legacy);
 result=invoke('secret-value',secret,'mysql','other-project:europe-west1:otthonra-mysql-dev');assert.notEqual(result.status,0);assert.ok(!result.stderr.includes(values['--password']));assert.equal(await readFile(secret,'utf8'),legacy);
 await writeFile(secret,original);result=invoke('secret-value',secret,'mysql','../invalid-instance');assert.notEqual(result.status,0);assert.ok(!result.stderr.includes(values['--password']));
}));

test('owned SQL configuration accepts reruns but rejects drift and foreign resources',async()=>temporary(async dir=>{
 const path=join(dir,'sql.json');const owned={databaseVersion:'MYSQL_8_4',region:'europe-west1',state:'RUNNABLE',settings:{userLabels:{app:'otthonra',environment:'dev','managed-by':'otthonra-bootstrap'},edition:'ENTERPRISE',tier:'db-f1-micro',availabilityType:'ZONAL',dataDiskType:'PD_SSD',dataDiskSizeGb:'10',storageAutoResize:true,storageAutoResizeLimit:'20',backupConfiguration:{enabled:true,backupRetentionSettings:{retainedBackups:7}},ipConfiguration:{sslMode:'ENCRYPTED_ONLY',authorizedNetworks:[]}}};
 await json(path,owned);for(let i=0;i<2;i++){const r=invoke('sql',path,'europe-west1');assert.equal(r.status,0,r.stderr);}
 for(const mutate of [x=>x.settings.userLabels.environment='prod',x=>x.settings.tier='db-custom-8-30720',x=>x.settings.storageAutoResizeLimit='0',x=>x.settings.backupConfiguration.enabled=false,x=>x.settings.ipConfiguration.authorizedNetworks=[{value:'0.0.0.0/0'}]]){const value=structuredClone(owned);mutate(value);await json(path,value);assert.notEqual(invoke('sql',path,'europe-west1').status,0);}
}));

test('disabled pools and providers or incorrect claim mappings are never adopted',async()=>temporary(async dir=>{
 const path=join(dir,'identity.json'),condition='reviewed-condition';const provider={description:marker,state:'ACTIVE',attributeCondition:condition,attributeMapping:mapping,oidc:{issuerUri:'https://token.actions.githubusercontent.com'}};
 await json(path,provider);assert.equal(invoke('provider',path,condition).status,0);
 for(const mutate of [x=>x.disabled=true,x=>x.attributeMapping={'google.subject':'assertion.sub'},x=>x.attributeCondition='true',x=>x.oidc.issuerUri='https://untrusted.example']){const value=structuredClone(provider);mutate(value);await json(path,value);assert.notEqual(invoke('provider',path,condition).status,0);}
 await json(path,{description:marker,disabled:true});assert.notEqual(invoke('description',path).status,0);
 await json(path,{description:marker,state:'ACTIVE'});assert.equal(invoke('description',path).status,0);
}));

test('Firebase operation polling completes pending work, retries only reads and fails immediately on operation errors',async()=>temporary(async dir=>{
 const bin=join(dir,'bin');await mkdir(bin);const state=join(dir,'state.json');await json(state,{calls:0});
 await executable(join(bin,'gcloud'),'#!/bin/sh\nprintf fake-bootstrap-access-token\n');
 await executable(join(bin,'sleep'),'#!/bin/sh\nexit 0\n');
 await executable(join(bin,'curl'),`#!/usr/bin/env node
const fs=require('node:fs'),args=process.argv.slice(2),file=process.env.POLL_STATE,s=JSON.parse(fs.readFileSync(file,'utf8'));s.calls++;fs.writeFileSync(file,JSON.stringify(s));const output=args[args.indexOf('--output')+1];let code='200',body;if(process.env.POLL_ERROR==='yes')body={done:true,error:{message:'Permission denied.',privateConfig:'This detail must not be printed'}};else if(s.calls===1){code='503';body={error:{message:'Transient read'}};}else body=s.calls===2?{done:false}:{done:true};fs.writeFileSync(output,JSON.stringify(body));process.stdout.write(code);
`);
 const source=await readFile(script,'utf8');const start=source.indexOf('rest() {'),end=source.indexOf('code="$(rest GET "https://firebase.googleapis.com/v1beta1/projects/',start);assert.ok(start>0&&end>start);
 const program=join(dir,'poll.sh');await writeFile(program,'set -euo pipefail\nhelper="$HELPER"\ntemporary="$POLL_TEMP"\nproject_id=ingatlan-513620\n'+source.slice(start,end)+'\nwait_operation operations/test\n');
 const env={...process.env,PATH:bin+':'+process.env.PATH,HELPER:helper,POLL_TEMP:dir,POLL_STATE:state};
 const done=spawnSync('bash',[program],{env,encoding:'utf8',timeout:4000});assert.equal(done.status,0,done.stderr);assert.equal(JSON.parse(await readFile(state,'utf8')).calls,3);assert.ok(!done.stdout.includes('fake-bootstrap-access-token'));
 await json(state,{calls:0});const failed=spawnSync('bash',[program],{env:{...env,POLL_ERROR:'yes'},encoding:'utf8',timeout:4000});assert.notEqual(failed.status,0);assert.match(failed.stderr,/provisioning operation failed/);assert.equal(JSON.parse(await readFile(state,'utf8')).calls,1);assert.ok(!failed.stderr.includes('This detail must not be printed'));assert.ok(!failed.stderr.includes('fake-bootstrap-access-token'));
}));

test('Cloud SQL creation uses beta for ownership labels and leaves a short phase summary after CLI help',async()=>temporary(async dir=>{
 const bin=join(dir,'bin');await mkdir(bin);const calls=join(dir,'calls');
 // Model the documented CLI contract: --labels is available only on beta create.
 await executable(join(bin,'gcloud'),`#!/usr/bin/env node
const fs=require('node:fs'),a=process.argv.slice(2),command=a.filter(v=>!v.startsWith('--')).join(' ');fs.appendFileSync(process.env.CALLS,JSON.stringify(a)+'\\n');
if(command.startsWith('billing projects describe '))console.log(JSON.stringify({billingEnabled:true}));
else if(command.startsWith('projects describe '))console.log(JSON.stringify({lifecycleState:'ACTIVE',projectNumber:'123456789012'}));
else if(command.includes('sql instances create ')){
 if(!command.startsWith('beta sql instances create ')&&a.some(v=>v.startsWith('--labels='))){fs.writeSync(2,'ERROR: unrecognized arguments: --labels\\nUsage: gcloud sql instances create INSTANCE [FLAGS]\\n');process.exit(2);}
 if(!a.some(v=>v.startsWith('--labels=')))process.exit(93);
 console.log('SQL creation accepted');
}else if(command.includes(' describe ')){console.error('NOT_FOUND: fixture resource does not exist');process.exit(1);}
else if(!command.startsWith('services enable ')&&!command.startsWith('iam service-accounts create ')&&!command.startsWith('artifacts repositories create '))process.exit(92);
`);
 const source=await readFile(script,'utf8'),end=source.indexOf('if ! describe "$temporary/database.json"');assert.ok(end>0);
 // Run the real bootstrap through SQL creation, then stop before later APIs.
 const prefix=source.slice(0,end).replace('helper="$root/scripts/gcp/bootstrap-dev.py"','helper="$HELPER"');
 const program=join(dir,'create.sh');await writeFile(program,prefix);
 const env={...process.env,PATH:bin+':'+process.env.PATH,CALLS:calls,HELPER:helper};
 const good=spawnSync('bash',[program,'--project','ingatlan-513620'],{env,encoding:'utf8',timeout:5000});assert.equal(good.status,0,good.stderr);
 const commands=(await readFile(calls,'utf8')).trim().split('\n').map(JSON.parse);const creation=commands.find(a=>a.includes('create')&&a.includes('instances'));assert.ok(creation?.includes('beta'));assert.ok(creation.some(a=>a.startsWith('--labels=app=otthonra,environment=dev,')));
 // The former GA invocation reproduces the real failure and must keep the
 // useful fixed phase below the help text, without printing credential flags.
 await writeFile(program,prefix.replace('gc beta sql instances create','gc sql instances create'));
 const bad=spawnSync('bash',[program,'--project','ingatlan-513620'],{env,encoding:'utf8',timeout:5000});assert.equal(bad.status,2);assert.match(bad.stderr,/unrecognized arguments: --labels/);
 assert.match(bad.stderr.trim().split('\n').at(-1),/TELEPÍTÉS MEGÁLLT: Cloud SQL tesztadatbázis \(hibakód: 2\)/);assert.doesNotMatch(bad.stderr,/root-password|flags-file|Password=/);
}));

async function cloudRunFixture(action) {
 return temporary(async dir=>{
  const bin=join(dir,'bin');await mkdir(bin);
  const state=join(dir,'run-state.json');await json(state,{created:false,calls:[]});
  await executable(join(bin,'gcloud'),`#!/usr/bin/env node
const fs=require('node:fs'),args=process.argv.slice(2),path=process.env.RUN_STATE,state=JSON.parse(fs.readFileSync(path,'utf8'));
state.calls.push(args);fs.writeFileSync(path,JSON.stringify(state));
const a=args.filter(v=>!v.startsWith('--'));
if(a.slice(0,3).join(' ')==='run services describe') {
 if(state.created || process.env.RUN_EXISTS==='yes') {
  console.log(JSON.stringify({metadata:{labels:{app:'otthonra',environment:process.env.RUN_FOREIGN==='yes'?'prod':'dev','managed-by':'otthonra-bootstrap','cloud.googleapis.com/location':'europe-west1'}},spec:{template:{spec:{serviceAccountName:'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com'}}}}));
 } else { console.error(process.env.RUN_ERROR);process.exit(1); }
} else if(a.slice(0,2).join(' ')==='run deploy') {
 if(!args.includes('--region=europe-west1') || !args.includes('--project=ingatlan-513620') || !args.includes('otthonra-api-dev')) process.exit(93);
 state.created=true;fs.writeFileSync(path,JSON.stringify(state));
} else process.exit(92);
`);
  const source=await readFile(script,'utf8');
  const describeStart=source.indexOf('describe() {'),describeEnd=source.indexOf('gc projects describe ',describeStart);
  const serviceStart=source.indexOf('if describe "$temporary/service.json"'),serviceEnd=source.indexOf('gc run services add-iam-policy-binding ',serviceStart);
  assert.ok(describeStart>0&&describeEnd>describeStart&&serviceStart>0&&serviceEnd>serviceStart);
  const program=join(dir,'cloud-run.sh');
  await writeFile(program,'set -euo pipefail\ntemporary="$RUN_TEMP"\nhelper="$HELPER"\nregion=europe-west1\nruntime_account=otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com\nlabels=app=otthonra,environment=dev,managed-by=otthonra-bootstrap\ngc() { gcloud --project=ingatlan-513620 --quiet "$@"; }\n'+source.slice(describeStart,describeEnd)+source.slice(serviceStart,serviceEnd));
  const run=error=>spawnSync('bash',[program],{encoding:'utf8',timeout:5000,env:{...process.env,PATH:bin+':'+process.env.PATH,RUN_TEMP:dir,HELPER:helper,RUN_STATE:state,...error}});
  const readState=async()=>JSON.parse(await readFile(state,'utf8'));
  await action({run,readState});
 });
}

test('the actual Cloud Run missing-service error creates the dev service once and reruns preserve it',async()=>{
 await cloudRunFixture(async({run,readState})=>{
  const result=run({RUN_ERROR:'ERROR: (gcloud.run.services.describe) Cannot find service [otthonra-api-dev].'});
  assert.equal(result.status,0,result.stderr);
  let state=await readState();assert.equal(state.created,true);
  assert.equal(state.calls.filter(a=>a.includes('deploy')).length,1);
  const again=run({RUN_ERROR:'must not be used after creation'});assert.equal(again.status,0,again.stderr);
  state=await readState();assert.equal(state.calls.filter(a=>a.includes('deploy')).length,1);
 });
});

test('the reported parentheses variant of Cannot find service enters creation without logging an error',async()=>{
 await cloudRunFixture(async({run,readState})=>{
  const result=run({RUN_ERROR:'ERROR: (gcloud.run.services.describe): cannot find service (otthonra-api-dev)'});
  assert.equal(result.status,0,result.stderr);assert.equal(result.stderr,'');assert.equal((await readState()).created,true);
 });
});

test('access and transport failures remain fatal even when their text also mentions not found',async()=>{
 for(const error of [
  'ERROR: (gcloud.run.services.describe) NOT_FOUND: service not found or Permission denied.',
  'ERROR: (gcloud.run.services.describe) HTTPError: 403 Forbidden. Service not found.',
  'ERROR: (gcloud.run.services.describe) Cannot find service [otthonra-api-dev].\nCould not find the default credentials.',
  'ERROR: (gcloud.run.services.describe) 503 Service unavailable: upstream not found.',
  'ERROR: (gcloud.run.services.describe) Connection timeout: endpoint not found.'
 ]) await cloudRunFixture(async({run,readState})=>{
  const result=run({RUN_ERROR:error});assert.notEqual(result.status,0);assert.equal((await readState()).created,false);
  assert.equal((await readState()).calls.filter(a=>a.includes('deploy')).length,0);
 });
});

test('an unrelated missing service, endpoint or CLI argument is never mistaken for the requested service',async()=>{
 for(const error of [
  'ERROR: (gcloud.run.services.describe) Cannot find service [another-api-dev].',
  'ERROR: (gcloud.run.services.describe) Deployment endpoint was not found. The provided region is invalid.',
  'ERROR: (gcloud.run.services.describe) unrecognized arguments: --not-found'
 ]) await cloudRunFixture(async({run,readState})=>{
  const result=run({RUN_ERROR:error});assert.notEqual(result.status,0);assert.equal((await readState()).created,false);
 });
});

test('an existing foreign Cloud Run service cannot be reused or overwritten',async()=>{
 await cloudRunFixture(async({run,readState})=>{
  const result=run({RUN_EXISTS:'yes',RUN_FOREIGN:'yes'});
  assert.notEqual(result.status,0);assert.match(result.stderr,/not marked as this Otthonra test deployment/);
  assert.equal((await readState()).calls.filter(a=>a.includes('deploy')).length,0);
 });
});

const schedulerJob = () => ({
 name:'projects/ingatlan-513620/locations/europe-west1/jobs/otthonra-refunds-dev',
 description:marker,state:'ENABLED',schedule:'17 * * * *',timeZone:'Etc/UTC',
 httpTarget:{uri:'https://otthonra-api-dev-123456789012.europe-west1.run.app/internal/refunds/run',httpMethod:'POST',oidcToken:{
  serviceAccountEmail:'otthonra-refunds-dev@ingatlan-513620.iam.gserviceaccount.com',
  audience:'https://otthonra-api-dev-123456789012.europe-west1.run.app'
 }}
});

test('refund job ownership, fixed target and verified identity cannot be replaced by a foreign scheduler configuration',async()=>temporary(async dir=>{
 const path=join(dir,'scheduler.json');await json(path,schedulerJob());
 const check=()=>invoke('scheduler',path,'ingatlan-513620','123456789012','europe-west1');
 assert.equal(check().status,0);
 const numeric=schedulerJob();numeric.name=numeric.name.replace('ingatlan-513620','123456789012');await json(path,numeric);assert.equal(check().status,0);
 for(const mutate of [
  x=>x.name=x.name.replace('otthonra-refunds-dev','otthonra-refunds-prod'),
  x=>x.description='Created by another application',
  x=>x.httpTarget.uri='https://another.example/internal/refunds/run',
  x=>x.httpTarget.httpMethod='GET',
  x=>x.httpTarget.oidcToken.audience='https://another.example',
  x=>x.httpTarget.oidcToken.serviceAccountEmail='otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  x=>x.httpTarget.oauthToken={serviceAccountEmail:'other@example.com'},
  x=>x.state='PAUSED'
 ]) {const value=schedulerJob();mutate(value);await json(path,value);assert.notEqual(check().status,0);}
}));

async function schedulerFixture(action) {
 return temporary(async dir=>{
  const bin=join(dir,'bin');await mkdir(bin);const state=join(dir,'scheduler-state.json');await json(state,{job:null,calls:[]});
  await executable(join(bin,'gcloud'),`#!/usr/bin/env node
const fs=require('node:fs'),args=process.argv.slice(2),path=process.env.SCHEDULER_STATE,state=JSON.parse(fs.readFileSync(path,'utf8'));
state.calls.push(args);fs.writeFileSync(path,JSON.stringify(state));
if(!args.includes('--project=ingatlan-513620'))process.exit(96);
const command=args.filter(v=>!v.startsWith('--')).join(' ');
if(command.startsWith('scheduler jobs describe ')) {
 if(process.env.SCHEDULER_ERROR){console.error(process.env.SCHEDULER_ERROR);process.exit(1);}
 if(!state.job){console.error('NOT_FOUND: scheduler job does not exist');process.exit(1);}
 console.log(JSON.stringify(state.job));
} else if(command.startsWith('scheduler jobs create http ')||command.startsWith('scheduler jobs update http ')) {
 if(command.startsWith('scheduler jobs update http ')&&args.some(x=>x.startsWith('--headers=')))process.exit(93);
 if(command.startsWith('scheduler jobs create http ')&&!args.includes('--headers=Content-Type=application/json'))process.exit(92);
 if(command.startsWith('scheduler jobs update http ')&&!args.includes('--update-headers=Content-Type=application/json'))process.exit(91);
 const value=prefix=>args.find(x=>x.startsWith(prefix)).slice(prefix.length);
 if(!args.includes('otthonra-refunds-dev')||value('--location=')!=='europe-west1')process.exit(95);
 state.job={name:'projects/ingatlan-513620/locations/europe-west1/jobs/otthonra-refunds-dev',description:value('--description='),state:'ENABLED',schedule:value('--schedule='),timeZone:value('--time-zone='),httpTarget:{uri:value('--uri='),httpMethod:value('--http-method='),oidcToken:{serviceAccountEmail:value('--oidc-service-account-email='),audience:value('--oidc-token-audience=')}}};
 fs.writeFileSync(path,JSON.stringify(state));
} else if(!command.startsWith('beta services identity create')&&!command.startsWith('projects add-iam-policy-binding ')&&!command.startsWith('run services add-iam-policy-binding '))process.exit(94);
`);
  const source=await readFile(script,'utf8'),describeStart=source.indexOf('describe() {'),describeEnd=source.indexOf('gc projects describe ',describeStart);
  const start=source.indexOf("step 'Óránkénti teszt kreditvisszatérítés'"),end=source.indexOf("step 'GitHub rövid életű Google-identitás'",start);
  assert.ok(start>0&&end>start);
  const program=join(dir,'scheduler.sh');await writeFile(program,'set -euo pipefail\ntemporary="$SCHEDULER_TEMP"\nhelper="$HELPER"\nproject_id=ingatlan-513620\nproject_number=123456789012\nregion=europe-west1\nrefund_account=otthonra-refunds-dev@ingatlan-513620.iam.gserviceaccount.com\nmarker="Managed by st-agnes/ingatlan bootstrap-dev."\ngc() { gcloud --project="$project_id" --quiet "$@"; }\nstep() { :; }\n'+source.slice(describeStart,describeEnd)+source.slice(start,end));
  const run=extra=>spawnSync('bash',[program],{encoding:'utf8',timeout:5000,env:{...process.env,PATH:bin+':'+process.env.PATH,SCHEDULER_TEMP:dir,SCHEDULER_STATE:state,HELPER:helper,...extra}});
  const readState=async()=>JSON.parse(await readFile(state,'utf8'));
  await action({run,readState,state});
 });
}

test('the hourly refund job is provisioned once, updated on rerun and wakes the direct Run service with short-lived OIDC',async()=>{
 await schedulerFixture(async({run,readState})=>{
  const first=run();assert.equal(first.status,0,first.stderr);let state=await readState();
  assert.deepEqual(state.job,schedulerJob());
  const created=state.calls.find(a=>a.includes('create')&&a.includes('scheduler'));assert.ok(created);
  for(const flag of ['--attempt-deadline=180s','--max-retry-attempts=3','--max-retry-duration=1800s','--min-backoff=15s','--max-backoff=120s','--max-doublings=3'])assert.ok(created.includes(flag));
  assert.ok(state.calls.some(a=>a.includes('--role=roles/cloudscheduler.serviceAgent')&&a.includes('--member=serviceAccount:service-123456789012@gcp-sa-cloudscheduler.iam.gserviceaccount.com')));
  const invoker=state.calls.find(a=>a.includes('--role=roles/run.invoker'));
  assert.ok(invoker.includes('otthonra-api-dev'));assert.ok(invoker.includes('--member=serviceAccount:otthonra-refunds-dev@ingatlan-513620.iam.gserviceaccount.com'));
  assert.ok(!state.calls.some(a=>a.includes('--role=roles/iam.serviceAccountTokenCreator')));
  const second=run();assert.equal(second.status,0,second.stderr);state=await readState();
  assert.equal(state.calls.filter(a=>a.includes('scheduler')&&a.includes('create')).length,1);
  assert.equal(state.calls.filter(a=>a.includes('scheduler')&&a.includes('update')).length,1);
 });
});

test('scheduler permission or network failures cannot become permission to create a job',async()=>{
 for(const error of ['PERMISSION_DENIED: job not found or permission denied.','Connection timeout: scheduler job not found.','HTTP 503 service unavailable; job not found.']) {
  await schedulerFixture(async({run,readState})=>{
   const result=run({SCHEDULER_ERROR:error});assert.notEqual(result.status,0);
   const state=await readState();assert.equal(state.job,null);assert.equal(state.calls.filter(a=>a.includes('scheduler')&&(a.includes('create')||a.includes('update'))).length,0);
  });
 }
});

test('a foreign or paused refund job cannot be silently adopted or resumed',async()=>{
 for(const mutate of [x=>x.description='Other deployment',x=>x.state='PAUSED',x=>x.httpTarget.uri='https://different.example/']) {
  await schedulerFixture(async({run,readState,state})=>{
   const job=schedulerJob();mutate(job);await json(state,{job,calls:[]});
   const result=run();assert.notEqual(result.status,0);
   const observed=await readState();assert.deepEqual(observed.job,job);assert.equal(observed.calls.filter(a=>a.includes('scheduler')&&(a.includes('create')||a.includes('update'))).length,0);
  });
 }
});
