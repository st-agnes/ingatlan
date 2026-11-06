/** City-area matching through the actual disposable API and MySQL database. */
import assert from 'node:assert/strict';
import {readFile, mkdir, writeFile, chmod} from 'node:fs/promises';
import {resolve, dirname} from 'node:path';
const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000');
if (origin.protocol !== 'http:' || !['localhost','127.0.0.1','[::1]'].includes(origin.hostname) || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) throw new Error('Use only a disposable loopback API.');
const fixturePath = resolve('.local/areas-upgrade-fixture.json');
async function call(path,{token,method='GET',body,status=200}={}) {
  const response = await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),
    headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},
    ...(body===undefined?{}:{body:JSON.stringify(body)})});
  assert.equal(response.status,status,`${method} ${path}: HTTP ${response.status}`);
  return response.status===204?null:response.json();
}
async function verify(fixture) {
  const entities=await call('/me/entities',{token:fixture.buyer});
  const search=entities.searchRequests.find(item=>item.id===fixture.searchId);
  assert.ok(search);
  assert.deepEqual(search.locationIds,['area:Budapest','area:Debrecen','city:Szeged']);
  assert.equal(search.locations[0].label,'Budapest és környéke (81 település)');
  assert.equal(search.locations[0].settlementCount,81);
  assert.equal(search.locations[1].settlementCount,13);
  assert.equal(search.locations[0].kind,'area');
  assert.deepEqual(entities.active,{kind:'search',id:fixture.searchId});
  const feed=await call('/feed',{token:fixture.buyer});
  for(const id of fixture.included)assert.ok(feed.items.some(item=>item.propertyId===id),'Missing area/member or exact-town recommendation');
  assert.ok(!feed.items.some(item=>item.propertyId===fixture.outside));
}
if(process.argv[3]==='--verify') {
  await verify(JSON.parse(await readFile(fixturePath,'utf8')));
  console.log('City-area restart preservation passed: selected area IDs, count labels, member matching and exact-town alternative survive.');
} else {
  const master=JSON.parse(await readFile(new URL('../dist/data/agglomerations.json',import.meta.url),'utf8'));
  const budapest=master.areas.find(area=>area.city==='Budapest'),debrecen=master.areas.find(area=>area.city==='Debrecen');
  assert.equal(budapest.settlements.length,81);assert.equal(debrecen.settlements.length,13);
  assert.ok(budapest.settlements.includes('Solymár'));
  const debrecenMember=debrecen.settlements.find(city=>city!=='Debrecen');
  const outside='Záhony';assert.ok(!budapest.settlements.includes(outside)&&!debrecen.settlements.includes(outside));
  const suffix=Date.now()+'-'+Math.random().toString(16).slice(2);
  const account=async name=>(await call('/auth/register',{method:'POST',body:{name:'Area '+name,email:`area-${name}-${suffix}@example.test`,password:'AreaSmokePassword2026!'}})).accessToken;
  const buyer=await account('buyer'),seller=await account('seller');
  const baseProperty={title:'Városkörnyéki helyszín API-próba',city:'Budapest',district:'V.',locationId:'district:Budapest:5',type:'Lakás',price:20000000,area:60,rooms:2,images:[],balcony:false,elevator:false};
  const create=async data=>call('/properties',{token:seller,method:'POST',body:{...baseProperty,...data},status:201});
  const central=await create({}),district23=await create({locationId:'district:Budapest:23',district:'XXIII.'});
  const nearby=await create({locationId:'city:Solymár',city:'Solymár',district:''});
  const provincial=await create({locationId:`city:${debrecenMember}`,city:debrecenMember,district:''});
  const exact=await create({locationId:'city:Szeged',city:'Szeged',district:''});
  const far=await create({locationId:`city:${outside}`,city:outside,district:''});
  const searchBody={title:'Város és környéke API-próba',city:'Budapest',locationIds:['area:Budapest'],type:'Lakás',minPrice:null,maxPrice:80000000,minArea:40,maxArea:null,minRooms:2,maxRooms:null,balcony:false,elevator:false};
  const search=await call('/searches',{token:buyer,method:'POST',body:searchBody,status:201});
  assert.deepEqual(search.locationIds,['area:Budapest'],'81 members must remain one selected area, below the 50-choice limit');
  assert.equal(search.locations[0].settlementCount,81);assert.equal(search.locations[0].kind,'area');
  await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
  let feed=await call('/feed',{token:buyer});
  for(const property of [central,district23,nearby])assert.ok(feed.items.some(item=>item.propertyId===property.id));
  for(const property of [provincial,exact,far])assert.ok(!feed.items.some(item=>item.propertyId===property.id));
  await call('/decisions',{token:buyer,method:'POST',body:{propertyId:provincial.id,searchRequestId:search.id,liked:true},status:400});
  const mixed={...searchBody,locationIds:['area:Budapest','area:Debrecen','city:Szeged']};
  await call('/searches/'+search.id,{token:buyer,method:'PUT',body:mixed});
  const fixture={buyer,seller,searchId:search.id,included:[central.id,district23.id,nearby.id,provincial.id,exact.id],outside:far.id};
  await verify(fixture);
  await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...mixed,maxPrice:10000000}});
  feed=await call('/feed',{token:buyer});
  assert.ok(feed.items.every(item=>!fixture.included.includes(item.propertyId)),'Other search filters still apply to every area member');
  await call('/searches/'+search.id,{token:buyer,method:'PUT',body:mixed});
  const suggestions=await call('/locations?q=Debrecen&kind=search');
  assert.equal(suggestions.items[0].id,'city:Debrecen');assert.equal(suggestions.items[1].id,'area:Debrecen');
  const precise=await call('/locations?q=Debrecen&kind=property');
  assert.ok(precise.items.every(item=>item.kind!=='area'));
  const full=await call('/locations?q='+encodeURIComponent('Debrecen és környéke (13 település)'));
  assert.equal(full.items[0].id,'area:Debrecen');
  await call('/locations?q=Debrecen&kind=invalid',{status:400});
  await call('/properties',{token:seller,method:'POST',body:{...baseProperty,city:'Debrecen',district:'',locationId:'area:Debrecen'},status:400});
  await call('/searches',{token:buyer,method:'POST',body:{...searchBody,locationIds:['area:Unknown']},status:400});
  await verify(fixture);
  await mkdir(dirname(fixturePath),{recursive:true});
  await writeFile(fixturePath,JSON.stringify(fixture),{mode:0o600});await chmod(fixturePath,0o600);
  console.log('City-area API integration passed: 81-member area stored once, center/district/member coverage, mixed OR, independent filters, property rejection and counted suggestions.');
}
