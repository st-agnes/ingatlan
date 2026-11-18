#!/usr/bin/env python3
"""Hash-checked intake of the six completed round-four assignments; no aliases."""
import hashlib,json,unicodedata
from collections import Counter
from pathlib import Path
from shapely.geometry import shape
H=Path(__file__).resolve().parent;ROOT=H.parents[2];DATA=ROOT/'data/neighborhoods';REG=DATA/'expansion-20261114/input-registry.json'
EXPECTED={
 'shard-0/features.geojson':(63,'6dba7c52351f2378b421d4b40ba32dea8f42f198f852b44115e59567bd0af50e'),
 'shard-1/features.geojson':(60,'6cf93c3986e2df8e519982eda788cb2971825a9468cd442e15230c9903c021b7'),
 'shard-2/features.geojson':(68,'015372b475a7203a1e2f7fa97670c32b622fd9407f611b35704c976711e528f9'),
 'shard-3/batch-01/features.geojson':(16,'c1c0a53f1b82cb6e280a98b79f7fb565a2681418b5b63c4524a667de91a46622'),
 'shard-3/batch-02/features.geojson':(14,'f5a31c6c5a6c8b755823445bfc1f6cb3505e7e6e2a5797c0c59486c6bf2b89d6'),
 'shard-3/batch-03/features.geojson':(12,'b4235b9fa3f0455c1641a18c8e63c7774e7650c5a3fc836d33122802031b4a69'),
 'shard-3/batch-04/features.geojson':(14,'a7737e859ac9f650ec8e4d0535e880916e2e482be3d37c6d0777fc6e4ca6d3bc'),
 'shard-3/batch-05/features.geojson':(7,'69f1f81a64ddd55d9b23848ba10b8d9cae635bd2c075caafd3523f8c7d22b52f'),
 'shard-3/batch-06/features.geojson':(1,'9217bea610de5da65651edade447a2cb58b8801f9a3709e787480102b7c1eab8'),
 'shard-4/features.geojson':(63,'ac81dd61f69f96deb3599b0f594bf615f04f04f7fc39446c709889e2ae85ab78'),
 'shard-5/features.geojson':(66,'bd36bf6990cfb2cff4c1599b89d02d351b2c8c5ba863043db19569cb7dbc5cf1')}
def key(s):return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
targets={(c['municipality'],key(t['name'])):(c['municipality'],t['name']) for p in sorted((H/'tasks').glob('shard-*.json')) for c in json.loads(p.read_text())['municipalities'] for t in c['targets']}
seen=set();packets=[];flagCounts=Counter()
for name,(count,digest) in EXPECTED.items():
 path=H/name;raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest,(name,'changed frozen SHA')
 fs=json.loads(raw)['features'];assert len(fs)==count,(name,'count')
 for f in fs:
  p=f['properties'];k=(p['municipality'],key(p['name']));g=shape(f['geometry'])
  assert k in targets and k not in seen,(name,k,'unexpected or duplicate name');seen.add(k)
  assert g.geom_type in ('Polygon','MultiPolygon') and not g.is_empty and g.is_valid,(name,k,'geometry')
  assert p.get('estimated') is True and p.get('lowConfidence') is True,(name,k,'uncertainty flags')
  assert not p.get('aliases'),(name,k,'aliases not authorized in this intake')
  for flag in ('partialFootprint','partialSourceFootprint','partialExtent','footprintOnly'):
   if p.get(flag):flagCounts[flag]+=1
 packets.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest,'featureCount':count})
assert len(seen)==384
registry=json.loads(REG.read_text());existing={e['path']:e for e in registry['datasets']}
for packet in packets:
 if packet['path'] in existing:assert existing[packet['path']]['sha256']==packet['sha256']
 else:registry['datasets'].append({k:packet[k] for k in ('path','sha256')})
state=json.loads((H/'WORK-STATE.json').read_text());completed={e['path']:e for e in state['completedPackets']}
for packet in packets:
 if packet['path'] in completed:assert completed[packet['path']]['sha256']==packet['sha256']
 else:state['completedPackets'].append(packet)
state['status']='collecting_and_checkpointing'
report={'schemaVersion':1,'scope':'technical_intake_not_geographic_accuracy_review','packetCount':len(packets),'featureCount':len(seen),'validGeometryCount':len(seen),'unexpectedNameCount':0,'duplicateMunicipalityNameCount':0,'aliasesApplied':0,'sourceUncertaintyPreserved':True,'partialSourcePropertyCounts':dict(flagCounts),'remainingAssignedNames':[{'municipality':targets[k][0],'name':targets[k][1]} for k in sorted(set(targets)-seen)],'packets':packets}
dump(REG,registry);dump(H/'WORK-STATE.json',state);dump(H/'intake-validation.json',report)
print(json.dumps({k:v for k,v in report.items() if k not in ['packets']},ensure_ascii=False))
