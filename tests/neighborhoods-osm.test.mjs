import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, readFile, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {classifyOsmBoundary, collectOsmCandidates, loadOsmSources, osmGeometry, stitchRings} from '../scripts/neighborhoods/osm.mjs';
import {buildCatalog, mergeCatalogs, validateGeometry} from '../scripts/neighborhoods/build.mjs';

const square = [[19,47],[19.1,47],[19.1,47.1],[19,47.1],[19,47]];
const geo = points => points.map(([lon,lat])=>({lon,lat}));
const member = (ref,points,role='outer')=>({type:'way',ref,role,geometry:geo(points)});
const way = (id=1,points=square,tags={})=>({type:'way',id,geometry:geo(points),tags:{name:'Teszt',place:'suburb',...tags}});
const relation = members=>({type:'relation',id:10,tags:{type:'multipolygon',name:'Teszt',place:'suburb'},members});
const snapshot = (elements,city='Budapest')=>({manifest:{city,query:'[out:json];out geom;',endpoint:'https://overpass.example/api/interpreter',osmTimestamp:'2026-11-12T20:00:00Z'},
  sha256:'c'.repeat(64),path:`sources/${city}.json`,document:{elements}});
const collect = (snapshots,cities=['Budapest','Debrecen'])=>collectOsmCandidates(snapshots,cities,validateGeometry);

test('Budapest kerületek and other administrative fallbacks are distinct from neighbourhood candidates',()=>{
  assert.equal(classifyOsmBoundary({boundary:'administrative',admin_level:'9',place:'suburb'},'Budapest').boundaryKind,'district');
  assert.equal(classifyOsmBoundary({admin_level:'9',place:'suburb'},'Budapest').boundaryKind,'district');
  assert.equal(classifyOsmBoundary({boundary:'administrative',admin_level:'11'},'Debrecen').boundaryKind,'neighbourhood');
  assert.equal(classifyOsmBoundary({boundary:'administrative',admin_level:'10'},'Budapest').boundaryKind,'neighbourhood');
  assert.equal(classifyOsmBoundary({boundary:'administrative',admin_level:'8'},'Debrecen').boundaryKind,'district');
  assert.equal(classifyOsmBoundary({place:'quarter'},'Debrecen').boundaryKind,'neighbourhood');
  assert.equal(classifyOsmBoundary({name:'Park',landuse:'residential'},'Budapest'),null);
});

test('closed named ways preserve source vertices and open ways never gain a fabricated closing edge',()=>{
  assert.deepEqual(osmGeometry(way()),{type:'Polygon',coordinates:[square]});
  assert.throws(()=>osmGeometry(way(1,square.slice(0,-1))),/unclosed_way/);
  assert.throws(()=>osmGeometry({...way(),nodes:[1,2,3,4,5]}),/unclosed_way/);
  assert.throws(()=>osmGeometry({...way(),geometry:undefined}),/missing_member_geometry/);
  const namedPoint={type:'node',id:2,lon:19,lat:47,bounds:{minlon:18,minlat:46,maxlon:20,maxlat:48},tags:{name:'Pontos városrész',place:'suburb'}};
  const result=collect([snapshot([namedPoint])]);
  assert.equal(result.features.length,0);
  assert.equal(result.excluded[0].reason,'not_polygon');
  assert.equal(result.excluded[0].geometryType,'Point');
});

test('outer member ways stitch through exact shared endpoints with direction reversal and no source mutation',()=>{
  const input=relation([member(1,square.slice(0,2)),member(2,[square[2],square[1]]),member(3,square.slice(2))]);
  const original=JSON.stringify(input);
  const geometry=osmGeometry(input);
  assert.deepEqual(geometry,{type:'Polygon',coordinates:[square]});
  assert.equal(JSON.stringify(input),original);
  assert.equal(validateGeometry(geometry).valid,true);
  const result=collect([snapshot([input])]);
  assert.equal(result.features.length,1);
  assert.equal(result.features[0].properties.source.geometryProcessing.includes('no snapping'),true);
  assert.equal(result.features[0].properties.source.license,'ODbL-1.0');
  assert.equal(result.features[0].properties.usableForAddressAssignment,false);
});

