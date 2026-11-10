/** Diverse, changing public samples through the real API; disposable CI only. */
import assert from 'node:assert/strict';
import {readFile,writeFile,chmod} from 'node:fs/promises';
import {resolve} from 'node:path';

const origin=new URL(process.argv[2]||'http://127.0.0.1:3000'),mode=process.argv[3];
if(process.env.CI!=='true'||origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Use only a disposable loopback CI API.');
const path=resolve('.local/landing-selection-fixture.json');
async function api(route,{token,body,status=200}={}){
 const response=await fetch(new URL('/api'+route,origin),{method:body?'POST':'GET',redirect:'error',signal:AbortSignal.timeout(20000),headers:{Accept:'application/json',...(token?{Authorization:`Bearer ${token}`} : {}),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 assert.equal(response.status,status,`Unexpected status for ${route}`);return response.json();
}
const marker='FELULETPROBALASPRIVATSZOVEG',cities=['Szekszárd','Dombóvár'],types=['Lakás','Ház','Nyaraló','Iroda'];
const contactText='https://private-contact.example.test';
if(mode==='--setup'){
 const previous=JSON.parse(await readFile(resolve('.local/landing-refund-fixture.json'),'utf8')),ids=[],expected={property:[],search:[]};
 // Ordinary saves already forbid phone/email text. Keep that protection;
 // URL-only legacy-shaped content additionally exercises the teaser fallback.
 for(const contact of ['public-title-contact@example.test','+36 30 555 0799']){
  await api('/properties',{token:previous.tokens.seller,status:400,body:{title:'Napfényes otthon '+contact,locationId:'city:Szekszárd',city:'Szekszárd',type:'Lakás',price:20000000,area:40,rooms:2,balcony:false,elevator:false,images:[]}});
  await api('/searches',{token:previous.tokens.buyer,status:400,body:{title:'Otthont keresek '+contact,locationIds:['city:Szekszárd'],city:'Szekszárd',type:'Lakás',maxPrice:20000000,minArea:30,minRooms:1,balcony:false,elevator:false}});
 }
 for(const [typeIndex,type] of types.entries())for(const [priceIndex,price] of [20000000,55000000,105000000,220000000].entries()){
  const city=cities[priceIndex%2],area=[35,65,110,190][priceIndex]+typeIndex*3,rooms=[1,2,4,6][priceIndex];
  const propertyTitle=`Napfényes ${type.toLowerCase()} ${city} közelében ${priceIndex+1}`;
  const searchTitle=`Otthont keresek ${city} környékén ${type.toLowerCase()} ${priceIndex+1}`;
  // The mandatory Iroda stratum exercises contact-bearing title suppression
  // on every response; the other strata must preserve actual ordinary titles.
  const unsafe=type==='Iroda';
  const property=await api('/properties',{token:previous.tokens.seller,status:201,body:{title:unsafe?propertyTitle+' '+contactText:propertyTitle,description:marker,address:marker,locationId:'city:'+city,city,type,price,area,rooms,wholeRooms:rooms,halfRooms:0,lotArea:type==='Ház'?400:null,floor:type==='Ház'?null:1,balcony:false,elevator:false,images:[]}});
  const search=await api('/searches',{token:previous.tokens.buyer,status:201,body:{title:unsafe?searchTitle+' '+contactText:searchTitle,description:marker,locationIds:['city:'+city],city,type,minPrice:null,maxPrice:price,minArea:Math.max(20,area-10),maxArea:area+15,minRooms:Math.max(1,rooms-1),maxRooms:rooms+1,balcony:false,elevator:false}});
  expected.property.push({title:unsafe?'Eladó iroda':propertyTitle,type,ownerFirstName:'Péter'});
  expected.search.push({title:unsafe?'Irodát keres':searchTitle,type,ownerFirstName:'Anna'});
  ids.push(property.id,search.id);
 }
 await writeFile(path,JSON.stringify({ids,expected}),{mode:0o600});await chmod(path,0o600);
 console.log('Diverse landing fixture prepared: 16 properties and 16 searches across four types, four budgets, two towns and varied sizes/room counts.');
}else if(mode==='--verify'){
 const fixture=JSON.parse(await readFile(path,'utf8'));
 const signature=rows=>rows.map(({key,...data})=>JSON.stringify(data)).sort().join('\n');
 let prior=null;
 for(let i=0;i<8;i++){
  const page=await api('/public/landing?region=HU233');
  assert.equal(page.scope,'region');assert.equal(page.region.id,'HU233');assert.equal(page.searches.length,8);assert.equal(page.properties.length,4);
  assert.deepEqual([...new Set(page.searches.map(row=>row.type))].sort(),[...types].sort());
  assert.deepEqual([...new Set(page.properties.map(row=>row.type))].sort(),[...types].sort());
  assert.ok(new Set(page.searches.map(row=>row.maxPrice)).size>=3,'Search previews should cover several budgets');
  assert.ok(new Set(page.properties.map(row=>row.price)).size>=2,'Property previews should cover several budgets');
  assert.equal(new Set(page.searches.flatMap(row=>row.locations)).size,2,'Searches should represent both towns');
  for(const row of page.properties)assert.ok(cities.includes(row.location));
  for(const row of page.searches)assert.ok(row.locations.every(label=>cities.includes(label)));
  const serialized=JSON.stringify(page);assert.ok(!serialized.includes(marker));
  for(const value of ['public-title-contact@example.test','+36 30 555 0799','private-contact.example.test','Nagy Péter','Kovács Anna'])assert.ok(!serialized.includes(value),'Landing cards exposed contact data or a full owner name');
  for(const [kind,rows] of [['property',page.properties],['search',page.searches]])for(const row of rows){
   assert.ok(fixture.expected[kind].some(expected=>expected.title===row.title&&expected.type===row.type&&expected.ownerFirstName===row.ownerFirstName),
    'Landing cards must retain ordinary ad titles and the real owner first name while suppressing contact-bearing titles');
  }
  for(const id of fixture.ids)assert.ok(!serialized.includes(id),'Public samples must not expose source IDs');
  const current={search:signature(page.searches),property:signature(page.properties)};
  if(prior){assert.notEqual(current.search,prior.search,'Refreshing must change search membership, not just order');assert.notEqual(current.property,prior.property,'Refreshing must change property membership, not just order');}
  prior=current;
 }
 const empty=await api('/public/landing?region=HU313');
 assert.equal(empty.region.id,'HU313');for(const row of empty.properties)assert.ok(!cities.includes(row.location),'Sampling must not leak another county into a selected region');
 console.log('Diverse public landing API passed: actual ad titles and owner first names, contact-bearing title suppression, four types, budget and town coverage, eight successive changing memberships inside the cache, county isolation and private data protection.');
}else throw new Error('Expected --setup or --verify.');
