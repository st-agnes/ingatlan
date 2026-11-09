import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyTestDeployment} from '../scripts/gcp/verify-dev.mjs';
import {TEST_FIXTURE_VERSION} from '../scripts/gcp/export-demo-data.mjs';

const origin = 'https://otthonra-dev-120611818277.web.app';
const health = {status:'ready', deployment:'test', testCreditsEnabled:true, testDataVersion:TEST_FIXTURE_VERSION};
const runtime = 'globalThis.OTTHONRA_CONFIG = Object.freeze({mode: "api", environment: "test"});';
const home = '<script src="/runtime-config.js"></script>';
const response = (path, value = health) => new Response(path === '/' ? home : path === '/runtime-config.js' ? runtime : JSON.stringify(value));

function harness({fetchResponse = (url) => response(url.pathname), attempts = 3} = {}) {
  const calls = [], logs = [], waits = [];
  return {calls, logs, waits, run: (extra = {}) => verifyTestDeployment({origin, hosting:true, attempts,
    delayMs:5, wait:async ms => waits.push(ms), log:message => logs.push(message),
    fetchImpl:async (url, options) => {calls.push({url, options});return fetchResponse(url, options);}, ...extra})};
}

test('a fully current hosted application passes without a wait and requests uncached public responses', async () => {
  const h = harness();
  assert.deepEqual(await h.run(), {ready:true, attempts:1});
  assert.equal(h.calls.length,3);assert.deepEqual(h.waits,[]);
  assert.match(h.logs[0], /Test application ready/);
  for (const {url,options} of h.calls) {
    assert.equal(url.origin,origin);assert.ok(url.searchParams.get('otthonra_deploy_check'));
    assert.equal(options.cache,'no-store');assert.equal(options.redirect,'error');
    assert.equal(options.headers['Cache-Control'],'no-cache, no-store');
    assert.ok(options.signal instanceof AbortSignal);
  }
});

test('a previous pinned fixture version during release propagation must become current before success', async () => {
  let checks=0;
  const old = '20261107-test-fixtures-v2';
  const h = harness({fetchResponse:url => response(url.pathname,url.pathname==='/api/health' && ++checks===1 ? {...health,testDataVersion:old} : health)});
  assert.deepEqual(await h.run(),{ready:true,attempts:2});assert.deepEqual(h.waits,[5]);
  assert.match(h.logs[0],new RegExp(`testDataVersion=${old} \\(expected ${TEST_FIXTURE_VERSION}\\)`));
  const checksUrls=h.calls.filter(call=>call.url.pathname==='/api/health').map(call=>call.url.href);
  assert.equal(new Set(checksUrls).size,2,'Retries must not reuse the stale URL');
});

test('a permanently old API remains a failed deployment with the exact received and expected versions',async()=>{
  const h=harness({fetchResponse:url=>response(url.pathname,{...health,testDataVersion:'20261107-test-fixtures-v2'})});
  await assert.rejects(h.run(), /Hosting verification failed after 3 check\(s\).*testDataVersion=20261107-test-fixtures-v2/);
  assert.equal(h.calls.length,9);assert.deepEqual(h.waits,[5,5]);
  assert.ok(h.logs.every(message=>!message.includes('application ready')));
});

test('the final attempt checks every requirement and cannot accept demo, production, disabled credits or an unready database',async()=>{
  for(const [field,value,message] of [
    ['status','database-unavailable','status is not ready'],['deployment','production','deployment is not test'],
    ['testCreditsEnabled',false,'test credits are not enabled'],['testDataVersion',null,'testDataVersion=<missing or invalid>']
  ]){
    const h=harness({fetchResponse:url=>response(url.pathname,{...health,[field]:value}),attempts:1});
    await assert.rejects(h.run(),error=>error.message.includes(message));assert.deepEqual(h.waits,[]);
  }
});

