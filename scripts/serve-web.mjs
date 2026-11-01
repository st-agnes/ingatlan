import {createServer, request as proxyRequest} from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {resolve, sep, extname} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../dist/',import.meta.url));
const upstream=new URL(process.env.API_ORIGIN||'http://127.0.0.1:5080');
const port=Number(process.env.WEB_PORT||8080);
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml'};
const server=createServer(async(req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  let pathname,parsed;
  try {parsed=new URL(req.url,'http://localhost');pathname=decodeURIComponent(parsed.pathname);}catch{res.writeHead(400).end();return;}
  if(pathname==='/api'||pathname.startsWith('/api/')) {
    const destination=new URL(upstream);destination.pathname=parsed.pathname;destination.search=parsed.search;destination.hash='';
    const proxy=proxyRequest(destination,{method:req.method,headers:{...req.headers,host:upstream.host}},reply=>{
      res.writeHead(reply.statusCode||502,reply.headers);reply.pipe(res);
    });
    proxy.setTimeout(20000,()=>proxy.destroy(new Error('API timeout')));
    proxy.on('error',()=>{if(!res.headersSent)res.writeHead(503,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify({message:'A .NET API még nem érhető el.'}));});
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
server.listen(port,'0.0.0.0',()=>console.log(`Otthonra web: http://localhost:${port} (same-origin /api proxy)`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>process.exit(0)));
