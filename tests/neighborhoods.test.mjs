import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {buildCatalog, buildFiles, loadSources, mergeCatalogs, TARGET_CITIES, validateGeometry} from '../scripts/neighborhoods/build.mjs';
import {loadOsmSources} from '../scripts/neighborhoods/osm.mjs';
import {loadNationalSource} from '../scripts/neighborhoods/national.mjs';
import {loadCountrySource} from '../scripts/neighborhoods/country.mjs';
import {loadManualSources} from '../scripts/neighborhoods/manual-sources.mjs';

const square = [[19,47],[19.1,47],[19.1,47.1],[19,47.1],[19,47]];
const polygon = coordinates => ({type:'Polygon',coordinates:[coordinates]});
const source = (id, properties = {}, geometry = polygon(square)) => ({
  feature:{type:'Feature',id,properties:{'wof:id':id,'wof:name':`Teszt ${id}`,'wof:country':'HU',
    'wof:placetype':'neighbourhood','wof:hierarchy':[{'locality_id':10}],
    'src:geom':'quattroshapes',...properties},geometry},
  path:`sources/${id}.geojson`,sha256:'a'.repeat(64),gitBlobSha:'b'.repeat(40),
  sourceUrl:`https://example.invalid/source/${id}.geojson`
});
const parent = (id = 10, name = 'Budapest') => source(id, {'wof:placetype':'locality','wof:name':name}, {type:'Point',coordinates:[19,47]});

function undirectedEdges(rings) {
  const edges = new Map();
  for (const ring of rings) for (let i = 1; i < ring.length; i++) {
    const points = [JSON.stringify(ring[i-1]),JSON.stringify(ring[i])].sort();
    const key = points.join('|');edges.set(key,(edges.get(key)??0)+1);
  }
  return [...edges].sort(([a],[b])=>a<b?-1:a>b?1:0);
}

function sourceOsmEdges(snapshot,id) {
  const [,type,idText] = id.split(':');
  const element = snapshot.document.elements.find(item=>item.type===type&&item.id===Number(idText));
  assert.ok(element,`source object ${id} is missing`);
  const geometry = item => {
    const full = item.geometry ? item : snapshot.document.elements.find(value=>value.type==='way'&&value.id===item.ref);
    assert.ok(full?.geometry,`source member geometry ${item.ref??item.id} is missing`);
    return full.geometry.map(({lon,lat})=>[lon,lat]);
  };
  return undirectedEdges(type==='way'?[geometry(element)]:element.members
    .filter(member=>member.type==='way'&&['outer','inner',''].includes(member.role??''))
    .map(geometry));
}

test('polygon validator rejects open, degenerate, malformed, nonfinite and crossing geometries', () => {
  assert.equal(validateGeometry(polygon(square)).valid,true);
  assert.equal(validateGeometry(polygon(square.slice(0,-1))).reason,'open_ring');
  assert.equal(validateGeometry(polygon([[19,47],[19.1,47],[19.2,47],[19,47]])).reason,'degenerate_ring');
  assert.equal(validateGeometry(polygon([[19,47],[19.1,Infinity],[19.1,47.1],[19,47]])).reason,'invalid_coordinate');
  assert.equal(validateGeometry(polygon([[190,47],[19.1,47],[19.1,47.1],[190,47]])).reason,'invalid_coordinate');
  assert.equal(validateGeometry(polygon([[19,47],[19.1,47,0],[19.1,47.1],[19,47]])).reason,'invalid_coordinate');
  assert.equal(validateGeometry({type:'MultiPolygon',coordinates:[]}).reason,'empty_geometry');
  assert.equal(validateGeometry({type:'Polygon',coordinates:square}).valid,false);
  assert.equal(validateGeometry(polygon([[19,47],[19.3,47.3],[19,47.3],[19.2,47],[19,47]])).reason,'self_intersection');
  assert.equal(validateGeometry(polygon(square),[0,0,1,1]).reason,'bbox_mismatch');
});

test('holes and duplicate vertices are checked without repairing or changing the source geometry', () => {
  const hole = [[19.02,47.02],[19.04,47.02],[19.04,47.04],[19.02,47.04],[19.02,47.02]];
  const withHole = {type:'Polygon',coordinates:[square,hole]};
  const before = JSON.stringify(withHole);
  assert.equal(validateGeometry(withHole).valid,true);
  assert.equal(JSON.stringify(withHole),before);
  const outsideHole = hole.map(([x,y])=>[x+1,y]);
  assert.equal(validateGeometry({type:'Polygon',coordinates:[square,outsideHole]}).reason,'hole_outside_shell');
  const touchingHole = hole.map(([x,y])=>[x-0.02,y]);
  assert.equal(validateGeometry({type:'Polygon',coordinates:[square,touchingHole]}).reason,'hole_outside_shell');
  assert.equal(validateGeometry({type:'Polygon',coordinates:[square,hole,hole]}).reason,'overlapping_holes');
  const duplicated = polygon([square[0],square[0],...square.slice(1)]);
  const duplicateBefore = JSON.stringify(duplicated);
  assert.equal(validateGeometry(duplicated).valid,true);
  assert.equal(JSON.stringify(duplicated),duplicateBefore);
  assert.equal(validateGeometry({type:'MultiPolygon',coordinates:[[square],[square.map(([x,y])=>[x+1,y])]]}).valid,true);
});

