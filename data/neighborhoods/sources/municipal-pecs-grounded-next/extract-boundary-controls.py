#!/usr/bin/env python3
from pathlib import Path
import json,osmium,hashlib
P=Path(__file__).resolve().parent;ROOT=P.parents[3];pbf=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf';geo=json.loads((P/'source-municipality.geojson').read_text());source=geo['properties']['source'];members=source['members'];way_ids={x['ref']for x in members if x['type']=='way'};rel_id=source['osmId'];ways={};relation=None
for obj in osmium.FileProcessor(str(pbf)).with_filter(osmium.filter.IdFilter(way_ids|{rel_id})):
 if isinstance(obj,osmium.osm.Way)and obj.id in way_ids:ways[obj.id]={'osmWayId':obj.id,'nodeRefs':[n.ref for n in obj.nodes],'tags':dict(obj.tags),'version':obj.version,'timestamp':str(obj.timestamp)}
 elif isinstance(obj,osmium.osm.Relation)and obj.id==rel_id:
  actual=[{'type':{'w':'way','n':'node','r':'relation'}.get(m.type,m.type),'ref':m.ref,'role':m.role}for m in obj.members];assert actual==members;assert dict(obj.tags)==source['tags'];relation={'osmRelationId':obj.id,'members':actual,'tags':dict(obj.tags),'version':obj.version,'timestamp':str(obj.timestamp)}
assert set(ways)==way_ids and relation is not None;ids={n for w in ways.values()for n in w['nodeRefs']};nodes={}
for obj in osmium.FileProcessor(str(pbf)).with_filter(osmium.filter.IdFilter(ids)):
 if isinstance(obj,osmium.osm.Node)and obj.id in ids:nodes[obj.id]={'osmNodeId':obj.id,'coordinates':[obj.lon,obj.lat],'version':obj.version,'timestamp':str(obj.timestamp)}
assert set(nodes)==ids;by_coords={}
for node in nodes.values():by_coords.setdefault(tuple(node['coordinates']),[]).append(node['osmNodeId'])
links=[]
for c in json.loads((P/'source-corner-candidates.json').read_text())['records']:
 matches=by_coords.get(tuple(c['worldCoordinates']),[]);assert matches
 links.append({'sourcePixel':c['sourcePixel'],'sourceContext':c['sourceContext'],'archivedOuterRingVertexIndex':c['archivedOuterRingVertexIndex'],'worldCoordinates':c['worldCoordinates'],'actualBoundaryNodeIds':matches,'memberWaysContainingNode':[wid for wid,w in ways.items()if any(n in w['nodeRefs']for n in matches)]})
coordinates=geo['geometry']['coordinates'];polys=[coordinates]if geo['geometry']['type']=='Polygon'else coordinates
for poly in polys:
 for ring in poly:
  for c in ring:assert tuple(c)in by_coords
h=hashlib.sha256()
with pbf.open('rb')as f:
 for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
assert h.hexdigest()==source['pbfSha256']
out={'schemaVersion':1,'sourcePbfSha256':h.hexdigest(),'sourceMunicipalitySha256':hashlib.sha256((P/'source-municipality.geojson').read_bytes()).hexdigest(),'sourceRelation':relation,'rawMemberWays':sorted(ways.values(),key=lambda x:x['osmWayId']),'rawBoundaryNodes':sorted(nodes.values(),key=lambda x:x['osmNodeId']),'cornerLinks':links,'allPolygonVerticesAreLiteralSourceBoundaryNodeCoordinates':True,'inventedWorldCoordinates':False,'independentAbsoluteAccuracyMetres':None}
(P/'boundary-source-proof.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'boundaryWays':len(ways),'literalBoundaryNodes':len(nodes),'cornerNodeLinks':links},ensure_ascii=False))