test('gaps, ambiguous joins, missing geometry, repeated members and boundary subrelations are rejected',()=>{
  assert.throws(()=>osmGeometry(relation([member(1,square.slice(0,2)),member(2,square.slice(2))])),/unclosed_member_ring/);
  const a=[19,47],b=[19.1,47],c=[19.1,47.1],d=[19,47.1];
  assert.throws(()=>stitchRings([{points:[a,b]},{points:[b,c]},{points:[b,d]}]),/ambiguous_member_join/);
  assert.throws(()=>osmGeometry(relation([{type:'way',ref:1,role:'outer'}])),/missing_member_geometry/);
  assert.throws(()=>osmGeometry(relation([member(1,square),member(1,square)])),/duplicate_boundary_member/);
  assert.throws(()=>osmGeometry(relation([{type:'relation',ref:2,role:'outer'}])),/unsupported_boundary_subrelation/);
  assert.throws(()=>osmGeometry(relation([member(1,square,'unknown')])),/unsupported_member_role/);
  assert.throws(()=>osmGeometry(relation([member(1,square,'inner')])),/missing_outer_ring/);
  assert.deepEqual(osmGeometry(relation([member(1,square),{type:'node',ref:3,role:'label'}])),{type:'Polygon',coordinates:[square]});
});

test('inner rings belong to exactly one containing shell and disjoint outers become MultiPolygon',()=>{
  const other=square.map(([x,y])=>[x+1,y]);
  const hole=[[19.02,47.02],[19.04,47.02],[19.04,47.04],[19.02,47.04],[19.02,47.02]];
  const geometry=osmGeometry(relation([member(1,square),member(2,other),member(3,hole,'inner')]));
  assert.equal(geometry.type,'MultiPolygon');
  assert.deepEqual(geometry.coordinates,[[square,hole],[other]]);
  assert.equal(validateGeometry(geometry).valid,true);
  assert.throws(()=>osmGeometry(relation([member(1,other),member(3,hole,'inner')])),/unassigned_inner_ring/);
  assert.throws(()=>osmGeometry(relation([member(1,square),member(2,square),member(3,hole,'inner')])),/ambiguous_inner_ring/);
  assert.throws(()=>osmGeometry(relation([member(1,square),member(2,hole)])),/nested_outer_rings/);
  const invalidHole=hole.map(([x,y])=>[x-.1,y]);
  const result=collect([snapshot([relation([member(1,square),member(3,invalidHole,'inner')])])]);
  assert.equal(result.features.length,0);
});

test('node references resolve only from complete actual node geometry; malformed topology stays excluded',()=>{
  const nodes=square.slice(0,-1).map(([lon,lat],index)=>({type:'node',id:index+1,lon,lat}));
  const source={type:'way',id:7,nodes:[1,2,3,4,1],tags:{name:'Négyzet',place:'suburb'}};
  assert.deepEqual(osmGeometry(source,new Map(nodes.map(node=>[`node:${node.id}`,node]))),{type:'Polygon',coordinates:[square]});
  assert.throws(()=>osmGeometry(source,new Map(nodes.slice(1).map(node=>[`node:${node.id}`,node]))),/missing_member_geometry/);
  const crossing=way(9,[[19,47],[19.3,47.3],[19,47.3],[19.2,47],[19,47]]);
  assert.equal(collect([snapshot([crossing])]).excluded[0].reason,'self_intersection');
  assert.equal(collect([snapshot([way()],'Invented City')]).excluded[0].reason,'unknown_municipality');
});

test('conflicting city contexts never pick an arbitrary municipality; repeated identical snapshots deduplicate',()=>{
  const conflicting=collect([snapshot([way()],'Budapest'),snapshot([way()],'Debrecen')]);
  assert.equal(conflicting.features.length,0);
  assert.equal(conflicting.excluded.length,2);
  assert.ok(conflicting.excluded.every(item=>item.reason==='ambiguous_municipality_context'));
  const repeated=collect([snapshot([way()]),snapshot([way()])]);
  assert.equal(repeated.features.length,1);
  assert.equal(repeated.excluded[0].reason,'duplicate_osm_snapshot');
  const old=snapshot([way(1)]);old.manifest.osmTimestamp='2025-01-01T00:00:00Z';
  const current=snapshot([way(1,square.map(([x,y])=>[x+.01,y]))]);
  const latest=collect([old,current]);
  assert.deepEqual(latest.features[0].geometry.coordinates[0],square.map(([x,y])=>[x+.01,y]));
  assert.equal(latest.excluded[0].reason,'superseded_osm_snapshot');
  current.manifest.osmTimestamp=old.manifest.osmTimestamp;
  const sameTimestampConflict=collect([old,current]);
  assert.equal(sameTimestampConflict.features.length,0);
  assert.ok(sameTimestampConflict.excluded.every(item=>item.reason==='conflicting_osm_snapshots'));
  const duplicateMemberVersions=collect([snapshot([relation([{type:'way',ref:3,role:'outer'}]),
    {...way(3),tags:{}},{...way(3,square.map(([x,y])=>[x+.01,y])),tags:{}}])]);
  assert.equal(duplicateMemberVersions.features.length,0);
  assert.equal(duplicateMemberVersions.excluded[0].reason,'conflicting_osm_identity');
});