test('names and bounding boxes never become polygons; unknown city associations stay excluded', () => {
  const point = source(101,{}, {type:'Point',coordinates:[19,47]});
  point.feature.bbox=[18,46,20,48];
  const unknown = source(102,{'wof:hierarchy':[{'locality_id':999}],'wof:parent_id':999});
  const unknownCanonical = source(103,{'wof:hierarchy':[{'locality_id':11}]});
  const ambiguous = source(104,{'wof:hierarchy':[{'locality_id':10},{'locality_id':12}]});
  const {catalog,coverage} = buildCatalog([parent(),parent(11,'Unknown City'),parent(12,'Debrecen'),point,unknown,unknownCanonical,ambiguous],['Budapest','Debrecen']);
  assert.equal(catalog.features.length,0);
  assert.deepEqual(coverage.excluded.map(item=>item.reason),['not_polygon','unknown_municipality','unknown_municipality','ambiguous_municipality']);
  assert.equal(coverage.targetCities.find(item=>item.municipality==='Budapest').status,'points_only');
  assert.equal(coverage.targetCities.find(item=>item.municipality==='Szeged').status,'no_polygon_found');
});

test('retired and superseded records cannot enter the draft catalog; duplicate IDs fail explicitly', () => {
  const records = [parent(),source(101,{'mz:is_current':0}),source(102,{'edtf:cessation':'2015-01-01'}),
    source(103,{'edtf:deprecated':'2023-uu-uu'}),source(104,{'wof:superseded_by':[105]}),source(105)];
  const {catalog,coverage}=buildCatalog(records,['Budapest']);
  assert.deepEqual(catalog.features.map(feature=>feature.id),['wof:105']);
  assert.equal(coverage.summary.reasons.retired_record,4);
  assert.throws(()=>buildCatalog([parent(),source(101),source(101)],['Budapest']),/Duplicate/);
});

test('a valid geometry retains its coordinates and source hashes but never implies reviewed city coverage', () => {
  const original=source(101,{'wof:name':'Magyar nev','name:hun_x_preferred':['Magyar név'],'mz:is_official':1,'mz:is_hard_boundary':1});
  const before=JSON.stringify(original);
  const {catalog,coverage}=buildCatalog([original,parent()],['Budapest']);
  const feature=catalog.features[0];
  assert.equal(feature.properties.name,'Magyar név');
  assert.equal(feature.properties.sourceName,'Magyar nev');
  assert.equal(feature.properties.nameReviewNeeded,false);
  assert.equal(feature.properties.municipality,'Budapest');
  assert.equal(feature.properties.municipalityId,'city:Budapest');
  assert.deepEqual(feature.geometry,original.feature.geometry);
  assert.equal(JSON.stringify(original),before);
  assert.equal(feature.properties.source.geometrySha256,createHash('sha256').update(JSON.stringify(original.feature.geometry)).digest('hex'));
  assert.equal(feature.properties.source.gitBlobSha,original.gitBlobSha);
  assert.equal(feature.properties.source.geometrySource,'quattroshapes');
  assert.equal(feature.properties.sourceIsOfficial,true);
  assert.equal(feature.properties.reviewStatus,'unreviewed');
  assert.equal(feature.properties.usableForAddressAssignment,false);
  assert.equal(catalog.usableForAddressAssignment,false);
  assert.equal(coverage.targetCities.length,26);
  assert.equal(new Set(TARGET_CITIES).size,26);
  assert.equal(coverage.targetCities.find(item=>item.municipality==='Budapest').completeness,'not_assessed');
  assert.equal(coverage.targetCities.find(item=>item.municipality==='Budapest').status,'unreviewed_polygons');
  const differentTranslation=buildCatalog([parent(),source(102,{'wof:name':'Albertfalva','name:hun_x_preferred':['Újbuda']})],['Budapest']).catalog.features[0];
  assert.equal(differentTranslation.properties.name,'Albertfalva');
  assert.equal(differentTranslation.properties.preferredHungarianName,'Újbuda');
  assert.equal(differentTranslation.properties.nameReviewNeeded,true);
});

