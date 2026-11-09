/** Embedded test fixtures through the actual disposable API. No external importer is used. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,chmod} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {DEMO_USERS,DEMO_FIXTURES,DEMO_PASSWORD} from '../scripts/gcp/demo-data.mjs';
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
if(origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback API.');
const mode=process.argv[3],fixturePath=resolve('.local/startup-seed-fixture.json'),version='20261109-test-fixtures-v3';
if(!['--initial','--preserved','--reset','--production'].includes(mode))throw new Error('Choose a startup seed check mode.');
async function api(path,{token,method='GET',body,status=200}={}){
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.equal(response.status,status,`${method} ${path}: HTTP ${response.status}`);return response.status===204?null:response.json();
}
const health=await api('/health');assert.equal(health.status,'ready');
if(mode==='--production'){assert.equal(health.deployment,'production');assert.equal(health.testCreditsEnabled,false);assert.equal(health.testDataVersion??null,null);}
else{assert.equal(health.deployment,'test');assert.equal(health.testDataVersion,version);}
const agent=DEMO_USERS.find(user=>user.accountType==='agent'),accounts=[...DEMO_USERS.slice(0,3),agent];
const catalog=key=>DEMO_FIXTURES.find(fixture=>fixture.key===key);
async function snapshot(f){return Promise.all(accounts.map(async user=>({key:user.key,profile:await api('/me',{token:f.tokens[user.key]}),entities:await api('/me/entities',{token:f.tokens[user.key]}),ledger:await api('/credits/ledger',{token:f.tokens[user.key]}),matches:await api('/matches',{token:f.tokens[user.key]})})));}
async function save(f){await mkdir(dirname(fixturePath),{recursive:true});await writeFile(fixturePath,JSON.stringify(f),{mode:0o600});await chmod(fixturePath,0o600);}
function entity(rows,fixture){return (fixture.kind==='property'?rows.entities.properties:rows.entities.searchRequests).find(item=>item.title===fixture.input.title);}
const signature=rows=>rows.map(({key,...data})=>JSON.stringify(data)).sort().join('\n');
async function seededLanding(){
 // Exercise the actual embedded startup catalog. The separate selector smoke
 // test uses invented API rows and cannot detect an impoverished shipped seed.
 const {regions}=JSON.parse(await readFile(new URL('./Otthonra.Api/Data/regions.json',import.meta.url),'utf8'));
 const {areas}=JSON.parse(await readFile(new URL('../dist/data/agglomerations.json',import.meta.url),'utf8'));
 const cityRegions=new Map(regions.flatMap(region=>region.settlements.map(city=>[city,region.id])));
 const labelRegions=new Map([...cityRegions].map(([city,id])=>[city,new Set([id])]));
 for(const roman of ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX','XXI','XXII','XXIII'])labelRegions.set(`Budapest ${roman}. kerület`,new Set(['HU110']));
 for(const area of areas)labelRegions.set(`${area.city} és környéke (${area.settlements.length} település)`,new Set(area.settlements.map(city=>cityRegions.get(city))));
 const searchKeys=['key','title','type','locations','minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms','ownerAccountType'].sort();
 const propertyKeys=['key','title','type','location','price','area','wholeRooms','halfRooms','rooms','lotArea','ownerAccountType'].sort();
 const expectedRegions=regions.map(({id,label})=>({id,label}));
 function check(page,region){
  assert.deepEqual(Object.keys(page).sort(),['properties','region','regions','scope','searches']);
  assert.deepEqual(page.regions,expectedRegions);assert.deepEqual(page.region,{id:region.id,label:region.label});assert.equal(page.scope,'region');
  assert.equal(page.searches.length,8,`${region.id}: the shipped catalog needs eight search previews`);
  assert.equal(page.properties.length,4,`${region.id}: the shipped catalog needs four property previews`);
  for(const [kind,items,keys] of [['search',page.searches,searchKeys],['property',page.properties,propertyKeys]]){
   assert.deepEqual([...new Set(items.map(row=>row.type))].sort(),['Ház','Lakás'],`${region.id}: ${kind} previews must include houses and apartments`);
   for(const [index,row] of items.entries()){
    assert.deepEqual(Object.keys(row).sort(),keys,'Public fixtures must expose only safe teaser fields');
    assert.equal(row.key,`${kind}-${index+1}`);assert.ok(['private','agent'].includes(row.ownerAccountType));
    assert.equal(row.title,kind==='property'?`Eladó ${row.type.toLowerCase()}`:row.type==='Ház'?'Házat keres':'Lakást keres');
    const labels=kind==='property'?[row.location]:row.locations;
    assert.ok(labels.length>0&&labels.every(label=>labelRegions.has(label)),'Only canonical public location labels are allowed');
    assert.ok(labels.some(label=>labelRegions.get(label).has(region.id)),`${region.id}: a teaser leaked from another county`);
   }
  }
  const serialized=JSON.stringify(page);
  for(const user of DEMO_USERS){assert.ok(!serialized.includes(user.email));assert.ok(!serialized.includes(user.phone));}
 }
 for(const region of regions)check(await api('/public/landing?region='+region.id),region);
 const region=regions.find(region=>region.id==='HU321'),searchSamples=new Set(),propertySamples=new Set(),allSearches=[],allProperties=[];
 for(let refresh=0;refresh<8;refresh++){
  const page=await api('/public/landing?region=HU321');check(page,region);
  for(const [name,min,max] of [['budgets','minPrice','maxPrice'],['sizes','minArea','maxArea'],['rooms','minRooms','maxRooms']]){
   assert.ok(new Set(page.searches.map(row=>JSON.stringify([row[min],row[max]]))).size>=3,`Actual Hajdú-Bihar searches must show at least three different ${name}`);
  }
  for(const field of ['price','area','rooms'])assert.ok(new Set(page.properties.map(row=>row[field])).size>=2,`Actual Hajdú-Bihar properties must have different ${field} values`);
  searchSamples.add(signature(page.searches));propertySamples.add(signature(page.properties));
  allSearches.push(...page.searches);allProperties.push(...page.properties);
 }
 assert.ok(searchSamples.size>=3,'Refreshing must visibly change seeded search membership, not merely source IDs or order');
 assert.ok(propertySamples.size>=3,'Refreshing must visibly change seeded property membership, not merely source IDs or order');
 for(const [label,values,low,high] of [
  ['property prices',allProperties.map(row=>row.price),60_000_000,120_000_000],
  ['property sizes',allProperties.map(row=>row.area),60,120],
  ['property rooms',allProperties.map(row=>row.rooms),2,4],
  ['search budgets',allSearches.map(row=>row.maxPrice).filter(value=>value!==null),40_000_000,120_000_000],
  ['search minimum sizes',allSearches.map(row=>row.minArea).filter(value=>value!==null),40,100],
  ['search minimum rooms',allSearches.map(row=>row.minRooms).filter(value=>value!==null),2,4]
 ])assert.ok(Math.min(...values)<=low&&Math.max(...values)>=high,`Actual Hajdú-Bihar ${label} must span small/affordable and large/premium cases`);
 console.log('Embedded catalog landing passed: all 20 regions have mixed housing previews; Hajdú-Bihar shows varied budgets, sizes and rooms across eight visibly changing samples, with canonical county isolation and no private fields.');
}
async function fresh(f){
 await seededLanding();
 const rows=await snapshot(f);
 for(const row of rows){const user=accounts.find(user=>user.key===row.key);assert.equal(row.profile.accountType,user.accountType??'private');assert.equal(row.profile.credits,100);assert.equal(row.entities.properties.length,DEMO_FIXTURES.filter(item=>item.owner===user.key&&item.kind==='property').length);assert.equal(row.entities.searchRequests.length,DEMO_FIXTURES.filter(item=>item.owner===user.key&&item.kind==='search').length);assert.deepEqual(row.entities.decisions,[]);assert.deepEqual(row.entities.reportedOwnerIds,[]);assert.deepEqual(row.matches,[]);assert.equal(row.ledger.length,1);assert.equal(row.ledger[0].amount,100);assert.ok([...row.entities.properties,...row.entities.searchRequests].every(item=>item.ownerAccountType===(user.accountType??'private')));const active=entity(row,catalog(user.active.key));assert.ok(active);assert.deepEqual(row.entities.active,{kind:user.active.kind,id:active.id});
  const feed=await api('/feed',{token:f.tokens[row.key]});assert.ok(feed.items.length>=30,`${row.key} must start with at least 30 recommendations`);assert.equal(feed.likeCost,user.active.kind==='property'?2:user.accountType==='agent'?1:0);
  const counterpart=item=>user.active.kind==='property'?item.searchRequest:item.property;
  if(user.accountType==='agent')assert.ok(feed.items.every(item=>counterpart(item).ownerAccountType==='private'),'Agents must see private counterparties only');
  else assert.ok(feed.items.some(item=>counterpart(item).ownerAccountType==='agent'));
  assert.ok(feed.items.some(item=>counterpart(item).ownerAccountType==='private'));
 }
 return rows;
}
if(mode==='--initial'){
 const f={tokens:{},ids:{}};
 for(const user of accounts){const session=await api('/auth/login',{method:'POST',body:{email:user.email,password:DEMO_PASSWORD}});f.tokens[user.key]=session.accessToken;f.ids[user.key]=session.user.id;}
 const rows=await fresh(f),anna=rows.find(row=>row.key==='anna'),peter=rows.find(row=>row.key==='peter'),agency=rows.find(row=>row.key===agent.key);
 const property=entity(peter,catalog('peter-pozsonyi')),search=entity(anna,catalog('anna-budapest')),agentSearch=entity(agency,catalog(agent.active.key));
 assert.equal((await api('/decisions',{token:f.tokens.anna,method:'POST',body:{propertyId:property.id,searchRequestId:search.id,liked:true}})).charged,0);
 const sellerLike=await api('/decisions',{token:f.tokens.peter,method:'POST',body:{propertyId:property.id,searchRequestId:search.id,liked:true}});assert.equal(sellerLike.charged,2);assert.ok(sellerLike.matchId);
 await api(`/matches/${sellerLike.matchId}/messages`,{token:f.tokens.anna,method:'POST',body:{text:'Cold-start preservation test message'},status:201});
 assert.equal((await api('/decisions',{token:f.tokens[agent.key],method:'POST',body:{propertyId:property.id,searchRequestId:agentSearch.id,liked:true}})).charged,1);
 await api('/reports',{token:f.tokens[agent.key],method:'POST',body:{entityKind:'property',entityId:property.id},status:201});
 const house=entity(anna,catalog('anna-solymar-house'));
 await api('/properties/'+house.id,{token:f.tokens.anna,method:'PUT',body:{...catalog('anna-solymar-house').input,title:'Edited and archived before cold start',archived:true}});
 await api('/me',{token:f.tokens.anna,method:'PUT',body:{name:'Edited before cold start',email:anna.profile.email,phone:anna.profile.phone}});
 await api('/me/active',{token:f.tokens.anna,method:'PUT',body:{kind:'search',id:entity(anna,catalog('anna-debrecen')).id}});
 f.expected=await snapshot(f);await save(f);console.log('Embedded startup fixtures passed: ready 12-account catalog, mixed-owner recommendations, agent/private/seller billing, match, message and changes recorded for restart preservation.');
}else{
 const f=JSON.parse(await readFile(fixturePath,'utf8'));
 if(mode==='--reset'){
  const rows=await fresh(f);for(const row of rows){const user=accounts.find(user=>user.key===row.key);assert.equal(row.profile.id,f.ids[row.key]);assert.equal(row.profile.name,user.name);}
  const agency=rows.find(row=>row.key===agent.key),peter=rows.find(row=>row.key==='peter'),property=entity(peter,catalog('peter-pozsonyi')),search=entity(agency,catalog(agent.active.key));
  await api('/me',{token:f.tokens[agent.key],method:'PUT',body:{name:'Later revision work',email:agency.profile.email,phone:agency.profile.phone}});
  assert.equal((await api('/decisions',{token:f.tokens[agent.key],method:'POST',body:{propertyId:property.id,searchRequestId:search.id,liked:true}})).charged,1);
  f.expected=await snapshot(f);await save(f);console.log('New test revision reset passed: original identities, full fixtures and 100 credits restored; later-revision work saved for old-replica guard.');
 }else{
  assert.deepEqual(await snapshot(f),f.expected,'A cold start, old revision replica or ordinary Production changed test data');
  console.log(mode==='--production'?'Ordinary Production safety passed: enabled seed flag did not reset or seed data.':'Same/previous revision preservation passed: edited profiles, archives, active selections, decisions, matches, messages, reports and balances unchanged.');
 }
}
