import {createServer, request as proxyRequest} from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {resolve, sep, extname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {developmentConfig} from './development-config.mjs';

const root=fileURLToPath(new URL('../dist/',import.meta.url));
const config=developmentConfig();
const upstream=new URL(config.apiOrigin);
const port=config.webPort;
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml'};
const server=createServer(async(req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('X-Otthonra-Development','web');
  let pathname,parsed;
  try {parsed=new URL(req.url,'http://localhost');pathname=decodeURIComponent(parsed.pathname);}catch{res.writeHead(400).end();return;}
  if(pathname==='/__dev/health') {
    if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{'Allow':'GET, HEAD'}).end();return;}
    const body=JSON.stringify({service:'otthonra-dev-web',port});
    res.writeHead(200,{'Content-Type':'application/json; charset=utf-8','Content-Length':Buffer.byteLength(body),'Cache-Control':'no-store'});
    res.end(req.method==='HEAD'?'':body);return;
  }
  if(pathname==='/api'||pathname.startsWith('/api/')) {
    const destination=new URL(upstream);destination.pathname=parsed.pathname;destination.search=parsed.search;destination.hash='';
    const proxy=proxyRequest(destination,{method:req.method,headers:{...req.headers,host:upstream.host}},reply=>{
      reply.on('error',()=>res.destroy());
      res.writeHead(reply.statusCode||502,reply.headers);reply.pipe(res);
    });
    proxy.setTimeout(20000,()=>proxy.destroy(new Error('API timeout')));
    proxy.on('error',()=>{
      if(res.destroyed||res.writableEnded)return;
      if(res.headersSent){res.destroy();return;}
      res.writeHead(503,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
      res.end(JSON.stringify({message:'A .NET API még nem érhető el. A webes felület továbbra is működik.'}));
    });
    req.on('aborted',()=>proxy.destroy());req.pipe(proxy);return;
  }
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{'Allow':'GET, HEAD'}).end();return;}
  if(pathname.includes('\0')||pathname.includes('\\')){res.writeHead(400).end();return;}
  const target=resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
  if(!target.startsWith(resolve(root)+sep)){res.writeHead(403).end();return;}
  try {
    const details=await stat(target);if(!details.isFile()){res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':types[extname(target)]||'application/octet-stream','Content-Length':details.size,'Cache-Control':'no-cache'});
    if(req.method==='HEAD'){res.end();return;}
    const stream=createReadStream(target);stream.on('error',()=>res.destroy());stream.pipe(res);
  }catch{res.writeHead(404).end();}
});
server.on('error',error=>{console.error(`Development web listener failed on port ${port}: ${error.code||error.message}`);process.exit(1);});
server.listen(port,'0.0.0.0',()=>console.log(`Otthonra web: http://localhost:${port} (same-origin /api proxy)`));
let stopping=false;
function stop(){
  if(stopping)return;stopping=true;
  const deadline=setTimeout(()=>{server.closeAllConnections?.();process.exit(0);},2000);
  deadline.unref();
  server.close(()=>{clearTimeout(deadline);process.exit(0);});
  server.closeIdleConnections?.();
}
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,stop);
