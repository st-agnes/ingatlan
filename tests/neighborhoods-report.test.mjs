import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp,mkdir,readFile,rm,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createReport,csvReport,markdownReport,normalizeName,writeReports} from '../scripts/neighborhoods/report.mjs';
import {createNeighborhoodExport,writeExport} from '../scripts/neighborhoods/export.mjs';

const geometry={type:'Polygon',coordinates:[[[20,47],[20.01,47],[20.01,47.01],[20,47]]]};
const feature=(id,name,municipality,provider='openstreetmap',extra={})=>({type:'Feature',id,geometry,
  properties:{id,name,municipality,boundaryKind:'neighbourhood',source:{provider},...extra}});
const collection=features=>({type:'FeatureCollection',features});

test('geometry counts and distinct source names remain separate; district fallbacks never become neighborhoods',()=>{
  const report=createReport(collection([
    feature('a','Újlak','Budapest'),feature('b','Ujlak','Budapest','whosonfirst'),
    feature('c','II. kerület','Budapest','openstreetmap',{boundaryKind:'district'})
  ]),{targetCities:[{municipality:'Budapest',osmQuery:{status:'downloaded'}}],excluded:[]});
  const city=report.cities[0];assert.equal(city.neighbourhoodGeometryCount,2);assert.equal(city.uniqueSourceNameCount,1);
  assert.equal(city.currentOsmGeometryCount,1);assert.equal(city.legacyOrOtherGeometryCount,1);
  assert.equal(city.districtFallbackGeometryCount,1);assert.equal(city.completeCoverage,false);
  assert.equal(city.nameConfirmedUniqueCount,0);assert.equal(report.summary.totalMissingCurrentNeighbourhoods,null);
});

test('failed, successful-empty and unrequested queries do not collapse to a common zero-status',()=>{
  const report=createReport(collection([]),{targetCities:[
    {municipality:'A',osmQuery:{status:'failed',reason:'request-timeout'}},
    {municipality:'B',osmQuery:{status:'downloaded'}},{municipality:'C',osmQuery:{status:'not_requested'}}],excluded:[]});
  assert.deepEqual(report.cities.map(row=>row.osmQuery.observedResult),['query_failed','downloaded_without_boundaries','not_requested']);
  assert.equal(report.summary.failedQueries,1);assert.equal(report.summary.successfulEmptyQueries,1);
  assert.equal(report.summary.unrequestedCities,1);
  assert.ok(report.cities.every(row=>row.totalCurrentNeighbourhoods===null && row.completeCoverage===false));
});

test('known point names subtract existing names without inventing all missing city neighborhoods',()=>{
  const excluded=[{id:'p1',name:'Újlak',municipality:'Budapest',reason:'not_polygon',geometryType:'Point'},
    {id:'p2',name:'Kertváros',municipality:'Budapest',reason:'not_polygon',geometryType:'Point'},
    {id:'p3',name:'Kertvaros',municipality:'Budapest',reason:'not_polygon',geometryType:'Point'},
    {id:'old',name:'Retired',municipality:'Budapest',reason:'retired_record',geometryType:'Polygon'},
    {id:'unknown',name:'Unassigned',municipality:null,reason:'unknown_municipality',geometryType:'Polygon'}];
  const report=createReport(collection([feature('a','Ujlak','Budapest')]),{excluded});
  const city=report.cities[0];assert.equal(city.knownNamesWithoutGeometryCount,1);
  assert.equal(city.knownNamesWithoutGeometry[0].sourceIds.length,2);
  assert.equal(report.unassignedSourceRecords.length,1);assert.equal(city.totalMissingCurrentNeighbourhoods,null);
});

test('reference comparisons retain the cited time period and match only explicit normalized names',()=>{
  const reference={municipality:'Debrecen',title:'Historical list',referencePeriod:'2021',sourceUrl:'https://example.test/reference',
    completeForReferencePeriod:true,currentCompletenessVerified:false,names:['Sestakert','Újkert','Kertváros']};
  const report=createReport(collection([feature('a','Sestakert','Debrecen'),feature('b','Ujkert','Debrecen')]),{excluded:[]},{references:{inventories:[reference]}});
  const comparison=report.cities[0].referenceComparisons[0];assert.equal(comparison.matchedNameCount,2);
  assert.deepEqual(comparison.missingNames,['Kertváros']);assert.equal(comparison.currentCompletenessVerified,false);
  assert.equal(comparison.completeForReferencePeriod,true);assert.equal(normalizeName('  József-Attila  telep '),'jozsefattilatelep');
});

