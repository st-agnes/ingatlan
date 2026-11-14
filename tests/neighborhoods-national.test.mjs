import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {cp, mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {applyNameAudit, buildCatalog, mergeCatalogs, validateGeometry} from '../scripts/neighborhoods/build.mjs';
import {collectNationalCandidates, loadNationalSource} from '../scripts/neighborhoods/national.mjs';

const root=fileURLToPath(new URL('..',import.meta.url));
const digest=value=>createHash('sha256').update(value).digest('hex');
const square={type:'Polygon',coordinates:[[[19,47],[19.1,47],[19.1,47.1],[19,47.1],[19,47]]]};
const canonical=['Budapest','Debrecen'];
const wofRecord=(id,name)=>({path:`wof-${id}.geojson`,sha256:'a'.repeat(64),
  feature:{type:'Feature',properties:{'wof:id':id,'wof:name':name,'wof:country':'HU','wof:placetype':'neighbourhood',
    'wof:hierarchy':[{locality_id:1}]},geometry:square}});
const wof=records=>buildCatalog([{feature:{properties:{'wof:id':1,'wof:name':'Budapest','wof:placetype':'locality'}}},...records],canonical);
const osm=features=>({features,excluded:[],sourceRecords:features.length,candidateRecords:features.length,
  neighbourhoodRecords:features.length,districtRecords:0,sourceSnapshots:1,
  queryResults:[{city:'Debrecen',status:'failed',error:'http_429'}]});
const candidate=(id,name,municipality='Budapest')=>({type:'Feature',id,geometry:square,properties:{id,name,municipality,
  boundaryKind:'neighbourhood',source:{provider:'openstreetmap',sha256:'b'.repeat(64)}}});

const edges=rings=>rings.flatMap(ring=>ring.slice(1).map((point,index)=>
  [ring[index],point].map(position=>position.map(value=>value.toFixed(8)).join(',')).sort().join('|'))).sort();
async function shapefileEdges(directory){
  const shp=await readFile(join(root,'data/neighborhoods/sources',directory,'admin10.shp'));
  const originalEdges=new Map();
  for(let offset=100;offset<shp.length;){
    const record=shp.readInt32BE(offset),length=shp.readInt32BE(offset+4)*2;
    offset+=8;
    assert.equal(shp.readInt32LE(offset),5,'the original geometry must be a Polygon shapefile record');
    const partCount=shp.readInt32LE(offset+36),pointCount=shp.readInt32LE(offset+40);
    const parts=Array.from({length:partCount},(_,index)=>shp.readInt32LE(offset+44+index*4));
    parts.push(pointCount);
    const points=Array.from({length:pointCount},(_,index)=>{
      const pointOffset=offset+44+partCount*4+index*16;
      return [shp.readDoubleLE(pointOffset)/6378137*180/Math.PI,
        (2*Math.atan(Math.exp(shp.readDoubleLE(pointOffset+8)/6378137))-Math.PI/2)*180/Math.PI];
    });
    originalEdges.set(record,edges(parts.slice(0,-1).map((start,index)=>points.slice(start,parts[index+1]))));
    offset+=length;
  }
  return originalEdges;
}

test('all 203 historical Budapest polygons retain every converted source vertex and original source fingerprints',async()=>{
  const snapshot=await loadNationalSource(root);
  assert.equal(snapshot.document.features.length,203);
  assert.equal(snapshot.sourceFiles.length,5);
  const converted=collectNationalCandidates(snapshot,canonical,validateGeometry);
  assert.equal(converted.features.length,203);
  assert.deepEqual(converted.excluded,[]);
  const originalEdges=await shapefileEdges('national-osm');
  assert.equal(originalEdges.size,203);
  let vertices=0;
  for(const feature of converted.features){
    const original=snapshot.document.features.find(item=>item.id===feature.id);
    assert.deepEqual(feature.geometry,original.geometry);
    assert.equal(feature.properties.source.geometrySha256,digest(JSON.stringify(original.geometry)));
    assert.equal(feature.properties.source.sourceRecord,original.properties.sourceRecord);
    assert.equal(feature.properties.source.historical,true);
    assert.equal(feature.properties.source.osmTimestamp,null);
    assert.equal(feature.properties.source.snapshotDate,'2022-11-23');
    assert.equal(feature.properties.source.inputCrs,'EPSG:3857');
    assert.equal(feature.properties.source.outputCrs,'EPSG:4326');
    assert.equal(feature.properties.source.license,'ODbL-1.0');
    assert.equal(feature.properties.usableForAddressAssignment,false);
    assert.equal(feature.properties.nameVerificationStatus,'not-individually-rechecked');
    assert.equal(feature.properties.geometryVerificationStatus,'historical-not-rechecked');
    const rings=feature.geometry.type==='Polygon'?feature.geometry.coordinates:feature.geometry.coordinates.flat();
    assert.deepEqual(edges(rings),originalEdges.get(original.properties.sourceRecord),
      `${feature.id}: every edge must come from actual shapefile vertices after the declared projection change`);
    vertices+=rings.reduce((sum,ring)=>sum+ring.length,0);
  }
  assert.equal(vertices,27342);
});

test('the 2025 archived polygons supersede equivalent 2022 names while older-only actual geometry is retained',async()=>{
  const previous=await loadNationalSource(root),current=await loadNationalSource(root,'national-osm-2025');
  assert.ok(current,'the pinned 2025 source must be present');
  assert.equal(current.document.features.length,202);
  const originalEdges=await shapefileEdges('national-osm-2025');
  assert.equal(originalEdges.size,202);
  const combined=collectNationalCandidates([previous,current],canonical,validateGeometry);
  assert.equal(combined.sourceSnapshots,2);
  assert.equal(combined.candidateRecords,405);
  let currentVertices=0;
  for(const feature of combined.features.filter(item=>item.properties.source.snapshotDate==='2025-08-28')){
    const rings=feature.geometry.type==='Polygon'?feature.geometry.coordinates:feature.geometry.coordinates.flat();
    currentVertices+=rings.reduce((sum,ring)=>sum+ring.length,0);
    assert.deepEqual(edges(rings),originalEdges.get(feature.properties.source.sourceRecord));
    assert.equal(feature.properties.source.url,current.manifest.upstreamArchiveUrl);
    assert.equal(feature.properties.source.sourceArchive.gitBlobSha1,current.manifest.archive.gitBlobSha1);
  }
  assert.equal(currentVertices,31618);
  const result=mergeCatalogs(wof([]),osm([]),combined);
  assert.equal(result.catalog.features.length,203);
  const preserved=result.catalog.features.filter(feature=>feature.properties.source.snapshotDate==='2022-11-23');
  assert.deepEqual(preserved.map(feature=>feature.properties.name),['Millenniumtelep']);
  assert.equal(result.coverage.summary.reasons.shadowed_by_newer_national_osm,202);
  assert.equal(result.coverage.summary.providers.openstreetmap.historicalSourceSnapshots,2);
  const magdolna=result.catalog.features.filter(feature=>feature.properties.name.replaceAll(' ','')==='Magdolnanegyed');
  assert.equal(magdolna.length,1);
  assert.equal(magdolna[0].properties.source.snapshotDate,'2025-08-28');
  const fresh=candidate('osm:way:999','Millenniumtelep');
  const withFresh=mergeCatalogs(wof([]),osm([fresh]),combined);
  assert.equal(withFresh.catalog.features.find(feature=>feature.properties.name==='Millenniumtelep').id,'osm:way:999');
  assert.equal(withFresh.coverage.summary.candidateRecords,withFresh.catalog.features.length+withFresh.coverage.excluded.length);
});

test('unknown municipalities, points and broken rings cannot become national polygons',async()=>{
  const snapshot=await loadNationalSource(root);
  const feature=snapshot.document.features[0];
  const altered={...snapshot,document:{features:[{...feature,properties:{...feature.properties,city:'Invented city'}}]}};
  assert.equal(collectNationalCandidates(altered,canonical,validateGeometry).excluded[0].reason,'unknown_municipality');
  altered.document.features=[{...feature,geometry:{type:'Point',coordinates:[19,47]},bbox:[18,46,20,48]}];
  assert.equal(collectNationalCandidates(altered,canonical,validateGeometry).excluded[0].reason,'not_polygon');
  altered.document.features=[{...feature,geometry:{type:'Polygon',coordinates:[square.coordinates[0].slice(0,-1)]}}];
  assert.equal(collectNationalCandidates(altered,canonical,validateGeometry).excluded[0].reason,'open_ring');
});

test('hash corruption in any original component or converted GeoJSON fails before import',async()=>{
  const temporary=await mkdtemp(join(tmpdir(),'national-boundaries-'));
  const sourceDirectory=join(root,'data/neighborhoods/sources/national-osm');
  const directory=join(temporary,'data/neighborhoods/sources/national-osm');
  try{
    await cp(sourceDirectory,directory,{recursive:true});
    for(const file of ['admin10.cpg','admin10.dbf','admin10.prj','admin10.shp','admin10.shx','admin10.geojson']){
      const path=join(directory,file),bytes=await readFile(path);
      await writeFile(path,Buffer.concat([bytes,Buffer.from(' ')]));
      await assert.rejects(loadNationalSource(temporary),file.endsWith('geojson')?/GeoJSON hash mismatch/:/source hash mismatch/);
      await writeFile(path,bytes);
    }
    const path=join(directory,'manifest.json'),manifest=JSON.parse(await readFile(path,'utf8'));
    manifest.sourceFiles[0].gitBlobSha1='0'.repeat(40);
    await writeFile(path,JSON.stringify(manifest));
    await assert.rejects(loadNationalSource(temporary),/source hash mismatch/);
  }finally{await rm(temporary,{recursive:true,force:true});}
});

test('source priority deduplicates accent/case/punctuation variants and preserves failed query status',()=>{
  const baseline=wof([wofRecord(10,'Új-Pest'),wofRecord(11,'Zugliget'),wofRecord(12,'Egyedi')]);
  const national={features:[candidate('national:1','uj pest'),candidate('national:2','ZUGLIGET')],excluded:[],
    sourceRecords:2,candidateRecords:2,neighbourhoodRecords:2};
  national.features.forEach(feature=>feature.properties.source.collection='national-osm-admin10');
  const result=mergeCatalogs(baseline,osm([candidate('osm:way:20','Új.Pest')]),national);
  assert.deepEqual(new Set(result.catalog.features.map(feature=>feature.id)),new Set(['osm:way:20','national:2','wof:12']));
  assert.equal(result.coverage.summary.reasons.shadowed_by_current_osm,2);
  assert.equal(result.coverage.summary.reasons.shadowed_by_national_osm,1);
  assert.equal(result.coverage.summary.candidateRecords,result.catalog.features.length+result.coverage.excluded.length);
  assert.equal(result.coverage.summary.providers.openstreetmap.historicalCandidateRecords,2);
  assert.equal(result.coverage.targetCities.find(item=>item.municipality==='Debrecen').osmQuery.status,'failed');
});

test('name evidence deduplicates historical aliases but never silently moves wrong-city or ambiguous geometry',()=>{
  const baseline=wof([wofRecord(10,'Auwinkel'),wofRecord(11,'Zugliget'),wofRecord(12,'Buda'),wofRecord(13,'Wrong city')]);
  const audit={records:[
    {id:'wof:10',sourceName:'Auwinkel',originalMunicipality:'Budapest',actualMunicipality:'Budapest',
      proposedHungarianName:'Zugliget',canonicalNameSupported:true,canonicalNameIsNeighborhood:true,
      sourceLabelIsCurrentName:false,validationStatus:'historical_alias'},
    {id:'wof:11',sourceName:'Zugliget',originalMunicipality:'Budapest',actualMunicipality:'Budapest',
      proposedHungarianName:'Zugliget',canonicalNameSupported:true,canonicalNameIsNeighborhood:true,sourceLabelIsCurrentName:true},
    {id:'wof:12',sourceName:'Buda',originalMunicipality:'Budapest',canonicalNameSupported:false,validationStatus:'macro_area'},
    {id:'wof:13',sourceName:'Wrong city',originalMunicipality:'Budapest',actualMunicipality:'Debrecen',
      canonicalNameSupported:true,municipalityCorrectionNeeded:true}
  ]};
  const result=mergeCatalogs(baseline,osm([]),null,audit);
  assert.deepEqual(result.catalog.features.map(feature=>feature.id),['wof:11']);
  assert.equal(result.coverage.summary.reasons.duplicate_canonical_neighbourhood_name,1);
  assert.equal(result.coverage.summary.reasons.audited_macro_area,1);
  assert.equal(result.coverage.summary.reasons.audited_municipality_mismatch,1);
  const alias=result.coverage.excluded.find(item=>item.id==='wof:10');
  assert.equal(alias.nameAudit.sourceName,'Auwinkel');
  assert.equal(alias.shadowedBy,'wof:11');
  assert.deepEqual(result.catalog.features[0].geometry,square);
  const corrupted=structuredClone(audit);corrupted.records[0].sourceSha256='0'.repeat(64);
  assert.throws(()=>applyNameAudit(baseline.catalog.features,corrupted),/source identity mismatch/);
  const unresolved=structuredClone(audit);unresolved.records[1].geometryAssociationNeedsReview=true;
  assert.ok(applyNameAudit(baseline.catalog.features,unresolved).excluded.some(item=>item.reason==='audited_geometry_association_unresolved'));
});
