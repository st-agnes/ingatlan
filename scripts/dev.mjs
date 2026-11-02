import {spawn,spawnSync} from 'node:child_process';
import {readFile,writeFile,mkdir,open,access,unlink,rm,rename,stat} from 'node:fs/promises';
import {createConnection} from 'node:net';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {supervisorPid,waitForServices,safeLogTail} from './development-lifecycle.mjs';
import {developmentConfig} from './development-config.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
process.chdir(root);
const runtime=join(root,'.local'),pidFile=join(runtime,'dev.pid'),statusFile=join(runtime,'dev-status.json');
const scriptPath=fileURLToPath(import.meta.url),config=developmentConfig();
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
await mkdir(runtime,{recursive:true});
async function status(){try{return JSON.parse(await readFile(statusFile,'utf8'));}catch{return null;}}
async function probe(url){try{return(await fetch(url,{signal:AbortSignal.timeout(1500)})).status;}catch{return 0;}}
function alive(pid){try{process.kill(pid,0);return true;}catch(error){if(error.code==='ESRCH')return false;throw error;}}
function portOpen(port){return new Promise(resolve=>{const socket=createConnection({host:'127.0.0.1',port});let settled=false;const finish=value=>{if(settled)return;settled=true;socket.destroy();resolve(value);};socket.setTimeout(700,()=>finish(false));socket.once('connect',()=>finish(true));socket.once('error',()=>finish(false));});}
async function unlinkIfPresent(path){try{await unlink(path);}catch(error){if(error.code!=='ENOENT')throw error;}}
function showAddress(){console.log(`Development web: ${config.webOrigin} (forward port ${config.webPort} as HTTP).`);if(config.forwardedOrigin)console.log(`Open in your browser: ${config.forwardedOrigin}/`);}

// Serialize lifecycle commands, including simultaneous postStart/postAttach hooks.
async function withCommandLock(action){
 const lock=join(runtime,'dev-command.lock'),owner=join(lock,'owner.json'),deadline=Date.now()+180000;
 for(;;){
  try{await mkdir(lock);await writeFile(owner,JSON.stringify({pid:process.pid}),{mode:0o600});break;}
  catch(error){
   if(error.code!=='EEXIST')throw error;
   let stale=false;
   try{const current=JSON.parse(await readFile(owner,'utf8'));if(!Number.isSafeInteger(current.pid)||current.pid<=1)throw new Error('Invalid lifecycle lock.');
    if(!alive(current.pid))stale=true;else{const args=String(await readFile(`/proc/${current.pid}/cmdline`,'utf8')).split('\0');stale=!args.includes(scriptPath);}
   }catch(error){if(error instanceof SyntaxError||error.code==='ENOENT'||error.code==='ESRCH'){try{stale=Date.now()-(await stat(lock)).mtimeMs>5000;}catch(error){if(error.code!=='ENOENT')throw error;}}else throw error;}
   if(stale){await rm(lock,{recursive:true,force:true});continue;}
   if(Date.now()>=deadline)throw new Error('Another development start/stop command is still running. Check node scripts/dev.mjs --status.');
   await delay(100);
  }
 }
 try{return await action();}finally{await rm(lock,{recursive:true,force:true});}
}

async function stopSupervisor(){
 const pid=await supervisorPid(pidFile,{scriptPath});
 if(!pid){await unlinkIfPresent(pidFile);console.log('No running development supervisor.');return;}
 const before=await status(),port=before?.supervisorPid===pid&&before.version===2?before.webPort:8080;
 process.kill(pid,'SIGTERM');
 const deadline=Date.now()+15000;
 while(await supervisorPid(pidFile,{scriptPath})===pid||await portOpen(port)||await portOpen(config.webPort)||await portOpen(5080)){
  if(Date.now()>=deadline)throw new Error('The previous development processes have not released their ports. Startup was stopped to avoid a port conflict; no unrelated process was killed.');
  await delay(100);
 }
 // A service removes its own PID file; old versions require this cleanup.
 if(String(await readFile(pidFile,'utf8').catch(()=>'' )).trim()===String(pid))await unlinkIfPresent(pidFile);
 console.log('Development supervisor and its web/API processes stopped. MySQL data is preserved.');
}

