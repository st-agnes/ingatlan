import assert from 'node:assert/strict';
import test from 'node:test';
import {inferredCandidates,summarizeInferred} from '../scripts/neighborhoods/export-secondary.mjs';

test('an inferred source remains a separate, explicitly unverified geometry without coordinate changes',()=>{
  const original={type:'Feature',id:'uncertain',properties:{name:'Jelölt',municipality:'Budapest',
    sourceIsOfficial:true,usableForAddressAssignment:true},
    geometry:{type:'Polygon',coordinates:[[[19,47],[19.01,47],[19.01,47.01],[19,47]]]}};
  const before=JSON.stringify(original);
  const result=inferredCandidates([{entry:{id:'reviewed-research',sha256:'a'.repeat(64),
    method:'source_map_estimate',evidenceUrls:['https://example.test/map'],license:'source_map_reuse_unverified',
    propertyOverrides:{boundaryKind:'inferred_area',candidateBoundaryKind:'planning_unit'}},
    path:'data/neighborhoods/research.geojson',document:{features:[original]}}],['Budapest']);
  assert.equal(result.features.length,1);assert.deepEqual(result.features[0].geometry,original.geometry);
  assert.equal(JSON.stringify(original),before);
  assert.equal(result.features[0].properties.estimated,true);
  assert.equal(result.features[0].properties.boundaryKind,'inferred_area');
  assert.equal(result.features[0].properties.candidateBoundaryKind,'planning_unit');
  assert.equal(result.features[0].properties.sourceIsOfficial,false);
  assert.equal(result.features[0].properties.usableForAddressAssignment,false);
  assert.equal(result.features[0].properties.canonicalNameIsNeighborhood,false);
  assert.equal(result.features[0].properties.source.license,'source_map_reuse_unverified');
});

test('unknown towns and open source rings stay quarantined even in the inferred layer',()=>{
  const source={type:'Feature',id:'x',properties:{name:'Jelölt',municipality:'Budapest'},
    geometry:{type:'Polygon',coordinates:[[[19,47],[19.01,47],[19.01,47.01]]]}};
  const snapshots=[{entry:{id:'test'},document:{features:[source]}}];
  assert.equal(inferredCandidates(snapshots,['Budapest']).features.length,0);
  assert.equal(inferredCandidates(snapshots,[]).rejected[0].reason,'unknown_municipality');
});

test('estimated city statistics count features rather than components and retain source-level distinctions',()=>{
  const feature=(name,kind,geometryType)=>({properties:{name,municipality:'Pécs',candidateBoundaryKind:kind},
    geometry:{type:geometryType}});
  const report=summarizeInferred({features:[feature('Régi név','neighbourhood','MultiPolygon'),
    feature('Régi név','neighbourhood','Polygon'),feature('Gyűjtőegység','planning_unit','MultiPolygon')]});
  assert.equal(report.primaryCoverageCredit,false);
  assert.equal(report.geometryCount,3);
  assert.equal(report.municipalityCount,1);
  assert.equal(report.cities[0].distinctSourceNameCount,2);
  assert.equal(report.cities[0].neighbourhoodCandidateCount,2);
  assert.equal(report.cities[0].planningCandidateCount,1);
});
