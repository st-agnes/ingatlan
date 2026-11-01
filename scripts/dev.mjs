import {spawn,spawnSync} from 'node:child_process';
import {readFile,writeFile,mkdir,open,access,unlink} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';

const root=fileURLToPath(new URL('../',import.meta.url));
process.chdir(root);
const runtime=join(root,'.local');
const pidFile=join(runtime,'dev.pid');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function healthy(url){try{return(await fetch(url,{signal:AbortSignal.timeout(1500)})).ok}catch{return false}}
if(process.argv.includes('--stop')) {
  try{const pid=Number(await readFile(pidFile,'utf8'));if(!Number.isInteger(pid)||pid<=1)throw new Error('Invalid supervisor PID.');const commandLine=await readFile(`/proc/${pid}/cmdline`,'utf8');if(!commandLine.includes(fileURLToPath(import.meta.url)))throw new Error('Saved PID does not belong to this development supervisor; no process was stopped.');process.kill(pid,'SIGTERM');await unlink(pidFile);console.log('Development supervisor stopped. MySQL data is preserved.');}catch(e){if(e.code!=='ENOENT'&&e.code!=='ESRCH')throw e;console.log('No running development supervisor.');}
  process.exit(0);
}
if(process.argv.includes('--background')) {
  await mkdir(runtime,{recursive:true});
  if(await healthy('http://127.0.0.1:8080/api/health')){console.log('Development services already ready at port 8080.');process.exit(0);}
  try{const pid=Number(await readFile(pidFile,'utf8'));process.kill(pid,0);console.log('Development services are starting; logs: .local/dev.log');process.exit(0);}catch(e){if(!['ENOENT','ESRCH'].includes(e.code))throw e;}
  const log=await open(join(runtime,'dev.log'),'a',0o600);
  const child=spawn(process.execPath,[fileURLToPath(import.meta.url),'--service'],{cwd:root,env:process.env,detached:true,stdio:['ignore',log.fd,log.fd]});
  await writeFile(pidFile,String(child.pid),{mode:0o600});child.unref();await log.close();
  console.log('Development services starting. Logs: .local/dev.log');process.exit(0);
}
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
 Cors__Origins__0:value('FRONTEND_ORIGIN','http://localhost:8080'),
 Stripe__SecretKey:process.env.Stripe__SecretKey||value('STRIPE_SECRET_KEY',''),
 Stripe__WebhookSecret:process.env.Stripe__WebhookSecret||value('STRIPE_WEBHOOK_SECRET',''),
 Stripe__SuccessUrl:process.env.Stripe__SuccessUrl||value('STRIPE_SUCCESS_URL','http://localhost:8080/?payment=success#credits'),
 Stripe__CancelUrl:process.env.Stripe__CancelUrl||value('STRIPE_CANCEL_URL','http://localhost:8080/?payment=cancel#credits')};
const children=[];let stopping=false;
function stop(code=0){if(stopping)return;stopping=true;process.exitCode=code;for(const child of children)child.kill('SIGTERM');setTimeout(()=>{for(const child of children)child.kill('SIGKILL');process.exit(code);},2500).unref();}
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>stop());
const api=spawn(dotnet,['run','--project','backend/Otthonra.Api/Otthonra.Api.csproj','--no-launch-profile','--urls','http://0.0.0.0:5080'],{cwd:root,env:apiEnvironment,stdio:'inherit'});children.push(api);
api.on('error',error=>{console.error(error.message);stop(1);});
api.on('exit',code=>{if(!stopping){console.error(`API exited (${code}).`);stop(code||1);}});
try {
 const deadline=Date.now()+55000;
 while(!await healthy('http://127.0.0.1:5080/api/health')){if(api.exitCode!==null||Date.now()>deadline)throw new Error('API did not become ready; inspect the .NET output above.');await delay(500);}
 const web=spawn(process.execPath,['scripts/serve-web.mjs'],{cwd:root,env:process.env,stdio:'inherit'});children.push(web);
 web.on('error',error=>{console.error(error.message);stop(1);});web.on('exit',code=>{if(!stopping)stop(code||1);});
 console.log('API and MySQL ready. Web: http://localhost:8080 . API is also available through /api on that address.');
}catch(error){console.error(error.message);stop(1);}
