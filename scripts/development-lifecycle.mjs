import {readFile} from 'node:fs/promises';

export async function supervisorPid(pidFile,{scriptPath,read=readFile,check=pid=>process.kill(pid,0)}={}) {
  try {
    const raw=String(await read(pidFile,'utf8')).trim();
    if(!/^[1-9][0-9]*$/.test(raw))return null;
    const pid=Number(raw);if(!Number.isSafeInteger(pid)||pid<=1)return null;
    check(pid);
    const args=String(await read(`/proc/${pid}/cmdline`,'utf8')).split('\0');
    return args.includes(scriptPath)&&args.includes('--service')?pid:null;
  }catch(error){if(['ENOENT','ESRCH'].includes(error.code))return null;throw error;}
}

export async function waitForServices({probe,isAlive,webOrigin='http://127.0.0.1:3000',timeoutMs=120000,intervalMs=500,now=Date.now,delay=ms=>new Promise(resolve=>setTimeout(resolve,ms))}) {
  const deadline=now()+timeoutMs;
  for(;;) {
    if(!await isAlive())throw new Error('Development supervisor exited before the web application became ready.');
    const statuses=await Promise.all([probe(new URL('/',webOrigin).href),probe(new URL('/api/health',webOrigin).href)]);
    if(statuses.every(status=>status===200)&&await isAlive())return;
    if(now()>=deadline)throw new Error(`Development web and API did not become ready within ${Math.round(timeoutMs/1000)} seconds.`);
    await delay(Math.min(intervalMs,Math.max(0,deadline-now())));
  }
}

export function safeLogTail(text,maxLines=12) {
  return String(text).split(/\r?\n/).slice(-maxLines).map(line=>
    /password|\bpwd\b|secret|token|authorization|jwt[_:]|sk_(?:test|live)_|whsec_|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\./i.test(line)
      ?'[sensitive log line omitted]':line
  ).join('\n').slice(-2000);
}
