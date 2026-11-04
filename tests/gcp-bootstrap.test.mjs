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
 const original=await readFile(secret,'utf8');assert.match(original,/ConnectionProtocol=Unix;Server=\/cloudsql\//);assert.equal((await stat(secret)).mode&0o777,0o600);
 for(let i=0;i<2;i++){result=invoke('secret-value',secret,'mysql',connection);assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'');assert.equal(await readFile(secret,'utf8'),original);}
 result=invoke('user-flags',secret,flags);assert.equal(result.status,0,result.stderr);const values=JSON.parse(await readFile(flags,'utf8'));assert.deepEqual(Object.keys(values),['--password']);assert.match(values['--password'],/^[0-9a-f]{64}$/);assert.ok(original.includes('Password='+values['--password']+';'));assert.equal((await stat(flags)).mode&0o777,0o600);
 result=invoke('root-flags',rootFlags);assert.equal(result.status,0,result.stderr);assert.match(JSON.parse(await readFile(rootFlags,'utf8'))['--root-password'],/^[0-9a-f]{64}$/);
 result=invoke('secret-value',secret,'mysql','other-project:europe-west1:otthonra-mysql-dev');assert.notEqual(result.status,0);assert.ok(!result.stderr.includes(values['--password']));assert.equal(await readFile(secret,'utf8'),original);
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
const fs=require('node:fs'),args=process.argv.slice(2),file=process.env.POLL_STATE,s=JSON.parse(fs.readFileSync(file,'utf8'));s.calls++;fs.writeFileSync(file,JSON.stringify(s));const output=args[args.indexOf('--output')+1];let code='200',body;if(process.env.POLL_ERROR==='yes')body={done:true,error:{message:'This detail must not be printed'}};else if(s.calls===1){code='503';body={error:{message:'Transient read'}};}else body=s.calls===2?{done:false}:{done:true};fs.writeFileSync(output,JSON.stringify(body));process.stdout.write(code);
`);
 const source=await readFile(script,'utf8');const start=source.indexOf('rest() {'),end=source.indexOf('code="$(rest GET "https://firebase.googleapis.com/v1beta1/projects/',start);assert.ok(start>0&&end>start);
 const program=join(dir,'poll.sh');await writeFile(program,'set -euo pipefail\nhelper="$HELPER"\ntemporary="$POLL_TEMP"\n'+source.slice(start,end)+'\nwait_operation operations/test\n');
 const env={...process.env,PATH:bin+':'+process.env.PATH,HELPER:helper,POLL_TEMP:dir,POLL_STATE:state};
 const done=spawnSync('bash',[program],{env,encoding:'utf8',timeout:4000});assert.equal(done.status,0,done.stderr);assert.equal(JSON.parse(await readFile(state,'utf8')).calls,3);assert.ok(!done.stdout.includes('fake-bootstrap-access-token'));
 await json(state,{calls:0});const failed=spawnSync('bash',[program],{env:{...env,POLL_ERROR:'yes'},encoding:'utf8',timeout:4000});assert.notEqual(failed.status,0);assert.match(failed.stderr,/provisioning operation failed/);assert.equal(JSON.parse(await readFile(state,'utf8')).calls,1);assert.ok(!failed.stderr.includes('This detail must not be printed'));assert.ok(!failed.stderr.includes('fake-bootstrap-access-token'));
}));
