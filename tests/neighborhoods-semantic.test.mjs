import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {applySemanticAudit} from '../scripts/neighborhoods/semantic-audit.mjs';

const geometry={type:'Polygon',coordinates:[[[19,47],[19.01,47],[19.01,47.01],[19,47]]]};
const fixture=()=>({features:[{type:'Feature',id:'osm:way:1',geometry,
  properties:{name:'vendégházak',municipality:'Testcity',canonicalNameSupported:true,
    canonicalNameIsNeighborhood:true,boundaryKind:'neighbourhood',
    source:{provider:'openstreetmap',sha256:'a'.repeat(64),tags:{tourism:'guest_house'}}}}],excluded:[]});
const audit=()=>({schemaVersion:1,records:[{id:'osm:way:1',municipality:'Testcity',sourceName:'vendégházak',
  sourceSha256:'a'.repeat(64),geometrySha256:createHash('sha256').update(JSON.stringify(geometry)).digest('hex'),
  action:'retain_as_local_area',semanticType:'accommodation_area',reason:'Exact source venue evidence',
  evidenceUrls:['https://example.test/source']}]});

test('a reviewed venue keeps its actual geometry and source while leaving the quarter count',()=>{
  const input=fixture(),before=JSON.stringify(input);
  const output=applySemanticAudit(input,['Testcity'],audit());
  assert.equal(JSON.stringify(input),before);
  const f=output.features[0];assert.deepEqual(f.geometry,geometry);
  assert.deepEqual(f.properties.source,input.features[0].properties.source);
  assert.equal(f.properties.boundaryKind,'local_area');
  assert.equal(f.properties.canonicalNameIsNeighborhood,false);
  assert.equal(f.properties.usableForAddressAssignment,false);
  assert.equal(output.excluded.length,0);
});

test('semantic corrections never become blanket filters for industrial or cemetery wording',()=>{
  const input=fixture();input.features.push({...input.features[0],id:'osm:way:2',
    properties:{...input.features[0].properties,name:'Temető'}});
  const output=applySemanticAudit(input,['Testcity'],audit());
  assert.equal(output.features[1],input.features[1]);
  assert.equal(output.features[1].properties.boundaryKind,'neighbourhood');
});

test('changed source bytes, name, geometry, or missing objects require a new review',()=>{
  for(const mutate of [input=>input.features[0].properties.source.sha256='b'.repeat(64),
    input=>input.features[0].properties.name='Different',input=>input.features[0].geometry={...geometry,coordinates:[[[19,47],[19.02,47],[19.02,47.01],[19,47]]] }]){
    const input=structuredClone(fixture());mutate(input);
    assert.throws(()=>applySemanticAudit(input,['Testcity'],audit()),/source changed/);
  }
  assert.throws(()=>applySemanticAudit({features:[],excluded:[]},['Testcity'],audit()),/missing source object/);
  const duplicate=audit();duplicate.records.push({...duplicate.records[0]});
  assert.throws(()=>applySemanticAudit(fixture(),['Testcity'],duplicate),/Invalid/);
});
