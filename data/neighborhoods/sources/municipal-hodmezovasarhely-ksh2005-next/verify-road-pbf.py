#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
import osmium
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf';EXPECTED='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(n):return json.loads((P/n).read_text())
assert hashlib.file_digest(PBF.open('rb'),'sha256').hexdigest()==EXPECTED
ways={f['properties']['osmWayId']:f for f in read('road-source-ways.geojson')['features']};nodes={};names={f['properties']['source']['osmId']:f for f in read('source-name-points.geojson')['features']}
for f in ways.values():
 for ref,c in zip(f['properties']['nodeRefs'],f['geometry']['coordinates']):
  if ref in nodes:assert nodes[ref]==c
  nodes[ref]=c
for ref,f in names.items():
 if ref in nodes:assert nodes[ref]==f['geometry']['coordinates']
 nodes[ref]=f['geometry']['coordinates']
seen_ways=set();seen_nodes=set();controls={r['targetOsmNodeId']for r in read('road-control-specification.json')['controls']+read('road-control-specification.json')['heldOutAmbiguousChecks']};control_records=[]
for o in osmium.FileProcessor(str(PBF)).with_filter(osmium.filter.IdFilter(set(ways)|set(nodes))):
 if isinstance(o,osmium.osm.Way)and o.id in ways:
  p=ways[o.id]['properties'];assert list(n.ref for n in o.nodes)==p['nodeRefs'];assert dict(o.tags)==p['tags'];assert o.version==p['version'] and str(o.timestamp)==p['timestamp'];seen_ways.add(o.id)
 elif isinstance(o,osmium.osm.Node)and o.id in nodes:
  assert [o.lon,o.lat]==nodes[o.id];seen_nodes.add(o.id)
  if o.id in controls:control_records.append({'osmNodeId':o.id,'coordinates':[o.lon,o.lat],'version':o.version,'timestamp':str(o.timestamp),'tags':dict(o.tags),'actualPbfVerified':True})
  if o.id in names:
   p=names[o.id]['properties']['source'];assert dict(o.tags)==p['tags'] and o.version==p['objectVersion'] and str(o.timestamp)==p['objectTimestamp']
assert seen_ways==set(ways)and seen_nodes==set(nodes)and {r['osmNodeId']for r in control_records}==controls
result={'schemaVersion':1,'sourcePbfSha256':EXPECTED,'sourcePbfBytes':PBF.stat().st_size,'sourceOsmTimestamp':'2026-11-12T21:23:05Z','independentFreshPbfPass':True,'completeWaysVerified':len(ways),'originalNodeReferenceSequencesVerified':len(ways),'allReferencedNodeCoordinatesVerified':len(nodes),'sourceNamePointsVerified':len(names),'targetControlAndCheckNodes':sorted(control_records,key=lambda r:r['osmNodeId']),'noSourceGeometryModified':True,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
(P/'road-pbf-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('PBF exact ways/nodes verified',len(ways),len(nodes))
