/** Native MySQL polygons and owner-address API regression. Disposable loopback CI only. */
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdir, readFile, writeFile, chmod} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {DEMO_NEIGHBORHOOD_SCENARIO as scenario} from '../scripts/gcp/demo-data.mjs';
import {neighborhoodDataset} from '../dist/neighborhoods-data.js';

const origin = new URL(process.argv[2] || 'http://127.0.0.1:3000');
const mode = process.argv[3] || '--setup', container = process.argv[4];
if (process.env.CI !== 'true' || origin.protocol !== 'http:' || !['localhost','127.0.0.1','[::1]'].includes(origin.hostname)
  || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash
  || !['--setup','--verify','--stale','--rebuilt'].includes(mode) || !/^[a-f0-9]{12,64}$/.test(container || '')) {
  throw new Error('Use only the disposable loopback CI API and its MySQL service container.');
}
const fixturePath = resolve('.local/neighborhood-api-fixture.json');
async function api(path, {token, method='GET', body, status=200}={}) {
  // Deliberately no automatic test-address helper: malformed address checks must reach the real validator unchanged.
  const response = await fetch(new URL('/api'+path, origin), {method, redirect:'error', signal:AbortSignal.timeout(20000),
    headers:{...(token ? {Authorization:`Bearer ${token}`} : {}), ...(body === undefined ? {} : {'Content-Type':'application/json'})},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  assert.equal(response.status, status, `${method} ${path}: HTTP ${response.status}`);
  if (response.status === 204 || status >= 400) {await response.text(); return null;}
  return response.json();
}
function sql(statement) {
  return execFileSync('docker', ['exec','--env','MYSQL_PWD=ci-only-password',container,'mysql','--user=otthonra',
    '--batch','--skip-column-names','otthonra_ci','--execute',statement], {encoding:'utf8',timeout:30000,stdio:['ignore','pipe','pipe']}).trim();
}
function dataset() {
  const row = sql('SELECT SourceSha256,FeatureCount,ImportedAt FROM __OtthonraNeighborhoodDataset WHERE Id=1').split('\t');
  assert.equal(row[0],neighborhoodDataset.sourceSha256); assert.equal(Number(row[1]),4308); assert.ok(row[2]);
  assert.equal(Number(sql('SELECT COUNT(*) FROM NeighborhoodSearchAreas')),4308);
  assert.equal(Number(sql('SELECT COUNT(DISTINCT Id) FROM NeighborhoodSearchAreas')),4308);
  assert.equal(Number(sql('SELECT COUNT(*) FROM NeighborhoodSearchAreas WHERE ST_SRID(Boundary)<>4326')),0);
  return row;
}
function membershipMarker() {
  const row=sql('SELECT SourceSha256,ReclassifiedAt FROM __OtthonraNeighborhoodMembership WHERE Id=1').split('\t');
  assert.equal(row[0],neighborhoodDataset.sourceSha256);assert.ok(row[1]);return row;
}
function propertyLinks(property) {
  assert.match(property.id,/^[a-f0-9-]{36}$/);
  const actual=sql(`SELECT NeighborhoodId FROM PropertyNeighborhoods WHERE PropertyId='${property.id}' ORDER BY NeighborhoodId`);
  assert.deepEqual(actual ? actual.split('\n') : [],[...property.neighborhoodIds].sort(), 'Indexed links must match the point-derived saved membership');
}
function geocodeSignature(id) {
  assert.match(id,/^[a-f0-9-]{36}$/);
  return sql(`SELECT SHA2(CONCAT_WS('|',Street,HouseNumber,PostalCode,Latitude,Longitude,GeocodedAt,GeocodingProvider,GeocodingPlaceId,GeocodingQuality,GeocodingAddressKey),256) FROM Properties WHERE Id='${id}'`);
}
function privateCard(card) {
  assert.equal(card.property.address,''); assert.equal(card.property.addressDetails ?? null,null);
  const serialized=JSON.stringify(card.property);
  for(const key of ['latitude','longitude','street','houseNumber','postalCode','geocodingAddressKey','geocodingPlaceId']) {
    assert.equal(serialized.includes('"'+key+'"'),false,`${key} is owner-only`);
  }
  assert.equal(serialized.includes('OTTHONRA TEST'),false);
}
const active = (token,kind,id) => api('/me/active',{token,method:'PUT',body:{kind,id}});
const contains = (page,property) => page.items.some(item=>item.propertyId===property.id);
async function verify(fixture) {
  assert.deepEqual(dataset(),fixture.dataset,'Restart must preserve the version marker and import timestamp');
  assert.deepEqual(membershipMarker(),fixture.membershipMarker,'A current membership version must not reclassify rows on each cold start');
  const own=(await api('/me/entities',{token:fixture.seller})).properties.find(item=>item.id===fixture.edited.id);
  assert.ok(own); assert.ok(own.neighborhoodIds.includes(scenario.sestakertId)); assert.equal(own.neighborhoodIds.includes(scenario.venkertId),false);
  assert.equal(own.addressDetails.houseNumber,'2'); assert.equal(own.addressDetails.geocodingStatus,'located');
  assert.equal(geocodeSignature(own.id),fixture.geocodeSignature,'Reclassification must retain the stored address, point and owner-scoped geocoder metadata');
  propertyLinks(own);
  await active(fixture.buyer,'search',fixture.mixedSearch.id);
  const page=await api('/feed?includeApproximate=true',{token:fixture.buyer});
  assert.ok(contains(page,fixture.town)); assert.equal(contains(page,fixture.edited),false); assert.equal(contains(page,fixture.sestakert),false);
  assert.equal(contains(page,fixture.outside),false); page.items.forEach(privateCard);
}

// Choose an interior point of a real hole. A bounding-box-only implementation
// would classify this point as inside, which the native exact predicate rejects.
function ringContains(point,ring) {
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [x,y]=ring[i],[px,py]=ring[j];
    if((y>point[1])!==(py>point[1])&&point[0]<(px-x)*(point[1]-y)/(py-y)+x)inside=!inside;
  }
  return inside;
}
function interior(ring) {
  const xs=ring.map(point=>point[0]),ys=ring.map(point=>point[1]);
  const [minX,maxX,minY,maxY]=[Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)];
  for(let y=1;y<20;y++)for(let x=1;x<20;x++){
    const point=[minX+(maxX-minX)*x/20,minY+(maxY-minY)*y/20];
    if(ringContains(point,ring))return point;
  }
  return null;
}
async function geometryChecks() {
  const runtime=JSON.parse(gunzipSync(await readFile(new URL('../dist/data/neighborhoods.json.gz',import.meta.url))));
  let holeCase;
  for(const row of runtime.slice(1)){
    const polygons=row.geometry.type==='Polygon'?[row.geometry.coordinates]:row.geometry.coordinates;
    for(const polygon of polygons)for(const hole of polygon.slice(1)){
      const point=interior(hole);
      if(point&&ringContains(point,polygon[0])&&!polygons.some(other=>other!==polygon&&ringContains(point,other[0])&&!other.slice(1).some(ring=>ringContains(point,ring)))){
        holeCase={id:row.id,point,boundary:polygon[0][0]};break;
      }
    }
    if(holeCase)break;
  }
  assert.ok(holeCase,'The real 4308-feature dataset must exercise an interior hole');
  assert.match(holeCase.id,/^neighborhood:[a-f0-9]{24}$/);
  const classify=point=>{
    assert.ok(point.every(Number.isFinite));
    const wkt=`ST_GeomFromText('POINT(${point[0]} ${point[1]})',4326,'axis-order=long-lat')`;
    return sql(`SELECT MBRIntersects(Boundary,${wkt}),ST_Intersects(Boundary,${wkt}),ST_Contains(Boundary,${wkt}) FROM NeighborhoodSearchAreas WHERE Id='${holeCase.id}'`).split('\t').map(Number);
  };
  assert.deepEqual(classify(holeCase.point),[1,0,0],'A hole is outside the polygon even when its bounding box contains the point');
  assert.deepEqual(classify(holeCase.boundary),[1,1,0],'Boundary points belong under the application ST_Intersects policy');
}

