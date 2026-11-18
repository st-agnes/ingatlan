#!/usr/bin/env python3
from pathlib import Path
import json,gzip
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
load=lambda f:json.loads(gzip.decompress((HERE/f).read_bytes()) if f.endswith('.gz') else (HERE/f).read_bytes())['features']
areas=load('source-areas.geojson.gz');pts=load('target-name-points.geojson');nodes=load('source-name-points.geojson')
to=Transformer.from_crs(4326,23700,always_xy=True).transform;geoms=[transform(to,shape(f['geometry'])) for f in areas]
print('Named village/forest references:')
for f in nodes+areas:
 n=f['properties'].get('name') or ''
 if any(x in n.casefold() for x in ['batid','szikán','mályvád','csókás','ponyi','dénesmajor','sitka','városerdő','ella']):print(f.get('id'),n,f['properties']['source']['tags'],shape(f['geometry']).bounds)
for f in pts:
 if f['properties']['municipality']=='Debrecen':continue
 p=transform(to,shape(f['geometry']));cand=[]
 for a,g in zip(areas,geoms):
  tags=a['properties']['source']['tags'];dist=g.distance(p)
  if dist<750 and (tags.get('landuse') in ['residential','farmyard','industrial','allotments','commercial'] or tags.get('name')):cand.append((round(dist,1),round(g.area,1),a['id'],a['properties'].get('name'),tags.get('landuse'),tags.get('natural'),tags.get('leisure')))
 print('\n',f['properties']['name'],f['geometry']['coordinates']);print(*sorted(cand)[:12],sep='\n')