test('joined and spaced neighborhood spellings use the same inventory and canonical-name identity',()=>{
  const report=createReport(collection([feature('osm:magdolna','Magdolnanegyed','Budapest')]),{excluded:[]},
    {references:{inventories:[{municipality:'Budapest',names:['Magdolna negyed']} ]},nameAudit:{records:[
      {id:'name:magdolna',actualMunicipality:'Budapest',proposedHungarianName:'Magdolna-negyed',canonicalNameSupported:true,
        evidenceUrls:['https://example.test/name']}
    ]}});
  const row=report.cities[0];assert.equal(row.referenceComparisons[0].matchedNameCount,1);
  assert.equal(row.referenceComparisons[0].missingNameCount,0);assert.equal(row.nameConfirmedUniqueCount,1);
  assert.equal(normalizeName('Magdolna negyed'),normalizeName('Magdolnanegyed'));
});

test('documented name equivalents and a same-named distinct missing area remain separate reference facts',()=>{
  const equivalence={referenceName:'Gerce',equivalentName:'Gercse',reason:'Documented municipal spelling variant',
    evidenceUrls:['https://example.test/municipal-list']};
  const reference={municipality:'Budapest',names:['Gerce','Orbánhegy','Missing'],nameEquivalences:[equivalence],
    distinctNeighborhoodIdentityCount:4,missingNamesEachRepresentOneIdentity:true,
    additionalMissingIdentities:[{name:'Orbánhegy',districts:[23],note:'The existing polygon belongs to district 12.'}]};
  const report=createReport(collection([feature('a','Gercse','Budapest'),feature('b','Orbánhegy','Budapest')]),{excluded:[]},
    {references:{inventories:[reference]}});
  const comparison=report.cities[0].referenceComparisons[0];
  assert.equal(comparison.referenceNameCount,3);assert.equal(comparison.matchedNameCount,2);
  assert.deepEqual(comparison.missingNames,['Missing']);assert.deepEqual(comparison.nameEquivalencesUsed,[equivalence]);
  assert.equal(comparison.additionalMissingIdentityCount,1);assert.equal(comparison.totalKnownMissingIdentityCount,2);
  assert.equal(comparison.referenceIdentityCount,4);
  assert.throws(()=>createReport(collection([]),{excluded:[]},{references:{inventories:[{...reference,
    nameEquivalences:[{referenceName:'Gerce',equivalentName:'Gercse'}]}]}}),/require explicit names, reason and evidence/);
});

test('mapped names outside the reference stay separate and documented aliases never become false extra names',()=>{
  const reference={municipality:'Budapest',names:['Gerce','Orbánhegy'],nameEquivalences:[
    {referenceName:'Gerce',equivalentName:'Gercse',reason:'Documented spelling variant',evidenceUrls:['https://example.test/reference']}
  ]};
  const report=createReport(collection([feature('a','Gercse','Budapest'),feature('b','Orbánhegy','Budapest'),
    feature('c','Kisebb lakópark','Budapest')]),{excluded:[]},{references:{inventories:[reference]}});
  const comparison=report.cities[0].referenceComparisons[0];
  assert.equal(comparison.matchedNameCount,2);assert.equal(comparison.collectedNameCount,3);
  assert.equal(comparison.matchedCollectedNameCount,2);assert.equal(comparison.collectedNamesNotInReferenceCount,1);
  assert.deepEqual(comparison.collectedNamesNotInReference,['Kisebb lakópark']);
  assert.equal(comparison.missingNameCount,0);
});