if(mode==='--stale') {
  const fixture=JSON.parse(await readFile(fixturePath,'utf8'));assert.match(fixture.edited.id,/^[a-f0-9-]{36}$/);
  sql(`START TRANSACTION;
    UPDATE Properties SET NeighborhoodIdsJson='["${scenario.venkertId}"]' WHERE Id='${fixture.edited.id}';
    DELETE FROM PropertyNeighborhoods WHERE PropertyId='${fixture.edited.id}';
    INSERT INTO PropertyNeighborhoods(PropertyId,NeighborhoodId) VALUES ('${fixture.edited.id}','${scenario.venkertId}');
    UPDATE __OtthonraNeighborhoodMembership SET SourceSha256='${'0'.repeat(64)}' WHERE Id=1;
    COMMIT`);
  console.log('Prepared one stale membership and version marker in the disposable CI database.');
} else if(mode==='--rebuilt') {
  const fixture=JSON.parse(await readFile(fixturePath,'utf8')),previous=fixture.membershipMarker;
  fixture.membershipMarker=membershipMarker();assert.notDeepEqual(fixture.membershipMarker,previous,'A stale version requires one completed reclassification pass');
  await verify(fixture);
  await writeFile(fixturePath,JSON.stringify(fixture),{mode:0o600});await chmod(fixturePath,0o600);
  console.log('Stale membership rebuild passed: stored coordinates restored actual polygons and indexed links, without reimporting geometry.');
} else if(mode==='--verify') {
  await verify(JSON.parse(await readFile(fixturePath,'utf8')));
  console.log('Neighborhood restart passed: one 4308-row import, version timestamp, edited point membership and indexed links preserved.');
} else {
  const initial=dataset(),initialMembership=membershipMarker(); await geometryChecks();
  for(const [query,id] of [['Vénkert',scenario.venkertId],['Sestakert',scenario.sestakertId],['Debrecen Ven',scenario.venkertId]]){
    const suggestions=await api('/locations?q='+encodeURIComponent(query));
    const item=suggestions.items.find(item=>item.id===id); assert.ok(item,`Normal autocomplete must find ${query}`);
    assert.equal(item.kind,'neighborhood'); assert.match(item.label,/Debrecen/);
  }
  assert.ok((await api('/locations?q=V%C3%A9nkert&kind=property')).items.every(item=>item.kind!=='neighborhood'));
  const suffix=Date.now()+'-'+Math.random().toString(16).slice(2);
  const account=async name=>(await api('/auth/register',{method:'POST',body:{name:'Neighborhood '+name,email:`neighborhood-${name}-${suffix}@example.test`,password:'NeighborhoodSmoke2026!'}})).accessToken;
  const buyer=await account('buyer'),seller=await account('seller'),outsider=await account('outsider');
  const propertyBody={title:'Városrész API teszt · kitalált cím',city:'Debrecen',district:'',locationId:'city:Debrecen',type:'Lakás',price:50000000,area:65,rooms:3,
    street:'OTTHONRA TEST',houseNumber:'1',postalCode:null,balcony:false,elevator:false,images:[]};
  const {street,houseNumber,...withoutAddress}=propertyBody;
  await api('/properties',{token:seller,method:'POST',body:{...withoutAddress,houseNumber},status:400});
  await api('/properties',{token:seller,method:'POST',body:{...withoutAddress,street},status:400});
  await api('/properties',{token:seller,method:'POST',body:{...propertyBody,street:' ',houseNumber:''},status:400});
  await api('/properties',{token:seller,method:'POST',body:{...propertyBody,postalCode:'invalid'},status:400});
  await api('/properties',{token:seller,method:'POST',body:{...propertyBody,locationId:scenario.venkertId},status:400});
  await api('/properties',{method:'POST',body:propertyBody,status:401});
  const create=body=>api('/properties',{token:seller,method:'POST',body:{...propertyBody,...body},status:201});
  const venkert=await create({latitude:0,longitude:0,neighborhoodIds:[scenario.sestakertId]});
  const sestakert=await create({houseNumber:'2'});
  const town=await create({city:'Hajdúsámson',locationId:'city:Hajdúsámson'});
  const outside=await create({city:'Szeged',locationId:'city:Szeged'});
  assert.ok(venkert.neighborhoodIds.includes(scenario.venkertId)); assert.equal(venkert.neighborhoodIds.includes(scenario.sestakertId),false);
  assert.ok(sestakert.neighborhoodIds.includes(scenario.sestakertId)); assert.equal(sestakert.neighborhoodIds.includes(scenario.venkertId),false);
  assert.ok(Number.isFinite(venkert.addressDetails.latitude)); assert.ok(Number.isFinite(venkert.addressDetails.longitude));
  assert.equal(venkert.addressDetails.street,'OTTHONRA TEST'); assert.equal(venkert.addressDetails.houseNumber,'1');
  for(const property of [venkert,sestakert,town,outside])propertyLinks(property);
  await api('/properties/'+venkert.id,{token:outsider,method:'PUT',body:{...propertyBody,houseNumber:'2'},status:404});
  await api('/properties/'+venkert.id,{token:outsider,method:'DELETE',status:404});
  const searchBody={title:'Vénkert vagy Sestakert',city:'Debrecen',locationIds:[scenario.venkertId,scenario.sestakertId],type:'Lakás',maxPrice:70000000,minArea:50,minRooms:2,balcony:false,elevator:false};
  const quarters=await api('/searches',{token:buyer,method:'POST',body:searchBody,status:201});
  assert.deepEqual(quarters.locationIds,searchBody.locationIds); assert.equal(quarters.locations.length,2);
  await active(buyer,'search',quarters.id); let feed=await api('/feed',{token:buyer});
  assert.ok(contains(feed,venkert)); assert.ok(contains(feed,sestakert)); assert.equal(contains(feed,town),false); assert.equal(contains(feed,outside),false);
  feed.items.forEach(privateCard);
  const mixedSearch=await api('/searches',{token:buyer,method:'POST',body:{...searchBody,title:'Vénkert vagy Hajdúsámson',locationIds:[scenario.venkertId,'city:Hajdúsámson']},status:201});
  await active(buyer,'search',mixedSearch.id); feed=await api('/feed?includeApproximate=true',{token:buyer});
  assert.ok(contains(feed,venkert)); assert.ok(contains(feed,town)); assert.equal(contains(feed,sestakert),false); assert.equal(contains(feed,outside),false);
  await api('/decisions',{token:buyer,method:'POST',body:{propertyId:sestakert.id,searchRequestId:mixedSearch.id,liked:true,allowApproximate:true},status:400});
  await active(seller,'property',sestakert.id); const sellerFeed=await api('/feed',{token:seller});
  assert.ok(sellerFeed.items.some(item=>item.searchRequestId===quarters.id)); assert.equal(sellerFeed.items.some(item=>item.searchRequestId===mixedSearch.id),false);
  await api('/decisions',{token:seller,method:'POST',body:{propertyId:sestakert.id,searchRequestId:mixedSearch.id,liked:false,allowApproximate:true},status:400});
  await active(seller,'property',venkert.id);
  assert.ok((await api('/feed',{token:seller})).items.some(item=>item.searchRequestId===mixedSearch.id),'Seller discovery uses the same quarter membership');
  await api('/searches/'+quarters.id,{token:buyer,method:'PUT',body:{...searchBody,maxPrice:1}});
  await active(buyer,'search',quarters.id); feed=await api('/feed',{token:buyer});
  assert.equal(contains(feed,venkert),false); assert.equal(contains(feed,sestakert),false,'Other exact criteria remain AND filters');
  await api('/searches/'+quarters.id,{token:buyer,method:'PUT',body:searchBody});
  const edited=await api('/properties/'+venkert.id,{token:seller,method:'PUT',body:{...propertyBody,houseNumber:'2'}});
  assert.ok(edited.neighborhoodIds.includes(scenario.sestakertId)); assert.equal(edited.neighborhoodIds.includes(scenario.venkertId),false);
  const fixture={dataset:initial,membershipMarker:initialMembership,geocodeSignature:geocodeSignature(edited.id),buyer,seller,edited,sestakert,town,outside,mixedSearch}; await verify(fixture);
  await mkdir(dirname(fixturePath),{recursive:true}); await writeFile(fixturePath,JSON.stringify(fixture),{mode:0o600}); await chmod(fixturePath,0o600);
  console.log('Neighborhood MySQL/API passed: 4308 polygons, holes/boundaries, normal autocomplete, required owner address, private coordinates, two-quarter and mixed-town OR, hard decisions and edited membership cleanup.');
}
