// One configuration for the development listener, readiness checks and URLs.
export function developmentConfig(env=process.env) {
  const rawPort=String(env.WEB_PORT??'3000').trim();
  const webPort=/^[0-9]+$/.test(rawPort)?Number(rawPort):NaN;
  if(!Number.isSafeInteger(webPort)||webPort<1||webPort>65535||webPort===5080)
    throw new Error('WEB_PORT must be an integer from 1 to 65535, excluding the API port 5080.');

  let api;
  try{api=new URL(env.API_ORIGIN||'http://127.0.0.1:5080');}
  catch{throw new Error('API_ORIGIN must be an HTTP origin such as http://127.0.0.1:5080.');}
  if(api.protocol!=='http:'||api.username||api.password||api.pathname!=='/'||api.search||api.hash)
    throw new Error('API_ORIGIN must use HTTP, without credentials, a path, a query or a fragment.');

  const codespace=String(env.CODESPACE_NAME||'').toLowerCase();
  const domain=String(env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN||'').toLowerCase();
  const label=/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
  const hostLabel=`${codespace}-${webPort}`;
  const domainLabels=domain.split('.');
  const forwardedOrigin=codespace&&label.test(codespace)&&label.test(hostLabel)
    &&`${hostLabel}.${domain}`.length<=253&&domainLabels.length>1&&domainLabels.every(part=>label.test(part))
    ?`https://${hostLabel}.${domain}`:null;
  return {webPort,webOrigin:`http://127.0.0.1:${webPort}`,apiOrigin:api.origin,forwardedOrigin};
}
