import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFile,mkdtemp,mkdir,writeFile,rm,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,sep,extname} from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {developmentConfig} from '../scripts/development-config.mjs';

const project=fileURLToPath(new URL('../',import.meta.url));
const source=(await readFile(join(project,'scripts/serve-web.mjs'),'utf8'))
 .replace(/^import .*;\n/gm,'')
 .replace("const root=fileURLToPath(new URL('../dist/',import.meta.url));",'const root=TEST_ROOT;');
function serverHarness(env={}){
 let handler,listener;const proxied=[];
 const fakeProcess={env,on(){}};
 vm.runInNewContext(source,{
  TEST_ROOT:join(project,'dist'),URL,Buffer,resolve,sep,extname,developmentConfig:()=>developmentConfig(env),process:fakeProcess,console:{log(){},error(){}},
  createServer(fn){handler=fn;return{listen(port,host){listener={port,host};},close(fn){fn?.()},on(){return this;}}},
  proxyRequest(url,options,callback){proxied.push({url:String(url),options});return{setTimeout(){},on(){},destroy(){}}},
  stat,
  createReadStream(){return{on(){return this},pipe(res){res.end('fixture file')}}}
 });
 async function request(url,method='GET'){
  const req={url,method,headers:{host:'forwarded.test'},on(){},pipe(){}};
  const res={status:0,headers:{},body:'',setHeader(k,v){this.headers[k]=v},writeHead(s,h={}){this.status=s;Object.assign(this.headers,h);return this},end(body=''){this.body=body;return this},destroy(){}};
  await handler(req,res);return res;
 }
 return{request,proxied,get listener(){return listener;}};
}
test('development proxy always targets configured API, including absolute-form request URLs',async()=>{
 const h=serverHarness();await h.request('http://untrusted.example/api/me?x=1');
 assert.equal(h.proxied.length,1);assert.equal(h.proxied[0].url,'http://127.0.0.1:5080/api/me?x=1');
 assert.equal(h.proxied[0].options.headers.host,'127.0.0.1:5080');
});
test('development static server serves JavaScript with correct MIME and rejects invalid paths/methods',async()=>{
 const h=serverHarness();const script=await h.request('/app.js','HEAD');
 assert.equal(script.status,200);assert.equal(script.headers['Content-Type'],'text/javascript; charset=utf-8');assert.equal(script.body,'');
 assert.equal((await h.request('/%00')).status,400);
 assert.equal((await h.request('/%5c..%5c.env')).status,400);
 assert.equal((await h.request('/index.html','POST')).status,405);
 assert.equal((await h.request('/does-not-exist')).status,404);
});
test('web configuration and listener share a canonical configurable port and HTTP API origin',()=>{
 const defaults=developmentConfig({});
 assert.equal(defaults.webPort,3000);assert.equal(defaults.webOrigin,'http://127.0.0.1:3000');
 assert.equal(defaults.apiOrigin,'http://127.0.0.1:5080');assert.equal(defaults.forwardedOrigin,null);
 const custom=developmentConfig({WEB_PORT:'4317',API_ORIGIN:'http://localhost:5080/'});
 assert.equal(custom.webPort,4317);assert.equal(custom.webOrigin,'http://127.0.0.1:4317');
 assert.equal(custom.apiOrigin,'http://localhost:5080');
 assert.deepEqual(serverHarness({WEB_PORT:'4317'}).listener,{port:4317,host:'0.0.0.0'});
});
test('invalid web ports and unsafe or mismatched upstream origins fail before binding',()=>{
 for(const port of ['', '0', '5080', '65536', 'abc', '3000.5', '3000evil'])assert.throws(()=>developmentConfig({WEB_PORT:port}),undefined,port);
 for(const origin of ['https://127.0.0.1:5080','http://user:password@localhost:5080','http://localhost:5080/api','http://localhost:5080/?secret=x','http://localhost:5080/#fragment'])assert.throws(()=>developmentConfig({API_ORIGIN:origin}),undefined,origin);
});
test('forwarded web address uses validated Codespaces context and the actual selected port',()=>{
 const env={CODESPACE_NAME:'quiet-cloud-123',GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:'app.github.dev',WEB_PORT:'4317'};
 assert.equal(developmentConfig(env).forwardedOrigin,'https://quiet-cloud-123-4317.app.github.dev');
 for(const patch of [{CODESPACE_NAME:'oops/path'},{CODESPACE_NAME:'bad name'},{GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:'app.github.dev/evil'},{GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:'evil.test?secret=x'}])assert.equal(developmentConfig({...env,...patch}).forwardedOrigin,null);
});
test('web health identifies this server and remains independent of API readiness',async()=>{
 const h=serverHarness({WEB_PORT:'4317'}),health=await h.request('/__dev/health');
 assert.equal(health.status,200);assert.equal(health.headers['X-Otthonra-Development'],'web');
 assert.match(health.headers['Content-Type'],/application\/json/);
 assert.deepEqual(JSON.parse(health.body),{service:'otthonra-dev-web',port:4317});assert.equal(h.proxied.length,0);
 const head=await h.request('/__dev/health','HEAD');assert.equal(head.status,200);assert.equal(head.body,'');
 const root=await h.request('/');assert.equal(root.status,200);assert.equal(root.headers['X-Otthonra-Development'],'web');
});
test('local setup creates separate environment entries and preserves existing secrets on rerun',async()=>{
 const root=await mkdtemp(join(tmpdir(),'otthonra-setup-'));
 try{
  await mkdir(join(root,'scripts'));const setup=await readFile(join(project,'scripts/setup-local.mjs'),'utf8');await writeFile(join(root,'scripts/setup-local.mjs'),setup);
  const run=()=>spawnSync(process.execPath,[join(root,'scripts/setup-local.mjs')],{encoding:'utf8'});
  assert.equal(run().status,0);const original=await readFile(join(root,'.env'),'utf8');
  const entries=Object.fromEntries(original.trim().split('\n').map(l=>l.split('=')));
  assert.equal(Object.keys(entries).length,8);assert.equal(entries.JWT_KEY.length,96);assert.equal(entries.MYSQL_PASSWORD.length,48);assert.notEqual(entries.MYSQL_PASSWORD,entries.MYSQL_ROOT_PASSWORD);
  assert.equal(run().status,0);assert.equal(await readFile(join(root,'.env'),'utf8'),original);
 }finally{await rm(root,{recursive:true,force:true})}
});

