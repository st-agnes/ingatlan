import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {applyOsmAssociationAudit, buildCatalog, mergeCatalogs, validateGeometry} from '../scripts/neighborhoods/build.mjs';
import {collectOsmCandidates, loadOsmSources} from '../scripts/neighborhoods/osm.mjs';

const root=fileURLToPath(new URL('..',import.meta.url));
const canonical=['Esztergom','Dorog'];
const geometry={type:'Polygon',coordinates:[[[18.72,47.72],[18.73,47.72],[18.73,47.73],[18.72,47.72]]]};
const feature=(id,name)=>({type:'Feature',id,bbox:[18.72,47.72,18.73,47.73],geometry,
  properties:{id,name,sourceName:name,municipality:'Esztergom',municipalityId:'city:Esztergom',
    municipalityEvidence:'canonical_query_context',boundaryKind:'neighbourhood',usableForAddressAssignment:false,
    source:{provider:'openstreetmap',path:'source/esztergom.json',sha256:'a'.repeat(64),license:'ODbL-1.0'}}});
const collected=()=>({features:[feature('osm:way:1','Kolónia'),feature('osm:relation:2','Ipari- gazdasági terület')],
  excluded:[],sourceRecords:3,candidateRecords:2,neighbourhoodRecords:2,districtRecords:0,sourceSnapshots:1,
  queryResults:[{city:'Esztergom',status:'downloaded'}]});
const audit=()=>({schemaVersion:1,records:[
  {id:'osm:way:1',sourceSha256:'a'.repeat(64),sourceMunicipality:'Esztergom',action:'reassign_municipality',
    verifiedMunicipality:'Dorog',boundaryKind:'neighbourhood',canonicalNameSupported:true,
    geometryAssociation:'crosses_2025_reference_municipal_boundaries',evidenceUrls:['https://example.test/dorog-colonia']},
  {id:'osm:relation:2',sourceSha256:'a'.repeat(64),sourceMunicipality:'Esztergom',action:'exclude',
    reason:'audited_unverified_neighbourhood',evidenceUrls:['https://example.test/association-review']}
]});

test('audited name-municipality association corrects metadata without changing geometry, provenance or query history',()=>{
  const input=collected(),before=JSON.stringify(input),result=applyOsmAssociationAudit(input,canonical,audit());
  assert.equal(result.features.length,1);
  const property=result.features[0].properties;
  assert.equal(property.municipality,'Dorog');assert.equal(property.municipalityId,'city:Dorog');
  assert.equal(property.sourceMunicipality,'Esztergom');
  assert.equal(property.municipalityEvidence,'verified_name_municipality_association');
  assert.equal(property.nameVerificationStatus,'supported_by_association_audit');
  assert.equal(property.canonicalNameSupported,true);
  assert.equal(property.geometryAssociation,'crosses_2025_reference_municipal_boundaries');
  assert.equal(property.sourceAssociationAudit.verifiedMunicipality,'Dorog');
  assert.deepEqual(property.source,input.features[0].properties.source);
  assert.deepEqual(result.features[0].geometry,input.features[0].geometry);
  assert.deepEqual(result.features[0].bbox,input.features[0].bbox);
  assert.deepEqual(result.queryResults,input.queryResults);
  assert.equal(result.features[0].properties.usableForAddressAssignment,false);
  assert.equal(JSON.stringify(input),before);
  assert.equal(result.excluded[0].reason,'audited_unverified_neighbourhood');
  assert.equal(result.excluded[0].id,'osm:relation:2');
  assert.equal(result.excluded[0].sourceAssociationAudit.action,'exclude');
  assert.equal(result.candidateRecords,result.features.length+result.excluded.length);
  const merged=mergeCatalogs(buildCatalog([],canonical),result);
  assert.equal(merged.coverage.municipalities.find(row=>row.municipality==='Dorog').polygonCount,1);
  assert.equal(merged.coverage.targetCities.find(row=>row.municipality==='Esztergom').polygonCount,0);
  assert.equal(merged.coverage.targetCities.find(row=>row.municipality==='Esztergom').osmQuery.status,'downloaded');
});

test('association audit rejects stale hashes, wrong query identities, unknown municipalities and duplicate evidence keys',()=>{
  const stale=audit();stale.records[0].sourceSha256='b'.repeat(64);
  assert.throws(()=>applyOsmAssociationAudit(collected(),canonical,stale),/source identity mismatch/);
  const wrongQuery=audit();wrongQuery.records[0].sourceMunicipality='Dorog';
  assert.throws(()=>applyOsmAssociationAudit(collected(),canonical,wrongQuery),/source identity mismatch/);
  const unknown=audit();unknown.records[0].verifiedMunicipality='Invented municipality';
  assert.throws(()=>applyOsmAssociationAudit(collected(),canonical,unknown),/Invalid audited municipality/);
  const duplicate=audit();duplicate.records.push(duplicate.records[0]);
  assert.throws(()=>applyOsmAssociationAudit(collected(),canonical,duplicate),/Duplicate OSM association audit identity/);
  const unsupported=audit();unsupported.records[0].action='invent_polygon';
  assert.throws(()=>applyOsmAssociationAudit(collected(),canonical,unsupported),/Invalid OSM association audit record/);
  assert.equal(applyOsmAssociationAudit(collected(),canonical,null).features.length,2);
});

test('actual boundary-crossing source records become one audited Dorog neighborhood and one documented exclusion',async()=>{
  const snapshots=await loadOsmSources(root);
  const snapshot=snapshots.find(item=>item.manifest.city==='Esztergom');
  assert.ok(snapshot,'the raw Esztergom query remains preserved');
  const input=collectOsmCandidates([snapshot],canonical,validateGeometry);
  assert.equal(input.features.length,2);
  const actualAudit=JSON.parse(await readFile(new URL('../data/neighborhoods/osm-association-audit.json',import.meta.url),'utf8'));
  const result=applyOsmAssociationAudit(input,canonical,actualAudit);
  assert.equal(result.features.length,1);
  const corrected=result.features[0],original=input.features.find(item=>item.id===corrected.id);
  assert.equal(corrected.id,'osm:way:988252508');assert.equal(corrected.properties.name,'Kolónia');
  assert.equal(corrected.properties.municipality,'Dorog');
  assert.deepEqual(corrected.geometry,original.geometry);
  assert.deepEqual(corrected.properties.source,original.properties.source);
  assert.equal(corrected.properties.sourceAssociationAudit.sourceSha256,snapshot.sha256);
  assert.equal(corrected.properties.canonicalNameSupported,true);
  assert.equal(corrected.properties.geometryAssociation.status,'crosses_2025_reference_municipal_boundaries');
  assert.deepEqual(corrected.properties.geometryAssociation.vertexCounts,{Dorog:10,Esztergom:8,outsideBoth:0});
  assert.equal(corrected.properties.geometryAssociation.areaOverlapComputed,false);
  assert.equal(corrected.properties.usableForAddressAssignment,false);
  assert.equal(result.excluded[0].id,'osm:relation:15865189');
  assert.equal(result.excluded[0].reason,'audited_unverified_neighbourhood');
  assert.equal(result.excluded[0].source.sha256,snapshot.sha256);
});
