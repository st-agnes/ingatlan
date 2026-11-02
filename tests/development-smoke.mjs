/** Live lifecycle regressions. Run only against the disposable CI development stack. */
import assert from 'node:assert/strict';
import {createServer} from 'node:net';
import {spawn} from 'node:child_process';
import {readFile,readdir} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {safeLogTail} from '../scripts/development-lifecycle.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
const devScript=join(root,'scripts/dev.mjs');
const webScript=join(root,'scripts/serve-web.mjs');
const statusFile=join(root,'.local/dev-status.json');
const defaultOrigin='http://127.0.0.1:3000';
const customOrigin='http://127.0.0.1:4317';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));

async function waitUntil(probe,{timeoutMs=45000,label='condition'}={}){
 const deadline=Date.now()+timeoutMs;
 for(;;){
  if(await probe())return;
  assert.ok(Date.now()<deadline,`Timed out waiting for ${label}`);
  await pause(Math.min(100,deadline-Date.now()));
 }
}

function command(flag,extraEnv={},timeoutMs=150000){
 return new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,[devScript,flag],{cwd:root,env:{...process.env,WEB_PORT:'3000',...extraEnv},stdio:['ignore','pipe','pipe']});
  let output='',settled=false;
  const append=chunk=>{output=(output+chunk.toString()).slice(-24000);};
  child.stdout.on('data',append);child.stderr.on('data',append);
  const finish=error=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve(output);};
  const timer=setTimeout(()=>{child.kill('SIGKILL');finish(new Error(`Development command ${flag} timed out.\n${safeLogTail(output)}`));},timeoutMs);
  child.once('error',finish);
  child.once('close',(code,signal)=>finish(code===0?null:new Error(`Development command ${flag} failed (${signal||code}).\n${safeLogTail(output)}`)));
 });
}

async function request(origin,path='/'){
 try{
  const response=await fetch(origin+path,{signal:AbortSignal.timeout(2000)});
  return{status:response.status,headers:response.headers,body:await response.text()};
 }catch{return{status:0,headers:new Headers(),body:''};}
}

async function status(){
 const state=JSON.parse(await readFile(statusFile,'utf8'));
 assert.equal(state.version,2);
 assert.ok(Number.isSafeInteger(state.supervisorPid)&&state.supervisorPid>1);
 return state;
}

async function processInfo(pid){
 try{
  const [commandLine,state]=await Promise.all([readFile(`/proc/${pid}/cmdline`,'utf8'),readFile(`/proc/${pid}/status`,'utf8')]);
  return{pid:Number(pid),args:commandLine.split('\0').filter(Boolean),parent:Number(state.match(/^PPid:\s+(\d+)/m)?.[1]),state:state.match(/^State:\s+(\S)/m)?.[1]};
 }catch(error){if(['ENOENT','ESRCH','EACCES','EPERM'].includes(error.code))return null;throw error;}
}

async function processes(){
 const names=await readdir('/proc');
 return(await Promise.all(names.filter(name=>/^\d+$/.test(name)).map(name=>processInfo(Number(name))))).filter(Boolean);
}

async function descendants(supervisor){
 const all=await processes(),owned=new Set([supervisor]);
 for(let changed=true;changed;){changed=false;for(const item of all)if(owned.has(item.parent)&&!owned.has(item.pid)){owned.add(item.pid);changed=true;}}
 return all.filter(item=>owned.has(item.pid)&&item.state!=='Z');
}

async function assertExited(records){
 for(const original of records){
  const current=await processInfo(original.pid);
  assert.ok(!current||current.state==='Z'||current.args.join('\0')!==original.args.join('\0'),`Owned development process ${original.pid} survived a completed stop/restart`);
 }
}

async function assertOneSupervisor(expected){
 const services=(await processes()).filter(item=>item.state!=='Z'&&item.args.includes(devScript)&&item.args.includes('--service'));
 assert.deepEqual(services.map(item=>item.pid),[expected],'Concurrent startup must not leave another development supervisor running');
}

async function terminateOwnedChild(runtime,key,signature){
 const pid=runtime[key];
 assert.ok(Number.isSafeInteger(pid)&&pid>1,`Missing ${key}`);
 const supervisor=await processInfo(runtime.supervisorPid),child=await processInfo(pid);
 assert.ok(supervisor?.args.includes(devScript)&&supervisor.args.includes('--service'),'Refusing to signal an unrelated supervisor');
 assert.equal(child?.parent,runtime.supervisorPid,'Refusing to signal a process not owned by this supervisor');
 assert.ok(child.args.some(arg=>arg.includes(signature)),'Refusing to signal an unrelated child command');
 process.kill(pid,'SIGKILL');
}

async function freePort(){
 const server=createServer();
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 const port=server.address().port;
 await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
 return port;
}