async function startBackground(){
 let pid=await supervisorPid(pidFile,{scriptPath});
 const current=await status();
 if(pid&&(current?.version!==2||current.supervisorPid!==pid||current.webPort!==config.webPort)){await stopSupervisor();pid=null;}
 if(!pid){
  if(await portOpen(config.webPort)||await portOpen(5080))throw new Error(`Port ${config.webPort} or 5080 is already in use outside this supervisor. No process was killed. Check node scripts/dev.mjs --status.`);
  await unlinkIfPresent(pidFile);
  const log=await open(join(runtime,'dev.log'),'a',0o600);
  const child=spawn(process.execPath,[scriptPath,'--service'],{cwd:root,env:process.env,detached:true,stdio:['ignore',log.fd,log.fd]});
  await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
  pid=child.pid;await writeFile(pidFile,String(pid),{mode:0o600});child.unref();await log.close();
 }
 showAddress();
 try{
  await waitForServices({probe,webOrigin:config.webOrigin,isAlive:async()=>await supervisorPid(pidFile,{scriptPath})===pid});
  console.log('Development web and API ready.');
 }catch(error){
  console.error(error.message);
  try{console.error(safeLogTail(await readFile(join(runtime,'dev.log'),'utf8')));}catch{}
  console.error('Full local log: .local/dev.log. The web stays available while the API retries; use --status for diagnostics.');
  throw new Error('The API is not ready yet. See the local status and log above.');
 }
}

async function showStatus(){
 const pid=await supervisorPid(pidFile,{scriptPath}),current=await status();
 const [web,api]=await Promise.all([probe(new URL('/__dev/health',config.webOrigin)),probe(new URL('/api/health',config.webOrigin))]);
 console.log(`Supervisor: ${pid?'running':'stopped'}. Web port: ${config.webPort}. Web HTTP: ${web||'unreachable'}. API through web: ${api||'unreachable'}.`);
 if(current?.webPort&&current.webPort!==config.webPort)console.log(`Running port differs (${current.webPort}); use --restart to apply the selected port.`);
 showAddress();
 if(web===200&&api===200)console.log('Local services are healthy. If the forwarded URL gives 502, check the Codespaces tunnel and HTTP port protocol; do not recreate the database.');
}

