/** Real postal streets through the disposable MySQL API; the next fixture revision resets these edits. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {DEMO_FIXTURES,DEMO_STREET_SCENARIO as scenario,DEMO_NEIGHBORHOOD_SCENARIO as quarters} from '../scripts/gcp/demo-data.mjs';

const origin=new URL(process.argv[2]||'http://127.0.0.1:3000');
if(process.env.CI!=='true'||origin.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname)
 ||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash||process.argv.length>3){
 throw new Error('Use only the disposable loopback CI API immediately before its fixture reset.');
}
const fixture=JSON.parse(await readFile(new URL('../.local/startup-seed-fixture.json',import.meta.url),'utf8'));
const tokens=fixture.tokens;
for(const owner of ['julia','marton','reka','bence'])assert.ok(tokens[owner],'Run the initial embedded fixture smoke first.');
async function api(path,{token,method='GET',body,status=200}={}){
 const response=await fetch(new URL('/api'+path,origin),{method,redirect:'error',signal:AbortSignal.timeout(20000),
  headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},
  ...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.equal(response.status,status,`${method} ${path}: HTTP ${response.status}`);
 if(status>=400||response.status===204){await response.text();return null;}
 return response.json();
}
const catalog=key=>DEMO_FIXTURES.find(item=>item.key===key);
const own=async owner=>(await api('/me/entities',{token:tokens[owner]}));
const entity=(rows,key)=>{const definition=catalog(key);return (definition.kind==='property'?rows.properties:rows.searchRequests).find(item=>item.title===definition.input.title);};
const select=(owner,kind,id)=>api('/me/active',{token:tokens[owner],method:'PUT',body:{kind,id}});
const has=(page,property)=>page.items.some(item=>item.propertyId===property.id);
function privateProperty(property){
 assert.equal(property.address,'');assert.equal(property.addressDetails??null,null);
 const serialized=JSON.stringify(property);
 for(const key of ['streetId','street','houseNumber','postalCode','latitude','longitude','geocodingPlaceId','geocodingAddressKey']){
  assert.equal(serialized.includes('"'+key+'"'),false,`${key} is owner-only`);
 }
 assert.equal(serialized.includes(scenario.firstName),false);assert.equal(serialized.includes('99999'),false);
}
const first=entity(await own('reka'),scenario.firstProperty),second=entity(await own('bence'),scenario.secondProperty);
const nearby=entity(await own('bence'),'bence-debrecen-2');
assert.ok(first&&second&&nearby);
for(const [property,id,name] of [[first,scenario.firstId,scenario.firstName],[second,scenario.secondId,scenario.secondName]]){
 assert.equal(property.addressDetails.streetId,id);assert.equal(property.addressDetails.street,name);
 assert.equal(property.addressDetails.houseNumber,'99999');assert.equal(property.addressDetails.provider,'synthetic-test-fixture');
 assert.equal(property.addressDetails.quality,'SYNTHETIC');assert.ok(Number.isFinite(property.addressDetails.latitude));
 assert.equal(Object.hasOwn(property,'streetId'),false,'The street identity belongs inside the private address DTO.');
 const scoped=await api('/streets?q='+encodeURIComponent(name)+'&locationId=city%3ADebrecen&limit=25');
 assert.ok(scoped.items.some(item=>item.id===id&&item.kind==='street'));
 assert.ok(scoped.items.every(item=>item.city==='Debrecen'));
 const locations=await api('/locations?q='+encodeURIComponent('Debrecen '+name)+'&kind=search&limit=25');
 assert.ok(locations.items.some(item=>item.id===id&&item.kind==='street'),'The normal location picker must find real postal streets.');
 assert.ok((await api('/locations?q='+encodeURIComponent(name)+'&kind=property&limit=25')).items.every(item=>item.kind!=='street'));
}
await api('/streets?q=utca&locationId=area%3ADebrecen',{status:400});
await api('/streets?q=utca&locationId='+encodeURIComponent(scenario.firstId),{status:400});
await api('/streets?q=utca&locationId=city%3AImaginaryTown',{status:400});
assert.ok((await api('/streets?q=utca&locationId=district%3ABudapest%3A2&limit=25')).items.every(item=>item.city==='Budapest'&&item.district==='II.'));

const input=catalog(scenario.firstProperty).input;
const beforeCredits=(await api('/me',{token:tokens.reka})).credits;
const invalid='street:'+'0'.repeat(24);
for(const changes of [
 {streetId:invalid}, {streetId:scenario.secondId}, {street:'Nem ez a közterület',streetId:scenario.firstId},
 {city:'Szeged',locationId:'city:Szeged',streetId:scenario.firstId},
 {postalCode:'9999',streetId:scenario.firstId}, {locationId:scenario.firstId}
])await api('/properties/'+first.id,{token:tokens.reka,method:'PUT',body:{...input,...changes},status:400});
const runtime=JSON.parse(gunzipSync(await readFile(new URL('../dist/data/streets.json.gz',import.meta.url))));
const health=await api('/health');assert.equal(health.streetCount,runtime[0].count);assert.equal(health.streetDatasetVersion,runtime[0].datasetVersion);
const capital=runtime.slice(1).find(row=>row.city==='Budapest'&&row.district==='II.');assert.ok(capital);
await api('/properties',{token:tokens.reka,method:'POST',body:{...input,city:'Budapest',district:'V.',locationId:'district:Budapest:5',street:capital.streetName,streetId:capital.id,postalCode:capital.postalCodes[0]},status:400});
assert.equal((await api('/me',{token:tokens.reka})).credits,beforeCredits,'Invalid street input must fail before billing.');
await api('/properties/'+first.id,{token:tokens.bence,method:'PUT',body:input,status:404});
// Reusing the unchanged owner address uses its cached synthetic point. Omitting
// a uniquely scoped street identity still resolves the same canonical street.
const {streetId,...inferredInput}=input;
const inferred=await api('/properties/'+first.id,{token:tokens.reka,method:'PUT',body:inferredInput});
assert.equal(inferred.addressDetails.streetId,scenario.firstId);
assert.equal(inferred.addressDetails.latitude,first.addressDetails.latitude);assert.equal(inferred.addressDetails.longitude,first.addressDetails.longitude);

const searchBase=catalog(scenario.streetSearch).input;
const create=changes=>api('/searches',{token:tokens.julia,method:'POST',body:{...searchBase,...changes},status:201});
const streets=await create({title:'CI · Két postai közterület'});
assert.deepEqual(streets.locationIds,[scenario.firstId,scenario.secondId]);
await select('julia','search',streets.id);let page=await api('/feed',{token:tokens.julia});
assert.ok(has(page,first));assert.ok(has(page,second));assert.equal(has(page,nearby),false);page.items.forEach(card=>privateProperty(card.property));
const mixed=await create({title:'CI · Utca vagy másik település',locationIds:[scenario.firstId,'city:Hajdúsámson']});
await select('julia','search',mixed.id);page=await api('/feed?includeApproximate=true',{token:tokens.julia});
assert.ok(has(page,first));assert.ok(has(page,nearby));assert.equal(has(page,second),false,'A street selection must not broaden to the entire city.');
const beforeBuyer=(await api('/me',{token:tokens.julia})).credits;
await api('/decisions',{token:tokens.julia,method:'POST',body:{propertyId:second.id,searchRequestId:mixed.id,liked:true,allowApproximate:true},status:400});
assert.equal((await api('/me',{token:tokens.julia})).credits,beforeBuyer);
await select('reka','property',first.id);assert.ok((await api('/feed',{token:tokens.reka})).items.some(card=>card.searchRequestId===mixed.id));
await select('bence','property',second.id);assert.equal((await api('/feed?includeApproximate=true',{token:tokens.bence})).items.some(card=>card.searchRequestId===mixed.id),false);
const beforeSeller=(await api('/me',{token:tokens.bence})).credits;
await api('/decisions',{token:tokens.bence,method:'POST',body:{propertyId:second.id,searchRequestId:mixed.id,liked:false,allowApproximate:true},status:400});
assert.equal((await api('/me',{token:tokens.bence})).credits,beforeSeller);
for(const [title,ids] of [['Utca vagy városrész',[scenario.firstId,quarters.sestakertId]],['Utca vagy környék',[scenario.firstId,'area:Debrecen']],['Utca vagy teljes város',[scenario.firstId,'city:Debrecen']]]){
 const search=await create({title:'CI · '+title,locationIds:ids});await select('julia','search',search.id);
 page=await api('/feed',{token:tokens.julia});assert.ok(has(page,first));assert.ok(has(page,second),'OR alternatives remain independent choices.');
}
for(const changes of [{locationIds:[invalid]},{locationIds:[scenario.firstId,invalid]}])await api('/searches',{token:tokens.julia,method:'POST',body:{...searchBase,...changes},status:400});
const houses=await create({title:'CI · Utcához kötött házkeresés',type:'Ház',locationIds:[scenario.firstId]});
await select('julia','search',houses.id);assert.equal((await api('/feed?includeApproximate=true',{token:tokens.julia})).items.length,0,'Property type stays a hard gate under approximate consent.');
const impossible=await create({title:'CI · Utcához kötött árkorlát',locationIds:[scenario.firstId],maxPrice:1});
await select('julia','search',impossible.id);assert.equal(has(await api('/feed',{token:tokens.julia}),first),false,'Other exact criteria still apply.');

// The deliberately unknown reserved test street remains valid geocoded free
// input. Changing away from a source street must remove its old association.
const free=await api('/properties/'+first.id,{token:tokens.reka,method:'PUT',body:{...input,street:'OTTHONRA TEST',streetId:null,houseNumber:'1',postalCode:null}});
assert.equal(free.addressDetails.streetId??null,null);assert.equal(free.addressDetails.street,'OTTHONRA TEST');
await select('julia','search',streets.id);assert.equal(has(await api('/feed?includeApproximate=true',{token:tokens.julia}),first),false);
const town=await create({title:'CI · Szabad közterület városi keresése',locationIds:['city:Debrecen']});
await select('julia','search',town.id);assert.ok(has(await api('/feed',{token:tokens.julia}),first),'A free street address remains eligible for ordinary city matching.');
const landing=await api('/public/landing?region=HU321');
for(const property of landing.properties){assert.equal(Object.hasOwn(property,'streetId'),false);assert.equal(Object.hasOwn(property,'addressDetails'),false);}
console.log('Street MySQL/API passed: real scoped autocomplete, canonical/inferred owner identity, private address fields, street and mixed OR matching for both roles, hard decisions/type gates, forged identity rejection and free-address cleanup. Reset the disposable fixture revision next.');