async function isolatedWeb(){
 const port=await freePort();let upstream=await freePort();while(upstream===port)upstream=await freePort();
 const origin=`http://127.0.0.1:${port}`;
 const child=spawn(process.execPath,[webScript],{cwd:root,env:{...process.env,WEB_PORT:String(port),API_ORIGIN:`http://127.0.0.1:${upstream}`},stdio:['ignore','pipe','pipe']});
 let output='';const append=chunk=>{output=(output+chunk.toString()).slice(-4000);};
 child.stdout.on('data',append);child.stderr.on('data',append);
 let launchError;child.once('error',error=>{launchError=error;});
 try{
  await waitUntil(async()=>{
   if(launchError)throw launchError;
   assert.equal(child.exitCode,null,`Isolated web exited: ${safeLogTail(output)}`);
   return(await request(origin,'/__dev/health')).status===200;
  },{timeoutMs:10000,label:'the isolated web listener'});
  const [home,script,health,api]=await Promise.all([request(origin),request(origin,'/app.js'),request(origin,'/__dev/health'),request(origin,'/api/health')]);
  assert.equal(home.status,200);assert.match(home.body,/<!doctype html>/i);
  assert.equal(home.headers.get('x-otthonra-development'),'web');
  assert.equal(script.status,200);assert.match(script.headers.get('content-type'),/text\/javascript/);
  assert.deepEqual(JSON.parse(health.body),{service:'otthonra-dev-web',port});
  assert.equal(api.status,503);assert.match(api.headers.get('content-type'),/application\/json/);assert.ok(JSON.parse(api.body).message);
  assert.equal((await request(origin)).status,200,'An unavailable API must not take the static web frontend down');
 }finally{
  if(child.exitCode===null&&!launchError){
   child.kill('SIGTERM');
   try{await waitUntil(async()=>child.exitCode!==null||child.signalCode!==null,{timeoutMs:5000,label:'isolated web shutdown'});}
   finally{if(child.exitCode===null&&child.signalCode===null)child.kill('SIGKILL');}
  }
 }
 console.log('Development standalone web passed: static content and web health remain available while the API returns a controlled 503.');
}

async function main(){
 await isolatedWeb();
 await command('--background');
 const first=await status();assert.equal(first.webPort,3000);
 await command('--background');
 assert.equal((await status()).supervisorPid,first.supervisorPid,'Repeated startup must reuse the running supervisor');
 await command('--status');
 assert.equal((await status()).supervisorPid,first.supervisorPid,'Status must not replace the running supervisor');
 const originalProcesses=await descendants(first.supervisorPid);
 await command('--stop',{},30000);
 await assertExited(originalProcesses);
 assert.equal((await request(defaultOrigin)).status,0,'Stop must wait for the web port to close');
 assert.equal((await request('http://127.0.0.1:5080','/api/health')).status,0,'Stop must wait for the API port to close');
 // No sleep: concurrent startup immediately follows a fully completed stop.
 await Promise.all([command('--background'),command('--background')]);
 const concurrent=await status();await assertOneSupervisor(concurrent.supervisorPid);
 assert.equal((await request(defaultOrigin)).status,200);assert.equal((await request(defaultOrigin,'/api/health')).status,200);
 console.log('Development startup passed: status is read-only, startup is idempotent, concurrent starts share one supervisor, and stop releases both ports.');

 await command('--stop',{},30000);
 await command('--background',{WEB_PORT:'4317'});
 const custom=await status();assert.equal(custom.webPort,4317);
 assert.equal((await request(customOrigin)).status,200);assert.equal((await request(customOrigin,'/api/health')).status,200);
 const customProcesses=await descendants(custom.supervisorPid);
 await command('--restart');
 await assertExited(customProcesses);
 const restarted=await status();assert.equal(restarted.webPort,3000);assert.notEqual(restarted.supervisorPid,custom.supervisorPid);
 assert.equal((await request(customOrigin)).status,0,'Restart must release the previous custom web port');
 assert.equal((await request(defaultOrigin)).status,200);assert.equal((await request(defaultOrigin,'/api/health')).status,200);
 console.log('Development restart passed: a custom web port participates in readiness, and restart returns cleanly to the configured default without sleeps.');

 await terminateOwnedChild(restarted,'apiPid','Otthonra.Api');
 let webSamples=0;
 await waitUntil(async()=>{
  const web=await request(defaultOrigin);webSamples++;assert.equal(web.status,200,'The web frontend must remain available while the API recovers');
  const next=await status();
  assert.equal(next.supervisorPid,restarted.supervisorPid);assert.equal(next.webPid,restarted.webPid);
  return Number.isSafeInteger(next.apiPid)&&next.apiPid!==restarted.apiPid&&(await request(defaultOrigin,'/api/health')).status===200;
 },{timeoutMs:60000,label:'automatic API recovery'});
 assert.ok(webSamples>0);
 const beforeWebCrash=await status();
 await terminateOwnedChild(beforeWebCrash,'webPid','serve-web.mjs');
 await waitUntil(async()=>{
  const next=await status();
  assert.equal(next.supervisorPid,beforeWebCrash.supervisorPid);assert.equal(next.apiPid,beforeWebCrash.apiPid);
  return Number.isSafeInteger(next.webPid)&&next.webPid!==beforeWebCrash.webPid&&(await request(defaultOrigin)).status===200;
 },{timeoutMs:15000,label:'automatic web recovery'});
 assert.equal((await request(defaultOrigin,'/api/health')).status,200);
 console.log('Development recovery passed: killing an owned API runner keeps the web available, and both API and web crashes recover automatically.');
 console.log('Development lifecycle smoke passed; the default web and API remain running for the remaining CI checks.');
}

try{await main();}
catch(error){
 console.error(error.stack||error);
 await command('--stop',{},30000).catch(cleanup=>console.error(safeLogTail(cleanup.message)));
 process.exitCode=1;
}