test('Google/name verification is never inferred; explicit name-audit evidence is counted separately',()=>{
  const report=createReport(collection([feature('a','A','City'),feature('b','B','City')]),{excluded:[]},{nameAudit:{records:[
    {id:'a',validationStatus:'verified_current',evidenceUrl:'https://example.test/name'},
    {id:'b',validationStatus:'unverified',evidenceUrl:'https://www.google.com/maps/search/?api=1&query=B'}]}});
  assert.equal(report.cities[0].nameConfirmedUniqueCount,1);assert.equal(report.cities[0].nameConfirmationUnrecordedCount,1);
  assert.ok(csvReport(report).startsWith('\uFEFF'));assert.match(markdownReport(report),/teljes jelenlegi városrészjegyzék/);
  assert.throws(()=>createReport(collection([{...feature('p','Point','City'),geometry:{type:'Point',coordinates:[20,47]}}]),{excluded:[]}),/non-area/);
});

test('supported canonical aliases count once; large areas and unsupported legacy names do not inflate neighborhood counts',()=>{
  const report=createReport(collection([
    feature('old1','Erzsebetfalva','Budapest','whosonfirst'),
    feature('old2','Erzsébetfalva','Budapest','whosonfirst'),
    feature('large','Csepel','Budapest','whosonfirst'),
    feature('uncertain','Old unknown','Budapest','whosonfirst'),
    feature('osm','Pesterzsébet','Budapest','openstreetmap',{source:{provider:'openstreetmap',historical:true,snapshotDate:'2022-11-23'}})
  ]),{excluded:[]},{nameAudit:{records:[
    ...['old1','old2'].map(id=>({id,proposedHungarianName:'Pesterzsébet',validationStatus:'historical_alias',
      canonicalNameSupported:true,canonicalNameIsNeighborhood:true,duplicateGroup:'Budapest:Pesterzsébet',
      countsAsCurrentNamedArea:false,excludeFromUniqueNeighborhoodCount:true})),
    {id:'large',proposedHungarianName:'Csepel',canonicalNameSupported:true,canonicalNameIsNeighborhood:false},
    {id:'uncertain',validationStatus:'ambiguous_name',canonicalNameSupported:false}
  ]}});
  const row=report.cities[0];assert.equal(row.neighbourhoodGeometryCount,5);
  assert.equal(row.acceptedNeighbourhoodNameCount,1);assert.deepEqual(row.acceptedNeighbourhoodNames,['Pesterzsébet']);
  assert.equal(row.acceptedCurrentAreaNameCount,2);assert.equal(row.unverifiedSourceNameCount,1);
  assert.equal(row.currentOsmGeometryCount,0);assert.equal(row.historicalOsmGeometryCount,1);
  assert.equal(row.legacyOrOtherGeometryCount,4);
  assert.equal(row.neighbourhoodGeometryCount,row.currentOsmGeometryCount+row.historicalOsmGeometryCount+row.legacyOrOtherGeometryCount);
  assert.equal(row.nameConfirmedUniqueCount,2);
});

test('exact canonical city/name evidence transfers across sources without transferring the audited geometry classification',()=>{
  const report=createReport(collection([
    feature('osm:new','Újlak','Budapest'),feature('osm:other-city','Újlak','Sopron'),feature('osm:other-name','Újlak alsó','Budapest')
  ]),{excluded:[]},{nameAudit:{records:[{id:'wof:old',actualMunicipality:'Budapest',proposedHungarianName:'Ujlak',
    canonicalNameSupported:true,canonicalNameIsNeighborhood:false,evidenceUrls:['https://example.test/name']} ]}});
  const budapest=report.cities.find(row=>row.municipality==='Budapest');
  assert.equal(budapest.nameConfirmedUniqueCount,1);assert.equal(budapest.acceptedNeighbourhoodNameCount,2);
  assert.equal(report.cities.find(row=>row.municipality==='Sopron').nameConfirmedUniqueCount,0);
});

test('actual stored city report is reproducible from current catalog and explicit references',async()=>{
  const report=await writeReports({check:true});
  assert.ok(report.summary.neighbourhoodGeometryCount>0);
  assert.ok(report.cities.some(row=>row.municipality==='Debrecen'));
  const debrecen=report.cities.find(row=>row.municipality==='Debrecen');
  assert.equal(debrecen.referenceComparisons[0].referenceNameCount,79);
  const budapest=report.cities.find(row=>row.municipality==='Budapest').referenceComparisons[0];
  assert.equal(budapest.referenceNameCount,211);assert.equal(budapest.referenceIdentityCount,212);
  assert.equal(budapest.currentCompletenessVerified,true);assert.ok(!budapest.missingNames.includes('Gerce'));
  assert.ok(budapest.additionalMissingIdentities.some(row=>row.name==='Orbánhegy' && row.districts.includes(23)));
  assert.equal(report.summary.completeNationalCoverage,false);
});