test('current OSM shadows only accent/case-equivalent WOF neighbourhood names within the same canonical city',()=>{
  const records=[{feature:{type:'Feature',properties:{'wof:id':10,'wof:name':'Budapest','wof:placetype':'locality'}}},
    {path:'wof.geojson',sha256:'a'.repeat(64),feature:{type:'Feature',properties:{'wof:id':20,'wof:name':'Angyalfold','wof:country':'HU','wof:placetype':'neighbourhood','wof:hierarchy':[{locality_id:10}]},geometry:{type:'Polygon',coordinates:[square]}}}];
  const wof=buildCatalog(records,['Budapest','Debrecen']);
  const osm=collect([snapshot([way(1,square,{name:'ANGYALFÖLD'})])]);
  const merged=mergeCatalogs(wof,osm);
  assert.deepEqual(merged.catalog.features.map(feature=>feature.id),['osm:way:1']);
  assert.equal(merged.coverage.excluded[0].reason,'shadowed_by_current_osm');
  assert.equal(merged.coverage.summary.candidateRecords,merged.catalog.features.length+merged.coverage.excluded.length);
  assert.equal(merged.coverage.summary.providers.openstreetmap.neighbourhoodPolygons,1);
  assert.equal(merged.coverage.targetCities[0].completeCoverage,false);
  const district=collect([snapshot([way(1,square,{name:'Angyalföld',boundary:'administrative',admin_level:'9'})])]);
  const districtMerged=mergeCatalogs(wof,district);
  assert.equal(districtMerged.catalog.features.length,2);
  assert.equal(districtMerged.coverage.targetCities[0].polygonCount,1);
  assert.equal(districtMerged.coverage.targetCities[0].districtCount,1);
  const elsewhere=collect([snapshot([way(1,square,{name:'Angyalföld'})],'Debrecen')]);
  assert.equal(mergeCatalogs(wof,elsewhere).catalog.features.length,2);
});

test('local Overpass snapshots require matching fingerprints and a complete response',async()=>{
  const root=await mkdtemp(join(tmpdir(),'otthonra-osm-'));
  try{
    assert.deepEqual(await loadOsmSources(root),[]);
    const dir=join(root,'data/neighborhoods/sources/openstreetmap');await mkdir(dir,{recursive:true});
    const raw=JSON.stringify({elements:[way()]});
    const manifest={city:'Budapest',sha256:createHash('sha256').update(raw).digest('hex'),query:'query',endpoint:'https://example.invalid'};
    await writeFile(join(dir,'budapest.json'),raw);await writeFile(join(dir,'budapest.source.json'),JSON.stringify(manifest));
    const [loaded]=await loadOsmSources(root);
    assert.equal(loaded.manifest.city,'Budapest');assert.equal(loaded.sha256,manifest.sha256);
    await writeFile(join(dir,'budapest.source.json'),JSON.stringify({...manifest,municipalityRelationId:123}));
    await assert.rejects(loadOsmSources(root),/municipality context mismatch/);
    await writeFile(join(dir,'budapest.source.json'),JSON.stringify(manifest));
    const capitalRaw=JSON.stringify({elements:[{type:'relation',id:123,tags:{name:'Budapest',admin_level:'6'}},way()]});
    const capitalManifest={...manifest,municipalityRelationId:123,municipalityAdminLevel:'6',sha256:createHash('sha256').update(capitalRaw).digest('hex')};
    await writeFile(join(dir,'budapest.json'),capitalRaw);await writeFile(join(dir,'budapest.source.json'),JSON.stringify(capitalManifest));
    assert.equal((await loadOsmSources(root)).length,1,'Budapest uses explicit admin6 municipality context');
    await writeFile(join(dir,'budapest.json'),raw);await writeFile(join(dir,'budapest.source.json'),JSON.stringify(manifest));
    await writeFile(join(dir,'other.json'),raw);
    await writeFile(join(dir,'other.source.json'),JSON.stringify({...manifest,file:'budapest.json'}));
    await assert.rejects(loadOsmSources(root),/Duplicate OSM source manifest/);
    await rm(join(dir,'other.json'));await rm(join(dir,'other.source.json'));
    await writeFile(join(dir,'budapest.json'),raw+'\n');
    await assert.rejects(loadOsmSources(root),/SHA256 mismatch/);
    const partial=JSON.stringify({elements:[],remark:'runtime error: Query timed out'});
    await writeFile(join(dir,'budapest.json'),partial);
    await writeFile(join(dir,'budapest.source.json'),JSON.stringify({...manifest,sha256:createHash('sha256').update(partial).digest('hex')}));
    await assert.rejects(loadOsmSources(root),/incomplete\/error/);
  }finally{await rm(root,{recursive:true,force:true});}
});
