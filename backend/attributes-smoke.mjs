/** Real API/MySQL attribute regression. Only disposable loopback environments. */
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile, chmod} from 'node:fs/promises';
import {resolve, dirname} from 'node:path';
const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000');
if (origin.protocol !== 'http:' || !['localhost','127.0.0.1','[::1]'].includes(origin.hostname)
    || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) throw new Error('Use only a disposable loopback API.');
const fixturePath = resolve('.local/attributes-upgrade-fixture.json');
async function call(path, {token, method='GET', body, status=200}={}) {
  const response = await fetch(new URL('/api'+path, origin), {method, redirect:'error', signal:AbortSignal.timeout(20000),
    headers:{...(token?{Authorization:`Bearer ${token}`} : {}), ...(body === undefined ? {} : {'Content-Type':'application/json'})},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  assert.equal(response.status,status,`${method} ${path}: HTTP ${response.status}`);
  return response.status === 204 ? null : response.json();
}
const propertyFields = ['condition','building','constructionAge','view','ceilingHeight','floor','heatingType','insulated','energyRating','airConditioning','solarPanels','parkingType'];
const searchFields = ['conditions','buildings','constructionAges','views','ceilingHeight','floors'];
async function verify(fixture) {
  const [seller,buyer] = await Promise.all([call('/me/entities',{token:fixture.seller}),call('/me/entities',{token:fixture.buyer})]);
  const property = seller.properties.find(x=>x.id === fixture.propertyId);
  const search = buyer.searchRequests.find(x=>x.id === fixture.searchId);
  assert.ok(property); assert.ok(search);
  for(const field of propertyFields)assert.deepEqual(property[field],fixture.property[field],`Property ${field} was not preserved`);
  for(const field of searchFields)assert.deepEqual(search[field],fixture.search[field],`Search ${field} was not preserved`);
  assert.equal(property.insulated,false); assert.equal(property.solarPanels,false); assert.equal(property.airConditioning,true);
  assert.equal(property.floor,12, 'An existing floor above 11 must retain its actual value');
}
if (process.argv[3] === '--verify') {
  await verify(JSON.parse(await readFile(fixturePath,'utf8')));
  console.log('Attribute restart preservation passed: selections, false/null distinction and actual floor survive.');
} else {
  const suffix=Date.now()+'-'+Math.random().toString(16).slice(2);
  const account=async name=>(await call('/auth/register',{method:'POST',body:{name:'Attributes '+name,email:`attrs-${name}-${suffix}@example.test`,password:'AttributeSmoke2026!'}})).accessToken;
  const buyer=await account('buyer'),seller=await account('seller');
  const baseProperty={title:'Opcionális adatok API-próbája',city:'Budapest',locationId:'district:Budapest:13',district:'XIII.',type:'Lakás',price:80000000,area:70,rooms:3,balcony:false,elevator:false,images:[]};
  const propertyBody={...baseProperty,condition:'Jó',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m feletti',floor:12,heatingType:'Hőszivattyú',insulated:false,energyRating:'A+',airConditioning:true,solarPanels:false,parkingType:'Udvari beálló'};
  const searchBody={title:'Több opcionális választás API-próbája',city:'Budapest',locationIds:['district:Budapest:13'],type:'Lakás',minPrice:null,maxPrice:100000000,minArea:40,maxArea:null,minRooms:2,maxRooms:null,balcony:false,elevator:false,conditions:['Átlagos','Jó'],buildings:['Tégla','Panel'],constructionAges:['10–30 év közötti','31–40 év közötti'],views:['Kertre néző','Panorámás'],ceilingHeight:'3 m feletti',floors:[11]};
  const property=await call('/properties',{token:seller,method:'POST',body:propertyBody,status:201});
  const search=await call('/searches',{token:buyer,method:'POST',body:searchBody,status:201});
  const excluded=[];
  for(const change of [{condition:'Felújítandó'},{building:'Vályog'},{constructionAge:'Több mint 50 éves'},{view:'Udvari'},{ceilingHeight:'3 m alatti'},{floor:3}]) {
    excluded.push(await call('/properties',{token:seller,method:'POST',body:{...propertyBody,...change},status:201}));
  }
  const unknown=await call('/properties',{token:seller,method:'POST',body:baseProperty,status:201});
  await call('/me/active',{token:buyer,method:'PUT',body:{kind:'search',id:search.id}});
  const feed=await call('/feed',{token:buyer});
  assert.ok(feed.items.some(x=>x.propertyId===property.id));
  assert.ok(feed.items.every(x=>![...excluded,unknown].some(p=>p.id===x.propertyId)));
  const card=feed.items.find(x=>x.propertyId===property.id).property;
  for(const field of propertyFields)assert.deepEqual(card[field],property[field],`Feed lost property ${field}`);
  for(const candidate of [...excluded,unknown]) await call('/decisions',{token:buyer,method:'POST',body:{propertyId:candidate.id,searchRequestId:search.id,liked:true},status:400});
  await call('/decisions',{token:buyer,method:'POST',body:{propertyId:property.id,searchRequestId:search.id,liked:true}});
  const cleared={...searchBody,conditions:[],buildings:[],constructionAges:[],views:[],ceilingHeight:'',floors:[]};
  await call('/searches/'+search.id,{token:buyer,method:'PUT',body:cleared});
  assert.ok((await call('/feed',{token:buyer})).items.some(x=>x.propertyId===unknown.id),'Empty optional filters must include an unannotated property');
  const duplicate=await call('/searches/'+search.id,{token:buyer,method:'PUT',body:{...searchBody,conditions:['Jó','Jó'],floors:[11,11]}});
  assert.deepEqual(duplicate.conditions,['Jó']);assert.deepEqual(duplicate.floors,[11]);
  await call('/searches/'+search.id,{token:buyer,method:'PUT',body:searchBody});
  for(const field of ['condition','building','constructionAge','view','ceilingHeight']) await call('/properties',{token:seller,method:'POST',body:{...propertyBody,[field]:'Ismeretlen opció'},status:400});
  for(const [field,value] of [['conditions',['Ismeretlen']],['buildings',['Ismeretlen']],['constructionAges',['Ismeretlen']],['views',['Ismeretlen']],['floors',[12]],['conditions',[null]],['ceilingHeight','Ismeretlen']]) {
    await call('/searches',{token:buyer,method:'POST',body:{...searchBody,[field]:value},status:400});
  }
  const blank={...baseProperty,floor:null,condition:null,building:null,constructionAge:null,view:null,ceilingHeight:null,heatingType:null,insulated:null,energyRating:null,airConditioning:null,solarPanels:null,parkingType:null};
  const reset=await call('/properties/'+property.id,{token:seller,method:'PUT',body:blank});
  for(const field of ['condition','building','constructionAge','view','ceilingHeight','heatingType','energyRating','parkingType'])assert.equal(reset[field],'');
  for(const field of ['floor','insulated','airConditioning','solarPanels'])assert.equal(reset[field],null);
  const restored=await call('/properties/'+property.id,{token:seller,method:'PUT',body:propertyBody});
  const fixture={buyer,seller,propertyId:property.id,searchId:search.id,property:restored,search};
  await verify(fixture);
  await mkdir(dirname(fixturePath),{recursive:true});
  await writeFile(fixturePath,JSON.stringify(fixture),{mode:0o600});await chmod(fixturePath,0o600);
  console.log('Attribute API integration passed: optional persistence, OR/AND filters, missing data exclusion, validation, clearing, false/null and floor 11+; incompatible decisions rejected.');
}