test('unified export selects one real source geometry per accepted name and preserves provenance and coordinates',()=>{
  const live=feature('live','Újlak','Budapest'),old=feature('old','Ujlak','Budapest','openstreetmap',
    {source:{provider:'openstreetmap',historical:true,snapshotDate:'2022-11-23',url:'https://example.test/source'},
      geometryVerificationStatus:'historical-not-rechecked'});
  const broad=feature('large','Nagy terület','Budapest','whosonfirst');
  const candidates=collection([old,broad,live]);
  const before=JSON.stringify(candidates);
  const report={cities:[{municipality:'Budapest',acceptedNeighbourhoodNames:['Újlak']}],summary:{acceptedNeighbourhoodNameCount:1}};
  const exported=createNeighborhoodExport(candidates,report);
  assert.equal(exported.features.length,1);assert.equal(exported.features[0].properties.id,'live');
  assert.deepEqual(exported.features[0].geometry,live.geometry);assert.deepEqual(exported.features[0].properties.source,live.properties.source);
  assert.equal(JSON.stringify(candidates),before);assert.equal(exported.completeNationalCoverage,false);
  const historical=createNeighborhoodExport(collection([old]),report);
  assert.deepEqual(historical.features[0].geometry,old.geometry);
  assert.equal(historical.features[0].properties.geometryVerificationStatus,'historical-not-rechecked');
  assert.deepEqual(historical.features[0].properties.source,old.properties.source);
  assert.throws(()=>createNeighborhoodExport(collection([]),report),/no matching source geometry/);
});

test('actual unified export exactly follows the current accepted city-name inventory',async()=>{
  const report=await writeReports({check:true}),exported=await writeExport({check:true});
  assert.equal(exported.features.length,report.summary.acceptedNeighbourhoodNameCount);
  assert.equal(new Set(exported.features.map(f=>normalizeName(f.properties.municipality)+'|'+normalizeName(f.properties.name))).size,exported.features.length);
});

test('standalone export rejects changed coverage and references before accepting or replacing an old release',async()=>{
  const root=await mkdtemp(join(tmpdir(),'neighborhood-export-freshness-'));
  const directory=join(root,'data/neighborhoods');
  try{
    await mkdir(directory,{recursive:true});
    await writeFile(join(directory,'catalog.geojson'),JSON.stringify(collection([feature('a','Sestakert','Debrecen')])));
    await writeFile(join(directory,'coverage.json'),JSON.stringify({targetCities:[{municipality:'Debrecen',osmQuery:{status:'downloaded'}}],excluded:[]}));
    await writeFile(join(directory,'reference-inventories.json'),JSON.stringify({inventories:[{municipality:'Debrecen',
      title:'Fixture inventory',referencePeriod:'2021',sourceUrl:'https://example.test/reference',names:['Sestakert','Újkert']}]}));
    await writeReports({root});
    await writeExport({root});
    const plain=await readFile(join(directory,'neighborhoods.geojson'));
    const compressed=await readFile(join(directory,'neighborhoods.geojson.gz'));
    for(const [file,expectedError] of [['coverage.json',/Coverage changed/],['reference-inventories.json',/Reference inventories changed/]]){
      const path=join(directory,file),original=await readFile(path,'utf8'),changed=JSON.parse(original);
      if(file==='coverage.json')changed.targetCities[0].osmQuery={status:'failed',reason:'request-timeout'};
      else changed.inventories[0].names.push('Kertváros');
      await writeFile(path,JSON.stringify(changed));
      await assert.rejects(writeExport({root,check:true}),expectedError);
      await assert.rejects(writeExport({root}),expectedError);
      assert.deepEqual(await readFile(join(directory,'neighborhoods.geojson')),plain,'a stale export must not be overwritten');
      assert.deepEqual(await readFile(join(directory,'neighborhoods.geojson.gz')),compressed);
      await writeFile(path,original);
    }
    await rm(join(directory,'reference-inventories.json'));
    await assert.rejects(writeExport({root,check:true}),/Reference inventories changed/);
  }finally{await rm(root,{recursive:true,force:true});}
});
