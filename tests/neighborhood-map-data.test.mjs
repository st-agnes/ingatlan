import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile,readdir} from 'node:fs/promises';
import {gunzipSync,gzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {getLocation,locations} from '../dist/locations.js';

const root=new URL('../',import.meta.url),directory=new URL('dist/data/map/',root);
const index=JSON.parse(await readFile(new URL('index.json',directory),'utf8'));
const sourceBytes=await readFile(new URL('dist/data/neighborhoods.json.gz',root));
const [header,...sourceRows]=JSON.parse(gunzipSync(sourceBytes));
const original=new Map(sourceRows.map(row=>[row.id,row]));
const canonical=locations.filter(item=>item.kind==='neighborhood');
const parts=geometry=>geometry.type==='Polygon'?[geometry.coordinates]:geometry.type==='MultiPolygon'?geometry.coordinates:assert.fail('Expected polygonal display geometry');
const topology=geometry=>parts(geometry).map(polygon=>polygon.length);
const allChunks=await Promise.all(index.cities.map(async city=>{
 const bytes=await readFile(new URL(city.file,directory));
 return {city,bytes,collection:JSON.parse(bytes)};
}));

function validBounds(bounds){
 assert.equal(bounds.length,4);assert.ok(bounds.every(Number.isFinite));
 assert.ok(bounds[0]>=16&&bounds[2]<=23&&bounds[1]>=45&&bounds[3]<=49);
 assert.ok(bounds[0]<bounds[2]&&bounds[1]<bounds[3]);
}

test('the display manifest pins the canonical source, all4308areas and every canonical town/district focus',()=>{
 assert.equal(index.schemaVersion,1);assert.equal(index.count,4308);assert.equal(index.displayOnly,true);
 assert.equal(index.sourceSha256,header.sourceSha256);
 assert.equal(index.municipalitiesSha256,header.testMunicipalitySourceSha256);
 assert.equal(index.version,'20261120-neighborhood-display-v1-367af069d58c-fb5f1293628b');
 assert.equal(index.cities.length,617);assert.equal(index.cities.reduce((sum,city)=>sum+city.count,0),4308);
 assert.equal(Object.keys(index.focus).length,3155+23+4308);
 for(const location of locations.filter(item=>['city','district','neighborhood'].includes(item.kind))){
  assert.ok(index.focus[location.id],`Missing focus bounds for ${location.id}`);validBounds(index.focus[location.id]);
 }
 assert.ok(index.attribution.some(value=>value.includes('OpenStreetMap contributors')));
 assert.ok(index.attribution.some(value=>value.includes('THIRD-PARTY-NOTICES.txt')));
 assert.match(index.sourceNotice,/unchanged full MySQL boundaries/);
});

test('content-addressed municipality files are the exact bounded lazy layer set',async()=>{
 assert.deepEqual((await readdir(directory)).sort(),['index.json',...index.cities.map(city=>city.file)].sort());
 const names=new Set();let bytes=0,compressed=0;
 for(const {city,bytes:content,collection}of allChunks){
  assert.match(city.file,/^city-[a-f0-9]{20}\.json$/);assert.ok(!names.has(city.file));names.add(city.file);
  assert.equal(city.file,`city-${createHash('sha256').update(content).digest('hex').slice(0,20)}.json`);
  assert.equal(collection.type,'FeatureCollection');assert.equal(collection.version,index.version);
  assert.equal(collection.city,city.city);assert.equal(collection.features.length,city.count);validBounds(city.bounds);
  assert.ok(content.byteLength<=2*1024*1024,'Each city is bounded independently of the country');
  bytes+=content.byteLength;compressed+=gzipSync(content).length;
 }
 assert.ok(bytes<=8*1024*1024,'Only requested city files should cross the browser boundary');
 assert.ok(compressed<=2*1024*1024,'The entire catalogue stays modest even though it is never fetched eagerly');
 assert.ok(index.cities.every(city=>!Object.hasOwn(city,'geometry')));
 assert.ok(!Object.hasOwn(index,'features'),'The initial manifest cannot contain country-wide polygon coordinates');
});

test('all display polygons retain canonical identities and every original hole/multipart component',()=>{
 const seen=new Set();let inputVertices=0,displayVertices=0,holes=0,multipart=0;
 for(const {city,collection}of allChunks)for(const feature of collection.features){
  assert.equal(feature.type,'Feature');assert.ok(!seen.has(feature.id));seen.add(feature.id);
  const location=getLocation(feature.id),source=original.get(feature.id);assert.ok(location&&source);
  assert.equal(location.kind,'neighborhood');assert.equal(location.city,city.city);
  assert.deepEqual(Object.keys(feature.properties).sort(),['city','estimated','id','label','name']);
  assert.equal(feature.properties.id,feature.id);assert.equal(feature.properties.name,location.name);
  assert.equal(feature.properties.city,location.city);assert.equal(feature.properties.label,location.label);
  assert.equal(feature.properties.estimated,location.estimated);
  assert.deepEqual(feature.bbox,index.focus[feature.id]);validBounds(feature.bbox);
  assert.equal(feature.geometry.type,source.geometry.type);assert.deepEqual(topology(feature.geometry),topology(source.geometry));
  for(const polygon of parts(source.geometry))for(const ring of polygon)inputVertices+=ring.length;
  if(parts(feature.geometry).length>1)multipart++;
  for(const polygon of parts(feature.geometry)){
   holes+=polygon.length-1;
   for(const ring of polygon){
    assert.ok(ring.length>=4);assert.deepEqual(ring[0],ring.at(-1));displayVertices+=ring.length;
    const origin=ring[0];let area=0;
    for(let i=0;i<ring.length;i++){
     const point=ring[i];assert.equal(point.length,2);assert.ok(point.every(Number.isFinite));
     assert.ok(point[0]>=16&&point[0]<=23&&point[1]>=45&&point[1]<=49);
     if(i){const last=ring[i-1];area+=(last[0]-origin[0])*(point[1]-origin[1])-(point[0]-origin[0])*(last[1]-origin[1]);}
    }
    assert.notEqual(area,0,'Quantization cannot collapse small original rings');
   }
  }
 }
 assert.deepEqual([...seen].sort(),canonical.map(item=>item.id).sort());assert.equal(seen.size,4308);
 assert.ok(holes>0&&multipart>0,'Real hole and multipart cases must actually be exercised');
 assert.ok(displayVertices<inputVertices*.6,'Display simplification must remove at least40% of vertex work without losing tiny parts or holes');
});

test('Budapest ward focus uses the actual canonical ward outline rather than a whole-city fallback',()=>{
 const roman=['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX','XXI','XXII','XXIII'];
 for(let number=1;number<=23;number++){
  const ward=canonical.find(item=>item.city==='Budapest'&&item.name===roman[number-1]+'. kerület');assert.ok(ward);
  assert.deepEqual(index.focus[`district:Budapest:${number}`],index.focus[ward.id]);
  assert.notDeepEqual(index.focus[`district:Budapest:${number}`],index.focus['city:Budapest']);
 }
});

test('a town without neighborhood boundaries still has real municipality focus bounds',()=>{
 const citiesWithAreas=new Set(index.cities.map(item=>item.city));
 const town=locations.find(item=>item.kind==='city'&&!citiesWithAreas.has(item.city));assert.ok(town);
 validBounds(index.focus[town.id]);
});
