import assert from 'node:assert/strict';
import test from 'node:test';
import {createHash} from 'node:crypto';
import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {collectManualCandidates, loadManualSources} from '../scripts/neighborhoods/manual-sources.mjs';
import {validateGeometry} from '../scripts/neighborhoods/build.mjs';

const ring = [[16.6,47.2],[16.61,47.2],[16.61,47.21],[16.6,47.21],[16.6,47.2]];
const feature = changes => ({type:'Feature', id:'belvaros', properties:{name:'Belváros',municipality:'Szombathely',
  method:'cited_street_circuit',evidenceUrls:['https://kbr.szombathely.hu/kbrfile/46469.pdf'],
  usableForAddressAssignment:true,...changes},geometry:{type:'Polygon',coordinates:[ring]}});
const snapshot = features => ({entry:{id:'source-circuit',sha256:'a'.repeat(64)},path:'data/neighborhoods/sources/manual.geojson',
  document:{type:'FeatureCollection',features}});

test('manual import preserves actual source geometry and evidence while retaining review flags',()=>{
  const original=feature(), before=JSON.stringify(original);
  const result=collectManualCandidates([snapshot([original])],['Szombathely'],validateGeometry);
  assert.equal(result.features.length,1);
  assert.deepEqual(result.features[0].geometry,original.geometry);
  assert.equal(JSON.stringify(original),before);
  assert.equal(result.features[0].properties.usableForAddressAssignment,false);
  assert.equal(result.features[0].properties.source.provider,'manual-derived');
  assert.equal(result.features[0].properties.source.method,'cited_street_circuit');
  assert.deepEqual(result.features[0].properties.source.evidenceUrls,original.properties.evidenceUrls);
});

test('open rings, missing evidence, unknown municipalities and inferred areas cannot become admitted manual polygons',()=>{
  const open=feature();open.geometry={type:'Polygon',coordinates:[ring.slice(0,-1)]};
  const originals=[open,feature({evidenceUrls:[]}),feature({municipality:'Nem létező város'}),feature({estimated:true})];
  originals.forEach((f,i)=>{f.id='sample-'+i;});
  const result=collectManualCandidates([snapshot(originals)],['Szombathely'],validateGeometry);
  assert.equal(result.features.length,0);
  assert.deepEqual(result.excluded.map(r=>r.reason),['manual_open_ring','manual_missing_construction_evidence',
    'manual_unknown_municipality','inferred_geometry_belongs_in_separate_layer']);
});

test('a planning cluster remains a planning cluster and never counts as a fine neighborhood',()=>{
  const source=snapshot([feature({boundaryKind:'neighbourhood',canonicalNameIsNeighborhood:true})]);
  source.entry.propertyOverrides={boundaryKind:'planning_unit',canonicalNameIsNeighborhood:false};
  const result=collectManualCandidates([source],['Szombathely'],validateGeometry);
  assert.equal(result.features.length,1);
  assert.equal(result.features[0].properties.boundaryKind,'planning_unit');
  assert.equal(result.features[0].properties.canonicalNameIsNeighborhood,false);
});

test('manual registry binds exact GeoJSON bytes and rejects changed sources and path traversal',async()=>{
  const root=await mkdtemp(join(tmpdir(),'manual-boundaries-'));
  const directory=join(root,'data/neighborhoods');await mkdir(directory,{recursive:true});
  const text=JSON.stringify({type:'FeatureCollection',features:[feature()]});
  const entry={id:'circuit',path:'data/neighborhoods/manual.geojson',sha256:createHash('sha256').update(text).digest('hex')};
  const registry=join(directory,'manual-source-registry.json');
  try{
    await writeFile(join(directory,'manual.geojson'),text);
    await writeFile(registry,JSON.stringify({schemaVersion:1,datasets:[entry]}));
    assert.equal((await loadManualSources(root)).length,1);
    await writeFile(join(directory,'manual.geojson'),text+'\n');
    await assert.rejects(()=>loadManualSources(root),/fingerprint mismatch/);
    await writeFile(registry,JSON.stringify({schemaVersion:1,datasets:[{...entry,path:'../outside.geojson'}]}));
    await assert.rejects(()=>loadManualSources(root),/leaves the public data directory/);
  }finally{await rm(root,{recursive:true,force:true});}
});
