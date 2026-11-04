/** Secret upgrades are local fixtures/mocked Google commands: no cloud calls. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp, mkdir, readFile, writeFile, rm, stat} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const helper=join(root,'scripts/gcp/bootstrap-dev.py');
const bootstrap=join(root,'scripts/gcp/bootstrap-dev.sh');
const connection='ingatlan-513620:europe-west1:otthonra-mysql-dev';
const password='a'.repeat(64), jwt='b'.repeat(96);
const prefix=`ConnectionProtocol=Unix;Server=/cloudsql/${connection};Database=otthonra_dev;User ID=otthonra_dev;Password=`;
const oldOptions=';SslMode=None;MaximumPoolSize=10;ConnectionTimeout=15;DefaultCommandTimeout=30;';
const newOptions=';SslMode=None;AllowPublicKeyRetrieval=True;MaximumPoolSize=10;ConnectionTimeout=15;DefaultCommandTimeout=30;';
const legacy=prefix+password+oldOptions, upgraded=prefix+password+newOptions;
const invoke=(...args)=>spawnSync('python3',[helper,...args],{encoding:'utf8',timeout:5000});
async function temporary(action){const dir=await mkdtemp(join(tmpdir(),'otthonra-mysql-upgrade-'));try{return await action(dir);}finally{await rm(dir,{recursive:true,force:true});}}

test('new managed Unix secrets enable RSA retrieval without changing socket, TLS tunnel or bounded pool selectors',async()=>temporary(async dir=>{
 const path=join(dir,'mysql');const result=invoke('make-secret',path,'mysql',connection);
 assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'');
 const value=await readFile(path,'utf8');assert.ok(value.startsWith(prefix));assert.ok(value.endsWith(newOptions));
 assert.equal((await stat(path)).mode&0o777,0o600);
 assert.equal(invoke('secret-value',path,'mysql',connection).status,0);
 const flags=join(dir,'user.json');assert.equal(invoke('user-flags',path,flags).status,0);
 const sqlPassword=JSON.parse(await readFile(flags,'utf8'))['--password'];
 assert.match(sqlPassword,/^[0-9a-f]{64}$/);assert.ok(value.includes('Password='+sqlPassword+';'));
}));

test('legacy conversion preserves the exact existing password and is repeatable without rewriting the source',async()=>temporary(async dir=>{
 const source=join(dir,'source'),destination=join(dir,'destination');await writeFile(source,legacy);await writeFile(destination,'prior',{mode:0o644});
 assert.equal(invoke('secret-value',source,'mysql',connection).status,0);
 const result=invoke('upgrade-mysql-secret',source,destination,connection);
 assert.equal(result.status,0,result.stderr);assert.equal(result.stdout.trim(),'changed');assert.equal(result.stderr,'');
 assert.equal(await readFile(source,'utf8'),legacy);assert.equal(await readFile(destination,'utf8'),upgraded);
 assert.equal((await stat(destination)).mode&0o777,0o600);
 const second=invoke('upgrade-mysql-secret',destination,join(dir,'second'),connection);
 assert.equal(second.status,0,second.stderr);assert.equal(second.stdout.trim(),'unchanged');
 assert.equal(await readFile(join(dir,'second'),'utf8'),upgraded);
 assert.ok(!(result.stdout+result.stderr+second.stdout+second.stderr).includes(password));
}));

test('TCP, foreign sockets and unexpected options are rejected before a destination can be changed',async()=>temporary(async dir=>{
 const source=join(dir,'source'),destination=join(dir,'destination');
 for(const value of [legacy.replace('ConnectionProtocol=Unix','ConnectionProtocol=Tcp'),legacy.replace(connection,'another-project-123:europe-west1:otthonra-mysql-dev'),legacy.replace('otthonra_dev;User ID=otthonra_dev','other_db;User ID=otthonra_dev'),legacy.replace('MaximumPoolSize=10','MaximumPoolSize=100'),legacy+'AllowPublicKeyRetrieval=True;',legacy.replace(password,'must-not-print-this-password')]){
  await writeFile(source,value);await writeFile(destination,'untouched');
  const result=invoke('upgrade-mysql-secret',source,destination,connection);
  assert.notEqual(result.status,0);assert.equal(result.stdout,'');assert.equal(await readFile(destination,'utf8'),'untouched');
  assert.ok(!result.stderr.includes(password));assert.ok(!result.stderr.includes('must-not-print-this-password'));
 }
 await writeFile(source,legacy.replace(connection,'../untrusted-socket'));
 const result=invoke('upgrade-mysql-secret',source,destination,'../untrusted-socket');
 assert.notEqual(result.status,0);assert.equal(await readFile(destination,'utf8'),'untouched');
}));

async function bootstrapFixture(modify,action){
 return temporary(async dir=>{
  const bin=join(dir,'bin');await mkdir(bin);const statePath=join(dir,'state.json');
  const initial={mysql:legacy,jwt,versions:0,calls:[],foreign:false};modify(initial);await writeFile(statePath,JSON.stringify(initial));
  await writeFile(join(bin,'gcloud'),`#!/usr/bin/env node
const fs=require('node:fs'),file=process.env.MYSQL_STATE,s=JSON.parse(fs.readFileSync(file,'utf8')),args=process.argv.slice(2);s.calls.push(args);fs.writeFileSync(file,JSON.stringify(s));const a=args.filter(v=>!v.startsWith('--')),command=a.slice(0,3).join(' ');
if(command==='sql users list')console.log(JSON.stringify([{name:'otthonra_dev',host:'%'}]));
else if(a.slice(0,2).join(' ')==='secrets describe')console.log(JSON.stringify({labels:{app:'otthonra',environment:s.foreign?'prod':'dev','managed-by':'otthonra-bootstrap'}}));
else if(command==='secrets versions access'){const name=args.find(x=>x.startsWith('--secret=')).slice('--secret='.length);process.stdout.write(name==='otthonra-mysql-dev'?s.mysql:s.jwt);}
else if(command==='secrets versions add'){if(a[3]!=='otthonra-mysql-dev')process.exit(93);const path=args.find(x=>x.startsWith('--data-file=')).slice('--data-file='.length);if((fs.statSync(path).mode&0o777)!==0o600)process.exit(94);s.mysql=fs.readFileSync(path,'utf8');s.versions++;fs.writeFileSync(file,JSON.stringify(s));console.log('Created version.');}
else if(a.slice(0,2).join(' ')==='secrets add-iam-policy-binding'||a.slice(0,2).join(' ')==='projects add-iam-policy-binding')console.log('Policy updated.');
else process.exit(92);
`,{mode:0o700});
  const source=await readFile(bootstrap,'utf8');
  const describeStart=source.indexOf('describe() {'),describeEnd=source.indexOf('gc projects describe ',describeStart);
  const loopStart=source.indexOf("step 'Tesztadatbázis-jelszó és JWT-titok'"),loopEnd=source.indexOf("step 'Cloud Run tesztszolgáltatás és jogosultságok'",loopStart);
  assert.ok(describeStart>0&&describeEnd>describeStart&&loopStart>0&&loopEnd>loopStart);
  const program=join(dir,'bootstrap-secrets.sh');
  await writeFile(program,'set -euo pipefail\numask 077\ntemporary="$MYSQL_TEMP"\nhelper="$HELPER"\nproject_id=ingatlan-513620\nregion=europe-west1\nruntime_account=otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com\nlabels=app=otthonra,environment=dev,managed-by=otthonra-bootstrap\nstep(){ :; }\ngc(){ gcloud --project="$project_id" --quiet "$@"; }\n'+source.slice(describeStart,describeEnd)+source.slice(loopStart,loopEnd));
  const run=()=>spawnSync('bash',[program],{encoding:'utf8',timeout:5000,env:{...process.env,PATH:bin+':'+process.env.PATH,MYSQL_TEMP:dir,MYSQL_STATE:statePath,HELPER:helper}});
  const read=async()=>JSON.parse(await readFile(statePath,'utf8'));
  await action({run,read});
 });
}

test('the real secret loop adds one managed version, never rotates SQL/JWT credentials and does nothing extra on rerun',async()=>{
 await bootstrapFixture(()=>{},async({run,read})=>{
  const first=run();assert.equal(first.status,0,first.stderr);
  let state=await read();assert.equal(state.mysql,upgraded);assert.equal(state.jwt,jwt);assert.equal(state.versions,1);
  assert.match(first.stdout,/existing password preserved/);assert.ok(!(first.stdout+first.stderr).includes(password));assert.ok(!(first.stdout+first.stderr).includes(jwt));
  const second=run();assert.equal(second.status,0,second.stderr);state=await read();assert.equal(state.versions,1);assert.equal(state.mysql,upgraded);assert.equal(state.jwt,jwt);
  assert.ok(!state.calls.some(a=>a.includes('set-password')||a.includes('--password')||(a.includes('sql')&&a.includes('create'))));
  assert.ok(!JSON.stringify(state.calls).includes(password));
 });
});

test('the real secret loop refuses foreign or invalid secret payloads without adding a version',async()=>{
 for(const modify of [s=>s.foreign=true,s=>s.mysql=legacy.replace('ConnectionProtocol=Unix','ConnectionProtocol=Tcp')]){
  await bootstrapFixture(modify,async({run,read})=>{
   const result=run();assert.notEqual(result.status,0);const state=await read();assert.equal(state.versions,0);assert.equal(state.jwt,jwt);
   assert.ok(!state.calls.some(a=>a.includes('add')&&a.includes('versions')));assert.ok(!(result.stdout+result.stderr).includes(password));
  });
 }
});