async function runService(){
 let stopping=false,stateWrites=Promise.resolve();
 const children=new Map(),timers=new Set();
 const snapshot={version:2,supervisorPid:process.pid,webPort:config.webPort,webPid:null,apiPid:null};
 function persist(){const text=JSON.stringify(snapshot);stateWrites=stateWrites.then(async()=>{const temporary=statusFile+'.'+process.pid;await writeFile(temporary,text,{mode:0o600});await rename(temporary,statusFile);}).catch(error=>console.error(`Development status update failed (${error.code||'error'}).`));return stateWrites;}
 function signalGroup(child,signal){if(!child?.pid)return;try{if(process.platform==='win32')child.kill(signal);else process.kill(-child.pid,signal);}catch(error){if(error.code!=='ESRCH')console.error(`Could not stop owned child process (${error.code}).`);}}
 async function stop(code=0){
  if(stopping)return;stopping=true;
  for(const timer of timers)clearTimeout(timer);
  const owned=[...children.values()];for(const child of owned)signalGroup(child,'SIGTERM');
  const force=setTimeout(()=>{for(const child of owned)signalGroup(child,'SIGKILL');},4000);
  await Promise.all(owned.map(child=>child.exitCode!==null||child.signalCode!==null?Promise.resolve():new Promise(resolve=>child.once('close',resolve))));
  clearTimeout(force);for(const child of owned)signalGroup(child,'SIGKILL');
  await stateWrites;
  if(String(await readFile(pidFile,'utf8').catch(()=>'' )).trim()===String(process.pid)){await unlinkIfPresent(pidFile);await unlinkIfPresent(statusFile);}
  process.exit(code);
 }
 for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{void stop();});
 await writeFile(pidFile,String(process.pid),{mode:0o600});await persist();
 function launch(label,executable,args,env=process.env){
  let failures=0;
  const start=()=>{
   if(stopping)return;
   const started=Date.now(),child=spawn(executable,args,{cwd:root,env,stdio:'inherit',detached:process.platform!=='win32'});
   children.set(label,child);snapshot[label+'Pid']=child.pid||null;void persist();
   child.on('error',error=>console.error(`${label} process could not start (${error.code||'error'}).`));
   child.once('close',code=>{
    // dotnet run may exit before its application child; remove that owned group too.
    signalGroup(child,'SIGKILL');children.delete(label);snapshot[label+'Pid']=null;void persist();
    if(stopping)return;
    failures=Date.now()-started>30000?0:Math.min(failures+1,4);
    const pause=Math.min(1000*2**failures,15000);
    console.error(`${label} process exited (${code}); restarting in ${pause/1000} seconds. The other service stays available.`);
    const timer=setTimeout(()=>{timers.delete(timer);start();},pause);timers.add(timer);
   });
  };
  start();
 }
 // The web listener is independent of API startup or a later API failure.
 launch('web',process.execPath,['scripts/serve-web.mjs']);
 try{
await import('./setup-local.mjs');
const lines=(await readFile(join(root,'.env'),'utf8')).split(/\r?\n/);
const cfg={};
for(const line of lines){const match=line.match(/^([A-Z][A-Z0-9_]*)=(.*)$/);if(match)cfg[match[1]]=match[2].replace(/^(["'])(.*)\1$/,'$2');}
const value=(name,fallback)=>process.env[name]??cfg[name]??fallback;
const command=(name,args,env=process.env)=>{const result=spawnSync(name,args,{cwd:root,env,stdio:'inherit'});if(result.error)throw result.error;if(result.status!==0)throw new Error(`${name} failed (${result.status}).`);};
const database=process.env.ConnectionStrings__MySql;
if(!database)command('docker',['compose','up','-d','--wait','mysql']);
let dotnet=process.env.DOTNET_ROOT?join(process.env.DOTNET_ROOT,'dotnet'):'dotnet';
try{await access(join(runtime,'dotnet','dotnet'));dotnet=join(runtime,'dotnet','dotnet');}catch{}
const apiEnvironment={...process.env,
 ASPNETCORE_ENVIRONMENT:value('ASPNETCORE_ENVIRONMENT','Development'),
 ConnectionStrings__MySql:database||`Server=127.0.0.1;Port=3306;Database=otthonra;User=otthonra;Password=${value('MYSQL_PASSWORD','')}`,
 Jwt__Key:process.env.Jwt__Key||value('JWT_KEY',''),
 Database__Initialize:process.env.Database__Initialize||value('DATABASE_INITIALIZE','true'),
 Database__SeedDemo:process.env.Database__SeedDemo||value('SEED_DEMO','true'),
 Credits__EnableDemoTopup:process.env.Credits__EnableDemoTopup||value('ENABLE_DEMO_TOPUP','true'),
 Cors__Origins__0:value('FRONTEND_ORIGIN',config.webOrigin),
 Stripe__SecretKey:process.env.Stripe__SecretKey||value('STRIPE_SECRET_KEY',''),
 Stripe__WebhookSecret:process.env.Stripe__WebhookSecret||value('STRIPE_WEBHOOK_SECRET',''),
 Stripe__SuccessUrl:process.env.Stripe__SuccessUrl||value('STRIPE_SUCCESS_URL',config.webOrigin+'/?payment=success#credits'),
 Stripe__CancelUrl:process.env.Stripe__CancelUrl||value('STRIPE_CANCEL_URL',config.webOrigin+'/?payment=cancel#credits')};

 launch('api',dotnet,['run','--project','backend/Otthonra.Api/Otthonra.Api.csproj','--no-launch-profile','--urls','http://0.0.0.0:5080'],apiEnvironment);
 console.log('Development supervisor started. Web and API are monitored and restarted after unexpected exits.');
 showAddress();
 }catch(error){console.error(`API setup failed: ${safeLogTail(error.message)}. The web remains available; fix setup and use --restart.`);}
}

try{
 if(process.argv.includes('--status'))await showStatus();
 else if(process.argv.includes('--stop'))await withCommandLock(stopSupervisor);
 else if(process.argv.includes('--restart'))await withCommandLock(async()=>{await stopSupervisor();await startBackground();});
 else if(process.argv.includes('--background'))await withCommandLock(startBackground);
 else await runService();
}catch(error){console.error(error.message);process.exitCode=1;}