test('different canonical municipalities never merge when only their accents differ',()=>{
  const records=[parent(10,'Komló'),parent(11,'Kömlő'),
    source(101,{'wof:name':'Belváros','wof:hierarchy':[{'locality_id':10}]}),
    source(102,{'wof:name':'Belváros','wof:hierarchy':[{'locality_id':11}]})];
  const wof=buildCatalog(records,['Komló','Kömlő']);
  const empty={features:[],excluded:[],sourceRecords:0,candidateRecords:0,neighbourhoodRecords:0,
    districtRecords:0,sourceSnapshots:0,queryResults:[]};
  const result=mergeCatalogs(wof,empty);
  assert.deepEqual(result.catalog.features.map(f=>f.properties.municipality).sort(),['Komló','Kömlő'].sort());
});

test('checked-in draft is reproducible from pinned original records and canonical municipality names', async () => {
  const records=await loadSources();
  const {catalog,coverage}=await buildFiles({check:true});
  const canonical=new Set(JSON.parse(await readFile(new URL('../dist/data/settlements.json',import.meta.url),'utf8')).settlements);
  assert.ok(records.length>0,'missing actual source files');
  assert.ok(catalog.features.length>0,'missing actual polygons');
  assert.equal(coverage.summary.candidateRecords,catalog.features.length+coverage.excluded.length);
  assert.equal(new Set(catalog.features.map(feature=>feature.id)).size,catalog.features.length);
  const osmSources = new Map((await loadOsmSources(new URL('..',import.meta.url).pathname)).map(snapshot=>[snapshot.path,snapshot]));
  const nationalSources = await Promise.all(['national-osm','national-osm-2025'].map(directory=>
    loadNationalSource(new URL('..',import.meta.url).pathname,directory)));
  const countrySource=await loadCountrySource(new URL('..',import.meta.url).pathname);
  const manualSources=new Map((await loadManualSources(new URL('..',import.meta.url).pathname)).map(snapshot=>[snapshot.path,snapshot]));
  for(const feature of catalog.features){
    assert.ok(canonical.has(feature.properties.municipality));
    assert.ok(validateGeometry(feature.geometry,feature.bbox).valid);
    assert.equal(feature.properties.reviewStatus,'unreviewed');
    assert.equal(feature.properties.usableForAddressAssignment,false);
    assert.match(feature.properties.source.sha256,/^[a-f0-9]{64}$/);
    if(feature.properties.source.provider==='whosonfirst'){
      assert.match(feature.properties.source.gitBlobSha,/^[a-f0-9]{40}$/);
      const original=records.find(record=>`wof:${record.feature.properties?.['wof:id']}`===feature.id);
      assert.ok(original);
      assert.deepEqual(feature.geometry,original.feature.geometry);
    }else if(feature.properties.source.collection==='national-osm-admin10'){
      const nationalSource=nationalSources.find(snapshot=>snapshot?.path===feature.properties.source.path);
      assert.ok(nationalSource,'missing pinned national source cohort');
      const original=nationalSource.document.features.find(item=>item.id===feature.id);
      assert.ok(original,'missing exact national source record');
      assert.deepEqual(feature.geometry,original.geometry,'national geometry must equal the pinned converted original');
      assert.equal(feature.properties.source.sha256,nationalSource.sha256);
      assert.equal(feature.properties.source.historical,true);
      assert.equal(feature.properties.source.osmTimestamp,null);
      assert.equal(feature.properties.source.license,'ODbL-1.0');
    }else if(feature.properties.source.provider==='manual-derived'){
      const snapshot=manualSources.get(feature.properties.source.path);
      assert.ok(snapshot,'missing pinned manual source');
      const original=snapshot.document.features[feature.properties.source.featureIndex];
      assert.ok(original,'missing exact manual source feature');
      assert.deepEqual(feature.geometry,original.geometry,'manual import must preserve the reviewed construction');
      assert.equal(feature.properties.source.sha256,snapshot.entry.sha256);
    }else if(feature.properties.source.collection==='country-osm'){
      assert.ok(countrySource,'missing pinned country source');
      const original=countrySource.document.features.find(item=>item.id===feature.id);
      assert.ok(original,'missing exact country source feature');
      assert.deepEqual(feature.geometry,original.geometry,'country source vertices must be preserved');
      assert.equal(feature.properties.source.sha256,countrySource.sha256);
      assert.equal(feature.properties.source.pbfSha256,countrySource.manifest.input.sha256);
    }else{
      assert.equal(feature.properties.source.provider,'openstreetmap');
      const original=osmSources.get(feature.properties.source.path);
      assert.ok(original);
      assert.equal(feature.properties.source.sha256,original.sha256);
      assert.equal(feature.properties.source.license,'ODbL-1.0');
      assert.equal(feature.properties.source.geometrySha256,createHash('sha256').update(JSON.stringify(feature.geometry)).digest('hex'));
      const outputRings=feature.geometry.type==='Polygon'?feature.geometry.coordinates:feature.geometry.coordinates.flat();
      assert.deepEqual(undirectedEdges(outputRings),sourceOsmEdges(original,feature.id),`${feature.id}: every original boundary edge is retained and no new edge is invented`);
    }
  }
});