const {supervisorPid,waitForServices,safeLogTail}=await import('../scripts/development-lifecycle.mjs');
test('background readiness requires both the real web root and proxied API to return 200',async()=>{
 let clock=0,calls=[];
 await waitForServices({now:()=>clock,delay:async ms=>{clock+=ms},timeoutMs:1000,intervalMs:100,isAlive:async()=>true,
  probe:async url=>{calls.push(url);return url.endsWith('/api/health')||clock>=200?200:503;}});
 assert.equal(clock,200);assert.equal(calls.length,6);assert.ok(calls.includes('http://127.0.0.1:3000/'));
});
test('readiness probes the selected web port rather than an unrelated default listener',async()=>{
 const calls=[];
 await waitForServices({webOrigin:'http://127.0.0.1:4317',probe:async url=>{calls.push(url);return 200;},isAlive:async()=>true});
 assert.deepEqual(calls,['http://127.0.0.1:4317/','http://127.0.0.1:4317/api/health']);
});
test('default readiness budget accommodates a cold API build but remains bounded',async()=>{
 let clock=0;
 await assert.rejects(waitForServices({probe:async()=>503,isAlive:async()=>true,now:()=>clock,delay:async ms=>{clock+=ms;},intervalMs:60000}),/within 120 seconds/);
 assert.equal(clock,120000);
});
test('background startup reports a dead supervisor and a bounded readiness timeout',async()=>{
 await assert.rejects(waitForServices({probe:async()=>200,isAlive:async()=>false}),/supervisor exited/);
 let clock=0;
 await assert.rejects(waitForServices({probe:async()=>503,isAlive:async()=>true,now:()=>clock,delay:async ms=>{clock+=ms},timeoutMs:1000,intervalMs:200}),/did not become ready/);
 assert.equal(clock,1000);
});
test('saved development PID must identify the exact service supervisor before reuse',async()=>{
 const scriptPath='/workspaces/ingatlan/scripts/dev.mjs';let checks=0;
 const inspect=async(raw,args)=>supervisorPid('/fixture/dev.pid',{scriptPath,check(){checks++},read:async p=>p.endsWith('cmdline')?args:raw});
 assert.equal(await inspect('42',`node\0${scriptPath}\0--service\0`),42);
 assert.equal(await inspect('42','node\0/unrelated/server.mjs\0--service\0'),null);
 assert.equal(await inspect('42',`node\0${scriptPath}\0--background\0`),null);
 assert.equal(await inspect('0',''),null);assert.equal(checks,3);
});
test('startup failure tail is bounded and omits credential-bearing lines',()=>{
 const output=safeLogTail('ordinary startup\nPassword=do-not-show\nAuthorization: Bearer hidden\nJWT_KEY=private\nAPI exited (1).');
 assert.ok(output.includes('API exited (1).'));assert.ok(!output.includes('do-not-show'));assert.ok(!output.includes('Bearer'));assert.ok(!output.includes('private'));
 assert.ok(safeLogTail('x'.repeat(4000)).length<=2000);
});
