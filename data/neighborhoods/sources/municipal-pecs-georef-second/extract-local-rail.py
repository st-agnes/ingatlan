#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,osmium
P=Path(__file__).resolve().parent;ROOT=P.parents[3];pbf=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
# First read retains railway ways, then exact referenced nodes; no derived or snapped vertices.
ways={}
for o in osmium.FileProcessor(str(pbf)).with_filter(osmium.filter.KeyFilter('railway')):
 if isinstance(o,osmium.osm.Way) and o.tags.get('railway') in ['rail','disused','abandoned','narrow_gauge']:
  ways[o.id]={'osmWayId':o.id,'tags':dict(o.tags),'nodeRefs':[n.ref for n in o.nodes],'version':o.version,'timestamp':str(o.timestamp)}
ids={n for w in ways.values()for n in w['nodeRefs']};nodes={}
for o in osmium.FileProcessor(str(pbf)).with_filter(osmium.filter.IdFilter(ids)):
 if isinstance(o,osmium.osm.Node)and o.id in ids:nodes[o.id]={'coordinates':[o.lon,o.lat],'version':o.version,'timestamp':str(o.timestamp)}
features=[]
for w in ways.values():
 if not all(n in nodes for n in w['nodeRefs']):continue
 coords=[nodes[n]['coordinates']for n in w['nodeRefs']]
 if not any(18.1<x<18.42 and 45.99<y<46.19 for x,y in coords):continue
 features.append({'type':'Feature','properties':w,'geometry':{'type':'LineString','coordinates':coords}})
needed={n for f in features for n in f['properties']['nodeRefs']}
out={'type':'FeatureCollection','sourcePbfSha256':hashlib.sha256(pbf.read_bytes()).hexdigest(),'selectionBbox':[18.1,45.99,18.42,46.19],'selectionDoesNotClipWays':True,'features':features,'nodes':{str(n):nodes[n]for n in sorted(needed)}}
(P/'local-rail-original.geojson').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'regionalRailways':len(features),'originalNodes':len(needed),'sha256':out['sourcePbfSha256']}))