test('missing homepage script and wrong runtime flags identify their own failing path',async()=>{
  for(const [path,text,message] of [
    ['/','<html>Other site</html>','/: runtime-config.js script is missing'],
    ['/runtime-config.js','mode: "demo", environment: "production"','API mode is missing'],
    ['/runtime-config.js','mode: "api", environment: "production"','test environment is missing']
  ]){
    const h=harness({fetchResponse:url=>url.pathname===path?new Response(text):response(url.pathname),attempts:1});
    await assert.rejects(h.run(),error=>error.message.includes(message));
  }
});

test('untrusted response bodies and fetch error details are never printed',async()=>{
  for(const value of ['private-token-value','{"testDataVersion":"private token value","token":"private-token-value"}',null]){
    const h=harness({attempts:1,fetchResponse:url=>{
      if(url.pathname!=='/api/health')return response(url.pathname);
      if(value===null)throw new Error('private-token-value');return new Response(value);
    }});
    await assert.rejects(h.run(),error=>!error.message.includes('private-token-value')&&!error.message.includes('private token value'));
    assert.doesNotMatch(h.logs.join('\n'),/private-token-value/);
  }
});

test('a temporary HTTP failure is retried, but an access denial stops immediately',async()=>{
  let reads=0;
  const h=harness({fetchResponse:url=>url.pathname==='/api/health'&&++reads===1?new Response('private error',{status:503}):response(url.pathname)});
  assert.equal((await h.run()).attempts,2);assert.match(h.logs[0],/\/api\/health: HTTP 503/);
  for(const status of [401,403]){
    const denied=harness({fetchResponse:url=>url.pathname==='/api/health'?new Response('private error',{status}):response(url.pathname)});
    await assert.rejects(denied.run(),new RegExp(`after 1 check.*HTTP ${status}`));assert.deepEqual(denied.waits,[]);
  }
});

test('request timeouts are bounded, reported by path, and never declare readiness',async()=>{
  const h=harness({attempts:2,fetchResponse:async(url,{signal})=>{
    if(url.pathname!=='/api/health')return response(url.pathname);
    await new Promise((resolve,reject)=>{signal.addEventListener('abort',()=>reject(signal.reason),{once:true});setTimeout(resolve,100);});
    throw new Error('A timed-out request must not continue');
  }});
  await assert.rejects(h.run({timeoutMs:5}),/failed after 2 check.*\/api\/health: request timed out/);
  assert.deepEqual(h.waits,[5]);
});

test('direct API verification uses the same strict fixture and database requirements before Hosting changes',async()=>{
  const h=harness();
  assert.equal((await h.run({origin:'https://otthonra-api-dev-120611818277.europe-west1.run.app',hosting:false})).ready,true);
  assert.deepEqual(h.calls.map(call=>call.url.pathname),['/api/health']);
  const old=harness({attempts:1,fetchResponse:url=>response(url.pathname,{...health,testDataVersion:'old'})});
  await assert.rejects(old.run({origin:'https://otthonra-api-dev-120611818277.europe-west1.run.app',hosting:false}),/API verification failed.*expected/);
});

test('invalid origins and unbounded verification options fail before any request',async()=>{
  for(const change of [
    {origin:'http://otthonra-dev-120611818277.web.app'}, {origin:'https://user:password@otthonra-dev-120611818277.web.app'},
    {origin:'https://example.com'}, {origin:origin+'/path'}, {origin:origin+'?token=value'},
    {attempts:13},{attempts:0},{delayMs:5001},{timeoutMs:10001},{delayMs:NaN},{timeoutMs:Infinity},{delayMs:'5'}
  ]){
    const h=harness();await assert.rejects(h.run(change));assert.deepEqual(h.calls,[]);
  }
});

test('network diagnostics expose an allowlisted cause code without printing the raw error',async()=>{
  const h=harness({attempts:1,fetchResponse:()=>{throw new Error('private-token-value',{cause:{code:'ECONNREFUSED'}});}});
  await assert.rejects(h.run(),error=>error.message.includes('ECONNREFUSED')&&!error.message.includes('private-token-value'));
});
